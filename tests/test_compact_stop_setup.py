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
        # An installed plugin must live outside any git work tree.
        self.plugin = self.home / "plugin with ' quote"
        (self.plugin / '.claude-plugin').mkdir(parents=True)
        (self.plugin / '.claude-plugin/plugin.json').write_text('{"name":"finolabs-vibecode"}')
        (self.plugin / 'scripts').mkdir()
        for name in ('metrics_hook.py', 'compact_stop_hook.py', 'data_root.py'):
            (self.plugin / 'scripts' / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
        patch = mock.patch.object(cs, '__file__', str(self.plugin / 'skills/fnl-setup/scripts/compact_stop_setup.py'))
        patch.start()
        self.addCleanup(patch.stop)
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
        self.assertIn('python3 -I ', out)
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
        script = str(self.plugin / 'scripts/compact_stop_hook.py')
        self.assertEqual(shlex.split(command), ['[', '-f', script, ']', '&&', 'python3', '-I', script,
                                               '--host', 'antigravity', '--event', 'PreInvocation', '||', 'echo', '{}'])
        self.assertTrue(self.host.read_bytes().startswith(old_host))
        self.assertIn(b'Enabled: yes\r\nLimit bytes: 50000', self.host.read_bytes())
        backup, = self.config.parent.glob('hooks.json.bak-*')
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertRegex(backup.name, r'^hooks\.json\.bak-[0-9]{8}-[0-9]{6}-[1-9][0-9]*$')

    def test_stored_command_allows_when_script_disappears(self):
        self.apply(self.preview())
        command = json.loads(self.config.read_bytes())[cs.GROUP]['PreInvocation'][0]['command']
        # The fixture bootstraps shell Python with the synthetic account.
        for missing in (False, True):
            if missing:
                (self.plugin / 'scripts/compact_stop_hook.py').unlink()
            result = subprocess.run(['sh', '-c', command], input='{}', capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '{}\n')
            self.assertEqual(result.stderr, '')

    def test_preview_never_prints_other_group_contents(self):
        secret = 'FAKE_SECRET_DO_NOT_PRINT'
        other = {'other': {'SessionStart': [{'command': 'example --token ' + secret}]}}
        self.config.write_text(json.dumps(other))
        for args in (('--limit', '50000'), ('--remove',)):
            code, out, err = self.run_cli('preview', *args)
            self.assertEqual(code, 0, err)
            self.assertNotIn(secret, out + err)
            self.assertNotIn('example --token', out + err)
            self.assertIn('other', out)
            self.assertIn(cs.GROUP, out)
            if args[0] == '--limit':
                self.assertIn('  "PreInvocation": [', out)

    def test_plugin_root_git_and_writable_paths_refused(self):
        for parent in (self.plugin, self.plugin.parent):
            for directory in (False, True):
                value = self.preview()
                marker = parent / '.git'
                if directory:
                    marker.mkdir()
                else:
                    marker.write_text('gitdir: elsewhere')
                before = self.snapshot()
                self.refuse('preview', '--limit', '50000')
                self.refuse('apply', '--digest', value, '--yes')
                self.assertEqual(before, self.snapshot())
                marker.rmdir() if directory else marker.unlink()
            for mode in (0o720, 0o702):
                value = self.preview()
                original = stat.S_IMODE(parent.stat().st_mode)
                parent.chmod(mode)
                try:
                    before = self.snapshot()
                    self.refuse('preview', '--limit', '50000')
                    self.refuse('apply', '--digest', value, '--yes')
                    self.assertEqual(before, self.snapshot())
                finally:
                    parent.chmod(original)

    def test_backup_permissions_are_intersection_with_owner_read_write(self):
        self.config.chmod(0o440)
        self.apply(self.preview())
        backup, = self.config.parent.glob('hooks.json.bak-*')
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o440)

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
        self.config.chmod(0o620)
        self.refuse('preview', '--remove')
        self.refuse('apply', '--digest', value, '--yes')
        self.config.chmod(0o600)
        self.config.parent.chmod(0o777)
        self.refuse('preview', '--remove')
        self.refuse('apply', '--digest', value, '--yes')

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

    def test_missing_files_and_config_option_rejected(self):
        self.host.unlink()
        self.config.unlink()
        self.apply(self.preview())
        self.assertIn(cs.GROUP, json.loads(self.config.read_bytes()))
        custom = self.home / 'custom.json'
        custom.write_text('{}')
        self.refuse('preview', '--limit', '50000', '--config', str(custom))
        self.assertEqual(custom.read_text(), '{}')
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
        self.assertEqual(shlex.split(cs.hook_command())[2],
                         str(self.plugin / 'scripts/compact_stop_hook.py'))

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
        self.assertIn('set up', stop)
        self.assertNotIn('`--config', stop)
        delegate = (ROOT / 'skills/fnl-delegate/SKILL.md').read_text()
        for text in ('agy -p', 'status: ERROR', 'context limit', 'not a model failure',
                     'The conversation is large. Run /compact, or start a fresh session with a short handover, then continue.'):
            self.assertIn(text, delegate)
        for name, token in (('skills/fnl-session-hygiene/SKILL.md', 'Antigravity compaction stop'),
                            ('PRIVACY.md', 'state/compact-stop/'), ('README.md', 'compaction-stop.md'),
                            ('CHANGELOG.md', 'opt-in Antigravity pre-invocation compaction stop'),
                            ('docs/specs/index.md', '(compaction-stop.md)')):
            self.assertIn(token, (ROOT / name).read_text())
        # The bundled hook declarations must not carry the stop: it lives only in the user's own hooks file.
        for name in ('.claude-plugin/hooks.json', '.codex-plugin/hooks.json'):
            declared = (ROOT / name).read_text()
            for token in ('PreInvocation', 'compact_stop', 'compact-stop'):
                self.assertNotIn(token, declared)

    def test_backups_are_unique_private_and_never_overwritten(self):
        with mock.patch.object(cs.time, 'strftime', return_value='20261106-120000'):
            original = self.config.read_bytes()
            self.apply(self.preview())
            first, = self.config.parent.glob('hooks.json.bak-*')
            self.apply(self.preview('--remove'))
            backups = list(self.config.parent.glob('hooks.json.bak-*'))
            self.assertEqual(len(backups), 2)
            self.assertEqual(first.read_bytes(), original)
            for backup in backups:
                self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
            value = self.preview()
            planned = json.loads(self.plan.read_bytes())['plan']['backup']
            occupied = self.config.parent / planned
            occupied.write_text('keep')
            before = self.snapshot()
            self.refuse('apply', '--digest', value, '--yes')
            self.assertEqual(self.snapshot(), before)

    def test_hooks_folder_symlink_git_and_wrong_owners_refused(self):
        value = self.preview()
        folder = self.config.parent
        moved = folder.with_name('original-config')
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
        self.refuse('preview', '--remove')
        self.refuse('apply', '--digest', value, '--yes')
        folder.unlink()
        moved.rename(folder)
        for parent in (folder, folder.parent):
            (parent / '.git').write_text('gitdir: elsewhere')
            self.refuse('preview', '--remove')
            self.refuse('apply', '--digest', value, '--yes')
            (parent / '.git').unlink()
        original = os.fstat
        for target in (folder, self.config):
            inode = target.stat().st_ino
            def wrong_owner(fd):
                info = original(fd)
                if info.st_ino == inode:
                    fields = list(info)
                    fields[4] = os.getuid() + 1
                    return os.stat_result(fields)
                return info
            with mock.patch.object(os, 'fstat', side_effect=wrong_owner):
                self.refuse('preview', '--remove')
                self.refuse('apply', '--digest', value, '--yes')

    def test_apply_rejects_stored_custom_target(self):
        self.preview()
        saved = json.loads(self.plan.read_bytes())
        custom = self.home / 'custom.json'
        custom.write_bytes(self.config.read_bytes())
        saved['plan']['path'] = str(custom)
        saved['plan']['backup'] = saved['plan']['backup'].replace('hooks.json', 'custom.json', 1)
        saved['digest'] = cs.cs.digest(saved['plan'])
        self.plan.write_text(json.dumps(saved))
        before = self.snapshot()
        self.refuse('apply', '--digest', saved['digest'], '--yes')
        self.assertEqual(self.snapshot(), before)
