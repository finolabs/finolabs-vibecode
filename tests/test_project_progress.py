"""Project progress acceptance: synthetic account, files, records and clock only."""
import importlib.util
import json
import os
import shutil
import stat
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ProgressTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / 'home')
        self.pp = module('project_progress_test', ROOT / 'scripts/project_progress.py')
        self.repo = Path(self.tmp.name).resolve() / 'private-repository'
        self.repo.mkdir()
        (self.repo / '.git').mkdir()
        self.data = self.home / '.finolabs/vibecode'
        self.data.mkdir(parents=True)
        self.host = self.data / 'host.md'
        self.host.write_text('# Host\n\n## Project progress\n\n- Project progress: on\n')
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(os.environ, {'FNL_PROGRESS': '', 'FNL_METRICS': ''}).start()

    def taskfile(self, feature='003-private-name', text='- [ ] T012 [US1] private task\n'):
        path = self.repo / 'specs' / feature / 'tasks.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def collect(self, **kwargs):
        return self.pp.collect(self.repo, 'aaaaaaaa', **kwargs)

    def consent(self):
        state = self.data / 'state'
        state.mkdir(exist_ok=True)
        (state / 'consent.json').write_text(json.dumps(dict(date='2026-11-06', retention_days=30)))

    def settings_file(self):
        return self.repo / '.finolabs/vibecode/settings.json'

    def stored(self):
        return json.loads(self.settings_file().read_text()) if self.settings_file().exists() else {}

    def test_invalid_values_are_refused_and_an_invalid_file_changes_nothing(self):
        import hashlib
        self.consent()
        bad_values = [('ledger', v) for v in ('', ' ', 'x' * 41, 'a;', 'a=b', 'a\nb', 'a\x00b', 'a\\b', 'é')]
        bad_values += [('tasks', v) for v in ('', '/a.md', '../a.md', 'a/../b.md', './a.md', 'a//b.md',
                       'specs/archive/a.md', 'a.txt', 'a b.md', 'a\\b.md', 'a;.md', 'a=.md', 'a\x00.md', 'x' * 118 + '.md')]
        self.document('one.md', 'Status: implemented\n')
        before = self.collect()
        for key, value in bad_values:
            with self.subTest(key=key, value=repr(value)):
                with self.assertRaises(ValueError):
                    self.pp.set_setting(self.repo, key, value)
                self.assertFalse(self.settings_file().exists())
                raw = json.dumps({'version': 1, key: value}).encode()
                self.settings_file().parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                self.settings_file().write_bytes(raw)
                os.chmod(self.settings_file(), 0o600)
                approvals = self.data / 'state/settings-approved'
                approvals.mkdir(parents=True, exist_ok=True, mode=0o700)
                (approvals / (self.pp.repository_code(self.repo) + '.json')).write_text(
                    json.dumps({'sha256': hashlib.sha256(raw).hexdigest(), 'approved': 1}))
                self.assertEqual(self.pp.repository_settings({}, self.repo), {})
                self.assertEqual(self.collect(), before)
                self.settings_file().unlink()

    def test_settings_consent_atomic_private_and_cli_output(self):
        import io
        before = self.host.read_bytes()
        for value in ('PRIVATE', None):
            with self.assertRaises(ValueError):
                self.pp.set_setting(self.repo, 'ledger', value)
        self.assertEqual(self.host.read_bytes(), before)
        self.consent()
        with mock.patch.object(self.pp.store, 'write_setting', wraps=self.pp.store.write_setting) as write:
            self.assertTrue(self.pp.set_setting(self.repo, 'ledger', 'PRIVATE'))
            self.assertEqual(write.call_count, 1)
        self.assertFalse(self.pp.set_setting(self.repo, 'ledger', 'PRIVATE'))
        if True:
            with mock.patch('os.getcwd', return_value=str(self.repo)), mock.patch('sys.stdout', new_callable=io.StringIO) as out:
                self.assertEqual(self.pp.main(['settings', '--set', 'tasks=docs/private.md']), 0)
                self.assertIn('tasks changed', out.getvalue())
                self.assertNotIn('private', out.getvalue())
            with self.assertRaises(ValueError):
                self.pp.set_setting(self.repo, 'ledger', 'first=second')
            with mock.patch('os.getcwd', return_value=str(self.repo)), mock.patch.object(self.pp, 'set_setting', return_value=True) as write, mock.patch('sys.stdout', new_callable=io.StringIO) as out:
                self.assertEqual(self.pp.main(['settings', '--set', 'ledger=first=second']), 0)
                write.assert_called_once_with(str(self.repo), 'ledger', 'first=second')
                self.assertEqual(out.getvalue(), 'ledger changed\n')
            with mock.patch.object(self.pp.dr, 'atomic_write', side_effect=OSError('interrupted')):
                saved = self.settings_file().read_bytes()
                with self.assertRaises(OSError):
                    self.pp.set_setting(self.repo, 'ledger', 'other')
                self.assertEqual(saved, self.settings_file().read_bytes())
            self.assertTrue(self.pp.set_setting(self.repo, 'tasks', None))
            self.assertFalse(self.pp.set_setting(self.repo, 'tasks', None))
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.settings_file().stat().st_mode), 0o600)
        self.assertFalse(list(self.settings_file().parent.glob('.write-*')))

    def test_parallel_settings_validation(self):
        for value in ('1', '5', '32'):
            self.assertTrue(self.pp.valid_setting('parallel', value))
        for value in ('0', '33', '-1', '1.0', 'true', '', ' 2', '2 ', 2, None):
            self.assertFalse(self.pp.valid_setting('parallel', value))
        for value in ('claude=1', 'codex=32, antigravity=2', 'claude=2,codex=1,antigravity=3'):
            self.assertTrue(self.pp.valid_setting('parallel-caps', value))
        for value in ('', 'codex=0', 'codex=33', 'codex=1,codex=2', 'other=1', 'codex=1,', 'codex=true', None):
            self.assertFalse(self.pp.valid_setting('parallel-caps', value))
            if value is not None:
                with self.assertRaises(ValueError):
                    self.pp.set_setting(self.repo, 'parallel-caps', value)
        self.assertFalse(self.settings_file().exists())

    def test_parallel_settings_need_no_metrics_consent_but_ledger_and_tasks_do(self):
        self.assertTrue(self.pp.set_setting(self.repo, 'parallel', '4'))
        self.assertEqual(self.stored()['parallel'], '4')
        self.assertTrue(self.pp.set_setting(self.repo, 'parallel-caps', 'codex=2'))
        for key, value in (('ledger', 'Alias'), ('tasks', 'docs/t.md')):
            with self.assertRaises(ValueError):
                self.pp.set_setting(self.repo, key, value)
        self.assertEqual(sorted(self.stored()), ['parallel', 'parallel-caps', 'version'])

    def test_parallel_settings_cli_set_clear_preserves_other_entries(self):
        import io
        self.consent()
        before = self.host.read_bytes()
        self.assertTrue(self.pp.set_setting(self.repo, 'ledger', 'Alias'))
        with mock.patch('os.getcwd', return_value=str(self.repo)), mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            for key, value in (('parallel', '2'), ('parallel-caps', 'codex=1, claude=2')):
                self.assertEqual(self.pp.main(['settings', '--set', key + '=' + value]), 0)
                self.assertEqual(self.stored()[key], value)
                self.assertEqual(self.pp.main(['settings', '--clear', key]), 0)
                self.assertNotIn(key, self.stored())
            self.assertNotIn('Alias', out.getvalue())
        self.assertEqual(self.stored()['ledger'], 'Alias')
        self.assertEqual(self.host.read_bytes(), before)

    def test_budget_restores_alarm_after_timeout_during_cancel(self):
        signal = self.pp.signal
        for body_timeout in (False, True):
            with self.subTest(body_timeout=body_timeout):
                calls = []
                previous = object()
                cancel_attempts = 0
                def timer(kind, seconds):
                    nonlocal cancel_attempts
                    calls.append(('timer', seconds))
                    if seconds == 0:
                        cancel_attempts += 1
                        if cancel_attempts == 1:
                            raise self.pp.ProgressTimeout()
                def handler(kind, value):
                    calls.append(('handler', value))
                    return previous
                with mock.patch.object(signal, 'getitimer', return_value=(0, 0)), \
                        mock.patch.object(signal, 'setitimer', side_effect=timer), \
                        mock.patch.object(signal, 'signal', side_effect=handler):
                    def run():
                        with self.pp.budget():
                            if body_timeout:
                                raise self.pp.ProgressTimeout('body')
                    if body_timeout:
                        with self.assertRaisesRegex(self.pp.ProgressTimeout, 'body'):
                            run()
                    else:
                        run()
                self.assertEqual(calls[-3:], [('timer', 0), ('timer', 0), ('handler', previous)])

    def test_task_instruction_denylist_is_closed_and_case_insensitive(self):
        names = ('CLAUDE.md', 'CLAUDE.local.md', 'AGENTS.md', 'AGENTS.override.md',
                 'GEMINI.md', 'copilot-instructions.md', 'CONVENTIONS.md',
                 '.cursorrules', '.windsurfrules', '.clinerules')
        for name in names:
            for folder in ('', '.github/', 'nested/'):
                relative = folder + name.swapcase()
                self.assertFalse(self.pp.valid_setting('tasks', folder + name))
                with self.subTest(relative=relative):
                    self.assertFalse(self.pp.valid_setting('tasks', relative))
                    with mock.patch.object(self.pp.os, 'dup') as dup:
                        with self.assertRaisesRegex(ValueError, 'instruction file skipped'):
                            self.pp.read_task(-1, relative)
                        dup.assert_not_called()
        self.assertTrue(self.pp.valid_setting('tasks', 'docs/my-conventions.md'))
        spec = (ROOT / 'docs/specs/work-tracking.md').read_text().split('## B.')[0]
        self.assertIn('closed, named set', spec)
        for name in names:
            self.assertIn('`' + name + '`', spec)

    def test_settings_outside_a_repository_refuse_without_echoing_value(self):
        import io
        self.consent()
        self.host.unlink()
        with mock.patch('os.getcwd', return_value=str(self.repo.parent)), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out, \
                mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(self.pp.main(['settings', '--set', 'ledger=PRIVATE']), 1)
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(err.getvalue(), 'Project settings refused; no setting changed.\n')
        self.assertNotIn('PRIVATE', err.getvalue())
        self.assertFalse(self.host.exists())

    def test_settings_two_repositories_override_deprecated_globals(self):
        self.consent()
        other = self.repo.with_name('other')
        other.mkdir()
        (other / '.git').mkdir()
        self.host.write_text('## Project progress\n- Ledger project: old\n- Task file: missing.md\n')
        self.pp.set_setting(self.repo, 'ledger', 'PRIVATE one')
        self.pp.set_setting(other, 'ledger', 'PRIVATE two')
        self.pp.set_setting(self.repo, 'tasks', 'tasks.md')
        (self.repo / 'tasks.md').write_text('- [ ] T1\n')
        starts = {str(i): dict(project=name, task='001 T1', ts='2026-11-06T00:00:00Z')
                  for i, name in enumerate(('PRIVATE one', 'PRIVATE two', 'old'))}
        one = self.collect(starts=starts)
        two = self.pp.collect(other, 'bbbbbbbb', starts=starts)
        self.assertEqual(one['features'][0]['tasks'][0]['runs'][0]['id'], '0')
        self.assertEqual(two['work'], {'active': 1})
        self.assertNotIn('PRIVATE', json.dumps([one, two]))
        self.pp.set_setting(self.repo, 'ledger', None)
        # The deprecated global line is never read: unset falls back to the folder name.
        self.assertNotIn('Ledger project', self.pp.repository_settings(self.pp.config(), self.repo))

    def test_work_record_template_parses_with_status_reader(self):
        import re
        template = ROOT / 'skills/fnl-coding-router/references/work-record.md'
        block = re.search(r'```markdown\n(.*?)\n```', template.read_text(), re.S)
        self.assertIsNotNone(block, 'keep one literal parseable template block')
        pp = module('template_status_reader', ROOT / 'skills/fnl-status/scripts/project_progress.py')
        item = pp.work_record(block[1], 1)
        self.assertIsNotNone(item)
        self.assertEqual(item['state'], 'todo')
        self.assertEqual([(s['stage'], s['done'], s['total']) for s in item['stages']],
                         [])
        self.assertEqual((item['done'], item['total']), (0, 0))
        self.assertEqual(item['tasks'], [])
        self.assertEqual(item['stories'], [])
        self.assertNotIn('<', json.dumps(item))
        text = template.read_text()
        self.assertIn('MIN depth creates no work record', text)
        for tool in ('grilling', 'to-spec', 'to-tickets', 'tdd', 'implement', 'code-review', 'pr'):
            self.assertIn('`' + tool + '`', text)

    def test_filled_work_record_template_counts(self):
        import re
        template = (ROOT / 'skills/fnl-coding-router/references/work-record.md').read_text()
        text = re.search(r'```markdown\n(.*?)\n```', template, re.S)[1]
        text = re.sub(r'<[^>]*>', 'Filled content', text).replace('- [ ]', '- [x]')
        item = self.pp.work_record(text, 1)
        self.assertEqual(item['state'], 'todo')
        self.assertEqual([(s['stage'], s['done'], s['total']) for s in item['stages']],
                         [('spec', 1, 1), ('plan', 1, 1), ('tasks', 1, 1), ('verify', 1, 1)])
        self.assertEqual(item['tasks'][0]['id'], 'T1')
        self.assertEqual(item['stories'][0]['story'], 'US1')

    def record(self, status='in progress', tasks='- [x] T1 PRIVATE\n', directory='docs/specs', name='work.md'):
        return self.document(name, '# PRIVATE title\nStatus: ' + status + '; PRIVATE\n'
            '## Goal and acceptance\n- [ ] AC1 PRIVATE\n## Plan\nPRIVATE plan\n'
            '## Tasks\n### US1 PRIVATE story\n' + tasks + '## Evidence\nPRIVATE evidence\n', directory)

    def test_work_record_stages_state_marks_and_closed_output(self):
        self.record()
        got = self.collect()
        self.assertEqual((got['source'], got['recognition']), ('work-record', 'work-record'))
        item = got['features'][0]
        self.assertEqual(item['state'], 'active')
        self.assertEqual(item['status_mark'], 'status-not-updated')
        self.assertEqual([(s['stage'], s['done'], s['total']) for s in item['stages']],
                         [('spec', 0, 1), ('plan', 1, 1), ('tasks', 1, 1), ('verify', 1, 1)])
        self.assertEqual(item['stories'], [dict(story='US1', done=1, total=1)])
        self.assertNotIn('PRIVATE', json.dumps(got))
        for status, state in [('draft', 'todo'), ('accepted', 'todo'), ('in progress', 'active'),
                              ('implemented', 'done'), ('released', 'done'), ('deferred', 'deferred'), ('PRIVATE', 'unknown')]:
            self.record(status)
            item = self.collect()['features'][0]
            self.assertEqual(item['state'], state)
            if status == 'accepted':
                self.assertEqual(item['status_mark'], 'accepted')
        self.document('work.md', 'Status: draft\n## Goal and acceptance\n- [x] AC1\n## Tasks\n- [ ] without id\n')
        self.assertEqual([s['stage'] for s in self.collect()['features'][0]['stages']], ['spec', 'tasks'])
        self.document('work.md', 'Status: implemented\n## Goal and acceptance\n')
        self.assertNotEqual(self.collect()['source'], 'work-record')

    def test_work_record_negated_completion_is_unknown(self):
        for status in ('implemented; not yet released', 'released; not done',
                       'implemented; not yet merged', 'implemented; not implemented'):
            with self.subTest(status=status):
                self.record(status)
                self.assertEqual(self.collect()['features'][0]['state'], 'unknown')
        self.record('implemented; tested locally')
        self.assertEqual(self.collect()['features'][0]['state'], 'done')

    def test_work_record_fenced_evidence_and_empty_status(self):
        text = 'Status: \n## Plan\n```sh\n## Tasks\n- [x] T9\n```\n## Evidence\n```sh\npython -m unittest\n```\n'
        item = self.pp.work_record(text, 1)
        self.assertIsNotNone(item)
        self.assertEqual(item['state'], 'unknown')
        self.assertEqual([(row['stage'], row['total']) for row in item['stages']], [('plan', 1), ('verify', 1)])
        self.assertEqual(item['tasks'], [])

    def test_work_record_precedence_flat_specs_and_shared_safe_parser(self):
        self.record(directory='specs')
        self.assertEqual(self.collect()['source'], 'work-record')
        (self.repo / 'specs/001-empty').mkdir()
        self.assertEqual(self.collect()['source'], 'none')
        self.record()
        self.taskfile()
        self.assertEqual(self.collect()['source'], 'speckit')
        self.assertEqual(self.pp.parse('```md\n## Phase 2\n- [x] T1\n```\n- [ ] T2\n', 1)['total'], 1)
        self.assertEqual(self.pp.priorities('~~~\n## User Story 1 (P1)\n~~~\n'), {})
        self.assertEqual(self.pp.status_line('```\nStatus: released\n```\nStatus: draft\n'), 'draft')
        self.assertEqual(self.pp.status_line('\n' * 40 + 'Status: released'), '')
        self.assertEqual(self.pp.work_record('Status: draft\n```\n## Plan\n## Tasks\n```\n', 1), None)

    @unittest.skipUnless(shutil.which('node') or Path('/opt/homebrew/bin/node').exists(), 'node is not installed')
    def test_work_record_amber_dot_renders_with_tooltip(self):
        from tests.test_dashboard_page import DashboardScriptTest
        self.record()
        got = self.collect()
        data = json.loads((ROOT / 'tests/fixtures/status-sample.json').read_text())
        data['progress'] = {'repositories': {'aaaaaaaa': got}, 'active': [
            {'repo': 'aaaaaaaa', 'label': 'Synthetic', 'hosts': ['codex'], 'sessions': 1, 'last': '2026-11-06T10:00:00Z'}]}
        page = DashboardScriptTest()
        out = page.render_freshness(data, {'hash': '#now'})
        marks = page.marks(out, 'pipeline-status-mark')
        self.assertEqual(len(marks), 1)
        self.assertIn('status not updated', json.dumps(marks))
        self.assertNotIn('PRIVATE', json.dumps(out))
        self.assertNotIn('undefined', ' '.join(m['text'] for m in page.marks(out, 'active-project')))

    def test_truncated_flat_specs_listing_cannot_prove_no_numbered_directory(self):
        for i in range(205):
            self.record('draft', directory='specs', name=f'{i:03d}.md')
        (self.repo / 'specs/001-empty').mkdir()
        original = self.pp.directory_entries
        def truncated(fd, relative, skipped, cap=200):
            if relative == 'specs':
                skipped.append('entry limit')
                return [(f'{i:03d}.md', False, True) for i in range(min(200, cap))]
            return original(fd, relative, skipped, cap)
        with mock.patch.object(self.pp, 'directory_entries', side_effect=truncated):
            got = self.collect()
        self.assertEqual(got['source'], 'none')
        self.assertGreaterEqual(got['work_records']['skipped'], 1)

    def test_work_record_caps_drop_order_and_unsafe_entries(self):
        for i in range(41):
            self.record('implemented' if i == 0 else 'draft', name=f'{i:03d}.md')
        got = self.collect()
        self.assertEqual(len(got['features']), 40)
        self.assertTrue(all(f['state'] == 'todo' for f in got['features']))
        self.assertEqual(got['work_records']['skipped'], 1)
        folder = self.repo / 'docs/specs'
        (folder / 'big.md').write_bytes(b'x' * (65536 + 1))
        (folder / 'link.md').symlink_to(folder / '001.md')
        os.mkfifo(folder / 'x.md')
        self.assertEqual(self.collect()['work_records']['skipped'], 4)
        shutil.rmtree(folder)
        folder.symlink_to(self.repo / 'specs')
        self.assertGreaterEqual(self.collect()['work_records']['skipped'], 1)
        folder.unlink()
        for i in range(205):
            self.document(f'{i:03d}.md', 'Status: draft\n## Plan\nx\n## Tasks\n')
        self.assertGreaterEqual(self.collect()['work_records']['skipped'], 1)
        with mock.patch.object(self.pp, 'work_record', side_effect=lambda *a: time.sleep(2)):
            started = time.monotonic()
            got = self.collect()
            self.assertEqual(got['reason'], 'progress timed out')
            self.assertEqual(got['work_records']['skipped'], 1)
            self.assertLess(time.monotonic() - started, 1.5)

    # Infographics acceptance 3: new metadata only, same safe reader.
    def test_priorities_archive_labels_and_finished_project(self):
        task = self.taskfile(text='- [x] T1 US1\n- [x] T2 US2\n- [x] T3 US3\n')
        task.with_name('spec.md').write_text('## User Story 1 (P1) - private heading\n'
            '### User Story 2 (P9) - <img secret>\n## User Story 3 (P10)\n')
        self.taskfile('archive/005-secret', '- [ ] T9 US9')
        self.taskfile('archive', '- [ ] T8 US8')
        result = self.collect()
        self.assertEqual(len(result['features']), 1)
        self.assertEqual([s.get('priority') for s in result['features'][0]['stories']], [1, 9, None])
        self.assertFalse(result['done'])  # checked tasks still need a verify artefact
        task.with_name('quickstart-results.md').write_text('')
        self.assertTrue(self.collect()['done'])
        self.assertEqual(result['label'], '')
        self.assertNotIn('private', json.dumps(result))
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('<img', json.dumps(result))
        for bad in ('', 'x' * 41, '<img>', 'a/b', 'a\nlabel', 'x\x01'):
            with self.subTest(label=bad), self.assertRaises(ValueError):
                self.pp.set_label(self.repo, bad)
        before = self.host.read_bytes()
        self.pp.set_label(self.repo, 'Fino tools-2.0')
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(self.stored()['label'], 'Fino tools-2.0')
        self.assertEqual(self.collect()['label'], 'Fino tools-2.0')
        self.assertIn('- Project progress: on', self.host.read_text())
        # Duplicate metadata is ambiguous, not last-heading-wins.
        task.with_name('spec.md').write_text('## User Story 1 (P2)\n## User Story 1 (P3)\n')
        self.assertIsNone(self.collect()['features'][0]['stories'][0]['priority'])

    def document(self, name, text, directory='docs/specs'):
        path = self.repo / directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_speckit_real_shape_artifacts_gaps_phase_stories_and_stale_status(self):
        task = self.taskfile('013-synthetic', '## Phase 2: User Story 1 - Synthetic (P1)\n- [x] T001\n- [x] T002\n'
                             '## Phase 3: User Story 2 - Synthetic (P2)\n- [x] T003\n')
        for name in ('spec.md', 'plan.md', 'research.md', 'data-model.md', 'quickstart-results-local.md',
                     'review-code-us1.md', 'review-security-us1.md', 'review-final-code.md',
                     'review-security-final.md', 'review-independent-check.md', 'review-design.md', 'release-notes-1.md'):
            task.with_name(name).write_text('**Status**: Draft\nPRIVATE NEVER OUTPUT\n')
        task.with_name('contracts').mkdir()
        self.document('spec.md', '**Status**: Draft\n', 'specs/016-synthetic')
        self.document('index.md', '| [Synthetic](elsewhere.md) | In progress |\n')
        got = self.collect()
        self.assertEqual(got['source'], 'speckit')
        self.assertEqual([f['feature'] for f in got['features']], [13, 16])
        done, new = got['features']
        self.assertEqual(done['state'], 'done')
        self.assertEqual(done['status_hint'], 'draft')
        self.assertEqual([s['stage'] for s in done['stages']], ['spec', 'plan', 'design', 'tasks', 'verify', 'review', 'ship'])
        self.assertEqual(done['review_counts'], dict(code=4, security=2, code_final=True, security_final=True))
        self.assertEqual([(s['story'], s['priority'], s['total']) for s in done['stories']], [('US1', 1, 2), ('US2', 2, 1)])
        self.assertEqual(new['state'], 'todo')
        self.assertEqual([s['stage'] for s in new['stages']], ['spec'])
        self.assertNotIn('PRIVATE', json.dumps(got))
        self.assertNotIn('synthetic', json.dumps(got))

    @unittest.skipUnless(shutil.which("node") or Path("/opt/homebrew/bin/node").exists(), "node is not installed")
    def test_collected_artifacts_and_source_b_render_chains_not_text_lanes(self):
        # Exercise collector output, not a hand-authored stages schema.
        from tests.test_dashboard_page import DashboardScriptTest
        task = self.taskfile('015-synthetic', '## Phase 1: User Story 1 - Synthetic (P1)\n- [x] T001\n- [ ] T002\n')
        for name in ('spec.md', 'plan.md', 'research.md', 'data-model.md', 'quickstart-results-local.md',
                     'review-code-us1.md', 'review-security-final.md', 'release-notes-1.md'):
            task.with_name(name).write_text('**Status**: Draft\nPRIVATE NEVER OUTPUT\n')
        self.document('spec.md', '**Status**: Draft\n', 'specs/016-synthetic')
        speckit = self.collect()
        shutil.rmtree(self.repo / 'specs')
        self.document('index.md', '| Title | Status |\n| --- | --- |\n'
                      '| [Synthetic](one.md) | In progress |\n| [Synthetic](two.md) | Released |\n')
        self.document('one.md', '# PRIVATE NEVER OUTPUT\n')
        self.document('two.md', '# PRIVATE NEVER OUTPUT\n')
        source_b = self.collect()
        data = json.loads((ROOT / 'tests/fixtures/status-sample.json').read_text())
        data['progress'] = {'repositories': {'aaaaaaaa': speckit, 'bbbbbbbb': source_b},
                            'active': [{'repo': code, 'label': 'Synthetic', 'hosts': ['codex'], 'sessions': 1,
                                        'last': '2026-11-06T10:00:00Z'} for code in ('aaaaaaaa', 'bbbbbbbb')]}
        page = DashboardScriptTest()
        out = page.render_freshness(data, {'hash': '#now'})
        self.assertEqual(len(page.marks(out, 'pipeline-chain')), 3)
        self.assertEqual([m['text'] for m in page.marks(out, 'pipeline-ordinal')], ['016', '015', '#1'])
        self.assertEqual([m['attrs']['data-stage'] for m in page.marks(out, 'pipeline-block')],
                         ['spec', 'spec', 'plan', 'design', 'tasks', 'verify', 'review', 'ship', 'spec'])
        self.assertEqual([m['text'] for m in page.marks(out, 'pipeline-finished')], ['✓ 1'])
        self.assertEqual(len(page.marks(out, 'pipeline-chevron')), 9)
        pane = ' '.join(m['text'] for m in page.marks(out, 'active-project'))
        for forbidden in ('undefined', 'untagged', 'PRIVATE', 'Synthetic](one.md)'):
            self.assertNotIn(forbidden, pane)

    def test_speckit_task_completion_needs_verification_and_started_join(self):
        task = self.taskfile(text='- [x] T1 US1\n')
        self.assertEqual(self.collect()['features'][0]['state'], 'active')
        task.with_name('quickstart-results.md').write_text('')
        self.assertEqual(self.collect()['features'][0]['state'], 'done')
        task.write_text('- [ ] T1 US1\n')
        starts = {'one': dict(project=self.repo.name, task='003 T1', ts='2026-11-06T09:00:00Z')}
        self.assertEqual(self.collect(starts=starts)['features'][0]['state'], 'active')
        self.assertEqual(self.collect()['features'][0]['state'], 'todo')

    def test_speckit_patterns_are_presence_only_and_ignore_non_regular_artifacts(self):
        task = self.taskfile()
        target = self.repo / 'target'
        target.write_text('private')
        for name in ('plan.md', 'research.md', 'quickstart-results-link.md', 'review-code-link.md', 'release-notes-link.md'):
            task.with_name(name).symlink_to(target)
        task.with_name('contracts').symlink_to(self.repo, target_is_directory=True)
        task.with_name('review-security-directory.md').mkdir()
        task.with_name('quickstart.md').write_text('')
        feature = self.collect()['features'][0]
        self.assertEqual([s['stage'] for s in feature['stages']], ['tasks'])
        self.assertFalse(feature['artifacts']['design'])
        self.assertEqual(feature['review_counts']['code'], 0)

    def test_package_ordinals_are_bounded_ascii_and_negations_are_unknown(self):
        text = '| # | Package | Status |\n| --- | --- | --- |\n' + ''.join(
            '| ' + value + ' | PRIVATE | implemented |\n' for value in ('²', '١', '1234567', '999999', '1'))
        self.assertEqual([r['ordinal'] for r in self.pp.package_rows(text, 80)], [999999, 1])
        for text in ('not released', 'not done', 'not yet merged', 'not implemented'):
            with self.subTest(text=text):
                self.assertEqual(self.pp.status_state(text), 'unknown')
                self.document('release.md', 'Status: ' + text + '\n| # | Package | Kind |\n| --- | --- | --- |\n| 1 | PRIVATE | fix |\n')
                got = self.collect()
                self.assertEqual(got['features'][0]['state'], 'unknown')
                self.assertEqual(got['features'][0]['packages'][0]['state'], 'unknown')

    def test_index_status_column_header_before_second_column_fallback(self):
        for header in ('Status', 'State'):
            self.document('index.md', '| Spec | Type | ' + header + ' |\n| --- | --- | --- |\n'
                          '| [PRIVATE](one.md) | implemented | in progress |\n')
            self.document('one.md', '# PRIVATE\n')
            self.assertEqual(self.collect()['features'][0]['state'], 'active')
        self.document('index.md', '| [PRIVATE](one.md) | deferred | implemented |\n')
        self.assertEqual(self.collect()['features'][0]['state'], 'deferred')

    def test_status_mapping_is_unknown_unless_stated_and_deferrals_remain_distinct(self):
        cases = {'Implemented for 0.1.7': 'done', 'merged; release pull request open': 'done',
                 'Released as 0.1.8': 'done', 'shipped': 'done', 'accepted': 'todo', 'done': 'done',
                 'In progress': 'active', 'In review': 'active', 'building': 'active', 'running locally': 'active',
                 'Spec; rule is merged; no pull request yet': 'active', 'Moved to 0.2.0 after merged work': 'deferred',
                 'deferred': 'deferred', 'See its verification and host limits': 'unknown', 'fix': 'unknown', '': 'unknown'}
        for text, state in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.pp.status_state(text), state)

    def test_repository_index_enriches_status_and_release_packages_without_leaking_text(self):
        self.document('index.md', '| Spec | Status |\n| --- | --- |\n'
            '| [PRIVATE TITLE](one.md) | See its verification and host limits |\n'
            '| [PRIVATE TITLE](two.md) | Spec |\n| [PRIVATE TITLE](release.md) | In progress |\n'
            '| [PRIVATE TITLE](three.md) | Nothing stated |\n')
        self.document('one.md', '# PRIVATE\nStatus: implemented for 0.1.7\n')
        self.document('two.md', '# PRIVATE\nStatus: owner decisions settled\n')
        self.document('three.md', '# PRIVATE\n')
        self.document('release.md', '# Release synthetic\nStatus: merged; release pull request open.\n'
            '| # | Package | Design | Status |\n| --- | --- | --- | --- |\n'
            '| 1 | PRIVATE | [PRIVATE](two.md) | Merged (pull request 97) |\n'
            '| 2 | PRIVATE | [PRIVATE](three.md) | Moved to 0.2.0 |\n'
            '\n| Wave | Dependencies | Files |\n| 0 | PRIVATE | PRIVATE |\n')
        result = self.collect()
        self.assertEqual((result['source'], result['recognition']), ('docs/specs', 'index'))
        self.assertEqual([f['state'] for f in result['features']], ['done', 'done', 'deferred', 'unknown'])
        release = result['features'][2]
        self.assertEqual([p['state'] for p in release['packages']], ['done', 'deferred'])
        self.assertEqual([s['stage'] for s in release['stages']], ['spec', 'packages'])
        self.assertEqual(result['ledger_join'], 'none')
        for private in ('PRIVATE', 'one.md', 'two.md', 'three.md', 'release.md', '0.2.0', 'pull request'):
            self.assertNotIn(private, json.dumps(result))

    def test_index_precedence_across_locations_and_safe_links(self):
        self.document('loose.md', 'Status: done\n')
        self.document('index.md', '| [A](pending.md) | In progress |\n'
                      '| [B](../outside.md) | done |\n| [C](/absolute.md) | done |\n', 'docs/spec')
        got = self.collect()
        self.assertEqual(got['source'], 'docs/spec')
        self.assertEqual(len(got['features']), 1)
        self.assertEqual(got['features'][0]['state'], 'active')

    def test_loose_documents_old_release_package_shape_and_released_floor(self):
        path = self.document('release.md', '# Release synthetic\n'
            '| # | Package | Kind |\n| --- | --- | --- |\n'
            '| 1 | PRIVATE | merged (pull request 58) |\n| 2 | PRIVATE | fix |\n| 3 | PRIVATE | deferred |\n')
        got = self.collect()
        self.assertEqual(got['recognition'], 'status')
        self.assertEqual([p['state'] for p in got['features'][0]['packages']], ['done', 'unknown', 'deferred'])
        path.write_text('Status: released as 0.1.8\n' + path.read_text())
        self.assertEqual([p['state'] for p in self.collect()['features'][0]['packages']], ['done'] * 3)
        self.assertTrue(self.collect()['done'])

    def test_ledger_exact_override_group_latest_outcome_strip_and_fallback(self):
        labels = ['PRIVATE task', 'PRIVATE task', 'PRIVATE active', 'PRIVATE blocked', 'PRIVATE cancelled', 'PRIVATE quota']
        starts = {str(i): dict(project='alias', task=label, ts='2026-11-06T09:%02d:00Z' % i) for i, label in enumerate(labels)}
        finishes = {'0': dict(outcome='error'), '1': dict(outcome='accepted'), '3': dict(outcome='blocked'),
                    '4': dict(outcome='cancelled'), '5': dict(outcome='quota')}
        self.assertEqual(self.collect(starts=starts, finishes=finishes)['source'], 'none')
        self.host.write_text('## Project progress\n- Ledger project: alias\n')
        self.assertEqual(self.collect(starts=starts, finishes=finishes)['source'], 'none')
        self.consent()
        self.pp.set_setting(self.repo, 'ledger', 'alias')
        got =self.collect(starts=starts, finishes=finishes)
        self.assertEqual(got['source'], 'ledger')
        self.assertEqual([f['ordinal'] for f in got['features']], [1, 2, 3, 4, 5])
        self.assertEqual(got['work'], dict(done=1, active=1, **{'needs-attention': 2}, deferred=1))
        self.assertNotIn('PRIVATE', json.dumps(got))
        self.assertNotIn('alias', json.dumps(got))
        self.document('one.md', '# PRIVATE\n')
        got = self.collect(starts=starts, finishes=finishes)
        self.assertEqual(got['source'], 'docs/specs')
        self.assertEqual(got['work']['done'], 1)
        self.taskfile()
        self.assertEqual(self.collect(starts=starts, finishes=finishes)['source'], 'speckit')
        self.assertEqual(self.pp.ledger_items('alias', starts, {'2': dict(outcome='needs-permission')})[1]['state'], 'needs-attention')

    def test_ledger_equal_timestamps_preserve_record_order_for_latest_attempt(self):
        starts = {ident: dict(project='alias', task='PRIVATE', ts='2026-11-06T09:00:00Z') for ident in ('z', 'a')}
        finishes = {'z': dict(outcome='error'), 'a': dict(outcome='accepted')}
        self.assertEqual(self.pp.ledger_items('alias', starts, finishes)[0]['state'], 'done')

    def test_repository_caps_oversize_symlinks_and_package_row_cap(self):
        for n in range(45):
            self.document('%02d.md' % n, 'Status: done\n')
        got = self.collect()
        self.assertEqual(len(got['features']), 40)
        self.assertIn('file limit', got['skipped'])
        first = self.repo / 'docs/specs/00.md'
        first.write_bytes(b'PRIVATE' * (64 * 1024 // 7 + 1))
        second = first.with_name('01.md')
        second.unlink()
        second.symlink_to(first)
        got = self.collect()
        self.assertEqual(len(got['features']), 39)  # next regular file fills symlink's slot
        self.assertIn('spec file skipped', got['skipped'])
        package = '# Release\n| # | Package | Kind |\n| --- | --- | --- |\n' + ''.join('| %d | PRIVATE | fix |\n' % n for n in range(1, 100))
        first.write_text(package)
        third = first.with_name('02.md')
        third.write_text(package)
        got = self.collect()
        self.assertEqual(sum(len(f.get('packages', [])) for f in got['features']), 80)
        self.assertNotIn('PRIVATE', json.dumps(got))

    def test_unrecognised_source_c_and_no_guessing_ledger_project(self):
        starts = {'one': dict(project='different', task='PRIVATE', ts='2026-11-06T09:00:00Z')}
        got = self.collect(starts=starts)
        self.assertEqual((got['source'], got['features'], got['work'], got['ledger_join']), ('none', [], {}, 'none'))

    def test_completion_percent_exact_cases(self):
        for done, total, expected in ((408, 410, 99), (56, 57, 98), (1, 3, 33),
                                      (2, 3, 66), (0, 5, 0), (5, 5, 100)):
            with self.subTest(done=done, total=total):
                self.assertEqual(self.pp.completion_percent(done, total), expected)

    def test_active_projects_deduplicate_and_count_24h_with_closed_metadata(self):
        from datetime import datetime, timedelta
        now = datetime(2026, 11, 6, 10).astimezone()
        def event(repo, sid, hours, host=None):
            row = dict(repo=repo, sid=sid, ts=(now - timedelta(hours=hours)).isoformat(), event='skill', name='private')
            if host:
                row.update(event='session_start', host=host)
            return row
        events = [event('aaaaaaaa', 'one', 1, 'codex'), event('aaaaaaaa', 'one', .2),
                  event('aaaaaaaa', 'two', 2, 'claude'), event('aaaaaaaa', 'yesterday', 12, 'antigravity'),
                  event('bbbbbbbb', 'one', 30, 'antigravity'), event('bbbbbbbb', 'one', 3), event('cccccccc', 'old', 24, 'codex'),
                  event('dddddddd', 'future', -1, 'codex'), event('eeeeeeee', 'unknown', 1, 'hostile'),
                  event('ffffffff', 'unnamed', .01, 'codex')]
        repos = {'aaaaaaaa': dict(features=[dict(done=408, total=410)])}
        labels = {'aaaaaaaa': 'Tools', 'bbbbbbbb': 'Other', 'eeeeeeee': 'Third'}
        result = self.pp.active_projects(events, repos, labels, now)
        self.assertEqual([r['repo'] for r in result], ['aaaaaaaa', 'eeeeeeee', 'bbbbbbbb'])
        row = result[0]
        self.assertEqual(set(row), {'repo', 'label', 'hosts', 'sessions', 'last', 'percent'})
        self.assertEqual(row['label'], 'Tools')
        self.assertEqual(row['sessions'], 3)
        self.assertEqual(row['hosts'], ['claude', 'codex', 'antigravity'])
        self.assertEqual(row['percent'], 99)
        self.assertEqual(result[1]['hosts'], [])
        self.assertIsNone(result[-1]['percent'])
        self.assertEqual(result[-1]['label'], 'Other')
        self.assertEqual(self.pp.active_projects(events, repos, {}, now), [])
        repos['aaaaaaaa']['features'][0]['done'] = 410
        self.assertIsNone(self.pp.active_projects(events, repos, labels, now)[0]['percent'])
        self.assertNotIn('private', json.dumps(result))
        many = [event('%08x' % n, 'same', n / 100, 'codex') for n in range(20)]
        self.assertEqual([r['repo'] for r in self.pp.active_projects(many, {}, {'%08x' % n: 'Named' for n in range(20)}, now)], ['%08x' % n for n in range(12)])
        self.assertEqual([r['repo'] for r in self.pp.active_projects(many, {}, {'%08x' % n: 'Named' for n in range(5, 20)}, now)], ['%08x' % n for n in range(5, 17)])

    def test_registration_reader_rejects_non_closed_or_unsafe_maps(self):
        state = self.data / 'state'
        state.mkdir(mode=0o700)
        path = state / 'projects.json'
        for bad in ([], {'not-code': 'Name'}, {'aaaaaaaa': ''}, {'aaaaaaaa': 'x' * 41},
                    {'aaaaaaaa': '<img>'}, {'aaaaaaaa': {'name': 'Name'}},
                    {'%08x' % n: 'Name' for n in range(51)}):
            path.write_text(json.dumps(bad))
            self.assertEqual(self.pp.registered_projects(), {})
        path.write_text('{bad json')
        self.assertEqual(self.pp.registered_projects(), {})
        path.write_text('{"aaaaaaaa": "Name"}')
        path.chmod(0o666)
        self.assertEqual(self.pp.registered_projects(), {})
        path.chmod(0o600)
        self.assertEqual(self.pp.registered_projects(), {'aaaaaaaa': 'Name'})
        path.unlink()
        target = state / 'other'
        target.write_text('{"aaaaaaaa": "Name"}')
        path.symlink_to(target)
        self.assertEqual(self.pp.registered_projects(), {})

    def test_registration_skips_empty_name_and_serialises_parallel_updates(self):
        from concurrent.futures import ThreadPoolExecutor
        blank = self.repo.parent / '   '
        (blank / '.git').mkdir(parents=True)
        self.pp.register_here(blank)
        self.assertFalse((self.data / 'state/projects.json').exists())
        repos = [self.repo.parent / ('parallel-%d' % n) for n in range(8)]
        for repo in repos:
            (repo / '.git').mkdir(parents=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(self.pp.register_here, repos))
        self.assertEqual(self.pp.registered_projects(), {self.pp.repository_code(repo): repo.name for repo in repos})
        self.assertFalse(list((self.data / 'state').glob('.write-*')))

    def test_label_worktree_code_matches_the_metrics_repository_identity(self):
        import hashlib
        main = self.repo
        metadata = main / '.git/worktrees/linked'
        metadata.mkdir(parents=True)
        (metadata / 'commondir').write_text('../..\n')
        linked = main.with_name('linked')
        linked.mkdir()
        (linked / '.git').write_text('gitdir: ' + str(metadata) + '\n')
        (metadata / 'gitdir').write_text(str(linked / '.git') + '\n')
        expected = hashlib.sha256(str(main).encode()).hexdigest()[:8]
        self.assertEqual(self.pp.repository_code(linked), expected)
        self.pp.set_label(linked, 'Shared project')
        self.assertEqual(self.stored()['label'], 'Shared project')
        self.assertFalse((linked / '.finolabs').exists())
        self.assertEqual(self.pp.project_label(linked), 'Shared project')
        self.assertNotIn('Shared project', self.host.read_text())

    def test_documented_infographics_metadata_and_setup(self):
        privacy = (ROOT / 'PRIVACY.md').read_text()
        for word in ('P1', 'P9', 'spec.md', 'specs/archive', 'settings.json', 'priority number'):
            self.assertIn(word, privacy)
        setup = (ROOT / 'skills/fnl-setup/references/features/project.md').read_text()
        self.assertIn('project_progress.py label --set', setup)
        self.assertIn('settings.json', setup)
        self.assertNotIn('## Project labels', (ROOT / 'skills/fnl-delegate/references/host-template.md').read_text())
        self.assertIn('[Dashboard infographics]', (ROOT / 'docs/specs/index.md').read_text())
        for doc in ('README.md', 'CHANGELOG.md', 'skills/fnl-status/SKILL.md'):
            for word in ('quota', 'overview', 'now'):
                self.assertIn(word, (ROOT / doc).read_text())

    def test_work_tracking_spec_documents_shipped_reader_limits(self):
        text = (ROOT / 'docs/specs/work-tracking.md').read_text().split('## E.')[1].split('## F.')[0]
        self.assertIn('(60 features, 200 entries)', text)
        self.assertIn('40 retained records', text)
        self.assertIn('200 surveyed directory entries', text)
        self.assertNotIn('20 features', text)

    def test_spec_uses_same_safe_read_and_sixty_feature_cap(self):
        for n in range(61):
            task = self.taskfile('%03d-safe' % n)
            task.with_name('spec.md').write_text('## User Story 1 (P2)\n')
        result = self.collect()
        self.assertEqual(len(result['features']), 60)
        self.assertIn('feature limit', result['skipped'])
        task = self.repo / 'specs/001-safe/spec.md'
        task.unlink()
        task.symlink_to(self.repo / 'specs/002-safe/spec.md')
        self.assertIsNone(self.collect()['features'][0]['stories'][0]['priority'])

    def test_parser_drops_everything_except_identifiers_and_numbers(self):
        text = ('# SECRET=secret\n## Phase 2: private heading\n'
                '- [x] T012 [US1] <img src=x>\u202e\x01 private\n'
                '- [ ] T1 [US2] ' + 'private' * 60 + '\n'
                '- [ ] T12345 ABT12 US1234\n- [ ] T0123 US\n'
                '- [ ] ' + 'z' * 81 + ' T9 US8\n'
                '### Phase 3\n- [X] T2 US2\n' + '- [ ] T8 ' + 'q' * 4096)
        got = self.pp.parse(text, 3)
        self.assertEqual(got['total'], 4)
        self.assertEqual(got['done'], 2)
        self.assertEqual(got['phases'], [{'phase': 2, 'done': 1, 'total': 3}, {'phase': 3, 'done': 1, 'total': 1}])
        self.assertEqual(got['stories'], [{'story': 'US1', 'done': 1, 'total': 1}, {'story': 'US2', 'done': 1, 'total': 2}])
        self.assertEqual([r['id'] for r in got['tasks']], ['T012', 'T1', 'T0123', 'T2'])
        raw = json.dumps(got)
        for word in ('private', 'SECRET', '<img', '\\u202e', '\\u0001', 'US1234', 'T12345', 'ABT12', 'qqqq'):
            self.assertNotIn(word, raw)
        self.assertEqual(len(self.pp.parse('\n'.join('- [ ] T%d' % i for i in range(300)), 1)['tasks']), 200)

    def test_reader_refuses_symlinks_fifo_size_owner_and_unsafe_paths(self):
        path = self.taskfile()
        self.assertEqual(self.collect()['features'][0]['total'], 1)
        self.consent()
        for configured in ('/etc/passwd', '../private', 'specs/../tasks.md'):
            # Neither the setter nor a host.md line can configure an unsafe path.
            with self.assertRaises(ValueError):
                self.pp.set_setting(self.repo, 'tasks', configured)
            self.host.write_text('## Project progress\n- Task file: ' + configured + '\n')
            self.assertNotIn('unsafe task path', self.collect()['skipped'])
        self.host.write_text('## Project progress\n- Project progress: on\n')
        path.unlink()
        os.mkfifo(path)
        began = time.monotonic()
        self.assertEqual(self.collect()['features'], [])
        self.assertLess(time.monotonic() - began, 1)
        path.unlink()
        path.write_bytes(b'x' * (512 * 1024 + 1))
        self.assertEqual(self.collect()['features'], [])
        path.write_text('- [ ] T1')
        real_fstat = os.fstat
        def wrong_owner(fd):
            info = real_fstat(fd)
            if stat.S_ISREG(info.st_mode) and info.st_ino == path.stat().st_ino:
                return SimpleNamespace(st_mode=info.st_mode, st_uid=os.getuid() + 1, st_size=info.st_size)
            return info
        with mock.patch.object(os, 'fstat', side_effect=wrong_owner):
            self.assertEqual(self.collect()['features'], [])
        target = path.with_name('real.md')
        path.rename(target)
        path.symlink_to(target)
        self.assertEqual(self.collect()['features'], [])
        path.unlink()
        target.rename(path)
        folder = path.parent
        folder.rename(self.repo / 'real')
        folder.symlink_to(self.repo / 'real', target_is_directory=True)
        self.assertEqual(self.collect()['features'], [])
        folder.unlink()
        (self.repo / 'real').rename(folder)
        specs = self.repo / 'specs'
        specs.rename(self.repo / 'actual')
        specs.symlink_to(self.repo / 'actual', target_is_directory=True)
        self.assertEqual(self.collect()['features'], [])
        alias = self.repo.with_name('alias')
        alias.symlink_to(self.repo, target_is_directory=True)
        self.assertIsNone(self.pp.find_root(alias))

    def test_walk_bounds_lists_files_ordinal_and_repository_config_ignored(self):
        nested = self.repo / 'nested/a'
        nested.mkdir(parents=True)
        self.assertEqual(self.pp.find_root(nested), self.repo)
        self.assertIsNone(self.pp.find_root(self.home))
        (self.repo / 'host.md').write_text('## Project progress\n- Task file: custom.md\n')
        (self.repo / 'custom.md').write_text('- [ ] T99')
        self.assertEqual(self.collect()['features'], [])
        self.host.write_text('## Project progress\n- Task file: custom.md\n')
        self.assertEqual(self.collect()['features'], [])
        self.consent()
        self.pp.set_setting(self.repo, 'tasks', 'custom.md')
        self.assertEqual(self.collect()['features'][0]['feature'], 1)
        self.pp.set_setting(self.repo, 'tasks', None)
        self.host.write_text('## Project progress\n- Project progress: on\n')
        for n in range(21):
            self.taskfile('%03d-private' % n)
        self.assertEqual(len(self.collect()['features']), 21)
        for n in range(201):
            (self.repo / 'specs' / ('junk%d' % n)).mkdir()
        self.assertIn('entry limit', self.collect()['skipped'])

    def test_deadline_interrupts_read_and_never_leaks_partial_data(self):
        self.taskfile()
        with mock.patch.object(self.pp, 'read_task', side_effect=lambda *a: time.sleep(2)):
            began = time.monotonic()
            result = self.collect()
            self.assertLess(time.monotonic() - began, 1.3)
            self.assertEqual(result['reason'], 'progress timed out')
            self.assertEqual(result['features'], [])

    def test_join_exact_project_feature_task_ranges_states_dispatch_and_manual_session(self):
        for feature in ('003-private', '004-private'):
            self.taskfile(feature, '- [ ] T1 US1\n- [ ] T012 US1\n- [x] T2\n- [ ] T3\n- [ ] T4\n')
        starts = {key: dict(project=self.repo.name, task=label, agent='codex', model='good-model', ts='2026-11-06T09:00:00Z')
                  for key, label in [('d1', '003 T12'), ('d2', '003 T1 T2'), ('d3', '003 T3-T4'),
                                     ('d4', 'T12'), ('d5', '003 no task'), ('d6', '004 T12'),
                                     ('d7', '003 T12')]}
        starts['d7']['project'] = 'other-project'
        starts['d2']['model'] = '<img secret>'
        finishes = {'d2': dict(outcome='accepted', ts='2026-11-06T09:05:00Z', rework_rounds=1),
                    'd3': dict(outcome='rejected', ts='2026-11-06T09:06:00Z', rework_rounds=0)}
        events = [dict(repo='aaaaaaaa', sid='session-private', event='session_start', host='claude', dispatch='d1', ts='2026-11-06T09:00:00Z'),
                  dict(repo='aaaaaaaa', sid='manual-session', event='session_start', host='codex', dispatch=None, ts='2026-11-06T09:00:00Z'),
                  dict(repo='aaaaaaaa', sid='manual-session', event='task', id='T3', ts='2026-11-06T09:01:00Z')]
        result = self.collect(starts=starts, finishes=finishes, events=events)
        one, two = result['features']
        self.assertEqual([r['state'] for r in one['tasks']], ['accepted, not ticked', 'in progress', 'done', 'todo', 'todo'])
        self.assertEqual(one['tasks'][1]['runs'][0]['id'], 'd1')
        self.assertEqual(one['tasks'][1]['sessions'][0]['host'], 'claude')
        self.assertEqual(two['tasks'][1]['runs'][0]['id'], 'd6')
        # Task receipts have no feature: duplicate ids across features stay unlinked.
        self.assertEqual(one['tasks'][3]['sessions'], [])
        self.assertEqual(result['labels_without_feature'], 1)
        self.assertEqual(result['unlinked_runs'], 2)
        self.assertEqual(one['tasks'][0]['runs'][0]['model'], 'other')
        self.assertNotIn('secret', json.dumps(result))
        (self.repo / 'specs/004-private/tasks.md').unlink()
        result = self.collect(starts=starts, finishes=finishes, events=events)
        self.assertEqual(result['features'][0]['tasks'][3]['sessions'][0]['host'], 'codex')
        self.assertEqual(self.pp.label_ids('003 T1-T99')[1], set())
        self.assertEqual(self.pp.label_ids('003 T1 T12')[1], {1, 12})

    def test_configured_feature_and_project_alias(self):
        path = self.repo / 'custom/007-private/tasks.md'
        path.parent.mkdir(parents=True)
        path.write_text('- [ ] T012 US1 private\n')
        self.consent()
        self.pp.set_setting(self.repo, 'tasks', 'custom/007-private/tasks.md')
        self.pp.set_setting(self.repo, 'ledger', 'alias')
        run =dict(project='alias', task='007 T12', agent='codex', model='m', ts='2026-11-06T09:00:00Z')
        result = self.collect(starts={'d1': run})
        self.assertEqual(result['features'][0]['feature'], 7)
        self.assertEqual(result['features'][0]['tasks'][0]['runs'][0]['id'], 'd1')
        self.assertNotIn('private', json.dumps(result))
    def test_prefix_boundary_never_turns_a_cut_token_into_a_shorter_id(self):
        # A token cut by the 80-character window must not become a shorter id.
        result = self.pp.parse('- [ ] ' + ' ' * 77 + 'T0123\n- [ ] T2 ' + ' ' * 74 + 'US12', 1)
        self.assertEqual([t['id'] for t in result['tasks']], ['T2'])
        self.assertIsNone(result['tasks'][0]['story'])

    def test_consent_canonical_section_default_off_unresolved_and_switch(self):
        self.assertTrue(self.pp.enabled())
        self.host.write_text('# resolved host, no progress section\n')
        self.assertTrue(self.pp.enabled())
        self.host.unlink()
        self.assertFalse(self.pp.enabled())
        for body in ('## Project progress\n- Project progress: off\n',
                     '## Project progress\n- Project progress: on\n## Project progress\n- Project progress: on\n',
                     '```\n## Project progress\n- Project progress: on\n',
                     '## Project progress\n- Project progress: maybe\n'):
            self.host.write_text(body)
            self.assertFalse(self.pp.enabled())
        self.host.write_text('# host\n## Agent snapshot\n- Snapshot: on\n\n## Project progress\n- Task file: custom.md\n- Ledger project: alias\n')
        before = self.host.read_text().split('## Project progress')[0]
        self.pp.configure('off', yes=True)
        self.assertFalse(self.pp.enabled())
        self.assertTrue(self.host.read_text().startswith(before))
        self.assertIn('Task file: custom.md', self.host.read_text())
        self.pp.configure('on', yes=True)
        self.assertTrue(self.pp.enabled())
        with mock.patch.dict(os.environ, {'FNL_PROGRESS': 'off'}):
            self.assertFalse(self.pp.enabled())
        with self.assertRaises(ValueError):
            self.pp.configure('off')

    def test_shared_copies_and_documented_consent_limits_and_ledger_labels(self):
        raw = (ROOT / 'scripts/project_progress.py').read_bytes()
        for relative in ('skills/fnl-status/scripts/project_progress.py', 'skills/fnl-setup/scripts/project_progress.py'):
            self.assertEqual(raw, (ROOT / relative).read_bytes())
        metrics = (ROOT / 'skills/fnl-setup/references/features/metrics.md').read_text()
        for value in ('project progress', 'FNL_PROGRESS=off', '... off --yes', 'if the root cannot be resolved it is off'):
            self.assertIn(value, metrics)
        project = (ROOT / 'skills/fnl-setup/references/features/project.md').read_text()
        self.assertIn('project-settings.md', project)
        settings = (ROOT / 'skills/fnl-setup/references/project-settings.md').read_text()
        for value in ('Task file:', 'Ledger project:', 'no longer read', 'settings.json'):
            self.assertIn(value, settings)
        for name in ('PRIVACY.md', 'README.md', 'CHANGELOG.md', 'skills/fnl-status/SKILL.md'):
            self.assertIn('FNL_PROGRESS=off', (ROOT / name).read_text())
        self.assertIn('<feature> T<id>', (ROOT / 'skills/fnl-delegate/references/ledger.md').read_text())
        self.assertIn('implemented', (ROOT / 'docs/specs/index.md').read_text().split('[Project progress]')[1].split('\n')[0])

    def test_notice_channels_once_version_fixed_content_and_no_events(self):
        for channel in ('dashboard', 'session'):
            self.assertTrue(self.pp.notice(channel, '0.1.10-dev'))
            self.assertFalse(self.pp.notice(channel, '0.1.10-dev'))
            self.assertEqual(self.pp.notice(channel, '0.1.11-dev'), channel == 'session')
        self.assertTrue((self.data / 'state/notices.json').is_file())
        self.assertEqual(list((self.data / 'state').glob('events*')), [])


class SettingsFileTest(unittest.TestCase):
    """Project settings live in <main checkout>/.finolabs/vibecode/settings.json, bound to an approved digest."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.home = account(self, base / 'home')
        self.data = self.home / '.finolabs/vibecode'
        self.data.mkdir(parents=True)
        self.host = self.data / 'host.md'
        self.host.write_text('# Host\n\n## Project progress\n\n- Project progress: on\n')
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(os.environ, {'FNL_PROGRESS': '', 'FNL_METRICS': ''}).start()
        self.pp = module('project_progress_file', ROOT / 'scripts/project_progress.py')
        self.slots = module('parallel_slots_file', ROOT / 'scripts/parallel_slots.py')
        self.repo = base / 'one'
        self.other = base / 'two'
        for repo in (self.repo, self.other):
            (repo / '.git/info').mkdir(parents=True)
        state = self.data / 'state'
        state.mkdir()
        (state / 'consent.json').write_text(json.dumps(dict(date='2026-11-06', retention_days=30)))

    def file(self, root=None):
        return (root or self.repo) / '.finolabs/vibecode/settings.json'

    def approval(self, root=None):
        return self.data / 'state/settings-approved' / (self.pp.repository_code(root or self.repo) + '.json')

    def settings(self, root=None):
        return self.pp.repository_settings({}, root or self.repo)

    def test_setters_write_the_project_file_and_its_approval_and_leave_host_identical(self):
        before = self.host.read_bytes()
        self.assertTrue(self.pp.set_setting(self.repo, 'ledger', 'Alias'))
        self.assertTrue(self.pp.set_setting(self.repo, 'tasks', 'docs/tasks.md'))
        self.assertTrue(self.pp.set_setting(self.repo, 'parallel', '5'))
        self.assertTrue(self.pp.set_setting(self.repo, 'parallel-caps', 'codex=2'))
        self.pp.set_label(self.repo, 'Synthetic label')
        self.assertEqual(self.host.read_bytes(), before)
        data = json.loads(self.file().read_text())
        self.assertEqual(data, {'version': 1, 'ledger': 'Alias', 'tasks': 'docs/tasks.md', 'parallel': '5',
                                'parallel-caps': 'codex=2', 'label': 'Synthetic label'})
        self.assertEqual(stat.S_IMODE(self.file().stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.file().parent.stat().st_mode), 0o700)
        self.assertTrue(self.approval().is_file())
        self.assertEqual(self.settings(), {'Ledger project': 'Alias', 'Task file': 'docs/tasks.md'})
        self.assertEqual(self.slots.parse_config('', self.repo)['limit'], 5)
        self.assertEqual(self.slots.parse_config('', self.repo)['caps']['codex'], 2)
        self.assertEqual(self.slots.parse_config('', self.repo)['scope']['project'], 'Alias')
        for key in ('ledger', 'tasks', 'parallel', 'parallel-caps'):
            self.assertTrue(self.pp.set_setting(self.repo, key, None))
            self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(json.loads(self.file().read_text()), {'version': 1, 'label': 'Synthetic label'})
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual((self.repo / '.git/info/exclude').read_text().count('.finolabs/'), 1)
        self.assertFalse((self.repo / '.gitignore').exists())

    def test_the_cli_writes_the_file_and_never_echoes_values(self):
        import io
        before = self.host.read_bytes()
        with mock.patch('os.getcwd', return_value=str(self.repo)), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(self.pp.main(['settings', '--set', 'parallel=4']), 0)
            self.assertEqual(self.pp.main(['label', '--set', 'PRIVATE label']), 0)
        self.assertNotIn('PRIVATE', out.getvalue())
        self.assertEqual(json.loads(self.file().read_text())['parallel'], '4')
        self.assertEqual(self.host.read_bytes(), before)

    def test_ledger_and_tasks_still_need_metrics_consent(self):
        (self.data / 'state/consent.json').unlink()
        for key, value in (('ledger', 'Alias'), ('tasks', 'docs/t.md')):
            with self.assertRaises(ValueError):
                self.pp.set_setting(self.repo, key, value)
        self.assertFalse(self.file().exists())
        self.assertTrue(self.pp.set_setting(self.repo, 'parallel', '2'))

    def test_two_repositories_keep_separate_files(self):
        self.pp.set_setting(self.repo, 'parallel', '6')
        self.pp.set_setting(self.other, 'ledger', 'Other')
        self.assertEqual(json.loads(self.file().read_text()), {'version': 1, 'parallel': '6'})
        self.assertEqual(json.loads(self.file(self.other).read_text()), {'version': 1, 'ledger': 'Other'})
        self.assertEqual(self.slots.parse_config('', self.other)['limit'], 3)
        self.assertEqual(self.settings(self.repo), {})
        self.assertNotEqual(self.approval(), self.approval(self.other))

    def test_a_linked_worktree_uses_the_main_checkouts_file(self):
        gitdir = self.repo / '.git/worktrees/side'
        gitdir.mkdir(parents=True)
        (gitdir / 'commondir').write_text('../..\n')
        linked = self.repo.parent / 'linked'
        linked.mkdir()
        (linked / '.git').write_text('gitdir: %s\n' % gitdir)
        (gitdir / 'gitdir').write_text(str(linked / '.git') + '\n')
        self.pp.set_setting(linked, 'parallel', '7')
        self.assertTrue(self.file().is_file())
        self.assertFalse((linked / '.finolabs').exists())
        self.assertEqual(self.slots.parse_config('', self.repo)['limit'], 7)
        self.assertEqual(self.slots.parse_config('', linked)['limit'], 7)

    def test_host_sections_are_never_read(self):
        code = self.pp.repository_code(self.repo)
        self.host.write_text('# Host\n\n## Project progress\n\n- Project progress: on\n- Ledger project: Old\n'
                             '- Task file: old.md\n\n## Project settings\n\n- %s parallel: 9\n- %s ledger: Host\n'
                             '- %s tasks: host.md\n\n## Project labels\n\n- %s: Host label\n' % (code, code, code, code))
        self.assertEqual(self.settings(), {})
        config = self.slots.parse_config(self.host.read_text(), self.repo)
        self.assertEqual((config['limit'], config['source'], config['scope']['project']), (3, 'default', 'one'))
        self.assertIsNotNone(self.pp.config())
        self.assertNotIn('Ledger project', self.pp.config())
        self.assertFalse(hasattr(self.pp, 'project_settings'))
        self.assertFalse(hasattr(self.pp, 'project_labels'))
        result = self.pp.collect(self.repo, code)
        self.assertEqual(result['label'], '')
        self.assertEqual(result['ledger_join'], 'none')

    def test_an_unapproved_or_edited_file_cannot_raise_parallel_or_redirect_tasks(self):
        self.pp.set_setting(self.repo, 'parallel', '2')
        (self.repo / 'docs').mkdir()
        (self.repo / 'docs/evil.md').write_text('- [ ] T1 private\n')
        edited = json.dumps({'version': 1, 'parallel': '32', 'tasks': 'docs/evil.md'}).encode()
        for case in ('edited', 'no approval', 'branch'):
            with self.subTest(case=case):
                self.file().write_bytes(edited)
                if case == 'no approval':
                    self.approval().unlink(missing_ok=True)
                self.assertEqual(self.slots.parse_config('', self.repo)['limit'], 3)
                self.assertEqual(self.settings(), {})
                self.assertNotEqual(self.pp.collect(self.repo, 'aaaaaaaa').get('source'), 'checkbox')
        # A setter starts from what readers see, so the edited values are not carried forward.
        self.pp.set_setting(self.repo, 'parallel', '4')
        self.assertEqual(json.loads(self.file().read_text()), {'version': 1, 'parallel': '4'})

    def test_unsafe_or_invalid_files_read_as_unset(self):
        self.pp.set_setting(self.repo, 'parallel', '4')
        os.chmod(self.file(), 0o620)
        self.assertEqual(self.slots.parse_config('', self.repo)['limit'], 3)
        os.chmod(self.file(), 0o600)
        self.assertEqual(self.slots.parse_config('', self.repo)['limit'], 4)
        import hashlib
        for raw in (b'{"version": 1, "parallel": "33"}', b'{"version": 2}', b'{"version": 1, "other": "x"}',
                    b'{"version": 1, "parallel": 4}', b'{"version": 1, "parallel": "4", "parallel": "5"}', b'[]'):
            with self.subTest(raw=raw):
                self.file().write_bytes(raw)
                self.approval().write_text(json.dumps({'sha256': hashlib.sha256(raw).hexdigest(), 'approved': 1}))
                self.assertEqual(self.slots.parse_config('', self.repo)['limit'], 3)

    def test_defaults_when_nothing_is_set(self):
        config = self.slots.parse_config('', self.repo)
        self.assertEqual((config['limit'], config['source'], config['scope']['project']), (3, 'default', 'one'))
        self.assertEqual(config['caps'], {'claude': None, 'codex': None, 'antigravity': None})
        self.assertEqual(self.settings(), {})
        self.assertEqual(self.slots.parse_config('', None)['limit'], 3)
        with mock.patch('os.getcwd', return_value=str(self.home)):
            self.assertTrue(self.slots.summary().startswith('3 free of 3'))
        self.assertEqual(self.pp.collect(self.home, None)['reason'], 'no repository')


class IdentityTest(unittest.TestCase):
    """Validated repository identity: only a reciprocal linked worktree borrows the main checkout's code."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.main = self.base / 'main'
        (self.main / '.git').mkdir(parents=True)
        self.pp = module('project_progress_identity', ROOT / 'scripts/project_progress.py')
        self.slots = module('parallel_slots_identity', ROOT / 'scripts/parallel_slots.py')
        self.checks = module('checks_list_identity', ROOT / 'scripts/checks_list.py')

    def own(self, root):
        import hashlib
        return hashlib.sha256(str(root).encode('utf-8')).hexdigest()[:8]

    def codes(self, root):
        return {self.pp.repository_code(root), self.slots.repository_code(root),
                self.checks.code_of(self.checks.layout(root)[0])}

    def link(self, name, gitdir, commondir='../..', back=None):
        linked = self.base / name
        linked.mkdir(exist_ok=True)
        (linked / '.git').write_text('gitdir: %s\n' % gitdir)
        gitdir.mkdir(parents=True, exist_ok=True)
        (gitdir / 'commondir').write_text(commondir + '\n')
        (gitdir / 'gitdir').write_text(str(back or linked / '.git') + '\n')
        return linked

    def test_a_real_git_worktree_keeps_the_main_checkouts_code(self):
        import subprocess
        shutil.rmtree(self.main / '.git')
        env = {'HOME': str(self.base), 'PATH': os.defpath + ':/usr/local/bin:/opt/homebrew/bin',
               'GIT_CONFIG_NOSYSTEM': '1'}

        def git(*argv):
            subprocess.run(['git', *argv], cwd=self.main, env=env, capture_output=True, check=True)
        git('init', '-q', '-b', 'main')
        git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com', 'commit', '-q',
            '--allow-empty', '-m', 'Start')
        git('worktree', 'add', '-q', str(self.base / 'linked'), '-b', 'side')
        self.assertEqual(self.codes(self.main), {self.own(self.main)})
        self.assertEqual(self.codes(self.base / 'linked'), {self.own(self.main)})
        self.assertEqual(self.checks.layout(self.base / 'linked'), (self.main, self.main / '.git'))

    def test_a_reciprocal_layout_without_git_keeps_the_main_code(self):
        linked = self.link('linked', self.main / '.git/worktrees/linked')
        self.assertEqual(self.codes(linked), {self.own(self.main)})

    def test_a_mismatched_back_pointer_falls_back_to_the_own_root(self):
        real = self.link('real', self.main / '.git/worktrees/real')
        intruder = self.base / 'intruder'
        intruder.mkdir()
        (intruder / '.git').write_text('gitdir: %s\n' % (self.main / '.git/worktrees/real'))
        self.assertEqual(self.codes(real), {self.own(self.main)})
        self.assertEqual(self.codes(intruder), {self.own(intruder)})
        self.assertEqual(self.checks.layout(intruder)[0], intruder)

    def test_a_fake_metadata_folder_cannot_borrow_another_repositorys_code(self):
        for name, gitdir, commondir in (
                ('borrow', self.base / 'borrow/meta/.git/worktrees/x', str(self.main / '.git')),
                ('inside', self.base / 'inside/meta/.git/worktrees/x', '../..'),
                ('flat', self.base / 'flat-meta/worktrees/x', str(self.main / '.git')),
                ('named', self.base / 'named-meta/x', '..')):
            with self.subTest(name=name):
                linked = self.link(name, gitdir, commondir, back=self.base / name / '.git')
                self.assertEqual(self.codes(linked), {self.own(linked)})
                self.assertEqual(self.checks.layout(linked)[0], linked)


if __name__ == '__main__':
    unittest.main()
