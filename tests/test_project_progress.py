"""Project progress acceptance: synthetic account, files, records and clock only."""
import importlib.util
import json
import os
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
        for configured in ('/etc/passwd', '../private', 'specs/../tasks.md'):
            self.host.write_text('## Project progress\n- Task file: ' + configured + '\n')
            self.assertIn('unsafe task path', self.collect()['skipped'])
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
        self.assertEqual(self.collect()['features'][0]['feature'], 1)
        self.host.write_text('## Project progress\n- Project progress: on\n')
        for n in range(21):
            self.taskfile('%03d-private' % n)
        self.assertEqual(len(self.collect()['features']), 20)
        self.assertIn('file limit', self.collect()['skipped'])
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

    def test_notice_channels_once_version_fixed_content_and_no_events(self):
        for channel in ('dashboard', 'session'):
            self.assertTrue(self.pp.notice(channel, '0.1.10-dev'))
            self.assertFalse(self.pp.notice(channel, '0.1.10-dev'))
            self.assertEqual(self.pp.notice(channel, '0.1.11-dev'), channel == 'session')
        self.assertTrue((self.data / 'state/notices.json').is_file())
        self.assertEqual(list((self.data / 'state').glob('events*')), [])


if __name__ == '__main__':
    unittest.main()
