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
    def test_session_cookie_substrings_are_found_and_redacted(self):
        value = 'fixture' * 4
        for name in ('J' + 'SESSIONID', 'PHP' + 'SESSID', 'WEB_' + 'SESSID', 'X' + 'SESSID' + 'Y',
                     'j' + 'sessionid', 'php' + 'sessid'):
            with self.subTest(case=name):
                self.write(name + '=' + value)
                result = log_scan.scan(self.log)
                self.assertEqual(result['status'], 'findings')
                self.assertEqual([hit['kind'] for hit in result['hits']], ['named_token'])
                self.assert_output(log_scan.safe_view(result), name + '=[REDACTED]')
        self.write('AUTHOR' + '_NAME=' + value)
        self.assertEqual(log_scan.scan(self.log)['status'], 'no_findings')

    def test_log_root_accepts_only_direct_children_of_a_known_run_log_folder(self):
        other = Path(self.tmp.name).resolve() / 'task'
        named = other / '.finolabs' / 'logs'
        self.assertEqual(log_scan.log_root(self.root / 'run.log'), self.root)
        self.assertEqual(log_scan.log_root(named / 'run.log', checkout=other), named)
        for bad, checkout in ((named / 'run.log', None), (self.root / 'sub' / 'run.log', None),
                              (Path(self.tmp.name) / 'run.log', other)):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                log_scan.log_root(bad, checkout=checkout)

    def test_main_checkout_is_the_parent_of_the_common_git_folder(self):
        import subprocess
        main = Path(self.tmp.name).resolve() / 'main'
        tree = Path(self.tmp.name).resolve() / 'tree'
        main.mkdir()
        git = ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com']
        subprocess.run([*git, 'init', '-q'], cwd=main, check=True)
        subprocess.run([*git, 'commit', '-q', '--allow-empty', '-m', 'init'], cwd=main, check=True)
        subprocess.run([*git, 'worktree', 'add', '-q', str(tree)], cwd=main, check=True)
        self.assertEqual(log_scan.main_checkout(tree), main)
        self.assertEqual(log_scan.main_checkout(main), main)
        self.assertIn(main / '.finolabs' / 'logs', log_scan.run_log_folders(tree))
        self.assertIsNone(log_scan.main_checkout(Path(self.tmp.name).resolve() / 'logs'))

    def test_an_empty_log_is_not_scanned(self):
        self.write(b'')
        self.assertEqual(log_scan.scan(self.log)['status'], 'not_scanned')

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

    def assert_output(self, actual, expected):
        self.assertTrue(actual == expected, 'output mismatch; content suppressed')

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

    def test_repeated_private_markers_scan_in_bounded_time(self):
        from tests.scan_timing import timed_scan
        marker = '-----' + 'BEGIN '
        self.write((marker * (1024 * 1024 // len(marker) + 1))[:1024 * 1024])
        status = timed_scan(self, lambda: log_scan.scan(self.log)['status'])
        self.assertEqual(status, 'no_findings')

    def test_private_blocks_keep_spans_and_bound_end_marker_search(self):
        from tests.scan_timing import timed_scan
        header = '-----' + 'BEGIN RSA PRIVATE KEY-----\n'
        footer = '-----' + 'END RSA PRIVATE KEY-----'
        block = header + 'fixture\n' + footer
        hits = sp.findings(block + '\n' + block)
        self.assertEqual([(h['start'], h['end']) for h in hits],
                         [(0, len(block)), (len(block) + 1, 2 * len(block) + 1)])
        marker = '-----' + 'END '
        self.write(header + (marker * (1024 * 1024 // len(marker) + 1))[:1024 * 1024])
        status = timed_scan(self, lambda: log_scan.scan(self.log)['status'])
        self.assertEqual(status, 'findings')

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
            self.assertFalse('fixture' in view, 'dump value exposed')
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
            self.assertFalse(value in view, 'dump value exposed')
        self.assertEqual(len(result['hits']), 12)
        self.write('\n'.join(f'NAME_{i}=a:b:c' for i in range(10)))
        self.assertFalse('a:b:c' in log_scan.safe_view(log_scan.scan(self.log)), 'dump value exposed')

    def test_binary_compressed_oversize_unreadable_not_scanned_and_show_refuses(self):
        for raw in (b'\x00fixture', b'\x1f\x8bfixture', b'f' * (sp.MAX_BYTES + 1)):
            self.write(raw)
            self.assertEqual(log_scan.scan(self.log)['status'], 'not_scanned')
            self.assert_output(self.cli('show', str(self.log)), (2, 'not_scanned\n'))
        self.assert_output(self.cli('scan', str(self.root / 'missing')), (1, 'not_scanned file=1\n'))
        with mock.patch.object(log_scan.os, 'read', side_effect=PermissionError):
            self.assert_output(self.cli('scan', str(self.log)), (1, 'not_scanned file=1\n'))

    def test_output_fixed_vocabulary_no_value_length_prefix_or_invalid_name(self):
        bad_name = 'ATTACK-NAME_TOKEN'
        value = 'fixture' * 5
        self.write(bad_name + '=' + value + '\nACCOUNT_TOKEN=' + value + '\n' + self.planted())
        code, out = self.cli('scan', str(self.log))
        self.assertEqual(code, 1)
        self.assert_output(out, 'findings file=1\nnamed_token file=1 line=1\n'
                         'named_token file=1 line=2 name=ACCOUNT_TOKEN\nkey file=1 line=3\n')
        for fragment in (bad_name, value, value[:8], str(len(value)), self.planted()[:3]):
            self.assertFalse(fragment in out, 'diagnostic exposed synthetic data')
        # A token-shaped name is itself redacted, never printed as a variable name.
        name = 'AK' + 'IA' + 'F' * 16
        self.write(name + '=' + value)
        self.assertFalse(name in self.cli('scan', str(self.log))[1], 'secret-shaped name exposed')

    def test_redact_preview_digest_yes_mode_excl_and_no_backup(self):
        self.write('ACCOUNT_TOKEN=' + 'fixture' * 4, mode=0o644)
        before = self.log.read_bytes()
        preview = log_scan.redact(self.log)
        self.assertTrue(self.log.read_bytes() == before, 'preview changed the log')
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
        self.assertTrue(self.log.read_text() == 'ACCOUNT_' + 'TOKEN=[REDACTED]', 'redaction mismatch')
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.root.iterdir()], ['run.log'])
        self.assertTrue(calls[0][0] & os.O_EXCL)
        self.assertEqual(calls[0][1], 0o600)

    def test_stale_digest_recent_log_refuse(self):
        self.write(self.planted())
        digest = log_scan.redact(self.log)['digest']
        self.write('changed ' + self.planted())
        with self.assertRaises(ValueError):
            log_scan.redact(self.log, yes=True, digest=digest)
        self.write(self.planted(), age=0)
        with self.assertRaises(ValueError):
            log_scan.redact(self.log)

    def test_osc_raw_and_normalized_union_preserves_original_lines(self):
        key = self.planted()
        osc = '\x1b]8;;' + 'https' + '://' + 'example.invalid/?t=' + key + '\n\x1b\\'
        self.write('before\n' + osc + 'link\x1b]8;;\x1b\\\n' + key)
        result = log_scan.scan(self.log)
        self.assertEqual(result['status'], 'findings')
        self.assertEqual({h['line'] for h in result['hits']}, {2, 4})
        code, output = self.cli('show', str(self.log))
        self.assertEqual(code, 0)
        self.assertFalse(key in output, 'show exposed a synthetic secret')
        self.write(key[:2] + '\x1b[31m' + key[2:])
        self.assertEqual(log_scan.scan(self.log)['status'], 'findings')
        self.assertFalse(key[2:] in self.cli('show', str(self.log))[1], 'normalized secret exposed')

    def test_unsupported_escapes_c1_and_format_characters_refuse(self):
        samples = [self.planted()[:6] + char + self.planted()[6:]
                   for char in ('\x1b', '\x1bX', '\x85', '\u200b', '\u200d', '\ufeff')]
        samples.append(self.planted() + '\x1b[')
        for text in samples:
            self.write(text)
            self.assertEqual(log_scan.scan(self.log)['status'], 'not_scanned')
            self.assert_output(self.cli('show', str(self.log)), (2, 'not_scanned\n'))

    def test_additional_secret_forms_and_safe_names(self):
        value = 'fixture' * 4
        for name in ('pass', 'auth', 'cookie', 'session', 'private', 'token'):
            for separator in ('=', ': '):
                self.write('db_' + name + separator + '"' + value + ' with spaces"')
                result = log_scan.scan(self.log)
                self.assertEqual(result['status'], 'findings')
                self.assertFalse(value in log_scan.safe_view(result), 'quoted secret exposed')
        for prefix in ('sk' + '_live_', 'sk' + '_test_', 'Authorization' + ': Bearer '):
            self.write(prefix + value)
            result = log_scan.scan(self.log)
            self.assertEqual(result['status'], 'findings')
            self.assertFalse(value in log_scan.safe_view(result), 'prefixed secret exposed')
        for name in ('AB' * 10, 'A0' * 10, 'GZ' * 10):
            self.write('\n'.join(name + '=' + value for _ in range(10)))
            output = self.cli('scan', str(self.log))[1]
            self.assertFalse(name in output, 'secret-shaped name exposed')
            self.assertTrue(sp.safe_name(name) is None, 'secret-shaped name accepted')

    def test_large_benign_logs_and_planted_value(self):
        from tests.scan_timing import timed_scan
        import json
        benign = ''.join(f'step {i}: ok\n' for i in range(5000))
        events = ''.join(json.dumps({'event': 'step', 'index': i, 'status': 'ok'}) + '\n'
                         for i in range(2000))
        for text in (benign, 'name: value\n' * 5000, events):
            self.write(text)
            status = timed_scan(self, lambda: log_scan.scan(self.log)['status'])
            self.assertEqual(status, 'no_findings')
        for position in (0, len(benign) // 2, len(benign)):
            before, after = benign[:position] + 'ACCOUNT_' + 'TOKEN=', '\n' + benign[position:]
            self.write(before + self.planted() + after)
            preview = log_scan.redact(self.log)
            self.assertEqual(preview['status'], 'findings')
            log_scan.redact(self.log, yes=True, digest=preview['digest'])
            self.assert_output(self.log.read_text(), before + '[REDACTED]' + after)

    def test_plain_pair_bound_refuses_without_a_finding(self):
        from tests.scan_timing import timed_scan
        self.write('a=b ' * 250000)
        self.assertEqual(timed_scan(self, lambda: log_scan.scan(self.log)['status']), 'no_findings')
        self.write('a=b ' * (sp.MAX_PAIRS + 1))
        self.assertEqual(timed_scan(self, lambda: log_scan.scan(self.log)['status']), 'not_scanned')
        self.assert_output(self.cli('show', str(self.log)), (2, 'not_scanned\n'))
        with self.assertRaises(ValueError):
            log_scan.redact(self.log, yes=True)

    def test_dump_requires_distinct_environment_style_names(self):
        self.assertFalse(sp.findings('NAME_0=value\n' * 2000), 'repeated name flagged')
        self.assertFalse(sp.findings('\n'.join(f'NAME{i}=value' for i in range(20))),
                         'names without underscores flagged')
        pairs = [f'NAME_{i}=value' for i in range(10)]
        self.assertFalse(sp.findings('\n'.join(pairs[:9] * 10)), 'nine distinct names flagged')
        self.assertEqual(len(sp.findings('\n'.join(pairs))), 10)
        self.assertEqual(len(sp.findings(pairs[0] + '\n' * 199 + ' '.join(pairs[1:]))), 10)
        self.assertFalse(sp.findings(pairs[0] + '\n' * 200 + '\n'.join(pairs[1:])),
                         'out-of-window names flagged')

    def test_sensitive_name_parts(self):
        value = 'fixture' * 4
        for name in ('AUTHOR_NAME', 'PASSENGER', 'COMPASS', 'SESSIONS_DIR', 'PRIVATEER', 'COOKIEJAR'):
            self.assertFalse(sp.findings(name + '=' + value), 'unrelated name flagged')
        for name in ('AUTH_TOKEN', 'DB_PASS', 'AUTH', 'SESSION_ID', 'DB_PRIVATE',
                     'DB_' + 'PASSWD', 'DB_' + 'PASSPHRASE', 'WEB_' + 'SESSIONID', 'HTTP_' + 'COOKIES'):
            self.assertTrue(sp.findings(name + '=' + value), 'sensitive name missed')

    def test_leading_bom_preserves_raw_spans(self):
        for prefix in ('', '\x1b[31m'):
            self.write('\ufeff' + prefix + self.planted() + '\nordinary')
            result = log_scan.scan(self.log)
            self.assertEqual(result['status'], 'findings')
            self.assertEqual(result['hits'][0]['start'], 1 + len(prefix))
            self.assert_output(log_scan.safe_view(result), '\ufeff' + prefix + '[REDACTED]\nordinary')
        self.write('\ufeffordinary\n')
        self.assertEqual(log_scan.scan(self.log)['status'], 'no_findings')
        self.write('\ufeff\ufeffordinary')
        self.assertEqual(log_scan.scan(self.log)['status'], 'not_scanned')

    def test_match_cap_redacts_whole_log(self):
        self.write((self.planted() + '\n') * sp.MAX_MATCHES)
        result = log_scan.scan(self.log)
        self.assertEqual(result['status'], 'findings')
        self.assertLessEqual(len(result['hits']), sp.MAX_MATCHES)
        self.assertEqual(result['hits'][0]['kind'], 'match_limit')
        self.assert_output(log_scan.safe_view(result), '[REDACTED]')

    def test_redact_never_queries_process_files_or_launches_commands(self):
        self.write(self.planted())
        with mock.patch.object(Path, 'iterdir', side_effect=PermissionError), \
                mock.patch('subprocess.run', side_effect=AssertionError('unexpected subprocess')):
            preview = log_scan.redact(self.log)
            with self.log.open('rb'):
                log_scan.redact(self.log, yes=True, digest=preview['digest'])
        self.assert_output(self.log.read_text(), '[REDACTED]')

    def test_metadata_changed_immediately_before_rename_refuses(self):
        for change in ('replace', 'size', 'mtime'):
            self.write(self.planted())
            digest = log_scan.redact(self.log)['digest']
            real_fsync = os.fsync
            def changed(fd):
                real_fsync(fd)
                if change == 'replace':
                    self.log.unlink()
                    self.log.write_text('changed')
                elif change == 'size':
                    with self.log.open('a') as stream:
                        stream.write('changed')
                else:
                    os.utime(self.log, None)
            with mock.patch.object(log_scan.os, 'fsync', side_effect=changed), \
                    mock.patch.object(log_scan.os, 'replace') as rename, self.assertRaises(ValueError):
                log_scan.redact(self.log, yes=True, digest=digest)
            rename.assert_not_called()
            self.assertEqual(len(list(self.root.iterdir())), 1)

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
            self.assert_output(self.cli('show', str(path)), (2, 'not_scanned\n'))
        hard.unlink()
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):
            log_scan.scan(self.log)
        self.assert_output(self.cli('show', str(self.log)), (2, 'not_scanned\n'))

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
        self.assertTrue(self.cli('show', str(self.log)) == (0, 'ACCOUNT_' + 'TOKEN=[REDACTED]'), 'show mismatch')
        result = log_scan.scan(self.log)
        result['hits'][0].pop('start')
        with mock.patch.object(log_scan, 'scan', return_value=result):
            self.assert_output(self.cli('show', str(self.log)), (2, 'not_scanned\n'))

    def test_cli_parse_errors_never_echo_input(self):
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', ['log_scan.py', self.planted()]), \
                contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stopped:
            log_scan.main()
        self.assertEqual(stopped.exception.code, 2)
        self.assert_output(output.getvalue(), 'not_scanned\n')

    def test_new_log_folder_is_private(self):
        new = self.root / 'new' / 'logs'
        with log_scan.folder_descriptor(new) as fd:
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o700)

    def test_open_folder_refusal_is_one_fixed_fix_message_and_mode_is_kept(self):
        self.write()
        self.root.chmod(0o755)
        with self.assertRaises(ValueError) as refused:
            log_scan.scan(self.log)
        self.assertEqual(str(refused.exception), log_scan.FOLDER_REFUSED)
        self.assertIn('chmod 700', log_scan.FOLDER_REFUSED)
        self.assertNotIn(str(self.root), log_scan.FOLDER_REFUSED)
        self.assertNotIn('/', log_scan.FOLDER_REFUSED)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o755)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assert_output(self.cli('scan', str(self.log)), (1, 'not_scanned file=1\n'))
        self.assertEqual(err.getvalue(), log_scan.FOLDER_REFUSED + '\n')
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o755)

    def test_other_refusals_keep_the_plain_message(self):
        self.write()
        link = self.root / 'link.log'
        link.symlink_to(self.log)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assert_output(self.cli('scan', str(link)), (1, 'not_scanned file=1\n'))
        self.assertEqual(err.getvalue(), '')


class NamedTokenStanceTest(unittest.TestCase):
    """Synthetic values only: shapes a security review showed could hide a credential stay flagged."""

    def assert_flagged(self, text):
        self.assertIn('named_token', [hit['kind'] for hit in sp.findings(text)], 'missing finding; content suppressed')

    def test_names_and_value_shapes_grant_no_exemption(self):
        opaque = 'fixture' * 4
        stamp = '2026-11-10T01:17:00Z'
        cases = ['true|API_KEY=' + opaque + ' /usr/bin/true', 'PASSWORD=' + '1234567890' * 3,
                 '"password": "' + stamp + '"', '"secret": "correct horse battery staple"',
                 'credential_expires_at=' + stamp, 'credential_expires_at=' + stamp + ',' + opaque]
        cases += [f'{name}={opaque}' for name in ('coord_session', 'session_id', 'expected_keys', 'key_end')]
        for index, text in enumerate(cases):
            with self.subTest(case=index):
                self.assert_flagged(text)


if __name__ == '__main__':
    unittest.main()
