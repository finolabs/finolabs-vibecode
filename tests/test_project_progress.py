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
        with mock.patch.object(self.pp, 'repository_code', return_value='aaaaaaaa'):
            self.pp.set_label(self.repo, 'Fino tools-2.0')
        self.assertIn('## Project labels', self.host.read_text())
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

    def test_status_mapping_is_unknown_unless_stated_and_deferrals_remain_distinct(self):
        cases = {'Implemented for 0.1.7': 'done', 'merged; release pull request open': 'done',
                 'Released as 0.1.8': 'done', 'shipped': 'done', 'accepted': 'done', 'done': 'done',
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
        got = self.collect(starts=starts, finishes=finishes)
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
        expected = hashlib.sha256(str(main).encode()).hexdigest()[:8]
        self.assertEqual(self.pp.repository_code(linked), expected)
        self.pp.set_label(linked, 'Shared project')
        self.assertIn('- ' + expected + ': Shared project', self.host.read_text())

    def test_documented_infographics_metadata_and_setup(self):
        privacy = (ROOT / 'PRIVACY.md').read_text()
        for word in ('P1', 'P9', 'spec.md', 'specs/archive', 'Project labels', 'priority number'):
            self.assertIn(word, privacy)
        setup = (ROOT / 'skills/fnl-setup/SKILL.md').read_text()
        self.assertIn('project_progress.py label --set', setup)
        self.assertIn('## Project labels', setup)
        self.assertIn('## Project labels', (ROOT / 'skills/fnl-delegate/references/host-template.md').read_text())
        self.assertIn('[Dashboard infographics]', (ROOT / 'docs/specs/index.md').read_text())
        for doc in ('README.md', 'CHANGELOG.md', 'skills/fnl-status/SKILL.md'):
            for word in ('quota', 'overview', 'now'):
                self.assertIn(word, (ROOT / doc).read_text())

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
        self.host.write_text('## Project progress\n- Task file: custom/007-private/tasks.md\n- Ledger project: alias\n')
        run = dict(project='alias', task='007 T12', agent='codex', model='m', ts='2026-11-06T09:00:00Z')
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
        setup = (ROOT / 'skills/fnl-setup/SKILL.md').read_text()
        for value in ('project progress', 'Task file:', 'Ledger project:', 'FNL_PROGRESS=off', 'project_progress.py off --yes', 'if it cannot be resolved it is off'):
            self.assertIn(value, setup)
        for name in ('PRIVACY.md', 'README.md', 'CHANGELOG.md', 'skills/fnl-status/SKILL.md'):
            self.assertIn('FNL_PROGRESS=off', (ROOT / name).read_text())
        self.assertIn('<feature> T<id>', (ROOT / 'skills/fnl-delegate/references/ledger.md').read_text())
        self.assertIn('Implemented', (ROOT / 'docs/specs/index.md').read_text().split('[Project progress]')[1].split('\n')[0])

    def test_notice_channels_once_version_fixed_content_and_no_events(self):
        for channel in ('dashboard', 'session'):
            self.assertTrue(self.pp.notice(channel, '0.1.10-dev'))
            self.assertFalse(self.pp.notice(channel, '0.1.10-dev'))
            self.assertEqual(self.pp.notice(channel, '0.1.11-dev'), channel == 'session')
        self.assertTrue((self.data / 'state/notices.json').is_file())
        self.assertEqual(list((self.data / 'state').glob('events*')), [])


if __name__ == '__main__':
    unittest.main()
