"""The pause marker, its status verdict and the heavy_run refusal; every case uses a temporary home and synthetic readings."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills' / 'delegate' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import heavy_run as heavy
import pause

DAY = 24 * 3600


class Base(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = account(self, Path(temporary.name) / 'home')
        self.root = self.home / '.finolabs' / 'vibecode'
        self.state = self.root / 'state'
        self.state.mkdir(parents=True, mode=0o700)
        self.root.chmod(0o700)
        (self.home / '.finolabs').chmod(0o700)
        patch = mock.patch.dict(os.environ, {'PATH': os.environ.get('PATH', '')}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def marker(self, **fields):
        data = {'started': time.time() - 60, 'kind': 'none', 'deadline': 0, **fields}
        self.raw_marker(json.dumps(data).encode())

    def raw_marker(self, raw, mode=0o600):
        path = self.state / 'pause.json'
        path.unlink(missing_ok=True)
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pause.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def ledger(self, *dispatches):
        lines = []
        for ident, minutes_ago, budget in dispatches:
            ts = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() - minutes_ago * 60))
            lines.append(json.dumps({'event': 'start', 'id': ident, 'ts': ts, 'project': 'p', 'task': 't', 'kind': 'implement',
                                     'grade': 'easy', 'agent': 'codex', 'model': 'm', 'reason': 'routing', 'budget_min': budget}))
        path = self.root / 'ledger.jsonl'
        path.write_text('\n'.join(lines) + '\n')
        path.chmod(0o600)

    def heavy(self, state='free', orphan=False, waiting=0):
        fd = os.open(os.devnull, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        for name, value in (('lock_state', lambda: state), ('open_lock', lambda: os.dup(fd)),
                            ('previous_group_running', lambda _fd: orphan), ('waiting_count', lambda: waiting),
                            ('holder', lambda: None)):
            patcher = mock.patch.object(heavy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def handover(self, session, age=0):
        import handover_state
        handover_state.write(session, 'goal')
        path = self.state / 'handover' / handover_state.filename(session)
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))


class MarkerStateTest(Base):
    def test_missing(self):
        self.assertEqual(pause.marker_state()[0], 'missing')
        self.assertFalse(pause.paused())

    def test_active_with_parsed_data(self):
        self.marker(kind='shutdown', deadline=time.time() + 600)
        state, data = pause.marker_state()
        self.assertEqual((state, data['kind']), ('active', 'shutdown'))
        self.assertTrue(pause.paused())

    def test_expired_after_a_day(self):
        self.marker(started=time.time() - DAY - 5)
        self.assertEqual(pause.marker_state()[0], 'expired')
        self.assertFalse(pause.paused())

    def test_invalid_shapes_are_never_a_pause(self):
        now = time.time()
        cases = {
            'wrong keys': {'started': now, 'kind': 'none'},
            'extra key': {'started': now, 'kind': 'none', 'deadline': 0, 'path': '/x'},
            'string started': {'started': 'now', 'kind': 'none', 'deadline': 0},
            'bool started': {'started': True, 'kind': 'none', 'deadline': 0},
            'bad kind': {'started': now, 'kind': 'reboot', 'deadline': 0},
            'negative deadline': {'started': now, 'kind': 'none', 'deadline': -1},
            'future start': {'started': now + 301, 'kind': 'none', 'deadline': 0},
        }
        for name, data in cases.items():
            with self.subTest(name):
                self.raw_marker(json.dumps(data).encode())
                self.assertEqual(pause.marker_state()[0], 'invalid')
                self.assertFalse(pause.paused())
        self.raw_marker(b'not json')
        self.assertEqual(pause.marker_state()[0], 'invalid')

    def test_small_future_skew_is_active(self):
        self.marker(started=time.time() + 100)
        self.assertEqual(pause.marker_state()[0], 'active')

    def test_unsafe_files_are_invalid(self):
        valid = json.dumps({'started': time.time(), 'kind': 'none', 'deadline': 0}).encode()
        self.raw_marker(valid, mode=0o660)
        self.assertEqual(pause.marker_state()[0], 'invalid')
        self.raw_marker(valid + b' ' * 600)
        self.assertEqual(pause.marker_state()[0], 'invalid')
        target = self.state / 'target'
        target.write_bytes(valid)
        target.chmod(0o600)
        (self.state / 'pause.json').unlink()
        (self.state / 'pause.json').symlink_to(target)
        self.assertEqual(pause.marker_state()[0], 'invalid')
        self.assertFalse(pause.paused())


class OversizedNumbersTest(Base):
    def test_an_integer_too_large_for_a_float_is_an_invalid_marker_not_an_error(self):
        self.raw_marker(('{"started":1%s,"kind":"none","deadline":0}' % ('0' * 400)).encode())
        self.assertEqual(pause.marker_state()[0], 'invalid')
        self.assertFalse(pause.paused())
        code, out, _ = self.cli('status')
        self.assertEqual(code, 0)
        self.assertIn('pause: invalid', out)


class StartTest(Base):
    def test_start_writes_exactly_three_keys_and_a_summary(self):
        code, out, _ = self.cli('start', 'shutdown', '--in', '15')
        self.assertEqual(code, 0)
        data = json.loads((self.state / 'pause.json').read_text())
        self.assertEqual(set(data), {'started', 'kind', 'deadline'})
        self.assertEqual(data['kind'], 'shutdown')
        self.assertAlmostEqual(data['deadline'] - data['started'], 900, delta=1)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn('shutdown', out)
        self.assertEqual(oct((self.state / 'pause.json').stat().st_mode & 0o777), '0o600')

    def test_kind_and_deadline_are_optional(self):
        self.assertEqual(self.cli('start')[0], 0)
        data = json.loads((self.state / 'pause.json').read_text())
        self.assertEqual((data['kind'], data['deadline']), ('none', 0))

    def test_deadline_bounds_and_kind_choices(self):
        for argv in (['start', '--in', '0'], ['start', '--in', '1441'], ['start', '--in', 'x'], ['start', 'reboot']):
            with self.subTest(argv), self.assertRaises(SystemExit):
                self.cli(*argv)
        self.assertEqual(self.cli('start', '--in', '1440')[0], 0)
        self.assertEqual(self.cli('start', '--in', '1')[0], 0)

    def test_an_existing_marker_is_replaced_and_said_so(self):
        self.marker(kind='restart')
        _, out, _ = self.cli('start', 'shutdown')
        self.assertIn('replaced', out)
        self.assertEqual(json.loads((self.state / 'pause.json').read_text())['kind'], 'shutdown')

    def test_start_ends_an_active_autopilot_lease(self):
        import autopilot
        calls = []
        with mock.patch.object(autopilot, 'stop', lambda folder: calls.append(folder)):
            self.cli('start')
            self.assertEqual(calls, [])  # no lease: nothing to end, and that is fine
            with mock.patch.object(autopilot, 'read_private', lambda folder, name, cap=0: b'{}'):
                _, out, _ = self.cli('start')
        self.assertEqual(len(calls), 1)
        self.assertIn('lease ended', out)

    def test_start_survives_an_autopilot_failure_and_says_so(self):
        import autopilot
        stop = mock.Mock(side_effect=OSError('x'))
        with mock.patch.object(autopilot, 'read_private', lambda folder, name, cap=0: b'{}'), \
                mock.patch.object(autopilot, 'stop', stop):
            code, out, _ = self.cli('start')
        self.assertEqual(code, 0)
        stop.assert_called_once()
        self.assertTrue(pause.paused())
        self.assertIn('autopilot lease not checked', out)


class StatusTest(Base):
    def setUp(self):
        super().setUp()
        self.marker()
        self.heavy()
        self.ledger()

    def status(self, *extra):
        return self.cli('status', *extra)[1]

    def verdict(self, *extra):
        return [line for line in self.status(*extra).splitlines() if line.startswith('verdict:')][0]

    def test_clear_when_nothing_is_recorded(self):
        out = self.status()
        self.assertIn('verdict: no recorded work remains', out)
        self.assertIn('restarting is your call', out)
        self.assertIn('outside heavy_run.py', out)

    def test_open_dispatch_blocks_and_stalled_is_reported_not_stopped(self):
        self.ledger(('d1', 10, 60), ('d2', 90, 60))
        out = self.status()
        self.assertTrue(self.verdict().startswith('verdict: blocked:'))
        self.assertIn('d1', out)
        stalled = [line for line in out.splitlines() if 'd2' in line][0]
        self.assertIn('stalled', stalled)
        self.assertNotIn('stalled', [line for line in out.splitlines() if 'd1' in line][0])
        self.assertIn("coordinator's own record", out)

    def test_held_lock_blocks(self):
        self.heavy(state='held', waiting=1)
        self.assertTrue(self.verdict().startswith('verdict: blocked:'))
        self.assertIn('lock', self.verdict())

    def test_a_known_holder_is_described_and_an_unknown_one_says_so(self):
        self.heavy(state='held')
        self.assertIn('owner unknown', self.status())
        record = {'label': 'build', 'pid': 123, 'started': int(time.time()) - 60, 'deadline': int(time.time()) + 600}
        with mock.patch.object(heavy, 'holder', lambda: record):
            out = self.status()
        self.assertIn('label: build', out)
        self.assertIn('pid: 123', out)

    def test_each_run_reports_how_many_checkpoints_it_checked(self):
        self.cli('start')
        self.heavy()
        self.handover('session-aaaa1111')
        self.handover('session-bbbb2222')
        one = self.status('--checkpoint', 'session-aaaa1111')
        two = self.status('--checkpoint', 'session-aaaa1111', '--checkpoint', 'session-bbbb2222')
        self.assertIn('checkpoints checked in this run: 1', one)
        self.assertIn('checkpoints checked in this run: 2', two)

    def test_stopped_wrapper_with_a_live_group_blocks(self):
        self.heavy(state='free', orphan=True)
        self.assertIn('stopped wrapper', self.verdict())
        self.assertTrue(self.verdict().startswith('verdict: blocked:'))

    def test_a_waiter_blocks_and_the_holder_is_not_counted_as_one(self):
        self.heavy(state='free', waiting=2)
        self.assertTrue(self.verdict().startswith('verdict: blocked:'))
        self.heavy(state='held', waiting=1)  # one wrapper is the holder itself
        self.assertNotIn('waiting', self.verdict())

    def test_unreadable_ledger_is_unknown(self):
        (self.root / 'ledger.jsonl').unlink()
        (self.root / 'ledger.jsonl').symlink_to(self.root / 'elsewhere')
        self.assertTrue(self.verdict().startswith('verdict: unknown:'))
        self.assertIn('ledger', self.verdict())

    def test_unknown_waiter_count_and_lock_are_unknown_not_zero(self):
        self.heavy(waiting=None)
        self.assertTrue(self.verdict().startswith('verdict: unknown:'))
        self.assertIn('waiting', self.verdict())
        self.heavy(state='refused')
        self.assertTrue(self.verdict().startswith('verdict: unknown:'))
        self.assertIn('lock', self.verdict())

    def test_blocked_wins_over_unknown(self):
        self.ledger(('d1', 1, 60))
        self.heavy(waiting=None)
        self.assertTrue(self.verdict().startswith('verdict: blocked:'))

    def test_missing_checkpoint_is_unknown_and_a_fresh_one_clears(self):
        session = 'session-abcdef12'
        self.assertIn(session, self.verdict('--checkpoint', session))
        self.assertTrue(self.verdict('--checkpoint', session).startswith('verdict: unknown:'))
        self.handover(session)
        self.assertEqual(self.verdict('--checkpoint', session), 'verdict: no recorded work remains')

    def test_a_handover_older_than_the_marker_or_expired_does_not_count(self):
        self.marker(started=time.time() - 60)
        self.handover('session-before1', age=3600)
        self.assertTrue(self.verdict('--checkpoint', 'session-before1').startswith('verdict: unknown:'))
        self.handover('session-expired', age=DAY + 60)
        self.assertTrue(self.verdict('--checkpoint', 'session-expired').startswith('verdict: unknown:'))

    def test_checkpoint_ids_are_validated(self):
        for bad in ('short', 'has space 12345', 'x' * 65, '../etc/passwd'):
            with self.subTest(bad), self.assertRaises(SystemExit):
                self.cli('status', '--checkpoint', bad)

    def test_checkpoint_without_an_active_marker_is_unknown(self):
        (self.state / 'pause.json').unlink()
        self.handover('session-abcdef12')
        self.assertTrue(self.verdict('--checkpoint', 'session-abcdef12').startswith('verdict: unknown:'))

    def test_marker_state_lines_and_deadline_messages(self):
        self.assertIn('pause: active', self.status())
        self.marker(kind='shutdown', deadline=time.time() + 600)
        out = self.status()
        self.assertRegex(out, r'to the deadline')
        self.assertIn('24 hours', out)
        self.marker(kind='restart', deadline=time.time() - 5)
        out = self.status()
        self.assertIn('deadline passed: ask the user about each remaining run, one at a time', out)
        self.assertNotIn('24 hours', out)
        self.marker(started=time.time() - DAY - 9)
        self.assertIn('pause: expired', self.status())
        self.raw_marker(b'{}')
        self.assertIn('pause: invalid', self.status())
        (self.state / 'pause.json').unlink()
        self.assertIn('pause: missing', self.status())

    def test_process_cache_is_data_after_the_verdict_and_never_collected(self):
        out = self.status()
        self.assertTrue(out.rstrip().endswith('not observed'))
        self.assertLess(out.index('verdict:'), out.index('agent processes seen, not identified: check these yourself before you restart'))
        self.cache(processes=[{'family': 'claude', 'elapsed_seconds': 5, 'descendants': {}},
                              {'family': 'claude', 'elapsed_seconds': 9, 'descendants': {}},
                              {'family': 'agy', 'elapsed_seconds': 1, 'descendants': {}}])
        out = self.status()
        self.assertIn('claude 2', out)
        self.assertIn('agy 1', out)
        self.assertIn('codex 0', out)
        self.assertEqual(self.verdict(), 'verdict: no recorded work remains')  # never an input

    def test_process_cache_off_switches_and_stale_or_bad_data(self):
        row = [{'family': 'claude', 'elapsed_seconds': 5, 'descendants': {}}]
        self.cache(processes=row)
        os.environ['FNL_AGENT_SNAPSHOT'] = 'off'
        self.assertIn('not observed', self.status())
        del os.environ['FNL_AGENT_SNAPSHOT']
        os.environ['FNL_METRICS'] = 'off'
        self.assertIn('not observed', self.status())
        del os.environ['FNL_METRICS']
        self.cache(processes=row, age=3600)
        self.assertIn('not observed', self.status())
        self.cache(processes=row, reason='ps failed')
        self.assertIn('not observed', self.status())
        self.cache(processes=row, snapshot_on=False)
        self.assertIn('not observed', self.status())
        self.cache(processes=row, consent=False)
        self.assertIn('not observed', self.status())
        self.cache(processes=row)
        (self.state / 'consent.json').write_text(json.dumps({'date': '2026-11-09', 'retention_days': None}))
        self.assertIn('not observed', self.status())
        (self.state / 'consent.json').write_text(json.dumps({'date': 5, 'retention_days': 30}))
        self.assertIn('not observed', self.status())
        (self.state / 'data.js').write_text('window.FNL_DATA = {broken')
        self.assertIn('not observed', self.status())

    def cache(self, processes, age=0, reason='', snapshot_on=True, consent=True):
        stamp = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() - age))
        body = {'running': {'processes': processes, 'snapshot': {'time': stamp, 'reason': reason, 'apps': {}}}}
        path = self.state / 'data.js'
        path.write_text('window.FNL_DATA = ' + json.dumps(body) + ';\n')
        path.chmod(0o600)
        host = self.root / 'host.md'
        host.write_text('## Agent snapshot\n\n- Snapshot: %s\n' % ('on' if snapshot_on else 'off'))
        host.chmod(0o600)
        consent_file = self.state / 'consent.json'
        consent_file.unlink(missing_ok=True)
        if consent:
            consent_file.write_text(json.dumps({'date': '2026-11-09', 'retention_days': 30}))
            consent_file.chmod(0o600)

    def test_a_fenced_snapshot_section_closed_only_by_an_info_string_line_stays_fenced(self):
        host = self.root / 'host.md'
        host.write_text('```text\n```md\n## Agent snapshot\n\n- Snapshot: on\n```\n')
        host.chmod(0o600)
        self.assertFalse(pause.host_section_on())
        host.write_text('```text\n## Agent snapshot\n- Snapshot: off\n```\n\n## Agent snapshot\n\n- Snapshot: on\n')
        self.assertTrue(pause.host_section_on())

    def test_output_has_no_paths_and_pause_runs_no_subprocess_or_network(self):
        out = self.status()
        self.assertNotIn(str(self.home), out)
        self.assertNotRegex(out, r'(^|\s)/\w')
        source = (SCRIPTS / 'pause.py').read_text()
        for word in ('subprocess', 'socket', 'urllib', 'http.client', 'os.system', 'os.popen'):
            self.assertNotIn(word, source)


class VerdictLengthTest(unittest.TestCase):
    def test_a_long_list_of_reasons_is_cut_to_five_and_a_count(self):
        import pause
        items = ['open dispatch d%d' % n for n in range(8)]
        text = pause.brief(items)
        self.assertEqual(text.count('open dispatch'), 5)
        self.assertTrue(text.endswith('; and 3 more'))
        self.assertEqual(pause.brief(items[:5]), '; '.join(items[:5]))
        self.assertEqual(pause.brief([]), '')


class ResumeTest(Base):
    def test_resume_removes_the_marker_and_missing_is_fine(self):
        self.marker()
        self.assertEqual(self.cli('resume')[0], 0)
        self.assertEqual(pause.marker_state()[0], 'missing')
        self.assertEqual(self.cli('resume')[0], 0)

    def test_resume_removes_even_an_invalid_marker(self):
        self.raw_marker(b'junk')
        self.cli('resume')
        self.assertFalse((self.state / 'pause.json').exists())

    def test_resume_counts_handovers_without_naming_them_and_lists_open_dispatches(self):
        self.marker()
        self.handover('session-aaaaaaaa', age=600)
        self.handover('session-bbbbbbbb', age=60)
        self.handover('session-cccccccc', age=DAY + 100)
        self.ledger(('d9', 5, 30))
        _, out, _ = self.cli('resume')
        self.assertIn('2 handover', out)
        self.assertIn('oldest 10 min', out)
        self.assertIn('d9', out)
        self.assertIn('without a finish line', out)
        import handover_state
        self.assertNotIn(handover_state.filename('session-aaaaaaaa')[:16], out)
        self.assertNotIn('aaaaaaaa', out)

    def test_resume_does_not_restart_autopilot_or_start_anything(self):
        import autopilot
        with mock.patch.object(autopilot, 'start', side_effect=AssertionError), \
                mock.patch.object(heavy, 'main', side_effect=AssertionError):
            self.assertEqual(self.cli('resume')[0], 0)


class HeavyRunRefusalTest(Base):
    def setUp(self):
        super().setUp()
        for name, value in (('read_load', lambda: 1.0), ('read_free_gb', lambda: 8.0), ('read_pressure', lambda: 'normal'),
                            ('read_swapout_bytes', lambda: 0)):
            patcher = mock.patch.object(heavy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        window = mock.patch.dict(heavy.DEFAULTS, {'memory_window_seconds': 0.01})
        window.start()
        self.addCleanup(window.stop)
        self.touched = self.home / 'ran'

    def run_heavy(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        command = [sys.executable, '-c', 'import pathlib; pathlib.Path(%r).write_text("x")' % str(self.touched)]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = heavy.main(['--poll', '0.02', 'run', *extra, '--', *command])
        return code, err.getvalue()

    MESSAGE = 'heavy_run: refused: a pause is active; run pause.py resume when the machine is back\n'

    def test_refuses_at_entry_before_the_resource_wait(self):
        self.marker()
        with mock.patch.object(heavy, 'resource_wait', side_effect=AssertionError):
            code, err = self.run_heavy()
        self.assertEqual((code, err), (77, self.MESSAGE))
        self.assertFalse(self.touched.exists())

    def test_refuses_again_after_the_lock_when_a_pause_appears_while_waiting(self):
        calls = []

        def appears(_config, _watch=None):
            calls.append(1)
            self.marker()
            return None

        with mock.patch.object(heavy, 'resource_wait', appears):
            code, err = self.run_heavy()
        self.assertEqual((code, err), (77, self.MESSAGE))
        self.assertEqual(len(calls), 1)
        self.assertFalse(self.touched.exists())
        self.assertEqual(heavy.lock_state(), 'free')  # the lock is released on refusal

    def test_runs_normally_when_not_paused(self):
        cases = {'missing': None, 'invalid': b'junk', 'expired': json.dumps(
            {'started': time.time() - DAY - 9, 'kind': 'none', 'deadline': 0}).encode()}
        for name, raw in cases.items():
            with self.subTest(name):
                self.touched.unlink(missing_ok=True)
                if raw is not None:
                    self.raw_marker(raw)
                self.assertEqual(self.run_heavy(), (0, ''))
                self.assertTrue(self.touched.exists())

    def test_runs_normally_when_pause_cannot_be_imported_or_raises(self):
        self.marker()
        with mock.patch.dict(sys.modules, {'pause': None}):
            self.assertEqual(self.run_heavy(), (0, ''))
        self.assertTrue(self.touched.exists())
        self.touched.unlink()
        with mock.patch.object(pause, 'paused', side_effect=RuntimeError):
            self.assertEqual(self.run_heavy(), (0, ''))
        self.assertTrue(self.touched.exists())

    def test_status_is_unchanged_while_paused(self):
        self.marker()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(heavy.main(['status']), 0)
        self.assertIn('heavy lock:', out.getvalue())


class PackagedCopyRefusalTest(Base):
    """The checks copy of heavy_run, run alone in an isolated interpreter, finds its own pause reader."""

    PACKAGED = ROOT / 'skills' / 'checks' / 'scripts'
    CHILD = '\n'.join((
        'import sys, unittest',
        'from pathlib import Path',
        'root, home, packaged, touched, when = sys.argv[1:6]',
        'sys.path.insert(0, root)',
        'from tests.data_root_fixture import account',
        'account(unittest.TestCase(), home)',
        'sys.path.remove(root)',
        'sys.path.insert(0, packaged)',
        'import heavy_run',
        'assert Path(heavy_run.__file__).resolve().parent == Path(packaged)',
        'heavy_run.read_load = lambda: 1.0',
        'heavy_run.read_free_gb = lambda: 8.0',
        'marker = Path(home) / ".finolabs/vibecode/state/pause.json"',
        'def appears(_config, _watch=None):',
        '    marker.write_text("{\\"started\\": %f, \\"kind\\": \\"none\\", \\"deadline\\": 0}" % __import__("time").time())',
        '    marker.chmod(0o600)',
        'if when == "wait":',
        '    heavy_run.resource_wait = appears',
        'command = [sys.executable, "-c", "import pathlib; pathlib.Path(%r).write_text(\\"x\\")" % touched]',
        'code = heavy_run.main(["--poll", "0.02", "run", "--", *command])',
        'loaded = sys.modules.get("pause")',
        'assert loaded is not None and Path(loaded.__file__).resolve().parent == Path(packaged), "pause not packaged"',
        'sys.exit(code)'))

    def launch(self, when):
        import subprocess
        touched = self.home / 'ran'
        done = subprocess.run([sys.executable, '-I', '-c', self.CHILD, str(ROOT), str(self.home),
                               str(self.PACKAGED.resolve()), str(touched), when],
                              capture_output=True, text=True, timeout=60, env={'PATH': os.defpath})
        return done, touched

    def test_refuses_at_entry_and_after_the_lock_without_starting_the_child(self):
        for when in ('entry', 'wait'):
            with self.subTest(when):
                (self.state / 'pause.json').unlink(missing_ok=True)
                if when == 'entry':
                    self.marker()
                done, touched = self.launch(when)
                self.assertEqual(done.returncode, 77, done.stderr[-400:])
                self.assertIn('heavy_run: refused: a pause is active', done.stderr)
                self.assertFalse(touched.exists())


if __name__ == '__main__':
    unittest.main()
