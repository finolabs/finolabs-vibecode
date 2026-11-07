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
