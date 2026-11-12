"""Advisory capacity uses canonical synthetic account state, never process settings."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import parallel_slots as slots
import project_progress as progress


class ParallelSlotsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve() / 'repository'
        (self.repo / '.git').mkdir(parents=True)
        self.code = progress.repository_code(self.repo)
        cwd = mock.patch('os.getcwd', return_value=str(self.repo))
        cwd.start()
        self.addCleanup(cwd.stop)
        self.home = account(self, Path(temporary.name) / 'home')
        self.root = self.home / '.finolabs' / 'vibecode'
        self.root.mkdir(parents=True, mode=0o700)
        patch = mock.patch.dict(os.environ, {}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, name, text):
        path = self.root / name
        path.write_text(text)
        path.chmod(0o600)
        return path

    def settings(self, values, repo=None, approve=True):
        """Write a project settings file as the setter does (0700 folders, a 0600 file) and approve its bytes."""
        import hashlib
        repo = repo or self.repo
        raw = json.dumps(dict(version=1, **values)).encode()
        folder = repo / '.finolabs/vibecode'
        folder.mkdir(parents=True, exist_ok=True)
        os.chmod(repo / '.finolabs', 0o700)
        os.chmod(folder, 0o700)
        (folder / 'settings.json').write_bytes(raw)
        os.chmod(folder / 'settings.json', 0o600)
        if approve:
            with slots.dr.data_folder('state/settings-approved', create=True, private=True) as approvals:
                slots.dr.atomic_write(approvals, progress.repository_code(repo) + '.json', json.dumps(
                    dict(sha256=hashlib.sha256(raw).hexdigest(), approved=1)).encode())
        return raw

    def host(self, total=6, caps='codex=3', **extra):
        values = dict(parallel=str(total), **extra)
        if caps is not None:
            values['parallel-caps'] = caps
        return self.settings(values)

    def ledger(self, agents):
        rows = [dict(event='start', id=str(n), agent=agent, project=self.repo.name) for n, agent in enumerate(agents)]
        return self.write('ledger.jsonl', '\n'.join(map(json.dumps, rows)) + '\n')

    def command(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = slots.main(list(args))
        return code, out.getvalue()

    def test_counts_mapping_finished_duplicate_and_order_independent(self):
        self.host(9, 'claude=4, codex=3')
        rows = [dict(event='finish', id='0'), dict(event='start', id='0', agent='codex')]
        rows += [dict(event='start', id=str(n + 1), agent=agent, project=self.repo.name) for n, agent in enumerate(slots.AGENTS)]
        rows.append(rows[-1])
        self.write('ledger.jsonl', '\n'.join(map(json.dumps, rows)))
        state = slots.status()
        self.assertEqual(state, dict(limit=9, open=5, stale=0, free=4, source='project settings', scope=dict(code=self.code, project=self.repo.name), other_projects=0, families={
            'claude': dict(open=3, cap=4, free=1), 'codex': dict(open=1, cap=3, free=2),
            'antigravity': dict(open=1, cap=None, free=None)}))
        code, output = self.command('status')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), state)

    def test_ended_and_away_lines_are_skipped_not_invalid(self):
        self.host(6, 'codex=3')
        rows = [dict(event='start', id='a', agent='codex', project=self.repo.name),
                dict(event='ended', id='a', ts='2026-11-12T00:00:00+00:00', exit=0),
                dict(event='decision', id='x'), dict(event='question_denied', id='y'),
                dict(event='start', id='b', agent='claude', project=self.repo.name),
                dict(event='finish', id='b')]
        self.write('ledger.jsonl', '\n'.join(map(json.dumps, rows)) + '\n')
        state = slots.status()
        self.assertEqual((state['open'], state['families']['codex']['open']), (1, 1))
        self.write('ledger.jsonl', json.dumps(dict(event='bogus', id='z')) + '\n')
        with self.assertRaises(ValueError):
            slots.open_counts((self.root / 'ledger.jsonl').read_bytes())

    def test_dispatches_past_their_hard_cap_are_stale_and_left_out(self):
        from datetime import datetime, timedelta, timezone
        now = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
        def start(n, agent, minutes_ago, budget='30', naive=False):
            when = now - timedelta(minutes=minutes_ago)
            row = dict(event='start', id=str(n), agent=agent, ts=(when.replace(tzinfo=None) if naive else when).isoformat())
            if budget is not None:
                row['budget_min'] = int(budget)
            return json.dumps(row)
        raw = '\n'.join([
            start(1, 'codex', 41),                  # budget 30: hard cap 40 minutes, so stale
            start(2, 'codex', 39),                  # inside the cap, counted
            start(3, 'claude', 600, budget='5'),    # cap is at least budget plus 10 minutes: stale
            start(4, 'antigravity', 600, budget=None),   # no budget: cannot tell, counted
            start(5, 'codex', 600, naive=True),     # no time zone: cannot tell, counted
            start(6, 'claude', 12, budget='5'),     # 12 < 15: counted
        ]).encode()
        stale = {}
        counts = slots.open_counts(raw, now=now, stale=stale)
        self.assertEqual(counts, dict(claude=1, codex=2, antigravity=1))
        self.assertEqual(stale, dict(codex=1, claude=1))
        self.assertEqual(slots.open_counts(raw, now=now), counts)

    def test_status_and_summary_report_stale_dispatches_without_counting_them(self):
        from datetime import datetime, timedelta, timezone
        self.host(4, None)
        old = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
        rows = [dict(event='start', id='old', agent='codex', project=self.repo.name, ts=old, budget_min=30)]
        self.write('ledger.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
        state = slots.status()
        self.assertEqual((state['open'], state['stale'], state['free']), (0, 1, 4))
        self.assertIn('1 stale not counted', slots.summary())
        self.assertEqual(self.command('check', '--family', 'codex', '--count', '4'), (0, 'Parallel slots: available\n'))

    def test_check_both_limits_overfull_and_count(self):
        self.host()
        self.ledger(['claude', 'codex', 'codex', 'codex'])
        for family, count, expected in [('codex', 1, False), ('claude', 2, True), ('claude', 3, False),
                                         ('antigravity', 2, True), ('claude', 33, False)]:
            with self.subTest(family=family, count=count):
                self.assertEqual(self.command('check', '--family', family, '--count', str(count)),
                                 (0, 'Parallel slots: available\n') if expected else (3, 'Parallel slots: full\n'))
        self.ledger(['claude'] * 7)
        self.assertEqual(slots.status()['free'], 0)
        self.assertEqual(self.command('check', '--family', 'antigravity'), (3, 'Parallel slots: full\n'))
        self.host(32, None)
        self.assertEqual(slots.status()['limit'], 32)

    def test_missing_and_invalid_totals_default_with_source(self):
        self.assertEqual(slots.status()['limit'], 3)
        for text in ('', '# Host\n', '## Other\n- Parallel dispatches: at most 8 at one time.\n',
                     *('## Limits\n- Parallel dispatches: at most %s at one time.\n' % value
                       for value in ('0', '33', '-1', '1.5', 'five', 'True', '9 extra')),
                     '## Limits\n- Parallel dispatches: at most 8 at one time.\n' * 1 +
                     '- Parallel dispatches: at most 9 at one time.\n'):
            with self.subTest(text=text):
                self.write('host.md', text)
                state = slots.status()
                self.assertEqual((state['limit'], state['source'], state['open']), (3, 'default', 0))
                self.assertEqual(self.command('check-config')[0], 3)
        for total in (1, 6, 32):
            self.host(total, None)
            self.assertEqual(slots.status()['limit'], total)

    def test_config_validation_subset_and_bad_caps(self):
        self.host(12, 'antigravity=2, claude=4')
        code, output = self.command('check-config')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), dict(limit=12, source='project settings',
                                                caps=dict(claude=4, codex=None, antigravity=2), legacy_limits=False))
        # An approved but invalid file is unknown, never the default of three.
        for caps in ('', 'codex=0', 'codex=33', 'codex=2, codex=3', 'other=1', 'codex=true',
                     'codex=2,', 'codex=2\n- %s parallel-caps: claude=1' % self.code):
            self.host(12, caps)
            self.assertEqual(self.command('status'), (3, 'unknown\n'))
            self.assertEqual(self.command('check-config'), (3, 'unknown\n'))
            self.assertEqual(self.command('check', '--family', 'codex'), (3, 'Parallel slots: unknown\n'))
        # A valid cap above the total is a contradiction the reader reports as unknown, as before.
        self.host(12, 'codex=13')
        self.assertEqual(self.command('status'), (3, 'unknown\n'))
        self.assertEqual(self.command('check-config'), (3, 'unknown\n'))

    def test_repository_scope_alias_other_projects_and_cli_repo(self):
        from datetime import datetime, timedelta, timezone
        self.host(2, 'codex=1', ledger='Alias')
        other = self.repo.parent / 'other'
        (other / '.git').mkdir(parents=True)
        old = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
        rows = [dict(event='start', id='mine', agent='codex', project='Alias'),
                dict(event='start', id='other', agent='claude', project='other'),
                dict(event='start', id='unknown', agent='codex'),
                dict(event='start', id='old-other', agent='codex', project='other', ts=old, budget_min=30)]
        self.write('ledger.jsonl', '\n'.join(map(json.dumps, rows)))
        state = slots.status()
        self.assertEqual((state['limit'], state['open'], state['other_projects'], state['stale']), (2, 1, 2, 0))
        self.assertEqual(state['scope'], dict(code=self.code, project='Alias'))
        code, output = self.command('status', '--repo', str(other / '.git'))
        self.assertEqual(code, 0)
        other_state = json.loads(output)
        self.assertEqual((other_state['limit'], other_state['source'], other_state['open'], other_state['other_projects']),
                         (3, 'default', 1, 2))
        self.assertEqual(self.command('check', '--repo', str(other), '--family', 'codex', '--count', '5'),
                         (3, 'Parallel slots: full\n'))
        code, output = self.command('check-config', '--repo', str(self.repo))
        self.assertEqual((code, json.loads(output)['limit']), (0, 2))

    def test_host_md_settings_and_the_global_ledger_line_are_never_read(self):
        self.write('host.md', '## Project progress\n- Ledger project: LegacyAlias\n\n## Project settings\n'
                              '- %s parallel: 9\n- %s ledger: HostName\n' % (self.code, self.code))
        rows = [dict(event='start', id='legacy', agent='codex', project='LegacyAlias'),
                dict(event='start', id='host', agent='codex', project='HostName'),
                dict(event='start', id='folder', agent='codex', project=self.repo.name)]
        self.write('ledger.jsonl', '\n'.join(map(json.dumps, rows)))
        state = slots.status()
        self.assertEqual((state['limit'], state['source'], state['open'], state['other_projects']), (3, 'default', 1, 2))
        self.assertEqual(state['scope']['project'], self.repo.name)
        self.host(2, None, ledger='EntryName')
        self.assertEqual(slots.status()['scope']['project'], 'EntryName')
        self.assertEqual(slots.status()['limit'], 2)

    def test_an_unapproved_settings_file_cannot_raise_the_limit(self):
        self.host(2, None)
        self.ledger(['codex', 'codex'])
        self.assertEqual(self.command('check', '--family', 'codex'), (3, 'Parallel slots: full\n'))
        # Replacing an approved file is unknown, never available and never the default.
        self.settings(dict(parallel='32'), approve=False)
        self.assertEqual(self.command('status'), (3, 'unknown\n'))
        self.assertEqual(self.command('check', '--family', 'codex'), (3, 'Parallel slots: unknown\n'))
        # With no approval record at all, a file nobody approved here sets nothing: the default.
        (self.root / 'state/settings-approved' / (self.code + '.json')).unlink()
        state = slots.status()
        self.assertEqual((state['limit'], state['source']), (3, 'default'))
        (self.repo / '.finolabs/vibecode/settings.json').write_text(json.dumps(dict(version=1, parallel='32')))
        self.assertEqual(slots.status()['limit'], 3)

    def test_outside_repository_counts_nothing_and_ignores_legacy_limits(self):
        self.write('host.md', '## Limits\n- Parallel dispatches: at most 32 at one time.\n')
        self.ledger(['codex', 'claude'])
        code, output = self.command('status', '--repo', str(self.repo.parent))
        self.assertEqual(code, 0)
        state = json.loads(output)
        self.assertEqual((state['scope'], state['limit'], state['source'], state['open'], state['other_projects']),
                         (None, 3, 'default', 0, 2))
        code, output = self.command('check-config', '--repo', str(self.repo.parent))
        self.assertEqual((code, json.loads(output)['legacy_limits']), (3, True))
        self.host(2, None)
        with (self.root / 'host.md').open('a') as host:
            host.write('## Limits\n- Parallel dispatches: at most 32 at one time.\n')
        self.assertEqual(slots.status()['limit'], 2)
        self.assertTrue(json.loads(self.command('check-config')[1])['legacy_limits'])
        (self.root / 'host.md').unlink()
        state = json.loads(self.command('status', '--repo', str(self.repo.parent))[1])
        self.assertEqual((state['limit'], state['source'], state['scope'], state['open']), (3, 'default', None, 0))

    def test_root_and_identity_parity_plain_checkout_and_linked_worktree(self):
        worktree = self.repo.parent / 'linked'
        worktree.mkdir()
        metadata = self.repo / '.git/worktrees/linked'
        metadata.mkdir(parents=True)
        (metadata / 'commondir').write_text('../..\n')
        (worktree / '.git').write_text('gitdir: ../repository/.git/worktrees/linked\n')
        (metadata / 'gitdir').write_text(str(worktree / '.git') + '\n')
        nested = worktree / 'nested'
        nested.mkdir()
        for path in (self.repo, self.repo / '.git', worktree, nested, self.repo.parent):
            with self.subTest(path=path):
                self.assertEqual(slots.find_root(path), progress.find_root(path))
        self.assertEqual(slots.repository_code(self.repo), progress.repository_code(self.repo))
        self.assertEqual(slots.repository_code(worktree), progress.repository_code(worktree))
        self.assertEqual(slots.repository_code(worktree), self.code)
        self.host(2, None)
        state = json.loads(self.command('status', '--repo', str(nested))[1])
        self.assertEqual((state['limit'], state['scope']['code'], state['scope']['project']), (2, self.code, 'linked'))
        (metadata / 'commondir').unlink()
        (metadata / 'commondir').symlink_to(self.repo / 'missing')
        self.assertEqual(slots.repository_code(worktree), progress.repository_code(worktree))

    def test_strict_project_settings_file_is_unknown_when_any_approved_value_is_invalid(self):
        for bad in (dict(parallel='0'), dict(parallel='33'), dict(parallel='two'), dict(parallel=2),
                    {'parallel-caps': 'codex=1, codex=2'}, dict(unknown='x'),
                    dict(ledger=''), dict(tasks='../bad.md'), dict(tasks='AGENTS.md'), dict(label='a;b')):
            with self.subTest(bad=bad):
                self.settings(dict(dict(parallel='2'), **bad))
                self.assertEqual(self.command('status'), (3, 'unknown\n'))
        self.host(2, None)
        self.assertEqual(slots.status()['limit'], 2)

    def test_caps_without_total_use_default_and_legacy_sections_are_only_detected(self):
        for cap in (3, 4):
            self.settings({'parallel-caps': 'codex=%s' % cap})
            code, output = self.command('status')
            if cap == 3:
                state = json.loads(output)
                self.assertEqual((code, state['limit'], state['source'], state['families']['codex']['cap']),
                                 (0, 3, 'default', 3))
                self.assertEqual(self.command('check-config')[0], 3)
            else:
                self.assertEqual((code, output), (3, 'unknown\n'))
        (self.repo / '.finolabs/vibecode/settings.json').unlink()
        self.assertEqual(self.command('status'), (3, 'unknown\n'))
        (self.root / 'state/settings-approved' / (self.code + '.json')).unlink()
        self.write('host.md', '## Limits\n- Parallel per family: broken\n## Limits\n')
        self.assertEqual(slots.status()['limit'], 3)
        self.assertTrue(json.loads(self.command('check-config')[1])['legacy_limits'])
        self.write('host.md', '```\n## Limits\n```\n')
        self.assertFalse(json.loads(self.command('check-config')[1])['legacy_limits'])

    def test_unsafe_unreadable_and_bounded_inputs_never_echo(self):
        for name, limit in [('host.md', slots.HOST_LIMIT), ('ledger.jsonl', slots.LEDGER_LIMIT)]:
            for kind in ('writable', 'symlink', 'directory', 'fifo', 'oversize', 'unicode'):
                with self.subTest(name=name, kind=kind):
                    path = self.write(name, '')
                    if kind == 'writable':
                        path.chmod(0o666)
                    elif kind == 'symlink':
                        path.unlink()
                        path.symlink_to(self.root / 'missing')
                    elif kind == 'directory':
                        path.unlink()
                        path.mkdir()
                    elif kind == 'fifo':
                        path.unlink()
                        os.mkfifo(path)
                    elif kind == 'oversize':
                        path.write_bytes(b'x' * (limit + 1))
                    else:
                        path.write_bytes(b'\xff')
                    self.assertEqual(self.command('status'), (3, 'unknown\n'))
                    self.assertEqual(self.command('check', '--family', 'codex'), (3, 'Parallel slots: unknown\n'))
                    self.assertEqual(slots.summary(), 'unknown')
                    path.rmdir() if path.is_dir() else path.unlink()
        with mock.patch.object(slots.dr, 'read_data', side_effect=PermissionError('private')):
            self.assertEqual(self.command('status'), (3, 'unknown\n'))
        self.write('root.json', '{}')
        self.assertEqual(self.command('status'), (3, 'unknown\n'))

    def test_malformed_ledger_is_unknown_and_counts_do_not_hide_ambiguous_runs(self):
        for raw in ('{broken', '[]', '{}', '{"id":1,"event":"start"}',
                    '{"id":"x","event":"start","agent":"other"}',
                    '{"id":"x","event":"start","agent":"codex"}\n'
                    '{"id":"x","event":"start","agent":"claude"}',
                    '{"id":"x","event":"start","agent":"codex","project":"a"}\n'
                    '{"id":"x","event":"start","agent":"codex","project":"b"}'):
            self.write('ledger.jsonl', raw)
            self.assertEqual(self.command('status'), (3, 'unknown\n'))

    def test_no_process_network_or_write_and_no_environment_override(self):
        self.host(8, None)
        self.ledger(['codex'] * 3)
        def snapshot():
            return {str(p): p.read_bytes() for folder in (self.root, self.repo)
                    for p in folder.rglob('*') if p.is_file()}
        before = snapshot()
        import socket
        import subprocess
        with mock.patch.object(socket, 'socket', side_effect=AssertionError('network')), \
                mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('process')):
            self.assertEqual(slots.status()['free'], 5)
        self.assertEqual(snapshot(), before)
        for folder in ('delegate', 'status'):
            self.assertEqual((ROOT / 'scripts/parallel_slots.py').read_bytes(),
                             (ROOT / 'skills' / folder / 'scripts/parallel_slots.py').read_bytes())

    def test_environment_paths_cannot_replace_canonical_state(self):
        self.host(8, None)
        self.ledger(['codex'] * 3)
        alternate = self.home / 'alternate'
        alternate.mkdir()
        config = alternate / 'host.md'
        config.write_text('## Limits\n- Parallel dispatches: at most 32 at one time.\n')
        ledger = alternate / 'ledger.jsonl'
        ledger.write_text('')
        with mock.patch.dict(os.environ, {'ORCHESTRATION_HOST_CONFIG': str(config),
                                         'ORCHESTRATION_LEDGER': str(ledger),
                                         'FNL_STATE_DIR': str(alternate)}, clear=True):
            self.assertEqual((slots.status()['limit'], slots.status()['open']), (8, 3))

    def test_relocated_canonical_root_uses_identity_checked_data_root(self):
        relocated = self.home / 'storage'
        relocated.mkdir(mode=0o700)
        (relocated / '.root-id').write_text('synthetic')
        (relocated / '.root-id').chmod(0o600)
        slots.dr.write_pointer(relocated, 'synthetic')
        self.host(10, None)
        self.assertEqual(slots.status()['limit'], 10)
        (relocated / '.root-id').write_text('changed')
        self.assertEqual(self.command('status'), (3, 'unknown\n'))

    def test_cli_isolated_entry_point_uses_fixture_account(self):
        import subprocess
        self.host(8, None)
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/parallel_slots.py'), 'status'],
                                capture_output=True, text=True, env={}, cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['limit'], 8)


if __name__ == '__main__':
    unittest.main()
