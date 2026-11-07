"""Navigator boundaries, including real Git config execution and temporary ledger roots."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('nav_state', ROOT / 'scripts/nav_state.py')
ns = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ns)


class NavStateTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = account(self, self.base / 'home')
        self.data = self.home / '.finolabs/vibecode'
        self.data.mkdir(parents=True)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / '.git').mkdir()
        self.anchors = self.write('anchors.md', '## Work tracking\nOutcome (2026-11-07): Verify claims\n- AC1: Require evidence\n')

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def cli(self, *args, payload=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, 'stdin', io.StringIO(json.dumps(payload))), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ns.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def collection(self):
        with mock.patch.object(ns, 'collect_git_evidence', return_value=(['a' * 12], ['#146'], [])):
            return ns.collect(self.anchors, '2026-11-01')

    def report(self):
        return {'anchors': [{'id': 'AC1', 'status': 'on course',
                             'judge_answers': [{'answer': 'yes', 'quote_ok': True}],
                             'evidence_refs': ['#146']}], 'unmatched_items': [],
                'options': [{'option': 'Continue', 'cost': 'One check'}]}

    def test_collect_only_anchors_and_bounded_metadata(self):
        self.write('specs/001-demo/spec.md', '# Demo\nStatus: in progress; PRIVATE\n## Success Criteria\n- **SC-001**: Check payload\n## Goal and acceptance\n- AC89: Wrong spec section\n')
        self.write('docs/specs/work.md', '# Work\nStatus: accepted\n## Goal and acceptance\n- [ ] AC9: Check report\n- AC10: <placeholder>\n## Success Criteria\n- AC88: Wrong record section\n## Plan\nPRIVATE PLAN\n')
        self.write('docs/specs/unconfirmed.md', '- AC99: Not confirmed\n')
        self.write('docs/spec/old.md', '# Old\nStatus: not yet released\n## Goal and acceptance\n- AC8: Preserve history\n## Evidence\n')
        self.write('docs/other/spec.md', '## Success Criteria\n- AC77: Outside glob\n')
        self.write('specs/archive/spec.md', '## Success Criteria\n- AC78: Archived\n')
        payload = self.collection()
        self.assertTrue(ns.validate_payload(payload))
        self.assertEqual(set(payload), {'since', 'criteria', 'evidence'})
        self.assertEqual({c['id'] for c in payload['criteria']}, {'OUTCOME-1', 'AC1', 'SC-001', 'AC9', 'AC8'})
        for item in payload['criteria']:
            self.assertEqual(set(item), {'id', 'criterion', 'evidence_refs'})
        self.assertEqual(payload['evidence']['specs'], [
            {'id': 'old', 'status': 'unknown'}, {'id': 'work', 'status': 'accepted'},
            {'id': '001-demo', 'status': 'in progress'}])
        self.assertNotIn('PRIVATE', json.dumps(payload))

    def test_unconfirmed_bullets_fences_and_unrelated_sections_are_not_anchors(self):
        text = '- AC1: Unconfirmed\n```md\nOutcome: Hidden\n```\n## Other\n- AC2: Other\n'
        self.assertEqual(ns.parse_criteria_from_markdown(text), [])
        text += '## Work tracking\nOutcome: Confirmed\n- AC3: Confirmed criterion\n## Plan\n- AC4: Plan only\n'
        self.assertEqual([c['id'] for c in ns.parse_criteria_from_markdown(text)], ['OUTCOME-1', 'AC3'])

    def test_reader_refuses_symlink_components_oversize_nonregular_and_wrong_owner(self):
        link = self.repo / 'link.md'
        link.symlink_to(self.anchors)
        directory = self.repo / 'linked'
        directory.symlink_to(self.repo, target_is_directory=True)
        big = self.write('big.md', 'x' * (ns.MAX_FILE_BYTES + 1))
        for path in (link, directory / 'anchors.md', big, self.repo):
            with self.subTest(path=path), self.assertRaises((OSError, ValueError)):
                ns.read_safe_file(path)
        info = self.anchors.stat()
        wrong = list(info)
        wrong[4] = os.getuid() + 1
        with mock.patch.object(ns.os, 'fstat', return_value=os.stat_result(wrong)):
            with self.assertRaises(ValueError):
                ns.read_safe_file(self.anchors)

    def test_since_is_a_real_date_before_git_or_file_access(self):
        for value in ('2026-02-30', '--all', '2026-1-01', '2026-11-01T00:00:00', '2026-11-01\n', ''):
            with self.subTest(value=value), mock.patch.object(ns, 'read_safe_file') as read, \
                    mock.patch.object(ns.subprocess, 'run') as run:
                self.assertEqual(self.cli('collect', '--anchors', str(self.anchors), '--since=' + value)[0], 2)
                with self.assertRaises(ValueError):
                    ns.collect_git_evidence(self.repo, value)
                read.assert_not_called()
                run.assert_not_called()
        self.assertEqual(ns.validate_since('2024-02-29'), '2024-02-29')

    def test_git_argv_env_pr_suffixes_and_identifier_linking(self):
        subjects = ['AC1 fix #12', 'AC1 issue #13 in prose', 'AC1 work (#146)',
                    'AC1 merge pull request #147', 'AC1 merge PR #148', 'AC1 work (#149) trailing',
                    'AC1 ' + 'x' * 150 + ' (#150)']
        raw = ''.join(f'{i + 1:040x}\t{s}\n' for i, s in enumerate(subjects)).encode()
        with mock.patch.object(ns.shutil, 'which', return_value='/custom/git/bin/git'), \
                mock.patch.dict(os.environ, {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'bad', 'SECRET': 'private'}), \
                mock.patch.object(ns.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, raw)) as run:
            payload = ns.collect(self.anchors, '2026-11-01')
        self.assertEqual(run.call_args.args[0], [
            '/custom/git/bin/git', '-c', 'log.showSignature=false', '-c', 'core.fsmonitor=false',
            '-C', str(self.repo), 'log', '--no-show-signature', '--no-color', '--no-ext-diff',
            '--no-textconv', '--format=%H%x09%s', '--since=2026-11-01'])
        self.assertEqual(run.call_args.kwargs['env'], {
            'PATH': os.defpath + os.pathsep + '/custom/git/bin', 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0'})
        self.assertEqual(payload['evidence']['pull_requests'], ['#146', '#147', '#148', '#150'])
        ac1 = next(c for c in payload['criteria'] if c['id'] == 'AC1')
        self.assertIn('#146', ac1['evidence_refs'])
        self.assertNotIn('#12', ac1['evidence_refs'])
        self.assertNotIn('subjects', payload['evidence'])

    def test_real_git_signature_config_cannot_execute_program(self):
        git = shutil.which('git')
        self.assertIsNotNone(git, 'real Git is required for this security regression')
        repo = self.base / 'real-repo'
        env = {'PATH': os.defpath + os.pathsep + str(Path(git).parent),
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
               'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
               'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'}

        def command(*args, input=None):
            return subprocess.run([git, '-C', str(repo), *args], env=env, input=input,
                                  capture_output=True, check=True).stdout.strip()

        repo.mkdir()
        command('init')
        tree = command('mktree', input=b'')
        original = command('commit-tree', tree.decode(), input=b'AC1 signed fixture (#146)\n')
        body = command('cat-file', 'commit', original.decode())
        headers, message = body.split(b'\n\n', 1)
        signed = headers + b'\ngpgsig -----BEGIN PGP SIGNATURE-----\n fixture\n -----END PGP SIGNATURE-----\n\n' + message + b'\n'
        commit = command('hash-object', '-t', 'commit', '-w', '--stdin', input=signed)
        command('update-ref', 'HEAD', commit.decode())
        marker = self.base / 'gpg-executed'
        program = self.base / 'fake-gpg'
        program.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
        program.chmod(0o700)
        command('config', 'log.showSignature', 'true')
        command('config', 'gpg.program', str(program))
        # Positive control: prove this fixture reaches the configured verifier.
        command('log', '-1', '--format=%H')
        self.assertTrue(marker.exists())
        marker.unlink()
        anchors = repo / 'anchors.md'
        anchors.write_text('## Work tracking\nOutcome: Safe Git\n- AC1: List commits\n')
        payload = ns.collect(anchors, '2000-01-01')
        self.assertFalse(marker.exists())
        self.assertIn(commit.decode()[:12], payload['evidence']['commits'])
        self.assertEqual(payload['evidence']['pull_requests'], ['#146'])

    def test_ledger_requires_project_and_caps_ids_and_counts_together(self):
        rows = []
        for i in range(205):
            rows.extend([{'event': 'start', 'id': f'run-{i}', 'project': 'demo', 'ts': '2026-11-07'},
                         {'event': 'finish', 'id': f'run-{i}', 'ts': '2026-11-07', 'outcome': 'accepted'}])
        rows += [{'event': 'start', 'id': 'other', 'project': 'elsewhere', 'ts': '2026-11-07'},
                 {'event': 'start', 'id': 'old', 'project': 'demo', 'ts': '2020-01-01'}]
        ledger = self.data / 'ledger.jsonl'
        ledger.write_text('bad json\n[]\n' + '\n'.join(map(json.dumps, rows)))
        with mock.patch.object(ns.dr, 'consent_root', side_effect=AssertionError('must not resolve without project')):
            self.assertEqual(ns.collect_ledger_evidence('2026-11-01'), {'status': 'absent', 'ids': [], 'counts': {}})
        evidence = ns.collect_ledger_evidence('2026-11-01', 'demo')
        self.assertEqual(len(evidence['ids']), 200)
        self.assertEqual(evidence['counts'], {'accepted': 200})
        self.assertNotIn('other', evidence['ids'])
        with mock.patch.object(ns, 'collect_git_evidence', return_value=([], [], [])):
            payload = ns.collect(self.anchors, '2026-11-01', project='demo')
        self.assertEqual(payload['evidence']['counts']['ledger_runs'], 200)
        self.assertTrue(ns.validate_payload(payload))
        ledger.unlink()
        self.assertEqual(ns.collect_ledger_evidence('2026-11-01', 'demo')['status'], 'absent')

    def test_screen_preserves_language_caps_and_removes_paths_tokens(self):
        private = ['/Users/fio/private.txt', '/home/user/private', r'C:\Users\fio\private',
                   'a' * 64, 'QWxhZGRpbjpvcGVuIHNlc2FtZQ' * 3, 'sk-privateToken', 'ghp_privateToken']
        phrase = 'Đảm bảo có dẫn chứng'
        for value in private:
            with self.subTest(value=value):
                payload = {'id': 'AC1', 'criterion': phrase + ' ' + value,
                           'restated_criterion': 'Support ' + value, 'question': 'Check ' + value,
                           'evidence_refs': ['#146']}
                code, out, err = self.cli('validate-payload', payload=payload)
                self.assertEqual((code, err), (0, ''))
                screened = json.loads(out)
                self.assertEqual(screened['criterion'], phrase + ' [removed]')
                self.assertEqual(screened['question'], 'Check [removed]')
                self.assertNotIn(value, out)
        self.assertLessEqual(len(ns.parse_criteria_from_markdown('Outcome: ' + 'word ' * 100)[0]['criterion']), 300)
        self.assertNotIn('\u202e', ns.sanitize_text('safe\u202etext'))

    def test_payload_refuses_unknown_fields_controls_counts_and_absolute_refs(self):
        good = self.collection()
        variants = []
        for ref in ('/Users/fio/file', '/home/fio/file', 'C:/private/file', '../private', '//server/share'):
            bad = copy.deepcopy(good)
            bad['criteria'][0]['evidence_refs'] = [ref]
            variants.append(bad)
        for key, value in [('criterion', 'a' * 301), ('criterion', 'bad\x07text'), ('secret', 'data')]:
            bad = copy.deepcopy(good)
            bad['criteria'][0][key] = value
            variants.append(bad)
        bad = copy.deepcopy(good)
        bad['evidence']['counts']['commits'] = 999
        variants.append(bad)
        bad = copy.deepcopy(good)
        bad['evidence']['specs'] = [{'id': 'demo', 'status': 'invented'}]
        variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad):
                self.assertEqual(self.cli('validate-payload', payload=bad)[0], 2)
        with self.assertRaises(ValueError):
            ns.read_json(self.write('duplicate.json', '{"id":1,"id":2}'))
        # Raw bytes avoid the invalid Python \\u escape warning in the regression fixture.
        malformed = self.write('malformed.json', br'{"x":"\uZZZZ"}'.decode())
        with self.assertRaises(ValueError):
            ns.read_json(malformed)

    def test_report_exact_schema_evidence_membership_and_cli(self):
        collection = self.collection()
        path = self.write('collected.json', json.dumps(collection))
        report = self.report()
        self.assertEqual(self.cli('check-report', '--collected', str(path), payload=report)[:2], (0, '{"ok": true}\n'))
        variants = []
        for refs in ([], ['#999'], ['/home/user/file']):
            bad = copy.deepcopy(report)
            bad['anchors'][0]['evidence_refs'] = refs
            variants.append(bad)
        for key, value in [('status', 'No drift'), ('answer', 'yes'), ('judge_answers', [{'answer': 'yes', 'quote_ok': False}]),
                           ('judge_answers', [{'answer': 'maybe', 'quote_ok': True}])]:
            bad = copy.deepcopy(report)
            bad['anchors'][0][key] = value
            variants.append(bad)
        variants.extend([{'anchors': report['anchors']}, report['anchors'],
                         {**report, 'unmatched_items': ['#999']},
                         {**report, 'options': report['options'] * 4},
                         {**report, 'options': [{'action': 'Alias', 'cost': '1h'}]}])
        for bad in variants:
            with self.subTest(bad=bad):
                code, out, err = self.cli('check-report', '--collected', str(path), payload=bad)
                self.assertEqual((code, out), (2, ''))
                self.assertIn('Navigator state refused:', err)

    def test_agent_frontmatter_has_structural_host_restrictions(self):
        text = (ROOT / 'agents/fnl-navigator.md').read_text()
        self.assertTrue(text.startswith('---\n'))
        front, body = text[4:].split('\n---\n', 1)
        fields = dict(line.split(': ', 1) for line in front.splitlines())
        self.assertEqual(set(fields), {'name', 'description', 'model', 'disallowedTools'})
        self.assertEqual(fields['name'], 'fnl-navigator')
        self.assertEqual(fields['model'], 'inherit')
        self.assertEqual([s.strip() for s in fields['disallowedTools'].strip('[]').split(',')],
                         ['Write', 'Edit', 'NotebookEdit'])
        headings = {line[3:] for line in body.splitlines() if line.startswith('## ')}
        self.assertTrue({'Inputs', 'Steps', 'Output'} <= headings)


if __name__ == '__main__':
    unittest.main()
