"""afk setup acceptance with synthetic accounts and the real lease reader."""
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
SCRIPT = ROOT / 'skills/setup/scripts/afk_setup.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AfkSetupTest(unittest.TestCase):
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
        self.host.write_bytes(b'# Host\r\n\r\n## Other\r\nkeep \xc3\xa9  \r\n')
        self.plan = self.host.parent / 'state/autopilot-setup/preview.json'

    def cli(self, *args):
        self.assertTrue(SCRIPT.is_file(), 'afk setup preview/apply writer is missing')
        writer = load('afk_setup_test', SCRIPT)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def preview(self, *args):
        code, out, err = self.cli('preview', *args)
        self.assertEqual(code, 0, err)
        self.assertIn('## afk', out)
        self.assertNotIn('## Autopilot', out)
        return out.split('Digest: ')[1].splitlines()[0]

    def apply(self, digest):
        code, _, err = self.cli('apply', '--yes', '--digest', digest)
        self.assertEqual(code, 0, err)

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes()
                for p in self.home.rglob('*') if p.is_file()}

    def reader(self):
        return load('afk_reader_test', ROOT / 'skills/delegate/scripts/afk.py')

    def test_round_trip_defaults_and_preview_only(self):
        before = self.host.read_bytes()
        digest = self.preview()
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        self.apply(digest[:12])
        reader = self.reader()
        owned = {key: value for key, value in reader.settings().items() if key in reader.DEFAULTS}
        self.assertEqual(owned, reader.DEFAULTS)
        self.assertEqual(next(self.host.parent.glob('host.md.bak-*')).read_bytes(), before)
        self.assertFalse(self.plan.exists())

    def test_explicit_values_round_trip_and_surrounding_bytes(self):
        prefix = self.host.read_bytes() + b'```\r\n## afk\r\nexample\r\n```\r\n'
        suffix = b'# Later\nlast line without newline'
        self.host.write_bytes(prefix + b'## afk\r\n- Merge: no\r\n- Mode: strict\r\n\r\n' + suffix)
        digest = self.preview('--hosts', 'Codex', 'Antigravity', '--lease-hours', '24', '--quota-floor-percent', '100',
                              '--third-party-instructions', 'open', '--default-branch', 'open')
        self.apply(digest)
        raw = self.host.read_bytes()
        self.assertTrue(raw.startswith(prefix))
        self.assertTrue(raw.endswith(suffix))
        self.assertNotIn(b'Mode', raw)  # the old lines go with the section the writer replaces
        self.assertNotIn(b'Merge', raw)
        reader = self.reader()
        self.assertEqual(reader.settings(), {
            'Hosts': 'Codex, Antigravity', 'Lease hours': 24, 'Quota floor percent': 100,
            'Third-party instructions': 'open', 'Default branch': 'open', 'Excerpts leave the machine': 'no'})

    def test_an_old_autopilot_section_is_left_for_the_user_and_afk_is_added(self):
        old = b'## Autopilot\n- Merge: yes\n\n'
        self.host.write_bytes(old)
        self.apply(self.preview())
        raw = self.host.read_bytes()
        # The old section is neither read nor rewritten; the upgrade note asks the user to delete it.
        self.assertTrue(raw.startswith(old))
        self.assertEqual(raw.count(b'## afk\n'), 1)
        self.assertEqual(self.reader().settings()['Lease hours'], 8)

    def test_mismatch_and_missing_yes_write_nothing(self):
        digest = self.preview()
        for args in (('apply', '--yes', '--digest', '0' * 64),
                     ('apply', '--digest', digest), ('apply', '--yes', '--digest', digest[:4])):
            before = self.snapshot()
            self.assertEqual(self.cli(*args)[0], 1)
            self.assertEqual(self.snapshot(), before)

    def test_changed_host_and_expired_preview_write_nothing(self):
        digest = self.preview()
        self.host.write_bytes(self.host.read_bytes() + b'changed\n')
        before = self.snapshot()
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.snapshot(), before)
        digest = self.preview()
        writer = load('afk_setup_clock', SCRIPT)
        with mock.patch.object(writer.time, 'time', return_value=0):
            self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.host.read_bytes(), before['.finolabs/vibecode/host.md'])

    def test_symlinks_refused_in_preview_and_apply(self):
        digest = self.preview()
        target = self.home / 'untouched.md'
        self.host.rename(target)
        self.host.symlink_to(target)
        before = self.snapshot()
        self.assertEqual(self.cli('preview')[0], 1)
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.snapshot(), before)

    def test_bounds_and_retired_options(self):
        before = self.snapshot()
        for option, values in {
            '--default-branch': ('off',), '--third-party-instructions': ('off',), '--lease-hours': ('0', '25'),
            '--quota-floor-percent': ('-1', '101', '1.5'), '--hosts': ('Unknown',),
            # Retired with `strict` (docs/specs/afk-one-mode.md): setup has no such option any more.
            '--mode': ('open', 'strict'), '--merge': ('yes', 'no'), '--max-runs': ('20',),
            '--max-runtime-minutes': ('480',), '--max-actions-per-hour': ('30',), '--task-choice': ('choose',),
            '--push-and-pull-requests': ('yes',), '--trusted-authors': ('own',), '--decide': ('Publishing',),
            '--non-production-target': ('npm run deploy:dev',), '--test-command': ('npm test',),
            '--top-level-file': ('TASKS.md',), '--release-target': ('git tag v1.0.0',),
            '--production-target': ('npm run deploy',),
        }.items():
            for value in values:
                with self.subTest(option=option, value=value):
                    self.assertEqual(self.cli('preview', option, value)[0], 1)
                    self.assertEqual(self.snapshot(), before)
        digest = self.preview('--lease-hours', '1', '--quota-floor-percent', '0')
        self.apply(digest)
        self.assertEqual(self.reader().settings()['Quota floor percent'], 0)

    def test_preview_or_backup_links_and_existing_backup_refuse_writes(self):
        digest = self.preview()
        saved = json.loads(self.plan.read_bytes())
        backup = self.host.parent / saved['plan']['backup']
        backup.write_bytes(b'keep existing backup')
        before = self.snapshot()
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.snapshot(), before)
        backup.unlink()
        backup.symlink_to(self.host)
        before = self.snapshot()
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.snapshot(), before)
        backup.unlink()
        target = self.home / 'saved-preview.json'
        self.plan.rename(target)
        self.plan.symlink_to(target)
        before = self.snapshot()
        self.assertEqual(self.cli('preview')[0], 1)
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.snapshot(), before)

    def writer(self):
        return load('afk_setup_names', SCRIPT)

    def test_names_and_bounds_match_the_reader(self):
        writer, reader = self.writer(), self.reader()
        self.assertEqual((writer.DEFAULTS, writer.NUMBERS, writer.CHOICES, writer.CONSENT),
                         (reader.DEFAULTS, reader.NUMBERS, reader.CHOICES, reader.CONSENT))

    def test_the_section_holds_the_guards_first_and_no_retired_line(self):
        code, out, err = self.cli('preview', '--default-branch', 'open')
        self.assertEqual(code, 0, err)
        self.apply(out.split('Digest: ')[1].splitlines()[0])
        section = self.host.read_text()
        section = section[section.index('## afk'):]
        self.assertEqual(section.splitlines()[2:8],
                         ['- Third-party instructions: guard', '- Default branch: open', '- Hosts: Claude Code',
                          '- Lease hours: 8', '- Quota floor percent: 15', '- Excerpts leave the machine: no'])
        for name in self.reader().RETIRED:
            self.assertNotIn('- %s:' % name, section)
        _, notices = self.reader().read_settings()
        self.assertEqual(notices, [])  # a fresh setup prints no retired-line notice

    def test_excerpt_consent_is_separate_and_off_by_default(self):
        self.apply(self.preview())
        reader = self.reader()
        self.assertEqual(reader.settings()[reader.CONSENT], 'no')
        self.assertIn('- Excerpts leave the machine: no\n', self.host.read_text())
        self.apply(self.preview('--excerpts-leave-the-machine', 'yes'))
        self.assertEqual(self.reader().settings()[reader.CONSENT], 'yes')
        self.assertEqual(self.cli('preview', '--excerpts-leave-the-machine', 'maybe')[0], 1)

    def test_ambiguous_host_refused_and_missing_host_created(self):
        for raw in (b'## afk\n- Merge: no\n## afk\n', b'```\nunclosed\n'):
            self.host.write_bytes(raw)
            self.assertEqual(self.cli('preview')[0], 1)
            self.assertEqual(self.host.read_bytes(), raw)
        self.host.unlink()
        self.apply(self.preview())
        self.assertEqual(self.reader().settings()['Lease hours'], 8)
        self.assertEqual(list(self.host.parent.glob('host.md.bak-*')), [])


if __name__ == '__main__':
    unittest.main()
