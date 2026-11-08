"""Autopilot setup acceptance with synthetic accounts and the real lease reader."""
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
SCRIPT = ROOT / 'skills/fnl-setup/scripts/autopilot_setup.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutopilotSetupTest(unittest.TestCase):
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
        self.assertTrue(SCRIPT.is_file(), 'Autopilot setup preview/apply writer is missing')
        writer = load('autopilot_setup_test', SCRIPT)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def preview(self, *args):
        code, out, err = self.cli('preview', '--merge', 'no', *args)
        self.assertEqual(code, 0, err)
        self.assertIn('## Autopilot', out)
        return out.split('Digest: ')[1].splitlines()[0]

    def apply(self, digest):
        code, _, err = self.cli('apply', '--yes', '--digest', digest)
        self.assertEqual(code, 0, err)

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes()
                for p in self.home.rglob('*') if p.is_file()}

    def reader(self):
        return load('autopilot_reader_test', ROOT / 'skills/fnl-delegate/scripts/autopilot.py')

    def test_round_trip_defaults_and_preview_only(self):
        before = self.host.read_bytes()
        digest = self.preview()
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        self.apply(digest[:12])
        reader = self.reader()
        self.assertEqual(reader.settings(), {**reader.DEFAULTS, 'Merge': 'no'})
        self.assertEqual(next(self.host.parent.glob('host.md.bak-*')).read_bytes(), before)
        self.assertFalse(self.plan.exists())

    def test_explicit_values_round_trip_and_surrounding_bytes(self):
        prefix = self.host.read_bytes() + b'```\r\n## Autopilot\r\nexample\r\n```\r\n'
        suffix = b'# Later\nlast line without newline'
        self.host.write_bytes(prefix + b'## Autopilot\r\n- Merge: no\r\n\r\n' + suffix)
        digest = self.preview('--hosts', 'Codex', 'Antigravity', '--task-choice', 'listed',
                              '--push-and-pull-requests', 'no', '--merge', 'yes',
                              '--lease-hours', '24', '--max-runs', '10000',
                              '--max-runtime-minutes', '1440', '--max-actions-per-hour', '10000',
                              '--quota-floor-percent', '100', '--trusted-authors', 'own')
        self.apply(digest)
        raw = self.host.read_bytes()
        self.assertTrue(raw.startswith(prefix))
        self.assertTrue(raw.endswith(suffix))
        self.assertEqual(self.reader().settings(), {
            'Hosts': 'Codex, Antigravity', 'Task choice': 'listed',
            'Push and pull requests': 'no', 'Merge': 'yes', 'Trusted authors': 'own',
            'Lease hours': 24, 'Max runs': 10000, 'Max runtime minutes': 1440,
            'Max actions per hour': 10000, 'Quota floor percent': 100})

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
        writer = load('autopilot_setup_clock', SCRIPT)
        with mock.patch.object(writer.time, 'time', return_value=0):
            self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.host.read_bytes(), before['.finolabs/vibecode/host.md'])

    def test_symlinks_refused_in_preview_and_apply(self):
        digest = self.preview()
        target = self.home / 'untouched.md'
        self.host.rename(target)
        self.host.symlink_to(target)
        before = self.snapshot()
        self.assertEqual(self.cli('preview', '--merge', 'yes')[0], 1)
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.snapshot(), before)

    def test_merge_required_and_bounds(self):
        before = self.snapshot()
        self.assertEqual(self.cli('preview')[0], 1)
        for option, values in {
            '--lease-hours': ('0', '25'), '--max-runs': ('0', '10001'),
            '--max-runtime-minutes': ('0', '1441'), '--max-actions-per-hour': ('0', '10001'),
            '--quota-floor-percent': ('-1', '101', '1.5'), '--hosts': ('Unknown',),
            '--task-choice': ('unknown',), '--trusted-authors': ('everyone',),
            '--merge': ('maybe',), '--push-and-pull-requests': ('maybe',),
        }.items():
            for value in values:
                with self.subTest(option=option, value=value):
                    self.assertEqual(self.cli('preview', '--merge', 'no', option, value)[0], 1)
                    self.assertEqual(self.snapshot(), before)
        digest = self.preview('--lease-hours', '1', '--max-runs', '1',
                              '--max-runtime-minutes', '1', '--max-actions-per-hour', '1',
                              '--quota-floor-percent', '0')
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
        self.assertEqual(self.cli('preview', '--merge', 'no')[0], 1)
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.snapshot(), before)

    def test_ambiguous_host_refused_and_missing_host_created(self):
        for raw in (b'## Autopilot\n- Merge: no\n## Autopilot\n', b'```\nunclosed\n'):
            self.host.write_bytes(raw)
            self.assertEqual(self.cli('preview', '--merge', 'no')[0], 1)
            self.assertEqual(self.host.read_bytes(), raw)
        self.host.unlink()
        self.apply(self.preview())
        self.assertEqual(self.reader().settings()['Merge'], 'no')
        self.assertEqual(list(self.host.parent.glob('host.md.bak-*')), [])


if __name__ == '__main__':
    unittest.main()
