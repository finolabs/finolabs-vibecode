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
import ssl
import urllib.error
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
        judge._calls = 0
        clean = mock.patch.dict(os.environ, {}, clear=True)
        clean.start()
        self.addCleanup(clean.stop)

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
        packet = dict(answer='yes', quote='added guard', evidence_sha256=hashlib.sha256(b'added guard').hexdigest(), question='Q')
        self.assertEqual(judge.check_host(packet, 'added guard', 'Q')['answer'], 'yes')
        self.assertEqual(judge.check_host(packet, 'guard changed', 'Q')['answer'], 'insufficient')
        self.assertEqual(judge.check_host(packet, 'added guard', 'other')['answer'], 'insufficient')

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

    def test_assignment_matrix_states_decide_the_judge(self):
        path = self.home / '.finolabs/vibecode/host.md'
        path.parent.mkdir(parents=True)
        matrix = '## Assignment matrix\n\n- Consent: yes (2026-11-09)\n- Judge: %s\n- codex: levels 1-5; roles code-review\n'
        legacy_jev = '## Agent roles\n- judge: jev\n\n'
        legacy_host = '## Agent roles\n- judge: host\n\n'
        cases = [
            ('absent, fenced example only', '```md\n' + matrix % 'host' + '```\n\n' + legacy_jev, 'jev'),
            ('valid jev over legacy host', legacy_host + matrix % 'jev', 'jev'),
            ('valid host over legacy jev', legacy_jev + matrix % 'host', 'host'),
            ('invalid matrix, valid legacy', legacy_jev + matrix % 'jev' + '- gemini: levels 1-2\n', 'host'),
            ('duplicate matrix', legacy_jev + matrix % 'jev' + matrix % 'jev', 'host'),
            ('no consent', legacy_jev + '## Assignment matrix\n- Consent: no\n- Judge: host\n', 'host'),
            ('consent missing', legacy_jev + (matrix % 'jev').replace('- Consent: yes (2026-11-09)\n', ''), 'host'),
        ]
        with mock.patch('urllib.request.build_opener') as opener:
            for name, text, expected in cases:
                with self.subTest(name=name):
                    path.write_text(text)
                    self.assertEqual(judge.configured_judge(), expected)
        opener.assert_not_called()

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
            with mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-test-key'}, clear=True), \
                    mock.patch.object(judge, 'configured_judge', return_value='jev'):
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

    def test_the_documented_noul_reply_shape_is_accepted(self):
        reply = {'model': 'jev-latest', 'usage': {'input_tokens': 1, 'output_tokens': 1}, 'answers': {'q': {'type': 'noul', 'noul': .9}}}
        with self.server(reply) as (url, seen):
            self.assertEqual(judge.ask_jev('Q?', 'E', base_url=url)['p'], .9)

    def test_errors_probabilities_redirects_are_unavailable(self):
        for response, status in [({}, 200), ({'answers': {'q': {'noul': True}}}, 200),
                                 ({'answers': {'q': {'noul': 2}}}, 200),
                                 ({'answers': {'q': {'noul': float('nan')}}}, 200),
                                 ({'answers': {'q': {'noul': .9, 'extra': True}}}, 200),
                                 ({'answers': {'q': {'noul': .9}}, 'extra': True}, 200),
                                 ({}, 401), ({}, 429), ({}, 500), ({}, 302)]:
            with self.subTest(response=response, status=status), self.server(response, status, {'Location': 'http://127.0.0.1:1/never'}) as (url, _):
                with self.assertRaises(judge.Unavailable):
                    judge.ask_jev('Q', 'E', base_url=url)
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(judge, 'configured_judge', return_value='jev'), \
                mock.patch('urllib.request.build_opener') as opener:
            with self.assertRaises(judge.Unavailable):
                judge.ask_jev('Q', 'E')
            opener.assert_not_called()

    def test_redirect_never_reaches_another_loopback_server(self):
        with self.server({'answers': {'q': {'noul': .9}}}) as (target, target_seen):
            with self.server({}, 302, {'Location': target}) as (source, source_seen):
                with self.assertRaises(judge.Unavailable):
                    judge.ask_jev('Q', 'E', base_url=source)
                self.assertEqual(len(source_seen), 1)
                self.assertEqual(target_seen, [])

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

    def test_short_and_punctuation_quotes_do_not_support_yes(self):
        for quote in ('guard', 'a', '        ', '...........', ' a.....b ', 'abcdefg'):
            with self.subTest(length=len(quote)):
                self.assertEqual(judge.check_host(dict(answer='yes', quote=quote), quote)['answer'], 'insufficient')
        self.assertEqual(judge.check_host(dict(answer='yes', quote='abcdefgh'), 'abcdefgh')['answer'], 'yes')

    def test_closed_site_schemas_and_utf8_field_and_body_caps(self):
        for site, schema in judge.SITE_SCHEMAS.items():
            with self.subTest(site=site):
                judge.payload('The guard was added.', 'added guard', site)
                for fields in ({'question': 'Q', 'evidence': 'E', 'extra': 'x'}, {'question': 'Q'}):
                    with self.assertRaises(judge.Unavailable):
                        judge.site_fields(site, fields)
                for name, cap in schema.items():
                    fields = dict(question='Q', evidence='E')
                    fields[name] = 'é' * (cap // 2 + 1)
                    with self.assertRaises(judge.Unavailable):
                        judge.site_fields(site, fields)
        judge.payload('The guard was added.', json.dumps({'head': 'a' * 40}))
        for site in ('unknown', 'instructions', ''):
            with self.assertRaises(judge.Unavailable):
                judge.payload('Q', 'E', site)
        # Escaping can overflow the body even when each input field fits.
        with self.assertRaises(judge.Unavailable):
            judge.payload('Q', '\x01' * 12000)

    def test_sensitive_payload_refuses_before_send_and_names_only_field(self):
        secrets = ('sk-' + 'x' * 24, 'password=synthetic-password',
                   'ghp_' + 's' * 30, '-----BEGIN PRIVATE KEY-----',
                   'https://person:synthetic-pass@example.com')
        paths = ('/Us' + 'ers/synthetic/private', '/ho' + 'me/synthetic/private',
                 'C:' + chr(92) + 'Us' + 'ers' + chr(92) + 'synthetic' + chr(92) + 'private', '~/private', '/root/private')
        with mock.patch.object(judge, 'configured_judge', return_value='jev'), \
                mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True), \
                mock.patch('urllib.request.build_opener') as opener:
            for site in judge.SITE_SCHEMAS:
                for field in ('question', 'evidence'):
                    for value in (*secrets, *paths, 'synthetic-key'):
                        fields = dict(question='Q', evidence='E')
                        fields[field] = value
                        with self.assertRaises(judge.Unavailable) as raised:
                            judge.ask_jev(**fields, site=site)
                        self.assertEqual(str(raised.exception), 'field: ' + field)
            opener.assert_not_called()

    def test_only_literal_loopback_http_override_and_never_environment(self):
        for url in ('http://127.0.0.1.evil.com', 'http://localhost', 'http://192.0.2.1',
                    'https://127.0.0.1', 'http://user:pass@127.0.0.1',
                    'http://127.0.0.1/?key=value', 'http://127.0.0.1/#fragment', 'http://[::1%lo0]'):
            with self.subTest(url=url), mock.patch.object(judge, 'configured_judge', return_value='jev'), \
                    mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True), \
                    mock.patch('urllib.request.build_opener') as factory:
                with self.assertRaises(judge.Unavailable):
                    judge.ask_jev('Q', 'E', base_url=url)
                factory.assert_not_called()
        self.assertEqual(judge.endpoint('http://[::1]:1234/v1/systemone'), 'http://[::1]:1234/v1/systemone')
        with mock.patch.object(judge, 'configured_judge', return_value='jev'), \
                mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key',
                    'FNL_JUDGE_BASE_URL': 'http://127.0.0.1:1', 'TYPESAFE_BASE_URL': 'http://127.0.0.1:1'}, clear=True), \
                mock.patch('urllib.request.build_opener') as factory:
            factory.return_value.open.side_effect = OSError('synthetic failure')
            with self.assertRaises(judge.Unavailable):
                judge.ask_jev('Q', 'E')
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, judge.ENDPOINT)
            self.assertEqual(factory.return_value.open.call_args.kwargs['timeout'], 15)

    def test_canonical_opt_in_disable_unresolved_and_invalid_pointer(self):
        host = self.home / '.finolabs/vibecode/host.md'
        host.parent.mkdir(parents=True)
        host.write_text('## Agent roles\n- judge: jev\n')
        self.assertEqual(judge.configured_judge(), 'jev')
        with mock.patch.dict(os.environ, {'FNL_JUDGE': 'off', 'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True), \
                mock.patch('urllib.request.build_opener') as opener:
            self.assertEqual(judge.configured_judge(), 'host')
            with self.assertRaises(judge.Unavailable):
                judge.ask_jev('Q', 'E')
            opener.assert_not_called()
        (host.parent / 'root.json').write_text('{"root":"relative","id":"invalid"}')
        self.assertEqual(judge.configured_judge(), 'host')
        (host.parent / 'root.json').unlink()
        with mock.patch('data_root.read_data', side_effect=KeyError('unresolved')):
            self.assertEqual(judge.configured_judge(), 'host')
        with mock.patch('data_root.account_home', side_effect=ValueError('unresolved')):
            self.assertEqual(judge.configured_judge(), 'host')
        host.unlink()
        outside = Path(self.tmp.name) / 'other-host.md'
        outside.write_text('## Agent roles\n- judge: jev\n')
        with mock.patch.dict(os.environ, {'ORCHESTRATION_HOST_CONFIG': str(outside),
                'FNL_JUDGE': 'jev', 'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True), \
                mock.patch('urllib.request.build_opener') as opener:
            self.assertEqual(judge.configured_judge(), 'host')
            with self.assertRaises(judge.Unavailable):
                judge.ask_jev('Q', 'E')
            opener.assert_not_called()

    def test_call_cap_counts_failed_attempts(self):
        with mock.patch.object(judge, 'configured_judge', return_value='jev'), \
                mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True), \
                mock.patch('urllib.request.build_opener') as factory:
            factory.return_value.open.side_effect = TimeoutError()
            for _ in range(judge.MAX_CALLS):
                with self.assertRaises(judge.Unavailable):
                    judge.ask_jev('Q', 'E')
            with self.assertRaisesRegex(judge.Unavailable, '^call cap$'):
                judge.ask_jev('Q', 'E')
            self.assertEqual(factory.return_value.open.call_count, 24)

    def test_transport_ignores_overrides_verifies_tls_and_never_exposes_key(self):
        synthetic = {'TYPESAFE_API_KEY': 'synthetic-header-only-key', 'HTTPS_PROXY': 'http://127.0.0.1:1',
            'HTTP_PROXY': 'http://127.0.0.1:1', 'ALL_PROXY': 'http://127.0.0.1:1',
            'https_proxy': 'http://127.0.0.1:1', 'SSL_CERT_FILE': '/synthetic/cert',
            'SSL_CERT_DIR': '/synthetic/certs', 'REQUESTS_CA_BUNDLE': '/synthetic/cert',
            'CURL_CA_BUNDLE': '/synthetic/cert', 'PYTHONHTTPSVERIFY': '0'}
        with mock.patch.dict(os.environ, synthetic, clear=True), \
                mock.patch.object(judge, 'configured_judge', return_value='jev'), \
                mock.patch('urllib.request.build_opener') as factory:
            factory.return_value.open.side_effect = OSError(synthetic['TYPESAFE_API_KEY'])
            with self.assertRaises(judge.Unavailable) as raised:
                judge.ask_jev('Q', 'E')
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer ' + synthetic['TYPESAFE_API_KEY'])
            for value in (request.full_url, request.data.decode(), str(raised.exception), str(sys.argv)):
                self.assertNotIn(synthetic['TYPESAFE_API_KEY'], value)
            handlers = factory.call_args.args
            self.assertEqual(handlers[0].proxies, {})
            self.assertIsInstance(handlers[1], judge.NoRedirect)
            context = handlers[2]._context
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
        # Prove trust loading selects compiled paths rather than override paths.
        with mock.patch.dict(os.environ, synthetic, clear=True), \
                mock.patch.object(ssl.SSLContext, 'load_verify_locations') as load:
            judge.tls_context()
            locations = load.call_args.kwargs
            self.assertNotIn('/synthetic/cert', locations.values())
            self.assertNotIn('/synthetic/certs', locations.values())

    def test_reply_byte_cap_and_duplicate_keys_fall_back(self):
        for raw in (b'x' * (judge.LIMIT + 1), b'[' * 2000 + b'0' + b']' * 2000,
                    b'{"answers":{"q":{"noul":0.9,"noul":0.1}}}'):
            with mock.patch.object(judge, 'configured_judge', return_value='jev'), \
                    mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True), \
                    mock.patch('urllib.request.build_opener') as factory:
                response = factory.return_value.open.return_value.__enter__.return_value
                response.read.return_value = raw
                with self.assertRaises(judge.Unavailable):
                    judge.ask_jev('Q', 'E')
                response.read.assert_called_once_with(judge.LIMIT + 1)

    def test_harness_refusal_falls_back_to_the_same_host_cases(self):
        cases = [dict(id='case1', question='The guard was added.', evidence='added guard', expected='yes')]
        answers = {'case1': dict(answer='yes', quote='added guard')}
        with mock.patch.object(judge, 'ask_jev', side_effect=judge.Unavailable('provider failure')) as client:
            report = judge.validate_cases(cases, 'jev', answers, client=client)
        self.assertEqual(report['source'], 'host')
        self.assertEqual(report['requested_source'], 'jev')
        self.assertTrue(report['fallback'])
        self.assertEqual(report['cases'][0]['source'], 'host')
        self.assertTrue(report['cases'][0]['fallback'])
        self.assertEqual(report['counts']['agree'], 1)
        self.assertEqual(client.call_args.args, ('The guard was added.', 'added guard'))


    def test_cli_loopback_flag_and_failure_host_fallback(self):
        host = self.home / '.finolabs/vibecode/host.md'
        host.parent.mkdir(parents=True)
        host.write_text('## Agent roles\n- judge: jev\n')
        evidence = Path(self.tmp.name) / 'cli-evidence'
        evidence.write_text('added guard')
        answers = Path(self.tmp.name) / 'cli-answers'
        answers.write_text(json.dumps(dict(answer='yes', quote='added guard')))
        with self.server({'answers': {'q': {'noul': .9}}}) as (url, seen):
            argv = ['judge.py', 'ask', '--question', 'The guard was added.', '--evidence-file', str(evidence), '--base-url', url]
            with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(judge.main(), 0)
            self.assertEqual(json.loads(output.getvalue())['source'], 'jev')
            self.assertEqual(len(seen), 1)
        failures = (TimeoutError(), urllib.error.HTTPError(judge.ENDPOINT, 401, 'refused', {}, None),
                    urllib.error.HTTPError(judge.ENDPOINT, 429, 'limited', {}, None),
                    urllib.error.URLError('DNS failure'), ssl.SSLError('TLS failure'), ValueError('invalid reply'))
        for error in failures:
            argv = ['judge.py', 'ask', '--question', 'Q', '--evidence-file', str(evidence), '--judge', 'jev', '--answers', str(answers)]
            with mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-header-only-key'}, clear=True), \
                    mock.patch('urllib.request.build_opener') as factory, \
                    mock.patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as errors:
                factory.return_value.open.side_effect = error
                self.assertEqual(judge.main(), 0)
                out = json.loads(output.getvalue())
                self.assertEqual((out['source'], out['answer'], out['fallback']), ('host', 'yes', True))
                self.assertIn('host judge', errors.getvalue())
                for value in (output.getvalue(), errors.getvalue(), str(argv)):
                    self.assertNotIn('synthetic-header-only-key', value)
        # Missing key also produces the same explicit fallback result.
        with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()) as output, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(judge.main(), 0)
            self.assertTrue(json.loads(output.getvalue())['fallback'])


class AwayDecisionSiteTest(unittest.TestCase):
    """Away decisions: the closed `away-decision` site chooses among two to six options; no network."""
    OPTIONS = ['Keep one schema', 'Split the schema']

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / 'home')
        judge._calls = 0
        clean = mock.patch.dict(os.environ, {}, clear=True)
        clean.start()
        self.addCleanup(clean.stop)

    def jev(self, reply):
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(judge, 'configured_judge', return_value='jev'))
        stack.enter_context(mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True))
        factory = stack.enter_context(mock.patch('urllib.request.build_opener'))
        response = factory.return_value.open.return_value.__enter__.return_value
        response.read.return_value = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
        self.addCleanup(stack.close)
        return factory

    def test_site_is_closed_and_separate_from_the_yes_no_sites(self):
        self.assertNotIn('away-decision', judge.SITE_SCHEMAS)
        self.assertEqual(set(judge.CHOICE_SITES), {'away-decision'})
        self.assertEqual(set(judge.CHOICE_SITES['away-decision']), {'question', 'options', 'evidence'})
        body = judge.choice_payload('Which schema fits the spec?', self.OPTIONS, 'The spec asks for one table.')
        self.assertEqual(body['questions']['q']['type'], 'choice')
        self.assertEqual(body['questions']['q']['criteria'], {'1': 'Keep one schema', '2': 'Split the schema'})
        self.assertEqual(set(body['questions']['q']), {'type', 'instructions', 'criteria'})
        self.assertEqual(body['state'], {'evidence': 'The spec asks for one table.'})
        # The yes/no payload never serves the choice site, and the choice payload never serves a yes/no site.
        with self.assertRaises(judge.Unavailable):
            judge.payload('Q', 'E', 'away-decision')
        for site in ('verification', 'navigator', 'unknown', ''):
            with self.assertRaises(judge.Unavailable):
                judge.choice_payload('Q', self.OPTIONS, 'E', site)

    def test_option_count_type_duplicates_and_byte_caps_refuse(self):
        caps = judge.CHOICE_SITES['away-decision']
        _, _, option_cap = caps['options']
        for options in ([], ['Only one'], ['o%d' % n for n in range(7)], ['Same', 'Same'], ['Fine', ''],
                        ['Fine', '   '], ['Fine', 7], 'Keep, Split', ['Fine', 'é' * (option_cap // 2 + 1)]):
            with self.subTest(options=str(options)[:40]):
                with self.assertRaises(judge.Unavailable):
                    judge.choice_payload('Which?', options, 'E')
        for count in (2, 6):
            judge.choice_payload('Which?', ['o%d' % n for n in range(count)], 'E')
        for name in ('question', 'evidence'):
            fields = dict(question='Which?', evidence='E')
            fields[name] = 'é' * (caps[name] // 2 + 1)
            with self.assertRaises(judge.Unavailable):
                judge.choice_payload(fields['question'], self.OPTIONS, fields['evidence'])
        with self.assertRaises(judge.Unavailable):
            judge.choice_payload('   ', self.OPTIONS, 'E')

    def test_secret_and_path_patterns_refuse_before_send_and_name_only_the_field(self):
        values = ('sk-' + 'x' * 24, 'password=synthetic-password', '/Us' + 'ers/synthetic/private', '~/private', 'synthetic-key')
        factory = self.jev({'answers': {'q': {'choice': '1', 'probabilities': {'1': .9, '2': .1}}}})
        for field in ('question', 'options', 'evidence'):
            for value in values:
                fields = dict(question='Which?', options=list(self.OPTIONS), evidence='E')
                if field == 'options':
                    fields['options'][1] = value
                else:
                    fields[field] = value
                with self.subTest(field=field, value=value[:8]):
                    with self.assertRaises(judge.Unavailable) as raised:
                        judge.ask_choice(fields['question'], fields['options'], fields['evidence'])
                    self.assertEqual(str(raised.exception), 'field: ' + field)
        factory.assert_not_called()

    def test_reply_gives_the_top_option_its_probability_and_the_threshold(self):
        self.jev({'answers': {'q': {'choice': '1', 'probabilities': {'1': .15, '2': .85}}}})
        out = judge.ask_choice('Which?', self.OPTIONS, 'E')
        self.assertEqual((out['option'], out['of'], out['settled'], out['source']), (2, 2, True, 'jev'))
        self.assertAlmostEqual(out['p'], .85)
        judge._calls = 0
        self.jev({'answers': {'q': {'choice': '1', 'probabilities': {'1': .55, '2': .45}}}})
        out = judge.ask_choice('Which?', self.OPTIONS, 'E')
        self.assertEqual((out['option'], out['settled']), (1, False))
        self.assertEqual(judge.SETTLE_THRESHOLD, 0.8)

    def test_reply_shape_failures_are_unavailable(self):
        for reply in ({'answers': {'q': {'noul': .9}}}, {'answers': {'q': {'choice': '1', 'probabilities': {'1': .9}}}},
                      {'answers': {'q': {'choice': '1', 'probabilities': {'1': .9, '3': .1}}}}, {'answers': {'q': {'choice': '1', 'probabilities': {'1': 1.5, '2': -.5}}}},
                      {'answers': {'q': {'choice': '1', 'probabilities': {'1': .9, '2': 'x'}}}}, {'answers': {'q': {'choice': '1'}}},
                      {'answers': {'q': {'choice': '1', 'probabilities': {'1': .9, '2': .1}, 'extra': 1}}}, [],
                      b'{"answers":{"q":{"choice":"1","probabilities":{"1":0.9,"1":0.1,"2":0.0}}}}', b'x' * (judge.LIMIT + 1)):
            with self.subTest(reply=str(reply)[:50]):
                judge._calls = 0
                self.jev(reply)
                with self.assertRaises(judge.Unavailable):
                    judge.ask_choice('Which?', self.OPTIONS, 'E')

    def test_off_switch_and_unconfigured_judge_never_open_a_connection(self):
        with mock.patch('urllib.request.build_opener') as opener:
            with mock.patch.dict(os.environ, {'FNL_JUDGE': 'off', 'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True):
                with self.assertRaises(judge.Unavailable):
                    judge.ask_choice('Which?', self.OPTIONS, 'E')
            with mock.patch.dict(os.environ, {'TYPESAFE_API_KEY': 'synthetic-key'}, clear=True):
                with self.assertRaises(judge.Unavailable):
                    judge.ask_choice('Which?', self.OPTIONS, 'E')  # no host config: judge host
            opener.assert_not_called()

    def test_the_documented_reply_shape_is_accepted_and_anything_else_refused(self):
        full = {'model': 'jev-latest', 'usage': {'input_tokens': 1, 'output_tokens': 1},
                'answers': {'q': {'type': 'choice', 'choice': '2', 'confidence': .7, 'probabilities': {'1': .2, '2': .8}}}}
        self.jev(full)
        out = judge.ask_choice('Which?', self.OPTIONS, 'E')
        self.assertEqual((out['option'], out['p'], out['settled']), (2, .8, True))
        for bad in (dict(full, extra=1), {'model': 'jev-latest', 'usage': {}},
                    dict(full, answers={'q': dict(full['answers']['q'], type='noul')})):
            self.jev(bad)
            with self.assertRaises(judge.Unavailable):
                judge.ask_choice('Which?', self.OPTIONS, 'E')

    def test_cli_choice_site_dry_run_refusals_and_unavailable(self):
        evidence = Path(self.tmp.name) / 'evidence'
        evidence.write_text('The spec asks for one table.')
        def run(*args):
            with mock.patch.object(sys, 'argv', ['judge.py', *args]), contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                code = judge.main()
            return code, out.getvalue(), err.getvalue()
        base = ('ask', '--site', 'away-decision', '--question', 'Which schema?', '--evidence-file', str(evidence))
        code, out, _ = run(*base, '--option', 'Keep', '--option', 'Split', '--dry-run')
        self.assertEqual(code, 0)
        self.assertEqual(set(json.loads(out)['fields']), {'model', 'state', 'questions'})
        self.assertNotIn('Keep', out)
        # Too few options and options on a yes/no site are refused.
        code, out, _ = run(*base, '--option', 'Keep', '--dry-run')
        self.assertEqual(code, 3)
        code, _, _ = run('ask', '--question', 'Q', '--evidence-file', str(evidence), '--option', 'A', '--option', 'B', '--dry-run')
        self.assertEqual(code, 2)
        # Without Jev the choice site has no host fallback: the ladder goes to the advisor.
        code, out, err = run(*base, '--option', 'Keep', '--option', 'Split')
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out), {'option': None, 'of': 2, 'p': None, 'settled': False, 'source': 'host', 'fallback': True})
        self.assertIn('unavailable', err)
        self.jev({'answers': {'q': {'choice': '1', 'probabilities': {'1': .9, '2': .1}}}})
        code, out, _ = run(*base, '--option', 'Keep', '--option', 'Split')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {'option': 1, 'of': 2, 'p': .9, 'settled': True, 'source': 'jev', 'fallback': False})



if __name__ == '__main__':
    unittest.main()
