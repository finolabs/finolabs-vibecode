"""Tests for skills/fnl-status/scripts/refresh.py: the six metrics from a fixture store and ledger, and the files it writes."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tests.data_root_fixture import account
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
REFRESH = ROOT / "skills/fnl-status/scripts/refresh.py"
LEDGER = ROOT / "skills/fnl-delegate/scripts/ledger.py"
PAGE = ROOT / "skills/fnl-status/assets/dashboard.html"
X, Y = "aaaaaaaa", "bbbbbbbb"


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / "home")
        self.dir = self.home / ".finolabs/vibecode/state"
        self.ledger = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.ledger.parent.mkdir(parents=True)
        self.env = {**os.environ, "HOME": str(self.home), "FNL_STATE_DIR": str(self.dir), "ORCHESTRATION_LEDGER": str(self.ledger)}
        self.env.pop("FNL_METRICS", None)
        self.at = datetime.now(timezone.utc)

    def refresh(self, *args, check=True):
        result = subprocess.run([sys.executable, "-I", str(REFRESH), *args], capture_output=True, text=True, env=self.env)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_progress_local_metadata_consent_refresh_overwrite_and_purge(self):
        repo = Path(self.tmp.name).resolve() / 'private-project'
        repo.mkdir()
        (repo / '.git').mkdir()
        tasks = repo / 'specs/003-private/tasks.md'
        tasks.parent.mkdir(parents=True)
        tasks.write_text('## Phase 1: secret\n- [ ] T012 US1 private <script>\n')
        self.ledger.parent.joinpath('host.md').write_text('## Project progress\n- Project progress: on\n')
        def run():
            result = subprocess.run([sys.executable, '-I', str(REFRESH), 'run'], cwd=repo,
                                    capture_output=True, text=True, env=self.env)
            self.assertEqual(result.returncode, 0, result.stderr)
            return self.data().get('progress')
        self.assertIsNone(run())
        self.consent()
        self.write_events([self.event(0, 's', X, 'task', id='T012')])
        events = {p: p.read_bytes() for p in self.dir.glob('events-*.jsonl')}
        block = run()
        self.assertRegex(block['current'], r'^[0-9a-f]{8}$')
        self.assertLessEqual(len(block['repositories']), 5)
        current = block['repositories'][block['current']]
        self.assertEqual(current['features'][0]['tasks'][0]['id'], 'T012')
        self.assertTrue(block['notice'])
        self.assertNotIn('secret', json.dumps(block))
        self.assertNotIn('<script>', json.dumps(block))
        tasks.write_text('- [x] T012 US1\n')
        block = run()
        self.assertFalse(block['notice'])
        self.assertEqual(block['repositories'][block['current']]['features'][0]['done'], 1)
        self.assertEqual({p: p.read_bytes() for p in events}, events)
        self.env['FNL_PROGRESS'] = 'off'
        self.assertIsNone(run())
        self.env.pop('FNL_PROGRESS')
        self.refresh('purge', '--yes')
        self.assertFalse((self.dir / 'data.js').exists())

    def test_pipeline_data_js_privacy_and_retained_metadata_from_real_shaped_documents(self):
        self.consent()
        self.ledger.parent.joinpath('host.md').write_text('## Project progress\n- Ledger project: synthetic-alias\n')
        repo = Path(self.tmp.name).resolve() / 'synthetic-folder'
        (repo / '.git').mkdir(parents=True)
        docs = repo / 'docs/specs'
        docs.mkdir(parents=True)
        (docs / 'index.md').write_text('| Spec | Status |\n| --- | --- |\n'
            '| [PRIVATE TITLE](alpha.md) | PRIVATE no status |\n| [PRIVATE TITLE](release.md) | In progress |\n')
        (docs / 'alpha.md').write_text('# PRIVATE TITLE\nStatus: owner decisions settled PRIVATE\n')
        (docs / 'release.md').write_text('# Release PRIVATE TITLE\nStatus: merged; release pull request open.\n'
            '| # | Package | Design | Status |\n| --- | --- | --- | --- |\n'
            '| 1 | PRIVATE TITLE | [PRIVATE](alpha.md) | merged (pull request 97) |\n'
            '| 2 | PRIVATE TITLE | PRIVATE | moved to 0.2.0 |\n')
        self.ledger.write_text('\n'.join(json.dumps(row) for row in [
            dict(event='start', id='one', ts=self.at.isoformat(), project='synthetic-alias', task='PRIVATE LABEL',
                 kind='implement', grade='hard', agent='codex', model='m', reason='routing'),
            dict(event='finish', id='one', ts=self.at.isoformat(), outcome='accepted', rework_rounds=0)]) + '\n')
        self.refresh('run', '--cwd', str(repo))
        data = self.data()
        code = data['progress']['current']
        project = data['progress']['repositories'][code]
        self.assertEqual((project['source'], project['recognition'], project['ledger_join']), ('docs/specs', 'index', 'configured'))
        self.assertEqual(project['work'], {'done': 1})
        self.assertEqual([f['state'] for f in project['features']], ['done', 'deferred'])
        raw = (self.dir / 'data.js').read_text()
        for private in ('PRIVATE', 'alpha.md', 'release.md', 'owner decisions', 'synthetic-alias', str(repo)):
            self.assertNotIn(private, raw)
        self.refresh('run', '--cwd', str(repo.parent))
        carried = self.data()['progress']['repositories'][code]
        self.assertEqual(carried['features'], project['features'])
        for key in ('source', 'recognition', 'ledger_join', 'work'):
            self.assertEqual(carried[key], project[key])
        # A second repository's Spec Kit snapshot also retains its artefact/hint metadata.
        other = repo.parent / 'synthetic-second'
        (other / '.git').mkdir(parents=True)
        feature = other / 'specs/016-synthetic'
        feature.mkdir(parents=True)
        (feature / 'spec.md').write_text('**Status**: Draft\nPRIVATE\n')
        (feature / 'plan.md').write_text('PRIVATE\n')
        (feature / 'research.md').write_text('PRIVATE\n')
        (feature / 'review-code-final.md').write_text('PRIVATE\n')
        self.refresh('run', '--cwd', str(other))
        second_code = self.data()['progress']['current']
        second = self.data()['progress']['repositories'][second_code]
        self.refresh('run', '--cwd', str(repo.parent))
        carried = self.data()['progress']['repositories'][second_code]
        self.assertEqual(carried['features'], second['features'])
        self.assertNotIn('PRIVATE', (self.dir / 'data.js').read_text())

    def test_previous_projects_retains_fixed_progress_failure_reasons(self):
        self.consent()
        self.ledger.parent.joinpath('host.md').write_text('# Host\n')
        for reason in ('progress timed out', 'progress unavailable', 'no repository'):
            data = {'progress': {'repositories': {'aaaaaaaa': {'features': [], 'reason': reason}}}}
            (self.dir / 'data.js').write_text('window.FNL_DATA = ' + json.dumps(data) + ';\n')
            self.refresh('run', '--cwd', str(Path(self.tmp.name).resolve()))
            self.assertEqual(self.data()['progress']['repositories']['aaaaaaaa']['reason'], reason)

    def test_work_record_data_privacy_retention_and_closed_marks(self):
        self.consent()
        repo = Path(self.tmp.name).resolve() / 'repo'
        (repo / '.git').mkdir(parents=True)
        docs = repo / 'docs/specs'
        docs.mkdir(parents=True)
        (docs / 'PRIVATE.md').write_text('# PRIVATE title\nStatus: in progress; PRIVATE\n'
            '## Goal and acceptance\n- [x] AC1 PRIVATE\n## Plan\nPRIVATE\n'
            '## Tasks\n- [x] T1 PRIVATE\n## Evidence\nPRIVATE command\n')
        code = __import__('hashlib').sha256(str(repo).encode()).hexdigest()[:8]
        self.ledger.parent.joinpath('host.md').write_text('## Project settings\n- ' + code + ' ledger: PRIVATE alias\n'
                                                       '- ' + code + ' tasks: PRIVATE.md\n')
        self.write_events([self.event(0, 's', X, 'session_start', host='codex')])
        events_before = {path: path.read_bytes() for path in self.dir.glob('events-*.jsonl')}
        self.refresh('run', '--cwd', str(repo))
        original = self.data()
        project = original['progress']['repositories'][code]
        self.assertEqual(project['source'], 'work-record')
        self.assertEqual(project['features'][0]['status_mark'], 'status-not-updated')
        self.assertNotIn('PRIVATE', (self.dir / 'data.js').read_text())
        self.refresh('run', '--cwd', str(repo.parent))
        self.assertEqual(self.data()['progress']['repositories'][code]['features'], project['features'])
        for bad in ('PRIVATE', {'model': 'PRIVATE'}, 123, True):
            tampered = json.loads(json.dumps(original))
            tampered['progress']['repositories'][code]['features'][0]['status_mark'] = bad
            (self.dir / 'data.js').write_text('window.FNL_DATA = ' + json.dumps(tampered) + ';\n')
            self.refresh('run', '--cwd', str(repo.parent))
            self.assertNotIn(code, self.data()['progress']['repositories'])
        for bad in ('PRIVATE', {'skipped': 'PRIVATE'}, {'skipped': True}, {'skipped': -1}):
            tampered = json.loads(json.dumps(original))
            tampered['progress']['repositories'][code]['work_records'] = bad
            (self.dir / 'data.js').write_text('window.FNL_DATA = ' + json.dumps(tampered) + ';\n')
            self.refresh('run', '--cwd', str(repo.parent))
            self.assertNotIn(code, self.data()['progress']['repositories'])
        self.assertEqual(events_before, {path: path.read_bytes() for path in self.dir.glob('events-*.jsonl')})
        host = self.ledger.parent / 'host.md'
        host_before = host.read_bytes()
        self.refresh('purge', '--yes')
        self.assertEqual(host.read_bytes(), host_before)

    def test_progress_builders_never_open_repository_instruction_files(self):
        self.consent()
        self.ledger.parent.joinpath('host.md').write_text('# Host\n')
        repo = Path(self.tmp.name).resolve() / 'repo'
        (repo / '.git').mkdir(parents=True)
        (repo / 'docs/specs').mkdir(parents=True)
        (repo / 'docs/specs/work.md').write_text('Status: draft\n## Plan\nx\n## Tasks\n- [ ] T1\n')
        for folder in (repo, repo / 'docs/specs'):
            for name in ('CLAUDE.md', 'AGENTS.md'):
                (folder / name).write_text('PRIVATE instructions\n')
        spec = importlib.util.spec_from_file_location('refresh_guard', REFRESH)
        refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(refresh)
        original = os.open
        def guarded(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)):
                self.assertNotIn(os.fsdecode(path).split('/')[-1], ('CLAUDE.md', 'AGENTS.md'))
            return original(path, *args, **kwargs)
        with mock.patch('os.open', side_effect=guarded):
            for path in (ROOT / 'scripts/project_progress.py', ROOT / 'skills/fnl-status/scripts/project_progress.py',
                         ROOT / 'skills/fnl-setup/scripts/project_progress.py'):
                spec = importlib.util.spec_from_file_location('progress_guard', path)
                pp = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(pp)
                self.assertEqual(pp.collect(repo, 'aaaaaaaa')['source'], 'work-record')
            self.assertIsNotNone(refresh.progress_metrics([], {'processes': [], 'snapshot': {'reason': 'off'}}, repo))
            self.assertIsNotNone(refresh.build(cwd=repo))
            for instruction in ('CLAUDE.md', 'AGENTS.md'):
                self.ledger.parent.joinpath('host.md').write_text('## Project progress\n- Task file: ' + instruction + '\n')
                with mock.patch.object(refresh.pp, 'work_records', return_value=[]), mock.patch.object(refresh.pp, 'repository_documents', return_value=('none', 'none', [])):
                    self.assertIsNotNone(refresh.progress_metrics([], {'processes': [], 'snapshot': {'reason': 'off'}}, repo))

    def test_pipeline_snapshot_rejects_text_in_new_enum_fields(self):
        self.consent()
        self.ledger.parent.joinpath('host.md').write_text('# Host\n')
        repo = Path(self.tmp.name).resolve() / 'synthetic'
        (repo / '.git').mkdir(parents=True)
        spec = repo / 'specs/001-synthetic/spec.md'
        spec.parent.mkdir(parents=True)
        spec.write_text('**Status**: Draft\n')
        self.refresh('run', '--cwd', str(repo))
        original = self.data()
        code = original['progress']['current']
        for field, bad in [('source', 'PRIVATE TITLE'), ('recognition', 'PRIVATE TITLE'), ('ledger_join', 'PRIVATE TITLE'),
                           ('source', {'model': 'PRIVATE-TITLE'}), ('ledger_join', 123)]:
            tampered = json.loads(json.dumps(original))
            tampered['progress']['repositories'][code][field] = bad
            (self.dir / 'data.js').write_text('window.FNL_DATA = ' + json.dumps(tampered) + ';\n')
            self.refresh('run', '--cwd', str(repo.parent))
            self.assertNotIn(code, self.data()['progress']['repositories'])
            self.assertNotIn('PRIVATE', (self.dir / 'data.js').read_text())
        tampered = json.loads(json.dumps(original))
        tampered['progress']['repositories'][code]['features'][0]['status_hint'] = 'PRIVATE TITLE'
        (self.dir / 'data.js').write_text('window.FNL_DATA = ' + json.dumps(tampered) + ';\n')
        self.refresh('run', '--cwd', str(repo.parent))
        self.assertNotIn('PRIVATE', (self.dir / 'data.js').read_text())

    def test_multiple_project_snapshots_and_quota_metadata(self):
        self.consent()
        self.ledger.parent.joinpath('host.md').write_text('# Host\n')
        quota = self.dir / 'quota'
        quota.mkdir(mode=0o700, exist_ok=True)
        (quota / 'quota.json').write_text(json.dumps({'codex': {'default': {
            'measured': self.at.isoformat(), 'source': 'local', 'groups': [
                {'name': 'five-hour', 'window': '5h', 'remaining_fraction': .08, 'reset_time': None}]}}}))
        codes = []
        for n in range(6):
            repo = Path(self.tmp.name).resolve() / ('project%d' % n)
            (repo / '.git').mkdir(parents=True)
            tasks = repo / 'specs/001-test/tasks.md'
            tasks.parent.mkdir(parents=True)
            tasks.write_text('- [ ] T1 US1\n')
            result = subprocess.run([sys.executable, '-I', str(REFRESH), 'run', '--cwd', str(repo)],
                                    env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            block = self.data()['progress']
            codes.append(block['current'])
            self.assertEqual(len(block['repositories']), min(n + 1, 5))
        self.assertNotIn(codes[0], block['repositories'])
        self.assertEqual(self.data()['running']['quota'][1]['pools'][0]['remaining_fraction'], .08)
        self.assertIn('updated', block['repositories'][codes[-1]])
        # A refresh outside a repository must not erase the other last-written projects.
        result = subprocess.run([sys.executable, '-I', str(REFRESH), 'run', '--cwd', str(Path(self.tmp.name).resolve())],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.data()['progress']['repositories']), set(codes[-5:]))

    def test_active_strip_rebuilt_with_labels_retained_cards_and_purge(self):
        # HOME alone does not redirect the account anchor; setUp also injects the
        # synthetic passwd home and guards real-account reads in every child.
        self.env['HOME'] = str(self.home)
        self.consent()
        repo = Path(self.tmp.name).resolve() / 'active-project'
        (repo / '.git').mkdir(parents=True)
        tasks = repo / 'specs/001-test/tasks.md'
        tasks.parent.mkdir(parents=True)
        tasks.write_text('- [x] T1 US1\n- [ ] T2 US1\n- [ ] T3 US1\n')
        self.ledger.parent.joinpath('host.md').write_text('# Host\n')
        self.refresh('run', '--cwd', str(repo))
        code = self.data()['progress']['current']
        self.ledger.parent.joinpath('host.md').write_text('# Host\n\n## Project labels\n- ' + code + ': My project\n')
        self.write_events([self.event(12, 'session1', code, 'session_start', host='codex', dispatch=None, source='startup'),
                           self.event(11, 'session1', code, 'skill', name='fnl-status'),
                           self.event(30, 'session2', X, 'session_start', host='claude', dispatch=None, source='startup')])
        self.refresh('run', '--cwd', str(repo))
        progress = self.data()['progress']
        active = progress['active']
        self.assertEqual([r['repo'] for r in active], [code])
        self.assertEqual(active[0]['label'], 'My project')
        self.assertEqual(active[0]['hosts'], ['codex'])
        self.assertEqual(active[0]['percent'], 33)
        self.assertEqual(set(active[0]), {'repo', 'label', 'hosts', 'sessions', 'last', 'percent'})
        # Old activity, even arbitrary text/unknown keys, is never carried over.
        tampered = self.data()
        tampered['progress']['active'] = [{'repo': 'ffffffff', 'label': '<script>private', 'path': 'private'}]
        (self.dir / 'data.js').write_text('window.FNL_DATA = ' + json.dumps(tampered) + ';\n')
        self.refresh('run', '--cwd', str(Path(self.tmp.name).resolve()))
        rebuilt = self.data()['progress']
        self.assertEqual(rebuilt['active'], active)
        self.assertIn(code, rebuilt['repositories'])
        self.assertNotIn('private', json.dumps(rebuilt))
        self.write_events([])
        for path in self.dir.glob('events-*.jsonl'):
            path.unlink()
        self.refresh('run', '--cwd', str(repo))
        self.assertEqual(self.data()['progress']['active'], [])
        self.refresh('purge', '--yes')
        self.assertFalse((self.dir / 'data.js').exists())
        self.assertFalse(list(self.dir.glob('events-*.jsonl')))

    def status_here(self, repo, *extra):
        result = subprocess.run([sys.executable, '-I', str(REFRESH), 'run', '--register-here', *extra],
                                cwd=repo, capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_registration_requires_consent_is_private_sanitised_and_label_wins(self):
        repo = Path(self.tmp.name).resolve() / ('  Démo<>_' + 'x' * 45)
        (repo / '.git').mkdir(parents=True)
        nested = repo / 'nested'
        nested.mkdir()
        projects = self.dir / 'projects.json'
        self.status_here(nested)
        self.assertFalse(projects.exists())
        self.consent()
        self.ledger.parent.joinpath('host.md').write_text('# Host\n')
        self.status_here(nested)
        names = json.loads(projects.read_text())
        code, name = next(iter(names.items()))
        self.assertRegex(code, r'^[0-9a-f]{8}$')
        self.assertEqual(name, ('D-mo--_' + 'x' * 45)[:40])
        self.assertEqual(projects.stat().st_mode & 0o777, 0o600)
        self.assertEqual(projects.parent.stat().st_mode & 0o777, 0o700)
        self.write_events([self.event(1, 's', code, 'session_start', host='codex', dispatch=None, source='startup')])
        self.status_here(nested)
        self.assertEqual(self.data()['progress']['active'][0]['label'], name)
        self.ledger.parent.joinpath('host.md').write_text('## Project labels\n- ' + code + ': Owner label\n')
        self.status_here(nested)
        self.assertEqual(self.data()['progress']['active'][0]['label'], 'Owner label')
        self.assertEqual(self.data()['progress']['repositories'][code]['label'], 'Owner label')
        self.refresh('purge', '--yes')
        self.assertFalse(projects.exists())
        self.assertIn('Owner label', self.ledger.parent.joinpath('host.md').read_text())

    def test_hook_refresh_never_registers_even_with_flag_and_non_repo_is_skipped(self):
        self.consent()
        repo = Path(self.tmp.name).resolve() / 'hook-project'
        (repo / '.git').mkdir(parents=True)
        self.refresh('run', '--cwd', str(repo))
        self.refresh('run', '--cwd', str(repo), '--register-here')
        self.assertFalse((self.dir / 'projects.json').exists())
        self.status_here(Path(self.tmp.name))
        self.assertFalse((self.dir / 'projects.json').exists())
        # Without the flag, even a refresh inside a repository is not registration.
        result = subprocess.run([sys.executable, '-I', str(REFRESH), 'run'], cwd=repo,
                                capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.dir / 'projects.json').exists())

    def test_registered_names_stay_canonical_and_purge_with_state_override(self):
        self.consent()
        self.env['FNL_STATE_DIR'] = str(Path(self.tmp.name).resolve() / 'alternate-state')
        repo = Path(self.tmp.name).resolve() / 'canonical-project'
        (repo / '.git').mkdir(parents=True)
        self.status_here(repo)
        self.assertTrue((self.dir / 'projects.json').exists())
        self.assertFalse((Path(self.env['FNL_STATE_DIR']) / 'projects.json').exists())
        self.refresh('purge', '--yes')
        self.assertFalse((self.dir / 'projects.json').exists())

    def test_registration_caps_new_entries_and_updates_existing_at_cap(self):
        self.consent()
        repo = Path(self.tmp.name).resolve() / 'named-project'
        (repo / '.git').mkdir(parents=True)
        self.status_here(repo)
        path = self.dir / 'projects.json'
        code = next(iter(json.loads(path.read_text())))
        names = {'%08x' % n: 'Existing' for n in range(49)}
        names[code] = 'Old name'
        path.write_text(json.dumps(names))
        self.status_here(repo)
        self.assertEqual(len(json.loads(path.read_text())), 50)
        self.assertEqual(json.loads(path.read_text())[code], repo.name)
        other = repo.parent / 'new-project'
        (other / '.git').mkdir(parents=True)
        self.status_here(other)
        self.assertEqual(json.loads(path.read_text()), {**names, code: repo.name})

    def test_reviews_use_canonical_labels_even_when_progress_is_off(self):
        self.consent()
        self.ledger.parent.joinpath('host.md').write_text('## Project progress\n- Project progress: off\n\n## Project labels\n- aaaaaaaa: My tools\n')
        self.write_events([self.event(0, 's', X, 'review', pr=31, verdict='APPROVE', kind='code')])
        self.refresh('run')
        data = self.data()
        self.assertIsNone(data['progress'])
        self.assertEqual(data['reviews'][0].get('label'), 'My tools')

    # Acceptance 1: ledger writes bypass only the age throttle.
    def test_freshness_newer_ledger_bypasses_throttle_older_or_absent_does_not(self):
        self.consent()
        self.refresh("run")
        data = self.dir / "data.js"
        original = data.read_bytes()
        built = data.stat().st_mtime
        self.refresh("run", "--throttle", "10")
        self.assertEqual(data.stat().st_mtime, built)
        self.fixture_ledger()
        os.utime(self.ledger, (built - 1, built - 1))
        self.refresh("run", "--throttle", "10")
        self.assertEqual(data.stat().st_mtime, built)
        os.utime(self.ledger, (built + 1, built + 1))
        self.refresh("run", "--throttle", "10")
        self.assertNotEqual(data.read_bytes(), original)
        self.assertEqual(sum(row["runs"] for row in self.data()["delegation"]), 2)

    # Acceptance 3: freshness reports source times, with null for missing sources.
    def test_freshness_build_host_ledger_and_quota_ages(self):
        self.consent()
        self.write_events([
            self.event(30, "a", X, "session_start", host="claude", dispatch=None, source="startup"),
            self.event(2, "a", X, "first_edit"),
            self.event(20, "b", X, "session_start", host="codex", dispatch=None, source="startup"),
            self.event(1, "c", X, "session_start", host="antigravity", dispatch=None, source="startup")])
        self.ledger.write_text(json.dumps({"ts": (self.at - timedelta(minutes=3)).isoformat()}) + "\n")
        quota = self.dir / "quota"
        quota.mkdir(mode=0o700)
        (quota / "quota.json").write_text(json.dumps({"codex": {"default": {
            "measured": (self.at - timedelta(hours=4)).isoformat(), "source": "app-server", "groups": []}}}))
        self.refresh("run")
        d = self.data()
        fresh = d["freshness"]
        self.assertEqual(fresh["built_at"], d["generated"])
        self.assertEqual(fresh["latest_event"], {"claude": self.event(2, "a", X, "first_edit")["ts"],
                         "codex": self.event(20, "b", X, "session_start")["ts"],
                         "antigravity": self.event(1, "c", X, "session_start")["ts"]})
        self.assertAlmostEqual(fresh["ledger_age_seconds"], 180, delta=3)
        self.assertAlmostEqual(fresh["quota_age_seconds"], 14400, delta=3)

    def test_freshness_missing_or_malformed_sources_are_not_zero_age(self):
        self.refresh("run")
        fresh = self.data()["freshness"]
        self.assertEqual(fresh["latest_event"], {})
        self.assertIsNone(fresh["ledger_age_seconds"])
        self.assertIsNone(fresh["quota_age_seconds"])
        self.ledger.write_text('{"ts":"invalid"}\n')
        quota = self.dir / "quota"
        quota.mkdir(mode=0o700)
        (quota / "quota.json").write_text('{"bad":null}')
        self.refresh("run")
        self.assertIsNone(self.data()["freshness"]["ledger_age_seconds"])
        self.assertIsNone(self.data()["freshness"]["quota_age_seconds"])

    # Acceptance 2: real elapsed time, no parent timeout or shorter test cap.
    def test_detached_run_exits_itself_at_twenty_seconds_and_releases_lock(self):
        wrapper = Path(self.tmp.name) / "capped.py"
        wrapper.write_text(
            "import importlib.util, sys, time\n"
            f"spec = importlib.util.spec_from_file_location('refresh_cap', {str(REFRESH)!r})\n"
            "refresh = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(refresh)\n"
            "refresh.build = lambda: time.sleep(30)\n"
            "sys.argv = ['refresh.py', 'run']\nrefresh.main()\n")
        before = time.monotonic()
        done = subprocess.run([sys.executable, "-I", str(wrapper)], env=self.env, capture_output=True, timeout=25)
        elapsed = time.monotonic() - before
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertGreaterEqual(elapsed, 19)
        self.assertLess(elapsed, 24)
        self.assertFalse((self.dir / "data.js").exists())
        import fcntl
        with (self.dir / "refresh.lock").open("r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_low_revoke_requires_explicit_yes_flag(self):
        self.consent()
        before = (self.dir / "consent.json").read_bytes()
        result = self.refresh("consent", "--revoke", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "consent: pass --yes once the user has confirmed\n")
        self.assertEqual((self.dir / "consent.json").read_bytes(), before)
        self.refresh("consent", "--revoke", "--yes")
        self.assertFalse((self.dir / "consent.json").exists())

    # Running-agents acceptance 3: synthetic snapshot, real canonical consent/ledger.
    def running_module(self):
        spec = importlib.util.spec_from_file_location("refresh_running", REFRESH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_live_sessions_distinct_window_boundary_future_and_cap(self):
        module = self.running_module()
        at = self.at
        def event(sid, minutes, kind='skill', host=None):
            row = dict(sid=sid, ts=(at - timedelta(minutes=minutes)).isoformat(), event=kind)
            if host is not None:
                row['host'] = host
            return row
        rows = [event('coordinator', 60, 'session_start', 'claude'),
                event('coordinator', 1), event('coordinator', 2),
                event('child', 10, 'session_start', 'claude'),
                event('idle', 15, 'session_start', 'claude'),
                event('future', -1, 'session_start', 'antigravity'),
                event('unknown', 0), event('agy', 0, 'session_start', 'antigravity')]
        for n in range(105):
            rows.append(event('codex%d' % n, 14.999, 'session_start', 'codex'))
        self.assertEqual(module.live_sessions(rows, at.isoformat()),
                         dict(window_minutes=15, claude=2, codex=99, antigravity=1))
        self.assertEqual(module.live_sessions([], at.isoformat()),
                         dict(window_minutes=15, claude=0, codex=0, antigravity=0))

    def test_live_sessions_are_built_from_existing_events_with_snapshot_off(self):
        self.consent()
        rows = [self.event(85 * 24 * 60, 'parent', X, 'session_start', host='claude', dispatch=None, source='startup'),
                self.event(1, 'parent', X, 'skill', name='fnl-status'),
                self.event(2, 'child', X, 'session_start', host='codex', dispatch=None, source='startup')]
        self.write_events(rows)
        before = {p: p.read_bytes() for p in self.dir.glob('events-*.jsonl')}
        self.refresh('run')
        running = self.data()['running']
        self.assertEqual(running['live'], dict(window_minutes=15, claude=1, codex=1, antigravity=0))
        self.assertEqual(running['snapshot']['reason'], 'snapshot off')
        self.assertEqual(running['open'], [])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_quota_all_pools_caps_placeholders_staleness_and_closed_metadata(self):
        module = self.running_module()
        at = self.at
        def entry(names, hours=0):
            return dict(measured=(at - timedelta(hours=hours)).isoformat(), source='PRIVATE SOURCE',
                        prompt='PRIVATE PROMPT', groups=[dict(name=name, window='weekly',
                            remaining_fraction=.5, reset_time=(at + timedelta(days=1)).isoformat(),
                            private='PRIVATE GROUP') for name in names])
        cache = dict(claude={str(n): entry(['week-all', 'session'], hours=n * 4) for n in range(5)},
                     codex=dict(default=entry(['codex'] * 12)))
        folder = self.dir / 'quota'
        folder.mkdir(parents=True, mode=0o700)
        path = folder / 'quota.json'
        path.write_text(json.dumps(cache))
        with mock.patch.dict(os.environ, self.env), mock.patch.object(module.fm, 'now', return_value=at):
            rows = module.quota_meters()
            self.assertEqual([r['agent'] for r in rows], ['claude', 'codex', 'agy'])
            self.assertEqual([len(r['pools']) for r in rows], [8, 8, 0])
            self.assertEqual([q['name'] for q in rows[0]['pools']], ['week-all', 'session'] * 4)
            self.assertEqual([q['unverified'] for q in rows[0]['pools']], [False] * 6 + [True] * 2)
            self.assertEqual(rows[1]['pools'][0]['name'], 'codex / weekly')
            for row in rows:
                self.assertEqual(set(row), {'agent', 'pools'})
                for pool in row['pools']:
                    self.assertEqual(set(pool), {'name', 'remaining_fraction', 'resets', 'measured', 'unverified'})
            self.assertNotIn('PRIVATE', json.dumps(rows))
            self.assertEqual(rows[0]['pools'][0]['resets'], (at + timedelta(days=1)).isoformat())
            cache['claude'] = {str(n): entry(['week-all']) for n in range(5)}
            cache['codex'] = dict(default=entry(['codex'], hours=-1))
            cache['agy'] = dict(default=dict(measured='PRIVATE TIME', groups=[]))
            path.write_text(json.dumps(cache))
            rows = module.quota_meters()
            self.assertEqual(len(rows[0]['pools']), 4)  # fifth entry is never read
            self.assertTrue(rows[1]['pools'][0]['unverified'])
            self.assertEqual(rows[2]['pools'], [])
            path.write_text('{bad')
            self.assertEqual([r['pools'] for r in module.quota_meters()], [[], [], []])
            path.unlink()
            self.assertEqual([r['pools'] for r in module.quota_meters()], [[], [], []])

    def snapshot_on(self):
        (self.ledger.parent / "host.md").write_text("## Agent snapshot\n\n- Snapshot: on\n")

    def test_running_merges_open_dispatches_and_family_mismatches_without_events(self):
        self.consent()
        self.snapshot_on()
        start = dict(event="start", id="open", ts=(self.at - timedelta(minutes=12)).isoformat(),
                     project="demo</script>&", task="task", kind="implement", grade="easy",
                     agent="claude", model="m", reason="routing", budget_min=20)
        closed = dict(start, id="closed", agent="codex")
        self.ledger.write_text("\n".join(map(json.dumps, [start, closed,
            dict(event="finish", id="closed", ts=self.at.isoformat(), outcome="accepted", rework_rounds=0)])) + "\n")
        self.write_events([self.event(1, "a", X, "first_edit")])
        before = {p: p.read_bytes() for p in self.dir.glob('events-*')}
        module = self.running_module()
        snap = dict(time=self.at.isoformat(), reason="", apps={"Claude": 2}, processes=[
            dict(family="codex", elapsed_seconds=5, descendants={"other": 1})])
        with mock.patch.dict(os.environ, self.env), mock.patch.object(module.ap, "snapshot", return_value=snap) as probe:
            module.cmd_run(mock.Mock(open=False, throttle=None))
            result = self.data()['running']
            self.assertEqual(len(result['open']), 1)
            row = result['open'][0]
            self.assertEqual(row['budget_min'], 20)
            self.assertAlmostEqual(row['age_min'], 12, delta=.1)
            self.assertTrue(row['check_due'])
            self.assertEqual(row['liveness'], 'unverified')
            self.assertTrue(row['no_process_found'])
            self.assertTrue(result['processes'][0]['not_started_by_coordinator'])
            self.assertEqual(result['snapshot']['time'], snap['time'])
            module.cmd_run(mock.Mock(open=False, throttle=10))
            probe.assert_called_once()
            # A foreground rebuild and a newer ledger still cannot resample in 10s.
            module.cmd_run(mock.Mock(open=False, throttle=None))
            probe.assert_called_once()
            with mock.patch.object(module.ap, 'enabled', return_value=False):
                module.cmd_run(mock.Mock(open=False, throttle=None))
            self.assertEqual(self.data()['running']['processes'], [])
        self.assertEqual(before, {p: p.read_bytes() for p in self.dir.glob('events-*')})
        raw = (self.dir / 'data.js').read_text()
        self.assertNotIn('</script>', raw)
        self.assertNotIn('&', raw)
        self.refresh('purge', '--yes')
        self.assertFalse((self.dir / 'data.js').exists())

    def test_running_snapshot_off_default_invalid_root_and_canonical_consent_only(self):
        module = self.running_module()
        with mock.patch.dict(os.environ, self.env), mock.patch.object(module.ap, 'snapshot') as probe:
            module.build()
            self.snapshot_on()
            module.build()  # snapshot on without metrics consent
            self.consent()
            with mock.patch.dict(os.environ, {'FNL_AGENT_SNAPSHOT': 'off'}):
                module.build()
            with mock.patch.dict(os.environ, {'FNL_METRICS': 'off'}):
                module.build()
            (self.ledger.parent / 'root.json').write_text('{}')
            module.build()
            probe.assert_not_called()

    def consent(self, days="90"):
        self.refresh("consent", "--retention", days)

    def event(self, minutes_ago, sid, repo, event, **fields):
        ts = (self.at - timedelta(minutes=minutes_ago)).isoformat(timespec="milliseconds")
        return {"ts": ts, "sid": sid, "repo": repo, "event": event, **fields}

    def write_events(self, events):
        self.dir.mkdir(parents=True, exist_ok=True)
        by_month = {}
        for e in events:
            by_month.setdefault(e["ts"][:7], []).append(json.dumps(e))
        for month, lines in by_month.items():
            (self.dir / ("events-%s.jsonl" % month)).write_text("\n".join(lines) + "\n")

    def data(self):
        text = (self.dir / "data.js").read_text()
        self.assertTrue(text.startswith("window.FNL_DATA = ") and text.endswith(";\n"))
        return json.loads(text[len("window.FNL_DATA = "):-2])

    def fixture_store(self):
        start = {"host": "claude", "dispatch": None, "source": "startup"}
        self.write_events([
            self.event(120, "a", X, "session_start", **start), self.event(119, "a", X, "skill", name="fnl-coding-router"),
            self.event(118, "a", X, "router", depth="DEEP", trigger="security"), self.event(110, "a", X, "first_edit"),
            self.event(100, "b", X, "session_start", **start), self.event(90, "b", X, "first_edit"),
            self.event(80, "c", X, "session_start", host="claude", dispatch="d20261103-1", source="startup"),
            self.event(70, "c", X, "first_edit"),
            self.event(60, "d", X, "first_edit"),
            self.event(50, "e", Y, "session_start", **start), self.event(49, "e", Y, "router", depth="MIN", trigger="none"),
            self.event(40, "e", Y, "first_edit"),
            self.event(35, "a", X, "agent", name="fnl-reviewer"), self.event(34, "a", X, "agent", name="fnl-reviewer"),
            self.event(30, "a", X, "review", kind="code", verdict="REWORK", pr=5),
            self.event(20, "a", X, "review", kind="security", verdict="APPROVE", pr=5),
            self.event(10, "e", Y, "review", kind="code", verdict="APPROVE", pr=7),
        ])

    def fixture_ledger(self):
        env = self.env
        start = ["start", "--project", "demo", "--task", "t", "--kind", "implement", "--grade", "medium",
                 "--agent", "codex", "--model", "m1", "--budget", "40"]
        ids = [subprocess.run([sys.executable, "-I", str(LEDGER), *start], capture_output=True, text=True, env=env).stdout.strip()
               for _ in range(2)]
        for dispatch_id, outcome in zip(ids, ("accepted", "quota")):
            subprocess.run([sys.executable, "-I", str(LEDGER), "finish", dispatch_id, "--outcome", outcome], check=True, env=env)

    def judge_ledger(self, rows):
        lines = []
        for i, (route_by, outcome, rework) in enumerate(rows):
            started = dict(event="start", id="j%d" % i, ts=self.at.isoformat(), project="demo", task="t",
                           kind="implement", grade="medium", agent="codex", model="m", reason="routing")
            if route_by is not None:
                started["route_by"] = route_by
            lines.append(started)
            if outcome:
                lines.append(dict(event="finish", id=started["id"], ts=self.at.isoformat(),
                                  outcome=outcome, rework_rounds=rework))
        self.ledger.write_text("".join(json.dumps(line) + "\n" for line in lines))

    def test_judge_block_is_absent_without_receipts_or_judge_routes(self):
        for rows in ([], [("table", "accepted", 0)], [(None, "accepted", 0)]):
            self.judge_ledger(rows)
            self.refresh("run")
            self.assertIsNone(self.data()["judge"])

    def test_judge_shares_and_site_counts_are_separate_from_ledger_outcomes(self):
        cases = [("route", "judge", "validated", "yes"), ("route", "judge", "validated", "no"),
                 ("depth", "judge", "validated", "na"), ("activity", "judge", "unverified", "na"),
                 ("instruction", "agent", "validated", "na"), ("route", "agent", "validated", "na")]
        self.write_events([self.event(i, "s", X if i % 2 else Y, "judge", site=site, grader=grader,
                                     result=result, followed=followed)
                           for i, (site, grader, result, followed) in enumerate(cases)])
        self.judge_ledger([("judge", "accepted", 0), ("judge", "accepted", 1), ("judge", "error", 0),
                           ("table", "accepted", 0)] + [("table", "quota", 0)] * 4 + [("user", "accepted", 0)])
        self.refresh("run")
        block = self.data()["judge"]
        self.assertEqual(block["receipts"], 6)
        self.assertEqual(block["usable_answers"], dict(validated=3, calls=4, share=.75))
        self.assertEqual(block["followed"], dict(yes=1, validated=3, share=1/3))
        self.assertEqual({(r["site"], r["grader"]): r["count"] for r in block["use"]},
                         {("route", "judge"): 2, ("depth", "judge"): 1, ("activity", "judge"): 1,
                          ("instruction", "agent"): 1, ("route", "agent"): 1})
        self.assertEqual(block["outcome_association"], [dict(route_by="judge", runs=3, first_pass=1/3, small=True),
                                                       dict(route_by="table", runs=5, first_pass=.2, small=False)])
        self.assertNotIn(X, json.dumps(block))
        self.assertNotIn(Y, json.dumps(block))

    def test_judge_ledger_without_receipts_or_consent_shows_only_association(self):
        self.judge_ledger([("judge", "accepted", 0), ("table", "rejected", 0), (None, "accepted", 0)])
        self.refresh("run")
        block = self.data()["judge"]
        self.assertEqual(block["receipts"], 0)
        self.assertEqual(block["note"], "No receipts were recorded.")
        for key in ("use", "usable_answers", "followed"):
            self.assertNotIn(key, block)
        self.assertEqual(len(block["outcome_association"]), 2)
        self.assertTrue(all(r["small"] for r in block["outcome_association"]))
        self.judge_ledger([("judge", None, 0)])
        self.refresh("run")
        self.assertEqual(self.data()["judge"]["outcome_association"], [])
        self.assertEqual(self.data()["judge"]["outcome_note"], "no finished runs in this period")

    def test_judge_empty_denominators_are_unknown_and_old_data_is_excluded(self):
        self.write_events([self.event(0, "s", X, "judge", site="route", grader="agent", result="validated", followed="na"),
                           self.days_ago(100, "s", X, "judge", site="route", grader="judge", result="validated", followed="yes")])
        self.refresh("run")
        block = self.data()["judge"]
        self.assertEqual(block["receipts"], 1)
        self.assertIsNone(block["usable_answers"]["share"])
        self.assertIsNone(block["followed"]["share"])
        self.write_events([self.event(0, "s", X, "judge", site="route", grader="judge", result="unverified", followed="na")])
        self.refresh("run")
        block = self.data()["judge"]
        self.assertEqual(block["usable_answers"]["share"], 0)
        self.assertIsNone(block["followed"]["share"])

    def test_the_metrics_match_a_hand_computation(self):
        self.consent()
        self.fixture_store()
        self.fixture_ledger()
        self.refresh("run")
        d = self.data()
        self.assertEqual(d["sessions"], {"total": 5, "with_edits": 5, "dispatch": 1, "unclassified": 1})
        self.assertEqual(d["router"], {"covered": 2, "missed": 1, "excluded": 1, "unclassified": 1, "eligible": 3})
        self.assertAlmostEqual(d["kpi"]["router_coverage"], 2 / 3)
        self.assertEqual({(u["kind"], u["name"], u["count"]) for u in d["use"]},
                         {("skill", "fnl-coding-router", 1), ("agent", "fnl-reviewer", 2)})
        self.assertEqual(d["kpi"]["calls"], 3)
        self.assertEqual({r["depth"]: (r["receipts"], r["reworked"]) for r in d["depth"]}, {"MIN": (1, 0), "DEEP": (1, 1)})
        self.assertEqual({(r["repo"], r["pr"]): r["verdicts"] for r in d["reviews"]},
                         {("repo-" + X, 5): ["REWORK", "APPROVE"], ("repo-" + Y, 7): ["APPROVE"]})
        [row] = d["delegation"]
        self.assertEqual((row["agent"], row["runs"], row["first_pass"], row["quota"], row["error"]), ("codex", 2, 0.5, 1, 0))
        self.assertAlmostEqual(d["kpi"]["first_pass"], 0.5)
        size = (ROOT / "skills/fnl-coding-router/SKILL.md").stat().st_size // 4
        self.assertEqual(d["load"]["top"], [{"name": "fnl-coding-router", "tokens": size, "loads": 1}])
        self.assertEqual(len(d["activity"]), 84)
        self.assertEqual(sum(a["count"] for a in d["activity"]), 17)
        self.assertEqual(d["errors"], 0)
        self.assertEqual(d["missing"], {})

    def days_ago(self, days, sid, repo, event, **fields):
        return self.event(days * 24 * 60, sid, repo, event, **fields)

    def test_weeks_without_data_are_null_not_zero(self):
        self.consent()
        start = {"host": "claude", "dispatch": None, "source": "startup"}
        self.write_events([
            self.days_ago(20, "a", X, "session_start", **start), self.days_ago(20, "a", X, "router", depth="MIN", trigger="none"),
            self.days_ago(20, "a", X, "first_edit"),
            self.days_ago(12, "b", X, "session_start", **start), self.days_ago(12, "b", X, "first_edit"),
        ])
        self.refresh("run")
        spark = self.data()["kpi"]["spark"]["router_coverage"]
        self.assertEqual(len(spark), 12)
        self.assertEqual((spark[9], spark[10]), (1.0, 0.0))
        self.assertTrue(all(v is None for i, v in enumerate(spark) if i not in (9, 10)))

    def test_with_no_events_the_weekly_charts_are_absent_not_zero(self):
        self.consent()
        self.refresh("run")
        spark = self.data()["kpi"]["spark"]
        self.assertEqual((spark["sessions"], spark["calls"], spark["router_coverage"]), (None, None, None))

    def test_the_rework_share_counts_every_pull_request_not_only_the_newest_twelve(self):
        self.consent()
        events = []
        for pr in range(1, 15):
            if pr % 2 == 0:
                events.append(self.event(100 - pr, "a", X, "review", kind="code", verdict="REWORK", pr=pr))
            events.append(self.event(50 - pr, "a", X, "review", kind="code", verdict="APPROVE", pr=pr))
        self.write_events(events)
        self.refresh("run")
        d = self.data()
        self.assertEqual(len(d["reviews"]), 12)
        self.assertEqual(d["review_stats"], {"total": 14, "reworked": 7})

    def test_events_without_skills_say_so_instead_of_blaming_the_hooks(self):
        self.consent()
        self.write_events([self.event(10, "a", X, "first_edit")])
        self.refresh("run")
        self.assertEqual(self.data()["missing"]["use"], "no fnl- skill or agent used in this period")

    def test_kept_work_is_counted_beside_the_implementation_runs_handed_off(self):
        self.consent()
        self.fixture_ledger()
        start = {"host": "codex", "dispatch": None, "source": "startup"}
        self.write_events([self.event(9, "k", X, "session_start", **start),
                           self.event(8, "k", X, "kept", tasks=2, reason="needs-context", route_by="table"),
                           self.event(7, "k", X, "kept", tasks=3, reason="needs-context", route_by="table"),
                           self.event(6, "m", X, "kept", tasks=2, reason="user-choice", route_by="user")])
        self.refresh("run")
        kept = self.data()["kept"]
        self.assertEqual((kept["receipts"], kept["tasks"], kept["handed_off"]), (3, 7, 2))
        self.assertEqual(kept["rows"], [
            {"coordinator": "codex", "reason": "needs-context", "route_by": "table", "receipts": 2, "tasks": 5},
            {"coordinator": "unknown", "reason": "user-choice", "route_by": "user", "receipts": 1, "tasks": 2}])

    def test_the_hand_off_count_leaves_out_subagents_and_reroutes_after_a_failure(self):
        self.consent()
        base = ["start", "--project", "demo", "--task", "t", "--kind", "implement", "--grade", "easy", "--model", "m", "--budget", "20"]
        for extra in (["--agent", "codex"], ["--agent", "codex", "--reason", "fallback-quota"],
                      ["--agent", "codex", "--reason", "fallback-failure"], ["--agent", "subagent"]):
            subprocess.run([sys.executable, "-I", str(LEDGER), *base, *extra], check=True, env=self.env, capture_output=True)
        self.write_events([self.event(9, "k", X, "first_edit")])
        self.refresh("run")
        self.assertEqual(self.data()["kept"]["handed_off"], 2)

    def test_without_consent_no_zero_is_shown_for_kept_work(self):
        self.fixture_ledger()
        self.refresh("run")
        self.assertIsNone(self.data()["kept"])

    def fixture_old_implementation_starts(self):
        starts = [{"event": "start", "id": "old-%d" % age,
                   "ts": (self.at - timedelta(days=age)).isoformat(),
                   "project": "demo", "task": "t", "kind": "implement", "grade": "easy",
                   "agent": "codex", "model": "m", "reason": "routing"}
                  for age in range(40, 50)]
        self.ledger.write_text("".join(json.dumps(s) + "\n" for s in starts))

    def test_old_handoffs_do_not_imply_zero_kept_since_consent_today(self):
        self.consent("30")
        self.write_events([self.event(0, "k", X, "first_edit")])
        self.fixture_old_implementation_starts()
        self.refresh("run")
        self.assertIsNone(self.data()["kept"])

    def test_handoffs_after_the_first_available_event_still_count(self):
        self.consent("30")
        self.write_events([self.event(0, "k", X, "first_edit"),
                           self.days_ago(2, "k", X, "first_edit")])
        self.fixture_old_implementation_starts()
        self.fixture_ledger()
        self.refresh("run")
        kept = self.data()["kept"]
        self.assertEqual((kept["tasks"], kept["handed_off"]), (0, 2))

    def test_handoff_window_uses_local_dates_at_the_first_event(self):
        self.env["TZ"] = "Asia/Ho_Chi_Minh"
        self.at = datetime.now(timezone(timedelta(hours=7))).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        self.consent("30")
        self.write_events([self.event(0, "k", X, "first_edit")])
        starts = [{"event": "start", "id": "local-%d" % hour,
                   "ts": (self.at + timedelta(hours=hour)).astimezone(timezone.utc).isoformat(),
                   "project": "demo", "task": "t", "kind": "implement", "grade": "easy",
                   "agent": "codex", "model": "m", "reason": "routing"}
                  for hour in (-1, 1)]
        self.ledger.write_text("".join(json.dumps(s) + "\n" for s in starts))
        self.refresh("run")
        self.assertEqual(self.data()["kept"]["handed_off"], 1)

    def test_with_consent_but_no_hook_running_no_zero_is_shown_for_kept_work(self):
        self.consent()
        self.fixture_ledger()
        self.refresh("run")
        self.assertIsNone(self.data()["kept"])

    def test_purge_removes_kept_work_with_the_other_events(self):
        self.consent()
        self.write_events([self.event(8, "k", X, "kept", tasks=2, reason="no-delegate", route_by="table")])
        self.refresh("run")
        self.assertEqual(self.data()["kept"]["tasks"], 2)
        self.refresh("purge", "--yes")
        self.refresh("run")
        self.assertIsNone(self.data()["kept"])

    def test_kept_work_stays_null_when_the_ledger_holds_neither_side(self):
        self.refresh("run")
        self.assertIsNone(self.data()["kept"])

    def test_a_malformed_ledger_line_does_not_stop_the_refresh(self):
        self.consent()
        start = {"event": "start", "id": "d1", "ts": "garbage", "project": "p", "task": "t", "kind": "implement",
                 "grade": "easy", "agent": "codex", "model": "m", "reason": "routing"}
        finish = {"event": "finish", "id": "d1", "ts": "garbage", "outcome": "accepted", "rework_rounds": 0}
        self.ledger.write_text(json.dumps(start) + "\n" + json.dumps(finish) + "\n")
        self.refresh("run")
        self.assertEqual(self.data()["missing"]["delegation"], "ledger could not be read")

    def test_missing_sources_are_named_not_shown_as_zero(self):
        self.refresh("run")
        d = self.data()
        self.assertIsNone(d["kpi"]["router_coverage"])
        self.assertIsNone(d["kpi"]["sessions"])
        self.assertIn("consent not given", d["missing"]["activity"])
        self.consent()
        self.refresh("run")
        self.assertEqual(self.data()["missing"]["activity"], "no events recorded yet")

    def test_the_written_files_are_ascii_private_and_the_page_is_a_byte_copy(self):
        self.consent()
        self.fixture_store()
        self.refresh("run")
        raw = (self.dir / "data.js").read_bytes()
        self.assertTrue(raw.isascii())
        self.assertEqual(oct((self.dir / "data.js").stat().st_mode & 0o777), "0o600")
        self.assertEqual((self.dir / "dashboard.html").read_bytes(), PAGE.read_bytes())
        self.assertEqual((self.dir / "dashboard.js").read_bytes(), PAGE.with_suffix(".js").read_bytes())
        self.assertEqual((self.dir / "dashboard.js").stat().st_mode & 0o777, 0o600)

    def test_a_tampered_store_line_cannot_reach_the_script_file(self):
        self.consent()
        self.fixture_store()
        evil = self.event(5, "z", X, "skill", name="</script><img src=x onerror=alert(1)>")
        with open(next(self.dir.glob("events-*.jsonl")), "a") as handle:
            handle.write(json.dumps(evil) + "\n")
        self.refresh("run")
        text = (self.dir / "data.js").read_text()
        self.assertNotIn("</script", text)
        self.assertNotIn("onerror", text)

    def test_purge_needs_a_yes_and_keeps_consent(self):
        self.consent()
        self.fixture_store()
        self.refresh("run")
        self.assertNotEqual(self.refresh("purge", check=False).returncode, 0)
        self.assertTrue(list(self.dir.glob("events-*")))
        self.refresh("purge", "--yes")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["consent.json", "refresh.lock"])  # the lock file stays on purpose

    def agy_hook(self, config, *args):
        return self.refresh("antigravity-hook", "--config", str(config), *args, check=False)

    def test_the_antigravity_hook_is_merged_with_a_backup_and_every_other_group_kept(self):
        config = Path(self.tmp.name) / "my config" / "hooks.json"
        config.parent.mkdir()
        others = {"finos": {"Stop": [{"type": "command", "command": "x", "timeout": 5}]}, "hatch": {"PreToolUse": []}}
        config.write_text(json.dumps(others))
        config.chmod(0o640)
        result = self.agy_hook(config, "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(config.read_text())
        self.assertEqual({k: data[k] for k in others}, others)
        group = data["finolabs-vibecode"]
        script = str(ROOT / "scripts/metrics_hook.py")
        self.assertIn(script, group["SessionStart"][0]["command"])
        self.assertIn("--host antigravity --event post_tool_use", group["PostToolUse"][0]["hooks"][0]["command"])
        self.assertEqual(group["PostToolUse"][0]["matcher"], "run_command|write_to_file|replace_file_content|multi_replace_file_content")
        self.assertEqual(oct(config.stat().st_mode & 0o777), "0o640")
        backups = list(config.parent.glob("hooks.json.finolabs-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), others)
        self.agy_hook(config, "--yes")
        self.assertEqual(len([k for k in json.loads(config.read_text()) if k == "finolabs-vibecode"]), 1)

    def test_the_antigravity_hook_can_be_removed_and_leaves_the_rest(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text(json.dumps({"finos": {"Stop": []}}))
        self.agy_hook(config, "--yes")
        self.assertEqual(self.agy_hook(config, "--remove", "--yes").returncode, 0)
        self.assertEqual(json.loads(config.read_text()), {"finos": {"Stop": []}})

    def test_the_antigravity_hook_is_refused_without_yes_or_for_a_file_that_is_not_a_json_object(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text("{}")
        self.assertNotEqual(self.agy_hook(config).returncode, 0)
        self.assertEqual(config.read_text(), "{}")
        for bad in ("not json", "[1]"):
            config.write_text(bad)
            self.assertNotEqual(self.agy_hook(config, "--yes").returncode, 0)
            self.assertEqual(config.read_text(), bad)
        self.assertEqual(list(config.parent.glob("hooks.json.finolabs-backup-*")), [])

    def test_a_commit_counts_as_a_change_when_files_were_written_through_the_shell(self):
        start = {"host": "claude", "dispatch": None, "source": "startup"}
        self.consent()
        self.write_events([self.event(30, "s", X, "session_start", **start), self.event(29, "s", X, "skill", name="fnl-coding-router"),
                           self.event(20, "s", X, "commit")])
        self.refresh("run")
        self.assertEqual(self.data()["router"]["eligible"], 1)
        self.assertEqual(self.data()["router"]["covered"], 1)

    def test_the_antigravity_hook_is_refused_for_a_skill_outside_the_plugin(self):
        tree = Path(self.tmp.name) / "repo" / ".claude"
        shutil.copytree(ROOT / "skills/fnl-status", tree / "skills/fnl-status")
        (tree / "scripts").mkdir()
        (tree / "scripts/metrics_hook.py").write_text("print('pwned')\n")
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text("{}")
        result = subprocess.run([sys.executable, "-I", str(tree / "skills/fnl-status/scripts/refresh.py"), "antigravity-hook",
                                 "--config", str(config), "--yes"], capture_output=True, text=True, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not inside the finolabs-vibecode plugin", result.stderr)
        self.assertEqual(config.read_text(), "{}")
        self.assertEqual(list(config.parent.glob("hooks.json.finolabs-backup-*")), [])

    def test_a_symlinked_hooks_file_is_edited_in_place_and_stays_a_link(self):
        real = Path(self.tmp.name) / "dotfiles" / "hooks.json"
        real.parent.mkdir()
        real.write_text(json.dumps({"finos": {}}))
        link = Path(self.tmp.name) / "hooks.json"
        link.symlink_to(real)
        self.assertEqual(self.agy_hook(link, "--yes").returncode, 0)
        self.assertTrue(link.is_symlink())
        self.assertIn("finolabs-vibecode", json.loads(real.read_text()))

    def test_a_hooks_file_with_nan_is_refused_and_non_ascii_text_is_kept_readable(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text('{"a": NaN}')
        self.assertNotEqual(self.agy_hook(config, "--yes").returncode, 0)
        self.assertEqual(config.read_text(), '{"a": NaN}')
        config.write_text(json.dumps({"note": "xin chào"}, ensure_ascii=False))
        self.agy_hook(config, "--yes")
        self.assertIn("xin chào", config.read_text())

    def test_a_lone_surrogate_escape_in_the_hooks_file_is_still_written(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text('{"note": "\\ud800"}')
        self.assertEqual(self.agy_hook(config, "--yes").returncode, 0)
        self.assertIn("finolabs-vibecode", json.loads(config.read_text()))

    def test_two_runs_in_one_second_keep_two_backups(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text("{}")
        self.agy_hook(config, "--yes")
        self.agy_hook(config, "--yes")
        self.assertEqual(len(list(config.parent.glob("hooks.json.finolabs-backup-*"))), 2)

    def test_consent_can_be_withdrawn_and_recorded_events_stay_until_purge(self):
        self.consent()
        self.refresh("run")
        self.refresh("consent", "--revoke", "--yes")
        self.assertFalse((self.dir / "consent.json").exists())
        self.assertNotEqual(self.refresh("consent", check=False).returncode, 0)

    def test_consent_rejects_an_unknown_retention(self):
        self.assertNotEqual(self.refresh("consent", "--retention", "7", check=False).returncode, 0)
        self.assertFalse((self.dir / "consent.json").exists())


class RefreshOverlapTest(unittest.TestCase):
    """Overlapping rebuilds. Threads stand in for hook processes; the lock is the operating system's, so they exclude each other."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        account(self, Path(self.tmp.name) / "home")
        patcher = mock.patch.dict(os.environ, {"FNL_STATE_DIR": str(Path(self.tmp.name) / "state")})
        patcher.start()
        self.addCleanup(patcher.stop)
        spec = importlib.util.spec_from_file_location("fnl_refresh_overlap", REFRESH)
        self.refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.refresh)
        self.state = Path(self.tmp.name) / "state"

    @staticmethod
    def data(tag="x"):
        return {"tag": tag, "missing": {}, "period": {"from": "", "to": ""}, "sessions": {"total": 0, "unclassified": 0}, "errors": 0}

    @staticmethod
    def args(throttle=None, open_page=False):
        return mock.Mock(throttle=throttle, open=open_page, cwd=None)

    def test_a_run_waits_for_a_rebuild_in_progress_and_then_rebuilds_so_the_newest_data_wins(self):
        inside, release, order = threading.Event(), threading.Event(), []

        def build():
            order.append("build")
            if len(order) == 1:
                inside.set()
                release.wait(5)
            return self.data("first" if len(order) == 1 else "second")

        with mock.patch.object(self.refresh, "build", build):
            first = threading.Thread(target=self.refresh.cmd_run, args=(self.args(),))
            first.start()
            self.assertTrue(inside.wait(5))
            second = threading.Thread(target=self.refresh.cmd_run, args=(self.args(),))
            second.start()
            time.sleep(0.3)
            self.assertEqual(order, ["build"], "the second run waits while the first builds")
            release.set()
            first.join(5)
            second.join(5)
        self.assertEqual(len(order), 2)
        self.assertIn('"tag":"second"', (self.state / "data.js").read_text())

    def test_a_throttled_run_that_waited_skips_because_the_data_it_waited_for_is_fresh(self):
        inside, release, builds = threading.Event(), threading.Event(), []

        def build():
            builds.append(1)
            inside.set()
            release.wait(5)
            return self.data()

        with mock.patch.object(self.refresh, "build", build):
            first = threading.Thread(target=self.refresh.cmd_run, args=(self.args(),))
            first.start()
            self.assertTrue(inside.wait(5))
            second = threading.Thread(target=self.refresh.cmd_run, args=(self.args(throttle=10),))
            second.start()
            time.sleep(0.2)
            release.set()
            first.join(5)
            second.join(5)
        self.assertEqual(len(builds), 1)

    def test_a_forced_run_after_a_throttled_one_still_rebuilds(self):
        with mock.patch.object(self.refresh, "build", return_value=self.data()) as build:
            self.refresh.cmd_run(self.args(throttle=10))
            self.refresh.cmd_run(self.args())
        self.assertEqual(build.call_count, 2)

    def test_a_run_gives_up_after_the_wait_and_never_hangs(self):
        self.state.mkdir(parents=True)
        held = self.refresh.take_lock(self.state / "refresh.lock", 0)
        try:
            started = time.monotonic()
            with mock.patch.object(self.refresh, "LOCK_WAIT", 0.2), mock.patch.object(self.refresh, "build") as build:
                self.refresh.cmd_run(self.args())
            self.assertLess(time.monotonic() - started, 3)
        finally:
            os.close(held)
        build.assert_not_called()

    def test_a_lock_file_left_by_a_killed_process_does_not_block(self):
        self.state.mkdir(parents=True)
        (self.state / "refresh.lock").write_text("")
        with mock.patch.object(self.refresh, "build", return_value=self.data()) as build:
            self.refresh.cmd_run(self.args())
        self.assertEqual(build.call_count, 1)

    def test_two_processes_cannot_hold_the_lock_at_once(self):
        self.state.mkdir(parents=True)
        first = self.refresh.take_lock(self.state / "refresh.lock", 0)
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(self.refresh.take_lock(self.state / "refresh.lock", 0))
        finally:
            os.close(first)
        second = self.refresh.take_lock(self.state / "refresh.lock", 0)
        self.assertIsNotNone(second, "released when the holder closes it")
        os.close(second)

    def test_a_symlink_directory_or_fifo_at_the_lock_name_is_refused_without_blocking(self):
        self.state.mkdir(parents=True)
        lock = self.state / "refresh.lock"
        target = Path(self.tmp.name) / "elsewhere"
        lock.symlink_to(target)
        self.assertIsNone(self.refresh.take_lock(lock, 0))
        self.assertFalse(target.exists())
        lock.unlink()
        lock.mkdir()
        self.assertIsNone(self.refresh.take_lock(lock, 0))
        lock.rmdir()
        os.mkfifo(lock)
        started = time.monotonic()
        self.assertIsNone(self.refresh.take_lock(lock, 0))
        self.assertLess(time.monotonic() - started, 2)

    def test_a_refused_lock_does_not_lose_the_request_to_open_the_page(self):
        self.state.mkdir(parents=True)
        (self.state / "dashboard.html").write_text("<html></html>")
        held = self.refresh.take_lock(self.state / "refresh.lock", 0)
        try:
            with mock.patch.object(self.refresh, "LOCK_WAIT", 0.1), mock.patch.object(self.refresh.webbrowser, "open") as opened, \
                    mock.patch.object(self.refresh, "build") as build:
                self.refresh.cmd_run(self.args(open_page=True))
        finally:
            os.close(held)
        opened.assert_called_once()
        build.assert_not_called()

    def test_purge_leaves_the_lock_file_so_a_holder_keeps_the_only_lock(self):
        self.state.mkdir(parents=True)
        held = self.refresh.take_lock(self.state / "refresh.lock", 0)
        try:
            self.refresh.cmd_purge(mock.Mock(yes=True))
            self.assertTrue((self.state / "refresh.lock").exists())
            self.assertIsNone(self.refresh.take_lock(self.state / "refresh.lock", 0))
        finally:
            os.close(held)


if __name__ == "__main__":
    unittest.main()
