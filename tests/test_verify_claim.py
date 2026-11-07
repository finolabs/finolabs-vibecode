"""Verification, receipt privacy and delegated acceptance on synthetic repositories."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('package_verify', SCRIPTS / 'verify_claim.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class VerificationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = account(self, self.root / 'home')
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'author@example.com')
        self.git('config', 'user.name', 'Synthetic Author')
        (self.checkout / 'target.txt').write_text('before\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Create fixture')
        self.base = self.git('rev-parse', 'HEAD')
        (self.checkout / 'target.txt').write_text('added guard\n')
        self.git('commit', '-qam', 'Add guard')
        self.head = self.git('rev-parse', 'HEAD')
        self.dispatch = 'd20261107-000000-abcd'
        self.brief = {'scope': ['target.txt'], 'tests': [[sys.executable, '-c', 'print("one test passed")']],
                      'criteria': [{'id': 'C1', 'question': 'The change adds a guard.'}]}
        self.output = io.StringIO()

    def git(self, *argv):
        return subprocess.run(['git', '-C', str(self.checkout), *argv], capture_output=True, text=True, check=True).stdout.strip()

    def run_verify(self, **kwargs):
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output):
            return verify.verify(self.brief, self.base, kwargs.get('head', self.head), self.dispatch,
                                 self.checkout, kwargs.get('source', 'host'), kwargs.get('answers', {}), timeout=kwargs.get('timeout', 5))

    def receipt(self):
        return json.loads((self.home / '.finolabs/vibecode/state/verification' / (self.dispatch + '.json')).read_text())

    def test_pass_runs_exact_commands_and_stores_only_metadata(self):
        passed, requests = self.run_verify()
        self.assertTrue(passed)
        self.assertIn('one test passed', self.output.getvalue())
        receipt = self.receipt()
        self.assertEqual(receipt['tests'], 'passed')
        self.assertEqual(receipt['mechanical'], 'passed')
        self.assertEqual(receipt['head'], self.head)
        self.assertNotIn('guard', json.dumps(receipt))
        self.assertNotIn(str(self.checkout), json.dumps(receipt))
        self.assertEqual(receipt['criteria'][0]['answer'], 'insufficient')
        path = self.home / '.finolabs/vibecode/state/verification' / (self.dispatch + '.json')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        packet = requests['C1']
        answer = {k: packet[k] for k in ('question', 'evidence_sha256')}
        answer.update(answer='yes', quote='one test passed')
        self.run_verify(answers={'C1': answer})
        self.assertEqual(self.receipt()['criteria'][0]['answer'], 'yes')

    def test_fallback_is_reported_in_receipt_with_same_evidence(self):
        with mock.patch.object(verify.judge, 'ask_jev', side_effect=verify.judge.Unavailable):
            self.run_verify(source='jev')
        self.assertTrue(self.receipt()['criteria'][0]['fallback'])
        self.assertEqual(self.receipt()['criteria'][0]['source'], 'host')
        self.assertIn('falling back', self.output.getvalue())

    def test_scope_dirty_checkout_and_failed_tests_cannot_pass(self):
        self.brief['scope'] = ['other.txt']
        passed, _ = self.run_verify()
        self.assertFalse(passed)
        self.assertEqual(self.receipt()['mechanical'], 'failed')
        self.brief['scope'] = ['target.txt']
        (self.checkout / 'untracked.txt').write_text('not committed')
        passed, _ = self.run_verify()
        self.assertFalse(passed)
        (self.checkout / 'untracked.txt').unlink()
        self.brief['tests'] = [[sys.executable, '-c', 'raise SystemExit(1)']]
        passed, _ = self.run_verify()
        self.assertFalse(passed)
        self.assertEqual(self.receipt()['tests'], 'failed')

    def test_stale_head_refuses_receipt_and_test_mutation_fails(self):
        with self.assertRaises(ValueError):
            self.run_verify(head=self.base)
        self.brief['tests'] = [[sys.executable, '-c', 'open("target.txt","w").write("changed")']]
        passed, _ = self.run_verify()
        self.assertFalse(passed)
        self.assertIn('FAIL final checkout', self.output.getvalue())

    def test_documents_are_asked_separately_and_compared_in_code(self):
        self.brief['criteria'] = [{'id': 'C1', 'documents': [
            {'path': 'target.txt', 'question': 'The document says the guard was added.'},
            {'path': 'target.txt', 'question': 'The document says the guard was added.'}]}]
        answers = [dict(id='C1.1', answer='yes', source='jev', fallback=False),
                   dict(id='C1.2', answer='no', source='jev', fallback=False)]
        with mock.patch.object(verify, 'ask', side_effect=answers) as ask:
            self.run_verify()
        self.assertEqual(ask.call_count, 2)
        self.assertEqual(ask.call_args_list[0].args[1], 'added guard')
        self.assertEqual(self.receipt()['criteria'][-1]['answer'], 'no')

    def test_timeout_output_limit_and_no_extra_command(self):
        for code in ['import time; time.sleep(5)', 'print("a"*70000)']:
            with self.subTest(code=code):
                passed, _, reason = verify.run_test([sys.executable, '-c', code], self.checkout, .2)
                self.assertFalse(passed)
                self.assertEqual(reason, 'limit')
        marker = self.root / 'marker'
        passed, _, _ = verify.run_test([sys.executable, '-c', 'import sys; print(sys.argv[1])', f'; touch {marker}'], self.checkout, 5)
        self.assertTrue(passed)
        self.assertFalse(marker.exists())

    def test_test_process_receives_only_allowlisted_environment(self):
        injected = {'TYPESAFE_API_KEY': 'synthetic-key', 'GIT_DIR': '/synthetic/git',
                    'GIT_WORK_TREE': '/synthetic/tree', 'GIT_CONFIG_COUNT': '1',
                    'HOME': str(self.home), 'AWS_SECRET_ACCESS_KEY': 'synthetic-secret',
                    'VERIFY_TEST_MARKER': 'must-not-inherit', 'PATH': os.defpath,
                    'LANG': 'C', 'TMPDIR': str(self.root)}
        code = ('import os; '
                'assert "TYPESAFE_API_KEY" not in os.environ; '
                'assert not any(k.startswith("GIT_") for k in os.environ); '
                'assert "AWS_SECRET_ACCESS_KEY" not in os.environ; '
                'assert "HOME" not in os.environ; '
                'assert "VERIFY_TEST_MARKER" not in os.environ; '
                'assert os.environ["PATH"]; '
                'assert os.environ["LANG"] == "C"; '
                f'assert os.environ["TMPDIR"] == {str(self.root)!r}')
        with mock.patch.dict(os.environ, injected, clear=True):
            passed, output, reason = verify.run_test([sys.executable, '-c', code], self.checkout, 5)
            self.assertEqual(os.environ['TYPESAFE_API_KEY'], 'synthetic-key')
            self.assertEqual(os.environ['GIT_DIR'], '/synthetic/git')
        self.assertTrue(passed, (output, reason))

    def test_record_git_receives_only_allowlisted_environment(self):
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        executable = bin_dir / 'git'
        executable.write_text(f'#!{sys.executable}\nimport json, os\n'
                              'print(json.dumps({"keys": sorted(os.environ), '
                              '"PATH": os.environ.get("PATH"), "LANG": os.environ.get("LANG"), '
                              '"TMPDIR": os.environ.get("TMPDIR")}))\n')
        executable.chmod(0o700)
        injected = {'PATH': str(bin_dir), 'LANG': 'C', 'TMPDIR': str(self.root),
                    'HOME': str(self.home), 'TYPESAFE_API_KEY': 'synthetic-key',
                    'AWS_SECRET_ACCESS_KEY': 'synthetic-secret', 'GIT_CONFIG_COUNT': '1',
                    'VERIFY_TEST_MARKER': 'must-not-inherit'}
        with mock.patch.dict(os.environ, injected, clear=True):
            child = json.loads(verify.record.git(self.checkout, 'status'))
            self.assertEqual(os.environ['TYPESAFE_API_KEY'], 'synthetic-key')
        for name in ('HOME', 'TYPESAFE_API_KEY', 'AWS_SECRET_ACCESS_KEY', 'VERIFY_TEST_MARKER'):
            self.assertNotIn(name, child['keys'])
        self.assertFalse(any(k.startswith('GIT_') for k in child['keys']))
        self.assertEqual(child['PATH'], str(bin_dir))
        self.assertEqual(child['LANG'], 'C')
        self.assertEqual(child['TMPDIR'], str(self.root))

    def test_configured_fsmonitor_never_runs_before_or_after_tests(self):
        marker = self.root / 'fsmonitor-ran'
        monitor = self.root / 'fsmonitor'
        monitor.write_text(f'#!{sys.executable}\nimport os\nfrom pathlib import Path\n'
                           f'Path({str(marker)!r}).write_text(os.environ.get("TYPESAFE_API_KEY", "no-key"))\n')
        monitor.chmod(0o700)
        for configured_by_test in (False, True):
            with self.subTest(configured_by_test=configured_by_test):
                marker.unlink(missing_ok=True)
                if configured_by_test:
                    self.git('config', '--unset', 'core.fsmonitor')
                    code = ('import subprocess; '
                            f'subprocess.run(["git", "config", "core.fsmonitor", {str(monitor)!r}], check=True)')
                    self.brief['tests'] = [[sys.executable, '-c', code]]
                else:
                    self.git('config', 'core.fsmonitor', str(monitor))
                with mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key',
                                                 'PATH': os.defpath, 'TMPDIR': str(self.root)}, clear=True), \
                        mock.patch.object(verify.judge, 'ask_jev', side_effect=verify.judge.Unavailable):
                    passed, _ = self.run_verify(source='jev')
                self.assertTrue(passed, self.output.getvalue())
                self.assertFalse(marker.exists(), 'fsmonitor executed with coordinator environment')
                self.assertEqual(self.receipt()['mechanical'], 'passed')

    def test_record_git_disables_checkout_hooks(self):
        marker = self.root / 'hook-ran'
        hooks = self.root / 'hooks'
        hooks.mkdir()
        hook = hooks / 'pre-commit'
        hook.write_text(f'#!{sys.executable}\nfrom pathlib import Path\n'
                        f'Path({str(marker)!r}).touch()\n')
        hook.chmod(0o700)
        self.git('config', 'core.hooksPath', str(hooks))
        verify.record.git(self.checkout, 'commit', '--allow-empty', '-qm', 'Check disabled hooks')
        self.assertFalse(marker.exists())
        self.assertNotEqual(verify.record.current_head(self.checkout), self.head)

    def test_invalid_utf8_document_records_insufficient_without_judging(self):
        (self.checkout / 'target.txt').write_bytes(b'guard\xff\n')
        self.git('commit', '-qam', 'Add invalid UTF-8 document')
        self.head = self.git('rev-parse', 'HEAD')
        self.brief['criteria'] = [{'id': 'C1', 'documents': [
            {'path': 'target.txt', 'question': 'The document describes the guard.'},
            {'path': 'target.txt', 'question': 'The document describes the guard.'}]}]
        with mock.patch.object(verify, 'ask', side_effect=AssertionError('must not judge invalid UTF-8')):
            passed, requests = self.run_verify(source='jev')
        self.assertFalse(passed)
        self.assertEqual(requests, {})
        receipt = self.receipt()
        self.assertEqual(receipt['tests'], 'passed')
        self.assertEqual(receipt['mechanical'], 'failed')
        self.assertEqual([c['answer'] for c in receipt['criteria']], ['insufficient'] * 3)
        brief = self.root / 'brief.json'
        brief.write_text(json.dumps(self.brief))
        for script in (SCRIPTS / 'verify_claim.py', ROOT / 'skills/fnl-verification/scripts/verify_claim.py'):
            with self.subTest(script=script):
                done = subprocess.run([sys.executable, '-I', str(script), '--brief', str(brief),
                                       '--base', self.base, '--head', self.head, '--ledger-id', self.dispatch,
                                       '--checkout', str(self.checkout), '--judge', 'host'],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertEqual(self.receipt()['mechanical'], 'failed')
                self.assertEqual([c['answer'] for c in self.receipt()['criteria']], ['insufficient'] * 3)

    def test_record_git_ignores_inherited_repository_and_config_overrides(self):
        other = self.root / 'other'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        expected_id = verify.record.checkout_identity(self.checkout)
        injected = {'GIT_DIR': str(other / '.git'), 'GIT_WORK_TREE': str(other),
                    'GIT_INDEX_FILE': str(other / 'index'),
                    'GIT_OBJECT_DIRECTORY': str(other / '.git/objects'),
                    'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.bare',
                    'GIT_CONFIG_VALUE_0': 'true'}
        with mock.patch.dict(os.environ, injected):
            self.assertEqual(verify.record.checkout_identity(self.checkout), expected_id)
            self.assertEqual(verify.record.current_head(self.checkout), self.head)
            self.assertEqual(verify.record.git(self.checkout, 'rev-parse', '--is-bare-repository'), 'false')

    def test_oversized_combined_evidence_records_failure_without_judging(self):
        for text, count in [('a' * 34000, 2), ('a' * 65500, 1), ('\u1ebf' * 11000, 2)]:
            with self.subTest(size=len(text.encode()), count=count):
                self.brief['tests'] = [[sys.executable, '-c', f'print({text!r})']] * count
                with mock.patch.object(verify, 'ask', side_effect=AssertionError('must not judge incomplete evidence')):
                    passed, requests = self.run_verify(source='jev')
                self.assertFalse(passed)
                self.assertEqual(requests, {})
                receipt = self.receipt()
                self.assertEqual(receipt['tests'], 'passed')
                self.assertEqual(receipt['mechanical'], 'failed')
                self.assertEqual(receipt['criteria'][0]['answer'], 'insufficient')
                self.assertNotIn(text, json.dumps(receipt))

    def test_oversized_committed_document_is_not_loaded_or_judged(self):
        (self.checkout / 'target.txt').write_text('\u1ebf' * 22000)
        self.git('commit', '-qam', 'Add oversized document')
        self.head = self.git('rev-parse', 'HEAD')
        self.brief['criteria'] = [{'id': 'C1', 'documents': [
            {'path': 'target.txt', 'question': 'The document describes the guard.'},
            {'path': 'target.txt', 'question': 'The document describes the guard.'}]}]
        original_git = verify.record.git

        def git(checkout, *args):
            self.assertNotEqual(args[0], 'show', 'oversized blob must not be loaded')
            return original_git(checkout, *args)

        with mock.patch.object(verify.record, 'git', side_effect=git), \
                mock.patch.object(verify, 'ask', side_effect=AssertionError('must not judge oversized document')):
            passed, requests = self.run_verify(source='jev')
        self.assertFalse(passed)
        self.assertEqual(requests, {})
        receipt = self.receipt()
        self.assertEqual(receipt['tests'], 'passed')
        self.assertEqual(receipt['mechanical'], 'failed')
        self.assertEqual([c['answer'] for c in receipt['criteria']], ['insufficient'] * 3)

    def test_json_brief_refuses_shell_full_suite_and_bad_shape(self):
        path = self.root / 'brief.json'
        for tests in [[['sh', '-c', 'test true']], [['python3', '-m', 'unittest', 'discover']], ['python3 test.py'], []]:
            with self.subTest(tests=tests):
                path.write_text(json.dumps({**self.brief, 'tests': tests}))
                with self.assertRaises(ValueError):
                    verify.load_brief(path)
        path.write_text(json.dumps(self.brief))
        self.assertEqual(verify.load_brief(path), self.brief)

    def test_bad_receipt_metadata_and_symlink_storage_are_refused(self):
        record = verify.record
        with self.assertRaises(ValueError):
            record.write_verification(self.dispatch, self.head, 'passed', 'passed',
                [dict(id='criterion text', answer='yes', source='host', fallback=False)], self.checkout)
        state = self.home / '.finolabs/vibecode/state'
        state.mkdir(parents=True)
        (state / 'verification').symlink_to(self.root)
        with self.assertRaises(OSError):
            self.run_verify()

    def test_complete_host_uses_exact_saved_run_and_keeps_fallback(self):
        with mock.patch.object(verify.judge, 'ask_jev', side_effect=verify.judge.Unavailable):
            passed, requests = self.run_verify(source='jev')
        packet = requests['C1']
        answer = {key: packet[key] for key in ('question', 'evidence_sha256')}
        answer.update(answer='yes', quote='one test passed')
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output), \
                mock.patch.object(verify, 'run_test', side_effect=AssertionError('must not rerun')):
            self.assertTrue(verify.complete_host(requests, {'C1': answer}, self.dispatch, self.head, self.checkout))
        self.assertEqual(self.receipt()['criteria'][0]['answer'], 'yes')
        self.assertTrue(self.receipt()['criteria'][0]['fallback'])
        requests['C1']['evidence'] = 'tampered'
        with self.assertRaises(ValueError):
            verify.complete_host(requests, {'C1': answer}, self.dispatch, self.head, self.checkout)

    def test_host_yes_never_replaces_failed_mechanics(self):
        self.brief['scope'] = ['other.txt']
        with mock.patch.object(verify, 'ask', return_value=dict(id='C1', answer='yes', source='host', fallback=False)):
            passed, _ = self.run_verify()
        self.assertFalse(passed)
        self.assertEqual(self.receipt()['mechanical'], 'failed')
        self.assertEqual(self.receipt()['criteria'][0]['answer'], 'yes')

    def test_packet_is_atomic_private_and_never_overwrites(self):
        packet = self.root / 'packet.json'
        verify.write_packet(packet, {'C1': {'evidence': 'data'}})
        before = packet.read_bytes()
        with self.assertRaises(FileExistsError):
            verify.write_packet(packet, {'C1': {'evidence': 'other'}})
        self.assertEqual(packet.read_bytes(), before)
        self.assertEqual(packet.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.root.glob('.verify-*')), [])

    def test_cli_host_two_phase_and_standalone_copies(self):
        brief = self.root / 'brief.json'
        brief.write_text(json.dumps(self.brief))
        requests = self.root / 'requests.json'
        command = [sys.executable, '-I', str(ROOT / 'skills/fnl-verification/scripts/verify_claim.py'),
                   '--brief', str(brief), '--base', self.base, '--head', self.head,
                   '--ledger-id', self.dispatch, '--checkout', str(self.checkout),
                   '--judge', 'host', '--requests-out', str(requests)]
        done = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(requests.stat().st_mode & 0o777, 0o600)
        packets = json.loads(requests.read_text())
        packet = packets['C1']
        answers = self.root / 'answers.json'
        answers.write_text(json.dumps({'C1': dict(answer='yes', quote='one test passed',
                           question=packet['question'], evidence_sha256=packet['evidence_sha256'])}))
        done = subprocess.run([sys.executable, '-I', str(SCRIPTS / 'verify_claim.py'),
                    '--complete-host', str(requests), '--host-answers', str(answers),
                    '--head', self.head, '--ledger-id', self.dispatch, '--checkout', str(self.checkout)],
                    capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.receipt()['criteria'][0]['answer'], 'yes')
        for name, skills in [('judge.py', ['fnl-delegate', 'fnl-verification', 'fnl-session-hygiene']),
                             ('verify_claim.py', ['fnl-verification'])]:
            for skill in skills:
                self.assertEqual((ROOT / 'skills' / skill / 'scripts' / name).read_bytes(),
                                 (SCRIPTS / name).read_bytes())

    def test_record_cli_and_copies(self):
        metadata = self.root / 'criteria.json'
        metadata.write_text('[]')
        for path in [SCRIPTS / 'record.py', ROOT / 'skills/fnl-verification/scripts/record.py',
                     ROOT / 'skills/fnl-delegate/scripts/record.py', ROOT / 'skills/fnl-coding-router/scripts/record.py']:
            self.assertEqual(path.read_bytes(), (SCRIPTS / 'record.py').read_bytes())
            done = subprocess.run([sys.executable, '-I', str(path), 'verify', '--id', self.dispatch,
                                   '--head', self.head, '--tests', 'passed', '--mechanical', 'passed',
                                   '--checkout', str(self.checkout), '--criteria-file', str(metadata)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
        metadata.write_text('[{"question":"private"}]')
        done = subprocess.run([sys.executable, '-I', str(SCRIPTS / 'record.py'), 'verify', '--id', self.dispatch,
                               '--head', self.head, '--tests', 'passed', '--mechanical', 'passed',
                               '--checkout', str(self.checkout), '--criteria-file', str(metadata)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertNotIn('private', done.stderr)


if __name__ == '__main__':
    unittest.main()
