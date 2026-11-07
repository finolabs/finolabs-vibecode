"""Offline judge contract tests; provider traffic is confined to loopback."""
import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_judge', ROOT / 'scripts/judge.py')
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / 'home')

    def test_host_quotes_are_verbatim_and_nonempty(self):
        for quote, expected in [('added guard', 'yes'), ('guard added', 'insufficient'),
                                ('', 'insufficient'), (' ', 'insufficient'), (None, 'insufficient')]:
            with self.subTest(quote=quote):
                out = judge.check_host(dict(answer='yes', quote=quote), '+ added guard\n')
                self.assertEqual(out['answer'], expected)
                self.assertEqual(out['quote_ok'], expected == 'yes')
                self.assertIsNone(out['p'])
        for answer in ('no', 'insufficient'):
            self.assertEqual(judge.check_host(dict(answer=answer), '')['answer'], answer)

    def test_host_rejects_wrong_schema_and_stale_bindings(self):
        for value in ([], {}, dict(answer='maybe'), dict(answer='yes', extra=True)):
            with self.assertRaises(ValueError):
                judge.check_host(value, '')
        packet = dict(answer='yes', quote='guard', evidence_sha256=hashlib.sha256(b'guard').hexdigest(), question='Q')
        self.assertEqual(judge.check_host(packet, 'guard', 'Q')['answer'], 'yes')
        self.assertEqual(judge.check_host(packet, 'guard changed', 'Q')['answer'], 'insufficient')
        self.assertEqual(judge.check_host(packet, 'guard', 'other')['answer'], 'insufficient')

    def test_absent_and_malformed_judge_configuration_default_to_host(self):
        self.assertEqual(judge.configured_judge(), 'host')
        path = self.home / '.finolabs/vibecode/host.md'
        path.parent.mkdir(parents=True)
        for text, expected in [('## Agent roles\n- judge: jev\n', 'jev'),
                               ('## Agent roles\n- navigator: codex\n', 'host'),
                               ('## Agent roles\n- judge: jev\n- judge: host\n', 'host'),
                               ('## Agent roles\n- judge: invalid\n', 'host'),
                               ('## Agent roles\n- judge: jev\n- code review: codex\n', 'host'),
                               ('## Agents on this machine\n| Codex | yes | synthetic |\n\n## Agent roles\n- judge: jev\n- code review: codex\n', 'jev')]:
            path.write_text(text)
            self.assertEqual(judge.configured_judge(), expected)

    @contextlib.contextmanager
    def server(self, response, status=200, headers=None):
        received = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(inner):
                received.append(json.loads(inner.rfile.read(int(inner.headers['Content-Length']))))
                inner.send_response(status)
                for key, value in (headers or {}).items():
                    inner.send_header(key, value)
                inner.end_headers()
                inner.wfile.write(json.dumps(response).encode())
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-test-key'}):
                yield f'http://127.0.0.1:{server.server_port}/v1/systemone', received
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_same_known_cases_with_both_judges(self):
        # Synthetic fixture agreement is not validation over independent merged PRs.
        cases = [('The guard was added.', '+ added guard', .9, 'yes', 'added guard'),
                 ('The guard was added.', '- removed guard', .1, 'no', ''),
                 ('The guard was added.', 'summary only', .5, 'insufficient', '')]
        for question, evidence, p, expected, quote in cases:
            with self.subTest(expected=expected), self.server({'answers': {'q': {'noul': p}}}) as (url, seen):
                remote = judge.ask_jev(question, evidence, base_url=url)
                local = judge.check_host(dict(answer=expected, quote=quote), evidence)
                self.assertEqual(remote['answer'], expected)
                self.assertEqual(local['answer'], expected)
                self.assertEqual(remote['p'], p)
                self.assertEqual(seen[0]['state'], dict(evidence=evidence))
                self.assertEqual(seen[0]['questions']['q']['type'], 'noul')
                self.assertNotIn('synthetic-test-key', json.dumps(seen))

    def test_errors_probabilities_redirects_are_unavailable(self):
        for response, status in [({}, 200), ({'answers': {'q': {'noul': True}}}, 200),
                                 ({'answers': {'q': {'noul': 2}}}, 200),
                                 ({'answers': {'q': {'noul': float('nan')}}}, 200), ({}, 500), ({}, 302)]:
            with self.subTest(response=response, status=status), self.server(response, status, {'Location': 'https://example.com'}) as (url, _):
                with self.assertRaises(judge.Unavailable):
                    judge.ask_jev('Q', 'E', base_url=url)
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch('urllib.request.build_opener') as opener:
            with self.assertRaises(judge.Unavailable):
                judge.ask_jev('Q', 'E')
            opener.assert_not_called()

    def test_validation_harness_uses_identical_cases_and_records_agreement(self):
        cases = [dict(id='case1', question='A guard was added.', evidence='added guard', expected='yes'),
                 dict(id='case2', question='A guard was added.', evidence='removed guard', expected='no')]
        answers = {'case1': dict(answer='yes', quote='added guard'), 'case2': dict(answer='no')}
        local = judge.validate_cases(cases, 'host', answers)
        with mock.patch.object(judge, 'ask_jev') as client:
            client.side_effect = [judge.result('yes', 'jev', .9), judge.result('no', 'jev', .1)]
            remote = judge.validate_cases(cases, 'jev', {}, client=client)
        self.assertEqual(local['counts'], remote['counts'])
        self.assertEqual(local['counts'], dict(agree=2, insufficient=0, wrong=0))
        self.assertEqual(local['validation'], 'unvalidated')
        answers['case1']['quote'] = 'missing'
        self.assertEqual(judge.validate_cases(cases, 'host', answers)['counts']['insufficient'], 1)
        with self.assertRaises(ValueError):
            judge.validate_cases(cases * 2, 'host', answers)

    def test_cli_host_check_dry_run_and_unavailable_are_bounded(self):
        evidence = Path(self.tmp.name) / 'evidence'
        evidence.write_text('added guard')
        answers = Path(self.tmp.name) / 'answers.json'
        answers.write_text(json.dumps(dict(answer='yes', quote='added guard')))
        def run(*args):
            return subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/judge.py'), *args], capture_output=True, text=True)
        checked = run('check-host', '--answers', str(answers), '--evidence-file', str(evidence))
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)['answer'], 'yes')
        dry = run('ask', '--question', 'Sensitive question', '--evidence-file', str(evidence), '--dry-run')
        self.assertEqual(dry.returncode, 0)
        self.assertEqual(set(json.loads(dry.stdout)['fields']), {'model', 'state', 'questions'})
        self.assertNotIn('Sensitive', dry.stdout)
        unavailable = run('ask', '--question', 'Q', '--evidence-file', str(evidence), '--judge', 'host')
        self.assertEqual(unavailable.returncode, 3)
        self.assertEqual(json.loads(unavailable.stdout)['answer'], 'insufficient')
        self.assertIn('unavailable', unavailable.stderr)


if __name__ == '__main__':
    unittest.main()
