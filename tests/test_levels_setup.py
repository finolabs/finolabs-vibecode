"""Agent levels setup: writer, strict reader and refusals with synthetic accounts."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/setup/scripts/levels_setup.py'
PREFIX = b'# Host\r\n\r\n## Other\r\nkeep \xc3\xa9  \r\n'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LevelsSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / 'home')
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
        patch = mock.patch.dict(os.environ, {'HOME': str(self.home)}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.host = self.home / '.finolabs/vibecode/host.md'
        self.host.parent.mkdir(parents=True, exist_ok=True)
        self.host.write_bytes(PREFIX)
        self.plan = self.host.parent / 'state/levels-setup/preview.json'

    def cli(self, *args):
        self.assertTrue(SCRIPT.is_file(), 'Agent levels writer is missing')
        writer = load('levels_setup_test', SCRIPT)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def preview(self, *args):
        code, out, err = self.cli('preview', *args)
        self.assertEqual(code, 0, err)
        return out.split('Digest: ')[1].splitlines()[0]

    def test_an_info_string_fence_line_does_not_close_a_fence(self):
        reader = load('levels_setup_fence_test', SCRIPT)
        text = ('## Other\n```text\n```md\n## Agent levels\n- Consent: no\n```\n\n'
                '## Agent levels\n\n- Consent: yes (2026-10-01)\n- codex: levels 1-4\n')
        self.assertEqual(reader.parse(text), {'consent': 'yes', 'date': '2026-10-01', 'installs': [['codex', 1, 4]]})

    def test_round_trip_keeps_other_bytes_and_show_reads_it(self):
        before = self.host.read_bytes()
        digest = self.preview('--install', 'claudework:3-5', '--install', 'claudeomni:1-2')
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        code, _, err = self.cli('apply', '--yes', '--digest', digest[:12])
        self.assertEqual(code, 0, err)
        raw = self.host.read_bytes()
        self.assertTrue(raw.startswith(before))
        self.assertIn(b'- claudework: levels 3-5', raw)
        self.assertEqual(next(self.host.parent.glob('host.md.bak-*')).read_bytes(), before)
        self.assertFalse(self.plan.exists())
        code, out, _ = self.cli('show')
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data['consent'], 'yes')
        self.assertEqual(data['installs'], [['claudework', 3, 5], ['claudeomni', 1, 2]])

    def test_families_are_valid_names_with_levels(self):
        digest = self.preview('--install', 'codex:1-5', '--install', 'claude:1-5', '--install', 'antigravity:1-2')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        names = [item[0] for item in json.loads(self.cli('show')[1])['installs']]
        self.assertEqual(names, ['codex', 'claude', 'antigravity'])

    def test_blank_command_range_is_kept_as_all_five(self):
        digest = self.preview('--install', 'claudework:1-5', '--install', 'codex:1-4')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        data = json.loads(self.cli('show')[1])
        self.assertEqual(data['installs'], [['claudework', 1, 5], ['codex', 1, 4]])

    def test_candidates_lists_names_only_and_runs_nothing(self):
        bin_dir = self.home / 'bin'
        bin_dir.mkdir()
        for name, mode in (('claudework', 0o755), ('claudeomni', 0o755), ('claudenox', 0o644), ('claude', 0o755), ('claudeBad', 0o755), ('other', 0o755),
                           ('codex', 0o755), ('antigravity', 0o755)):
            (bin_dir / name).write_text('#!/bin/sh\n')
            (bin_dir / name).chmod(mode)
        (self.home / '.claude-work').mkdir()
        (self.home / '.claude-link').symlink_to(self.home / '.claude-work')
        (self.home / '.claude-File').mkdir()
        with mock.patch.dict(os.environ, {'PATH': f'{bin_dir}:relative/bin'}), \
                mock.patch('subprocess.run', side_effect=AssertionError('command run')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('command run')):
            code, out, _ = self.cli('candidates')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {'commands': ['claudeomni', 'claudework'], 'folders': ['work']})
        self.assertNotIn(str(self.home), out)

    def test_show_reports_none_without_section(self):
        self.assertEqual(self.cli('show')[:2], (0, 'none\n'))

    def test_off_replaces_entries_and_leaves_no_install(self):
        self.host.write_bytes(PREFIX + b'## Agent levels\r\n- Consent: yes (2026-11-09)\r\n- claudework: levels 3-5\r\n')
        digest = self.preview('--off')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        data = json.loads(self.cli('show')[1])
        self.assertEqual((data['consent'], data['installs']), ('no', []))

    def test_invalid_entries_are_refused_and_write_nothing(self):
        before = self.host.read_bytes()
        bad = ('gemini:1-2', 'claudeWork:1-2', 'claudework', 'claudework:0-2', 'claudework:3-6',
               'claudework:5-3', 'claudework:3-5-1', 'claude_work:1-2', 'claude work:1-2',
               'claude' + 'a' * 25 + ':1-2')
        for item in bad:
            with self.subTest(item=item):
                self.assertEqual(self.cli('preview', '--install', item)[0], 1)
        self.assertEqual(self.cli('preview', '--install', 'claudework:1-2', '--install', 'claudework:3-5')[0], 1)
        self.assertEqual(self.cli('preview')[0], 1)
        self.assertEqual(self.cli('preview', '--off', '--install', 'claudework:1-2')[0], 1)
        many = [x for i in range(9) for x in ('--install', f'claudex{i}:1-2')]
        self.assertEqual(self.cli('preview', *many)[0], 1)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertFalse(self.plan.exists())

    def test_wrong_digest_missing_yes_and_changed_host_write_nothing(self):
        digest = self.preview('--install', 'claudework:3-5')
        before = self.host.read_bytes()
        self.assertEqual(self.cli('apply', '--yes', '--digest', '0' * 64)[0], 1)
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 1)
        self.host.write_bytes(before + b'changed\r\n')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertNotIn(b'claudework', self.host.read_bytes())

    def test_show_is_unreadable_for_ambiguous_or_unknown_content(self):
        cases = (
            b'## Agent levels\n- Consent: yes (2026-11-09)\n- claudework: levels 3-5\n## Agent levels\n- Consent: no\n',
            b'## Agent levels\n- Consent: yes (2026-11-09)\n- claudework: levels 3-5\n- claudework: levels 1-2\n',
            b'## Agent levels\n- claudework: levels 3-5\n',
            b'## Agent levels\n- Consent: yes (2026-11-09)\n- claudework: levels 5-3\n',
            b'## Agent levels\n- Consent: yes (2026-11-09)\n- extra: note\n',
            b'## Agent levels\n- Consent: no\n- claudework: levels 3-5\n',
        )
        for raw in cases:
            with self.subTest(raw=raw):
                self.host.write_bytes(raw)
                code, out, _ = self.cli('show')
                self.assertEqual((code, out), (3, 'unreadable\n'))

    def test_writer_runs_no_command_and_reads_no_shell_file(self):
        with mock.patch('subprocess.run', side_effect=AssertionError('command run')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('command run')):
            digest = self.preview('--install', 'claudework:3-5')
            self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)


@unittest.skipUnless(Path('/bin/zsh').exists(), 'zsh is required')
class FunctionDispatchEnvironmentTest(unittest.TestCase):
    """A shell-function command behind delegate_env.py gets only approved names (names only, no values)."""

    def run_function(self, host_text):
        import subprocess
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        import delegate_env
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            (home / '.zshrc').write_text('claudetest() { if (( ${+LEVELS_SYNTH_NAME} )); then print -r -- "state:set"; else print -r -- "state:unset"; fi; }\n')
            with mock.patch.dict(os.environ, {'HOME': str(home), 'LEVELS_SYNTH_NAME': 'x', 'PATH': '/usr/bin:/bin'}, clear=True):
                env = delegate_env.environment('claude', host_text=host_text)
            self.assertNotIn('ZDOTDIR', env)
            result = subprocess.run(['/bin/zsh', '-ic', 'claudetest'], env=env, capture_output=True, text=True, timeout=30)
        return [line for line in result.stdout.splitlines() if line.startswith('state:')]

    def test_a_name_that_is_not_approved_does_not_reach_the_function(self):
        self.assertEqual(self.run_function('## Delegate environment\n- claude: none\n'), ['state:unset'])

    def test_documented_launch_form_uses_the_filter_and_the_users_zsh(self):
        text = (ROOT / 'skills/delegate/references/agents.md').read_text()
        line = next(l for l in text.splitlines() if 'Declared Claude Code commands' in l)
        self.assertIn('delegate_env.py --family claude -- /bin/zsh -ic', line)
        self.assertNotIn('never behind `delegate_env.py`', line)

    def test_an_approved_name_reaches_the_function(self):
        self.assertEqual(self.run_function('## Delegate environment\n- claude: LEVELS_SYNTH_NAME\n'), ['state:set'])


if __name__ == '__main__':
    unittest.main()
