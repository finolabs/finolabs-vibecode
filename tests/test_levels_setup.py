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
SCRIPT = ROOT / 'skills/fnl-setup/scripts/levels_setup.py'
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


if __name__ == '__main__':
    unittest.main()
