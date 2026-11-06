"""Stored preview, private configuration and installer coexistence acceptance."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/fnl-setup/scripts/compact_stop_setup.py'
spec = importlib.util.spec_from_file_location('compact_stop_setup', SCRIPT)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


class CompactStopSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / 'home')
        # Only the world-writable system temporary ancestors are exempted in
        # tests; safety checks on the synthetic account remain fully active.
        ancestors = {p.stat().st_ino for p in base.parents if p.stat().st_mode & 0o022}
        original = os.fstat
        def fstat(fd):
            info = original(fd)
            if info.st_ino in ancestors and stat.S_ISDIR(info.st_mode):
                fields = list(info)
                fields[0] &= ~0o022
                return os.stat_result(fields)
            return info
        patch = mock.patch.object(os, 'fstat', side_effect=fstat)
        patch.start()
        self.addCleanup(patch.stop)
        self.root = self.home / '.finolabs/vibecode'
        self.root.mkdir(parents=True, mode=0o700)
        self.host = self.root / 'host.md'
        self.host.write_bytes(b'# Host\r\n\r\n## Other\r\nKeep: yes\r\n')
        self.config = self.home / '.gemini/config/hooks.json'
        self.config.parent.mkdir(parents=True, mode=0o700)
        self.other = '"other" : { "SessionStart" : [], "literal": "} , {", "number": 1e2 }'
        self.metrics = '"finolabs-vibecode" : {"SessionStart": [ {"type":"command", "command":"example"} ]}'
        self.config.write_text('{\n ' + self.other + ',\n ' + self.metrics + '\n}\n')
        self.plan = self.root / 'state/compact-stop-setup/preview.json'
        env = mock.patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, 'argv', [str(SCRIPT), *args]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cs.main()
        return code, out.getvalue(), err.getvalue()

    def preview(self, *args):
        code, out, err = self.run_cli('preview', *(args or ('--limit', '50000')))
        self.assertEqual(code, 0, err)
        self.assertIn(cs.GROUP, out)
        self.assertIn('system prompt is not counted', out)
        self.assertIn('Command: python3 -I ', out)
        return out.split('Digest: ')[1].splitlines()[0]

    def apply(self, value):
        code, out, err = self.run_cli('apply', '--digest', value, '--yes')
        self.assertEqual(code, 0, err)
        self.assertFalse(self.plan.exists())

    def refuse(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 1)
        self.assertEqual(len(err.splitlines()), 1)
        self.assertNotIn('private-content', err)
        return err

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}

    def test_acceptance_2_preview_writes_only_private_plan(self):
        before = self.snapshot()
        self.preview()
        after = self.snapshot()
        after.pop(str(self.plan.relative_to(self.home)))
        self.assertEqual(before, after)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.plan.parent.stat().st_mode), 0o700)

    def test_apply_preserves_other_groups_bytes_modes_and_backup(self):
        original, old_host = self.config.read_bytes(), self.host.read_bytes()
        self.config.chmod(0o640)
        self.apply(self.preview())
        text = self.config.read_text()
        self.assertIn(self.other, text)
        self.assertIn(self.metrics, text)
        data = json.loads(text)
        command = data[cs.GROUP]['PreInvocation'][0]['command']
        self.assertEqual(shlex.split(command), ['python3', '-I', str(ROOT / 'scripts/compact_stop_hook.py'), '--host', 'antigravity', '--event', 'PreInvocation'])
        self.assertTrue(self.host.read_bytes().startswith(old_host))
        self.assertIn(b'Enabled: yes\r\nLimit bytes: 50000', self.host.read_bytes())
        backup, = self.config.parent.glob('hooks.json.bak-*')
        self.assertEqual(backup.read_bytes(), original)
        for path in (backup, self.config):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    def test_remove_and_missing_group_preserve_metrics(self):
        self.apply(self.preview())
        self.apply(self.preview('--remove'))
        self.assertNotIn(cs.GROUP, json.loads(self.config.read_text()))
        self.assertIn(self.metrics, self.config.read_text())
        self.assertIn('Enabled: no', self.host.read_text())
        before = self.config.read_bytes()
        self.apply(self.preview('--remove'))
        self.assertEqual(before, self.config.read_bytes())

    def test_wrong_short_missing_yes_expired_and_tampered_preview(self):
        value = self.preview()
        before = self.snapshot()
        for digest in ('0' * 64, value[:12]):
            self.refuse('apply', '--digest', digest, '--yes')
            self.assertEqual(before, self.snapshot())
        self.refuse('apply', '--digest', value)
        self.assertEqual(before, self.snapshot())
        with mock.patch.object(cs.time, 'time', return_value=100000):
            value = self.preview()
        self.refuse('apply', '--digest', value, '--yes')
        saved = json.loads(self.plan.read_bytes())
        saved['plan']['limit'] = 70000
        self.plan.write_text(json.dumps(saved))
        self.refuse('apply', '--digest', value, '--yes')

    def test_changed_hooks_or_host_refused_before_writes(self):
        for target in (self.config, self.host):
            value = self.preview()
            target.write_bytes(target.read_bytes() + b' ')
            before = self.snapshot()
            self.refuse('apply', '--digest', value, '--yes')
            self.assertEqual(before, self.snapshot())

    def test_limit_bounds_and_other_hosts(self):
        for value in ('49999', '20000001', '1.5', 'true'):
            self.refuse('preview', '--limit', value)
        for host in ('claude', 'codex', 'unknown'):
            self.assertIn('compact_setup.py', self.refuse('preview', '--host', host, '--limit', '50000'))
        self.assertFalse(self.plan.exists())
        self.apply(self.preview('--limit', '20000000'))

    def test_json_invalid_nonobject_duplicates_and_nonfinite_refused(self):
        for text in ('private-content', '[]', '{"nested":{"x":1,"x":2}}', '{"x":NaN}', '{"x":1e400}', '{"x":Infinity}', '[' * 1500):
            self.config.write_text(text)
            self.refuse('preview', '--limit', '50000')
            self.assertEqual(self.config.read_text(), text)
            self.assertFalse(self.plan.exists())

    def test_unsafe_target_preview_and_apply(self):
        value = self.preview()
        original = self.config.with_name('original.json')
        self.config.rename(original)
        self.config.symlink_to(original)
        self.refuse('preview', '--remove')
        self.refuse('apply', '--digest', value, '--yes')
        self.config.unlink()
        original.rename(self.config)
        self.config.chmod(0o666)
        self.refuse('preview', '--remove')
        self.config.chmod(0o600)
        self.config.parent.chmod(0o777)
        self.refuse('preview', '--remove')

    def test_unsafe_root_and_plan(self):
        value = self.preview()
        self.plan.chmod(0o644)
        self.refuse('apply', '--digest', value, '--yes')
        self.refuse('preview', '--remove')
        self.plan.chmod(0o600)
        (self.root / '.git').write_text('gitdir: elsewhere')
        self.refuse('preview', '--remove')
        self.refuse('apply', '--digest', value, '--yes')
        (self.root / '.git').unlink()
        (self.root / 'root.json').write_text('{}')
        self.refuse('preview', '--remove')

    def test_missing_files_and_absolute_custom_config(self):
        self.host.unlink()
        self.config.unlink()
        self.apply(self.preview())
        self.assertIn(cs.GROUP, json.loads(self.config.read_bytes()))
        custom = self.home / 'custom.json'
        custom.write_text('{}')
        self.apply(self.preview('--limit', '50000', '--config', str(custom)))
        self.assertIn(cs.GROUP, json.loads(custom.read_bytes()))
        self.refuse('preview', '--limit', '50000', '--config', 'relative.json')

    def test_host_section_fences_and_other_sections_preserved(self):
        original = b'# Host\n```\n## Compaction stop\nexample\n```\n\n## Other\nKeep\n\n'
        self.host.write_bytes(original)
        self.apply(self.preview())
        self.apply(self.preview('--limit', '100000'))
        self.assertTrue(self.host.read_bytes().startswith(original))
        self.assertEqual(self.host.read_text().count('Enabled: yes'), 1)
        self.host.write_text(self.host.read_text() + '\n## Compaction stop\nEnabled: no\n')
        self.refuse('preview', '--remove')

    def test_plugin_root_check_and_quoted_command(self):
        with mock.patch.object(cs, '__file__', str(self.home / 'skills/fnl-setup/scripts/compact_stop_setup.py')):
            self.refuse('preview', '--limit', '50000')
        # A synthetic plugin exercises shell quoting without touching host config.
        root = self.home / "plugin with ' quote"
        (root / '.claude-plugin').mkdir(parents=True)
        (root / '.claude-plugin/plugin.json').write_text('{"name":"finolabs-vibecode"}')
        (root / 'scripts').mkdir()
        for name in ('metrics_hook.py', 'compact_stop_hook.py'):
            (root / 'scripts' / name).write_text('')
        with mock.patch.object(cs, '__file__', str(root / 'skills/fnl-setup/scripts/compact_stop_setup.py')):
            self.assertEqual(shlex.split(cs.hook_command())[2], str(root / 'scripts/compact_stop_hook.py'))

    def test_acceptance_3_installers_coexist_in_both_orders(self):
        refresh = ROOT / 'skills/fnl-status/scripts/refresh.py'
        def metrics(remove=False):
            result = subprocess.run([sys.executable, '-I', str(refresh), 'antigravity-hook', '--config', str(self.config), '--yes', *(['--remove'] if remove else [])], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        for metrics_first in (True, False):
            with self.subTest(metrics_first=metrics_first):
                self.config.write_text('{}')
                if metrics_first:
                    metrics()
                self.apply(self.preview())
                stop = json.loads(self.config.read_text())[cs.GROUP]
                if not metrics_first:
                    metrics()
                self.assertEqual(json.loads(self.config.read_text())[cs.GROUP], stop)
                metric_group = json.loads(self.config.read_text())['finolabs-vibecode']
                self.apply(self.preview('--remove'))
                self.assertEqual(json.loads(self.config.read_text())['finolabs-vibecode'], metric_group)
                self.apply(self.preview())
                metrics(remove=True)
                self.assertEqual(json.loads(self.config.read_text())[cs.GROUP], stop)

    def test_acceptance_4_docs_and_bundled_hooks_unchanged(self):
        setup = (ROOT / 'skills/fnl-setup/SKILL.md').read_text()
        self.assertIn('**Compaction stop**', setup)
        self.assertLess(setup.index('**Compaction plan approval.**'), setup.index('**Compaction stop**'))
        stop = setup.split('**Compaction stop**', 1)[1].split('**Steward explanation.**', 1)[0]
        for text in ('Advisory (agent judgment)', 'Enforcer:', 'none preselected', 'native question tool', 'system prompt', '--remove', '60-minute'):
            self.assertIn(text, stop)
        for name, token in (('skills/fnl-session-hygiene/SKILL.md', 'Antigravity compaction stop'),
                            ('PRIVACY.md', 'state/compact-stop/'), ('README.md', 'compaction-stop.md'),
                            ('CHANGELOG.md', 'opt-in Antigravity pre-invocation compaction stop'),
                            ('docs/specs/index.md', '(compaction-stop.md)')):
            self.assertIn(token, (ROOT / name).read_text())
        for name in ('.claude-plugin/hooks.json', '.codex-plugin/hooks.json'):
            result = subprocess.run(['git', 'show', 'main:' + name], cwd=ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((ROOT / name).read_bytes(), result.stdout)
