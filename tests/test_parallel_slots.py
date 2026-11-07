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


class ParallelSlotsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
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

    def host(self, total=6, caps='codex=3'):
        return self.write('host.md', '## Limits\n- Parallel dispatches: at most %s at one time.\n' % total +
                          ('- Parallel per family: %s\n' % caps if caps is not None else ''))

    def ledger(self, agents):
        rows = [dict(event='start', id=str(n), agent=agent) for n, agent in enumerate(agents)]
        return self.write('ledger.jsonl', '\n'.join(map(json.dumps, rows)) + '\n')

    def command(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = slots.main(list(args))
        return code, out.getvalue()

    def test_counts_mapping_finished_duplicate_and_order_independent(self):
        self.host(9, 'claude=4, codex=3')
        rows = [dict(event='finish', id='0'), dict(event='start', id='0', agent='codex')]
        rows += [dict(event='start', id=str(n + 1), agent=agent) for n, agent in enumerate(slots.AGENTS)]
        rows.append(rows[-1])
        self.write('ledger.jsonl', '\n'.join(map(json.dumps, rows)))
        state = slots.status()
        self.assertEqual(state, dict(limit=9, open=5, free=4, source='host config', families={
            'claude': dict(open=3, cap=4, free=1), 'codex': dict(open=1, cap=3, free=2),
            'antigravity': dict(open=1, cap=None, free=None)}))
        code, output = self.command('status')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), state)

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
        self.assertEqual(slots.status()['limit'], 5)
        for text in ('', '# Host\n', '## Other\n- Parallel dispatches: at most 8 at one time.\n',
                     *('## Limits\n- Parallel dispatches: at most %s at one time.\n' % value
                       for value in ('0', '33', '-1', '1.5', 'five', 'True', '9 extra')),
                     '## Limits\n- Parallel dispatches: at most 8 at one time.\n' * 1 +
                     '- Parallel dispatches: at most 9 at one time.\n'):
            with self.subTest(text=text):
                self.write('host.md', text)
                state = slots.status()
                self.assertEqual((state['limit'], state['source'], state['open']), (5, 'default', 0))
                self.assertEqual(self.command('check-config')[0], 3)
        for total in (1, 6, 32):
            self.host(total, None)
            self.assertEqual(slots.status()['limit'], total)

    def test_config_validation_subset_and_bad_caps(self):
        self.host(12, 'antigravity=2, claude=4')
        code, output = self.command('check-config')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), dict(limit=12, source='host config',
                                                caps=dict(claude=4, codex=None, antigravity=2)))
        for caps in ('', 'codex=0', 'codex=13', 'codex=2, codex=3', 'other=1', 'codex=true',
                     'codex=2,', 'codex=2\n- Parallel per family: claude=1'):
            self.host(12, caps)
            self.assertEqual(self.command('status'), (3, 'unknown\n'))
            self.assertEqual(self.command('check-config'), (3, 'unknown\n'))
        self.write('host.md', '## Limits\n## Limits\n')
        self.assertEqual(self.command('status'), (3, 'unknown\n'))

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
                    '{"id":"x","event":"start","agent":"claude"}'):
            self.write('ledger.jsonl', raw)
            self.assertEqual(self.command('status'), (3, 'unknown\n'))

    def test_no_process_network_or_write_and_no_environment_override(self):
        self.host(8, None)
        self.ledger(['codex'] * 3)
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        import socket
        import subprocess
        with mock.patch.object(socket, 'socket', side_effect=AssertionError('network')), \
                mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('process')):
            self.assertEqual(slots.status()['free'], 5)
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)
        for folder in ('fnl-delegate', 'fnl-status'):
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
        (relocated / 'host.md').write_text('## Limits\n- Parallel dispatches: at most 10 at one time.\n')
        self.assertEqual(slots.status()['limit'], 10)
        (relocated / '.root-id').write_text('changed')
        self.assertEqual(self.command('status'), (3, 'unknown\n'))

    def test_cli_isolated_entry_point_uses_fixture_account(self):
        import subprocess
        self.host(8, None)
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/parallel_slots.py'), 'status'],
                                capture_output=True, text=True, env={})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['limit'], 8)


if __name__ == '__main__':
    unittest.main()
