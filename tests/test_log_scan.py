"""Synthetic log acceptance tests; never read real run logs or credential stores."""
import contextlib
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import log_scan
import secret_patterns as sp


class LogScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'logs'
        self.root.mkdir(mode=0o700)
        self.log = self.root / 'run.log'
        self.patch = mock.patch.object(log_scan, 'run_log_folder', return_value=self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, text='ordinary output\n', age=120, mode=0o600):
        self.log.write_bytes(text.encode() if isinstance(text, str) else text)
        self.log.chmod(mode)
        os.utime(self.log, (time.time() - age, time.time() - age))
        return self.log

    def cli(self, *args):
        out = io.StringIO()
        with mock.patch.object(sys, 'argv', ['log_scan.py', *args]), contextlib.redirect_stdout(out):
            code = log_scan.main()
        return code, out.getvalue()

    def planted(self):
        return 'sk' + '-' + 'fixture' * 4

    def test_keys_private_block_ansi_and_named_base64_found(self):
        fixtures = [self.planted(), '-----' + 'BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----',
                    'sk' + '\x1b[31m-' + 'fixture' * 4 + '\x1b[0m',
                    'ACCOUNT_TOKEN=' + 'Zm' * 20]
        for index, text in enumerate(fixtures):
            with self.subTest(case=index):
                self.write(text)
                result = log_scan.scan(self.log)
                self.assertEqual(result['status'], 'findings')
                view = log_scan.safe_view(result)
                self.assertEqual(sp.findings(view), [])
                self.assertIn('[REDACTED]', view)

    def test_thresholds_all_prefixes_and_short_values(self):
        for prefix in ('sk' + '-', 'sk' + '-ant-', 'gh' + 'p_', 'gh' + 'o_', 'gh' + 'u_', 'gh' + 's_',
                       'github' + '_pat_', 'glpat' + '-', 'xox' + 'b-', 'xox' + 'p-', 'npm' + '_',
                       'AK' + 'IA', 'AS' + 'IA', 'AI' + 'za'):
            self.assertTrue(sp.findings(prefix + 'f' * 16))
            if prefix != 'sk' + '-ant-':  # The shorter sk- prefix independently reaches 16.
                self.assertFalse(sp.findings(prefix + 'f' * 15))
        self.assertFalse(sp.findings('ACCOUNT_TOKEN=' + 'f' * 15))
        self.assertTrue(sp.findings('ACCOUNT_TOKEN=' + 'f' * 16))

    def test_synthetic_dump_both_forms_and_window_boundary(self):
        for quoted in (False, True):
            pairs = [(f"'NAME_{i}': 'fixture{i}'" if quoted else f'NAME_{i}=fixture{i}') for i in range(10)]
            self.write('\n'.join(pairs))
            result = log_scan.scan(self.log)
            self.assertEqual(len([h for h in result['hits'] if h['kind'] == 'environment_dump']), 10)
            view = log_scan.safe_view(result)
            self.assertNotIn('fixture', view)
        self.assertFalse(sp.findings('\n'.join(pairs[:9])))
        self.assertFalse(sp.findings(pairs[0] + '\n' * 200 + '\n'.join(pairs[1:])))

    def test_dump_redacts_complete_values_with_colons_spaces_and_empty_strings(self):
        values = ['a:b:c', 'two words', '', 'escaped\\"quote']
        import json
        source = {f'NAME_{i}': values[i % len(values)] for i in range(12)}
        self.write(json.dumps(source))
        result = log_scan.scan(self.log)
        self.assertEqual(result['status'], 'findings')
        view = log_scan.safe_view(result)
        for value in ('a:b:c', 'two words', 'escaped'):
            self.assertNotIn(value, view)
        self.assertEqual(len(result['hits']), 12)
        self.write('\n'.join(f'NAME_{i}=a:b:c' for i in range(10)))
        self.assertNotIn('a:b:c', log_scan.safe_view(log_scan.scan(self.log)))

    def test_binary_compressed_oversize_unreadable_not_scanned_and_show_refuses(self):
        for raw in (b'\x00fixture', b'\x1f\x8bfixture', b'f' * (sp.MAX_BYTES + 1)):
            self.write(raw)
            self.assertEqual(log_scan.scan(self.log)['status'], 'not_scanned')
            self.assertEqual(self.cli('show', str(self.log)), (2, 'not_scanned\n'))
        self.assertEqual(self.cli('scan', str(self.root / 'missing')), (1, 'not_scanned file=1\n'))
        with mock.patch.object(log_scan.os, 'read', side_effect=PermissionError):
            self.assertEqual(self.cli('scan', str(self.log)), (1, 'not_scanned file=1\n'))

    def test_output_fixed_vocabulary_no_value_length_prefix_or_invalid_name(self):
        bad_name = 'ATTACK-NAME_TOKEN'
        value = 'fixture' * 5
        self.write(bad_name + '=' + value + '\nACCOUNT_TOKEN=' + value + '\n' + self.planted())
        code, out = self.cli('scan', str(self.log))
        self.assertEqual(code, 1)
        self.assertEqual(out, 'findings file=1\nnamed_token file=1 line=1\n'
                         'named_token file=1 line=2 name=ACCOUNT_TOKEN\nkey file=1 line=3\n')
        for fragment in (bad_name, value, value[:8], str(len(value)), self.planted()[:3]):
            self.assertNotIn(fragment, out)
        # A token-shaped name is itself redacted, never printed as a variable name.
        name = 'AK' + 'IA' + 'F' * 16
        self.write(name + '=' + value)
        self.assertNotIn(name, self.cli('scan', str(self.log))[1])

    def test_redact_preview_digest_yes_mode_excl_and_no_backup(self):
        self.write('ACCOUNT_TOKEN=' + 'fixture' * 4, mode=0o644)
        before = self.log.read_bytes()
        preview = log_scan.redact(self.log)
        self.assertEqual(self.log.read_bytes(), before)
        with self.assertRaises(ValueError):
            log_scan.redact(self.log, yes=True)
        with self.assertRaises(ValueError):
            log_scan.redact(self.log, yes=True, digest='0' * 64)
        original = os.open
        calls = []
        def opened(path, flags, *args, **kwargs):
            if str(path).startswith('.redact-'):
                calls.append((flags, args[0]))
            return original(path, flags, *args, **kwargs)
        with mock.patch.object(log_scan.os, 'open', side_effect=opened):
            log_scan.redact(self.log, yes=True, digest=preview['digest'])
        self.assertEqual(self.log.read_text(), 'ACCOUNT_TOKEN=[REDACTED]')
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.root.iterdir()], ['run.log'])
        self.assertTrue(calls[0][0] & os.O_EXCL)
        self.assertEqual(calls[0][1], 0o600)

    def test_stale_digest_recent_open_log_refuse(self):
        self.write(self.planted())
        digest = log_scan.redact(self.log)['digest']
        self.write('changed ' + self.planted())
        with self.assertRaises(ValueError):
            log_scan.redact(self.log, yes=True, digest=digest)
        self.write(self.planted(), age=0)
        with self.assertRaises(ValueError):
            log_scan.redact(self.log)
        self.write(self.planted())
        with self.log.open('rb'), self.assertRaises(ValueError):
            log_scan.redact(self.log)

    def test_symlink_hardlink_outside_directory_and_wide_folder_refused(self):
        self.write(self.planted())
        link = self.root / 'link.log'
        link.symlink_to(self.log)
        hard = self.root / 'hard.log'
        os.link(self.log, hard)
        outside = self.root.parent / 'outside.log'
        outside.write_text('ordinary')
        for path in (link, hard, self.log, outside):
            with self.assertRaises((OSError, ValueError)):
                log_scan.redact(path)
            self.assertEqual(self.cli('show', str(path)), (2, 'not_scanned\n'))
        hard.unlink()
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):
            log_scan.scan(self.log)
        self.assertEqual(self.cli('show', str(self.log)), (2, 'not_scanned\n'))

    def test_descriptor_hardlink_swap_owner_and_regular_checks(self):
        self.write()
        real_open = os.open
        def swapped(path, *args, **kwargs):
            fd = real_open(path, *args, **kwargs)
            if path == self.log.name:
                os.link(self.log, self.root / 'new-link')
            return fd
        with mock.patch.object(log_scan.os, 'open', side_effect=swapped), self.assertRaises(ValueError):
            log_scan.scan(self.log)
        (self.root / 'new-link').unlink()
        def replaced(path, *args, **kwargs):
            fd = real_open(path, *args, **kwargs)
            if path == self.log.name:
                self.log.unlink()
                self.log.write_text('replacement')
            return fd
        with mock.patch.object(log_scan.os, 'open', side_effect=replaced), self.assertRaises(ValueError):
            log_scan.scan(self.log)
        fd = os.open(self.root, os.O_RDONLY)
        try:
            with self.assertRaises(ValueError):
                log_scan.check_file(fd)
        finally:
            os.close(fd)
        fd = os.open(self.log, os.O_RDONLY)
        try:
            with mock.patch.object(log_scan.os, 'getuid', return_value=os.getuid() + 1), self.assertRaises(ValueError):
                log_scan.check_file(fd)
        finally:
            os.close(fd)

    def test_show_redacts_and_refuses_unlocatable_finding(self):
        self.write('ACCOUNT_TOKEN=' + 'fixture' * 4)
        self.assertEqual(self.cli('show', str(self.log)), (0, 'ACCOUNT_TOKEN=[REDACTED]'))
        result = log_scan.scan(self.log)
        result['hits'][0].pop('start')
        with mock.patch.object(log_scan, 'scan', return_value=result):
            self.assertEqual(self.cli('show', str(self.log)), (2, 'not_scanned\n'))

    def test_cli_parse_errors_never_echo_input(self):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['log_scan.py', self.planted()]), \
                contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stopped:
            log_scan.main()
        self.assertEqual(stopped.exception.code, 2)
        self.assertEqual(output.getvalue(), 'not_scanned\n')

    def test_new_log_folder_is_private(self):
        new = self.root / 'new' / 'logs'
        with log_scan.folder_descriptor(new) as fd:
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o700)


if __name__ == '__main__':
    unittest.main()
