"""The heavy-job wrapper keeps one protected job per machine; every case uses synthetic readings and short commands."""
import contextlib
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills' / 'fnl-delegate' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import heavy_run as heavy


class HeavyRunTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = account(self, Path(temporary.name) / 'home')
        self.root = self.home / '.finolabs' / 'vibecode'
        self.root.mkdir(parents=True, mode=0o700)
        patch = mock.patch.dict(os.environ, {'PATH': os.environ.get('PATH', '')}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.load = 1.0
        self.free = 8.0
        for name, value in (('read_load', lambda: self.load), ('read_free_gb', lambda: self.free)):
            patcher = mock.patch.object(heavy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, *argv, poll='0.02'):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = heavy.main(['--poll', poll, *argv])
        return code, out.getvalue(), err.getvalue()

    def lock_path(self):
        return self.root / 'heavy.lock'

    def spawn(self, *cli, wait_held=True, cwd=None, extra_env=None):
        """A real second process running the wrapper, as another repository's agent would."""
        pre = ('import sys, pwd, types; sys.path.insert(0, %r); '
               'pwd.getpwuid = lambda uid: types.SimpleNamespace(pw_dir=%r); import heavy_run as h; '
               'h.read_load = lambda: 1.0; h.read_free_gb = lambda: 8.0; '
               % (str(SCRIPTS), str(self.home)))
        code = pre + 'sys.exit(h.main(%r))' % (['--poll', '0.02', *cli],)
        child = subprocess.Popen([sys.executable, '-c', code], cwd=cwd, env={'PATH': os.environ['PATH'], **(extra_env or {})})
        self.addCleanup(self.stop, child)
        for _ in range(150 if wait_held else 0):
            if heavy.lock_state() == 'held':
                return child
            time.sleep(0.02)
        if wait_held:
            self.fail('holder did not take the lock')
        return child

    def hold(self, seconds=5, label='other'):
        return self.spawn('run', '--label', label, '--', 'sleep', str(seconds))

    def stop(self, child):
        if child.poll() is None:
            child.kill()
        child.wait()

    def test_runs_the_command_and_returns_its_exit_status(self):
        self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'raise SystemExit(7)')[0], 7)
        self.assertEqual(heavy.lock_state(), 'free')

    def test_waits_then_exits_75_without_starting_or_touching_the_holder(self):
        child = self.hold()
        marker = self.root / 'ran'
        code, _, err = self.run_cli('run', '--wait-seconds', '0.2', '--', sys.executable, '-c',
                                    'open(%r, "w").close()' % str(marker))
        self.assertEqual(code, 75)
        self.assertFalse(marker.exists())
        self.assertIn('other', err)
        self.assertIsNone(child.poll())
        self.assertEqual(heavy.lock_state(), 'held')

    def test_load_and_memory_gate_the_start(self):
        for attribute, value in (('load', 20.0), ('free', 0.5)):
            setattr(self, attribute, value)
            code, _, err = self.run_cli('run', '--wait-seconds', '0.1', '--', sys.executable, '-c', 'pass')
            self.assertEqual(code, 75, attribute)
            self.assertIn('load' if attribute == 'load' else 'memory', err)
            self.load, self.free = 1.0, 8.0
        self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 0)

    def test_without_a_memory_reading_only_load_is_checked(self):
        with mock.patch.object(heavy, 'read_free_gb', lambda: None):
            self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 0)
            self.assertIn('memory: unknown', self.run_cli('status')[1])

    def test_two_processes_racing_for_a_free_lock_start_exactly_one(self):
        children = [self.spawn('run', '--wait-seconds', '0.3', '--', 'sleep', '0.6', wait_held=False) for _ in range(2)]
        self.assertEqual(sorted(child.wait() for child in children), [0, 75])

    def test_wrapper_signal_reaches_the_child_and_the_lock_waits_for_it(self):
        code = ('import signal, sys, time; '
                'signal.signal(signal.SIGTERM, lambda *a: (time.sleep(0.3), sys.exit(5))); time.sleep(10)')
        holder = self.spawn('run', '--', sys.executable, '-c', code)
        time.sleep(0.2)
        os.kill(holder.pid, signal.SIGTERM)
        time.sleep(0.1)
        self.assertEqual(heavy.lock_state(), 'held')
        self.assertEqual(holder.wait(timeout=5), 5)
        self.assertEqual(heavy.lock_state(), 'free')

    def test_killed_wrapper_with_a_default_popen_grandchild_still_blocks_a_second_job(self):
        launcher = 'import subprocess, sys; subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])'
        wrapper = self.spawn('run', '--', sys.executable, '-c', launcher)
        time.sleep(0.4)
        wrapper.kill()
        wrapper.wait()
        marker = self.root / 'second'
        code, _, err = self.run_cli('run', '--wait-seconds', '0.2', '--', sys.executable, '-c',
                                    'open(%r, "w").close()' % str(marker))
        self.assertEqual(code, 75)
        self.assertIn('stopped wrapper', err)
        self.assertFalse(marker.exists())
        self.assertIn('still running', self.run_cli('status')[1])
        for _ in range(100):
            if 'still running' not in self.run_cli('status')[1]:
                break
            time.sleep(0.05)
        self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 0)

    def test_a_live_wrapper_waits_for_what_the_command_left_running(self):
        launcher = 'import subprocess, sys; subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.8)"])'
        wrapper = self.spawn('run', '--', sys.executable, '-c', launcher)
        time.sleep(0.4)
        self.assertIsNone(wrapper.poll())
        self.assertEqual(heavy.lock_state(), 'held')
        self.assertEqual(wrapper.wait(timeout=5), 0)
        self.assertEqual(heavy.lock_state(), 'free')

    def test_record_carries_the_source_without_paths_or_arguments(self):
        repo = self.home / 'projects' / 'demo-repo'
        (repo / '.git').mkdir(parents=True)
        child = self.spawn('run', '--label', 'tests', '--', 'sleep', '3', cwd=repo, extra_env={'FNL_DISPATCH_ID': 'd20261109-000000-abcd'})
        for _ in range(100):
            data = heavy.holder()
            if data:
                break
            time.sleep(0.02)
        self.assertEqual((data['label'], data['repo_name'], data['dispatch'], data['exe']),
                         ('tests', 'demo-repo', 'd20261109-000000-abcd', 'sleep'))
        self.assertRegex(data['repo'], r'^[0-9a-f]{8}$')
        self.assertEqual((data['pid'], data['child'] > 0), (child.pid, True))
        self.assertEqual(data['deadline'] - data['started'], 5400)
        for value in data.values():
            self.assertNotIn('/', str(value))
        self.assertNotIn('3', str(data['exe']))
        text = self.run_cli('status')[1]
        for expected in ('tests', 'demo-repo', 'd20261109-000000-abcd', 'command: sleep', 'at most 5400 s'):
            self.assertIn(expected, text)
        self.assertNotIn(str(self.home), text)

    def test_maximum_run_time_stops_the_command_and_frees_the_lock(self):
        code, _, err = self.run_cli('run', '--max-seconds', '0.3', '--', 'sleep', '30')
        self.assertEqual(code, 124)
        self.assertIn('maximum run time', err)
        self.assertEqual(heavy.lock_state(), 'free')

    def test_maximum_run_time_also_covers_a_worker_left_after_the_command_exits(self):
        launcher = 'import subprocess, sys; subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])'
        started = time.monotonic()
        code, _, err = self.run_cli('run', '--max-seconds', '0.4', '--', sys.executable, '-c', launcher)
        self.assertEqual(code, 124)
        self.assertIn('maximum run time', err)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(heavy.lock_state(), 'free')

    def test_an_old_record_does_not_free_a_group_that_is_still_running(self):
        worker = subprocess.Popen(['sleep', '30'], start_new_session=True)
        self.addCleanup(self.stop, worker)
        long_ago = int(time.time()) - 100000
        self.lock_path().write_text('{"v":1,"pid":1,"child":%d,"started":%d,"deadline":%d,"label":"old"}\n'
                                    % (worker.pid, long_ago, long_ago + 60))
        os.chmod(self.lock_path(), 0o600)
        marker = self.root / 'second'
        code, _, err = self.run_cli('run', '--wait-seconds', '0.2', '--', sys.executable, '-c',
                                    'open(%r, "w").close()' % str(marker))
        self.assertEqual(code, 75)
        self.assertIn('stopped wrapper', err)
        self.assertFalse(marker.exists())
        worker.kill()
        worker.wait()
        self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 0)

    def test_runtime_numbers_must_be_positive_and_finite_before_anything_starts(self):
        marker = self.root / 'ran'
        for option, value in (('--max-minutes', 'nan'), ('--max-minutes', 'inf'), ('--max-minutes', '0'),
                              ('--max-seconds', '-1'), ('--wait-seconds', 'nan')):
            code, _, err = self.run_cli('run', option, value, '--', sys.executable, '-c',
                                        'open(%r, "w").close()' % str(marker))
            self.assertEqual(code, 2, (option, value))
            self.assertFalse(marker.exists())
        self.assertEqual(heavy.lock_state(), 'free')

    def test_the_wait_cap_is_checked_before_a_late_attempt(self):
        clock = [0.0]

        def sleep(seconds):
            clock[0] += seconds

        attempts = []
        original = heavy.resource_wait

        def gate(config):
            attempts.append(clock[0])
            return 'busy' if clock[0] < 5 else None

        with mock.patch.object(heavy.time, 'monotonic', lambda: clock[0]), mock.patch.object(heavy.time, 'sleep', sleep), \
                mock.patch.object(heavy, 'resource_wait', gate):
            code, _, err = self.run_cli('run', '--wait-seconds', '3', '--', sys.executable, '-c', 'pass', poll='2')
        self.assertEqual(code, 75)
        self.assertTrue(all(moment <= 3 for moment in attempts), attempts)
        self.assertIn('busy', err)

    def test_a_single_spurious_missing_file_while_creating_the_lock_is_retried(self):
        real = os.open
        calls = []

        def flaky(path, *args, **kwargs):
            if path == heavy.LOCK_NAME and not calls:
                calls.append(path)
                raise FileNotFoundError()
            return real(path, *args, **kwargs)

        with mock.patch.object(heavy.os, 'open', flaky):
            self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 0)
        self.assertEqual(calls, [heavy.LOCK_NAME])

    def test_a_slow_resource_reading_that_crosses_the_wait_cap_starts_nothing(self):
        clock = [0.0]

        def gate(config):
            clock[0] += 2.0
            return None

        marker = self.root / 'ran'
        with mock.patch.object(heavy.time, 'monotonic', lambda: clock[0]), mock.patch.object(heavy.time, 'sleep', lambda s: None), \
                mock.patch.object(heavy, 'resource_wait', gate):
            code, _, err = self.run_cli('run', '--wait-seconds', '1', '--', sys.executable, '-c',
                                        'open(%r, "w").close()' % str(marker))
        self.assertEqual(code, 75)
        self.assertFalse(marker.exists())
        self.assertEqual(heavy.lock_state(), 'free')

    def test_out_of_range_process_ids_in_a_record_read_as_unknown_and_never_reach_a_signal(self):
        now = int(time.time())
        held = os.open(self.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            for field, value in (('pid', 2 ** 31), ('child', 2 ** 31), ('child', 2 ** 40 - 1), ('pid', 0), ('child', 0)):
                record = {'v': 1, 'pid': os.getpid(), 'child': None, 'started': now, 'deadline': now + 60, 'label': 'x'}
                record[field] = value
                self.lock_path().write_text(__import__('json').dumps(record) + '\n')
                real = heavy.os.killpg

                def guarded(group, number, real=real):
                    if not 0 < group < 2 ** 31:
                        raise AssertionError('signal sent to %r' % group)
                    return real(group, number)

                with mock.patch.object(heavy.os, 'killpg', guarded):
                    code, out, _ = self.run_cli('status')
                    self.assertEqual(code, 0, (field, value))
                    self.assertIn('free', out)
                    self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 0, (field, value))
                self.lock_path().write_text('')
        finally:
            os.close(held)

    def test_a_group_that_survives_the_kill_grace_keeps_its_record_and_blocks_the_next_start(self):
        worker = subprocess.Popen(['sleep', '30'], start_new_session=True)
        self.addCleanup(self.stop, worker)
        clock = [0.0]
        real_kill = heavy.os.killpg

        def ignore_kills(group, number):
            if number == 0:
                return real_kill(group, 0)
            return None

        def sleep(seconds):
            clock[0] += 5

        with mock.patch.object(heavy, 'subprocess', mock.MagicMock(Popen=lambda *a, **k: worker, SubprocessError=Exception, run=subprocess.run, TimeoutExpired=subprocess.TimeoutExpired)), \
                mock.patch.object(heavy.os, 'killpg', ignore_kills), mock.patch.object(heavy.time, 'monotonic', lambda: clock[0]), \
                mock.patch.object(heavy.time, 'sleep', sleep):
            code, _, err = self.run_cli('run', '--max-seconds', '1', '--', 'sleep', '30')
        self.assertEqual(code, 124)
        self.assertIn(str(worker.pid).encode(), self.lock_path().read_bytes())
        marker = self.root / 'second'
        code, _, err = self.run_cli('run', '--wait-seconds', '0.2', '--', sys.executable, '-c',
                                    'open(%r, "w").close()' % str(marker))
        self.assertEqual(code, 75)
        self.assertFalse(marker.exists())

    def test_the_script_runs_as_its_own_isolated_entry_point(self):
        done = subprocess.run([sys.executable, '-I', str(SCRIPTS / 'heavy_run.py'), '--help'],
                              capture_output=True, text=True, timeout=30, env={'PATH': os.environ['PATH']})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('status', done.stdout)

    def test_a_finished_job_leaves_no_record_to_misread_as_the_next_holder(self):
        self.assertEqual(self.run_cli('run', '--label', 'alpha', '--', sys.executable, '-c', 'pass')[0], 0)
        self.assertEqual(self.lock_path().read_bytes(), b'')

    def test_malformed_owner_records_read_as_unknown(self):
        now = int(time.time())
        held = os.open(self.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        import fcntl
        fcntl.flock(held, fcntl.LOCK_EX)
        try:
            for label in ('null', '1', '[]', '"bad/label"'):
                self.lock_path().write_text('{"v":1,"pid":%d,"child":null,"started":%d,"deadline":%d,"label":%s}\n'
                                            % (os.getpid(), now, now + 60, label))
                code, out, _ = self.run_cli('status')
                self.assertEqual(code, 0, label)
                self.assertIn('held, owner unknown', out, label)
            self.lock_path().write_text('{"v":1,"pid":%d,"child":null,"started":%d,"deadline":%d,"label":"ok","exe":7}\n'
                                        % (os.getpid(), now, now + 60))
            self.assertIn('held, owner unknown', self.run_cli('status')[1])
        finally:
            os.close(held)

    def test_lock_does_not_move_with_the_data_root(self):
        first = heavy.lock_identity()
        moved = self.home / 'elsewhere'
        moved.mkdir()
        (self.root / 'root.json').write_text('{"root": "%s", "id": "x"}' % moved)
        self.assertEqual(heavy.lock_identity(), first)
        self.assertEqual(self.lock_path().parent, self.root)

    def test_status_shows_holder_only_when_tied_to_a_live_process(self):
        self.assertIn('free', self.run_cli('status')[1])
        child = self.hold(label='alpha')
        for _ in range(100):
            text = self.run_cli('status')[1]
            if 'alpha' in text:
                break
            time.sleep(0.03)
        self.assertIn('held', text)
        self.assertIn('alpha', text)
        self.assertNotIn(str(self.home), text)
        child.kill()
        child.wait()
        self.lock_path().write_text('{"v":1,"pid":%d,"child":1,"started":%d,"deadline":%d,"label":"alpha"}\n' % (child.pid, int(time.time()), int(time.time()) + 60))
        os.chmod(self.lock_path(), 0o600)
        # A complete record whose process is gone must read as unknown, never as the holder.
        held = os.open(self.lock_path(), os.O_RDWR)
        import fcntl
        fcntl.flock(held, fcntl.LOCK_EX)
        try:
            text = self.run_cli('status')[1]
        finally:
            os.close(held)
        self.assertIn('held, owner unknown', text)
        self.assertNotIn('alpha', text)

    def test_refuses_a_symlinked_or_foreign_lock_location(self):
        target = self.root / 'elsewhere'
        target.write_text('')
        self.lock_path().symlink_to(target)
        self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 78)
        self.lock_path().unlink()
        self.lock_path().write_text('')
        os.chmod(self.lock_path(), 0o666)
        self.assertEqual(self.run_cli('run', '--', sys.executable, '-c', 'pass')[0], 78)

    def test_detached_launches_are_refused_before_the_lock_is_taken(self):
        for command in (['docker', 'compose', 'up', '-d'], ['docker-compose', 'up', '-d'],
                        ['docker', 'compose', 'run', '-d', 'web'], ['docker', 'run', '--detach', 'image'],
                        ['docker', 'container', 'run', '-dit', 'image']):
            code, _, err = self.run_cli('run', '--', *command)
            self.assertEqual(code, 64, command)
            self.assertIn('foreground', err)
            self.assertEqual(heavy.lock_state(), 'free')

    def test_detach_is_found_after_global_options_and_not_in_the_container_command(self):
        for command in (['docker', 'compose', '-f', 'fixture.yml', 'up', '-d'],
                        ['docker-compose', '-f', 'fixture.yml', 'up', '--detach'],
                        ['docker', '--context', 'fixture', 'run', '-d', 'image'],
                        ['docker', 'run', '--name', 'x', '-e', 'A=1', '-d', 'image'],
                        ['docker', 'compose', 'up', 'web', '-d'],
                        ['docker', 'run', '--pids-limit', '64', '-d', 'nginx'],
                        ['docker', 'run', '--memory-reservation', '1g', '--detach', 'nginx'],
                        ['docker', 'run', '--some-future-option', 'x', 'image'],
                        ['docker', 'run', '--detach=1', 'image'], ['docker', 'run', '--detach=T', 'image'],
                        ['docker', 'compose', 'up', '--detach=TRUE'], ['docker-compose', 'up', '--detach=True'],
                        ['docker', 'compose', 'up', '--wait'], ['docker-compose', 'up', '--wait'],
                        ['docker', 'compose', 'up', '--wait=true'], ['docker', 'run', '-d=maybe', 'image']):
            self.assertTrue(heavy.detached(command), command)
        for command in (['docker', 'run', 'image', 'command', '-d'],
                        ['docker', 'run', '-e', 'A=-d', 'image'],
                        ['docker', 'compose', 'run', 'web', 'tool', '-d'],
                        ['docker', 'compose', '-f', 'fixture.yml', 'up'],
                        ['docker', 'ps', '-d'], ['docker', 'run', '--detach=false', 'image'],
                        ['docker', 'compose', 'up', '--detach=0'], ['docker', 'compose', 'up', '--wait=false']):
            self.assertFalse(heavy.detached(command), command)

    def test_child_gets_only_allowlisted_names_plus_requested_ones(self):
        names = self.root / 'names'
        code = 'import os; open(%r, "w").write(",".join(sorted(os.environ)))' % str(names)
        extra = {'FNL_TEST_PASS': 'x', 'FNL_TEST_OTHER': 'y', 'HOME': str(self.home), 'LANG': 'C'}
        with mock.patch.dict(os.environ, extra):
            self.assertEqual(self.run_cli('run', '--pass-env', 'FNL_TEST_PASS', '--', sys.executable, '-c', code)[0], 0)
        got = set(names.read_text().split(','))
        self.assertIn('FNL_TEST_PASS', got)
        self.assertNotIn('FNL_TEST_OTHER', got)
        self.assertEqual(self.run_cli('run', '--pass-env', 'GIT_DIR', '--', sys.executable, '-c', 'pass')[0], 2)

    def test_label_is_bounded_and_plain(self):
        for label in ('x' * 41, 'a/b', ''):
            self.assertEqual(self.run_cli('run', '--label', label, '--', sys.executable, '-c', 'pass')[0], 2, label)

    def test_config_section_sets_limits_and_bad_values_fall_back(self):
        (self.root / 'host.md').write_text('## Heavy jobs\n- Load limit: 3\n- Memory minimum GB: 99999\n- Wait cap minutes: 5\n- Max job minutes: 30\n')
        os.chmod(self.root / 'host.md', 0o600)
        limits = heavy.limits()
        self.assertEqual((limits['load'], limits['memory_gb'], limits['wait_minutes'], limits['max_minutes']), (3.0, 3.0, 5.0, 30.0))
        self.load = 4.0
        self.assertEqual(self.run_cli('run', '--wait-seconds', '0.1', '--', sys.executable, '-c', 'pass')[0], 75)

    def test_status_prints_nothing_from_the_environment(self):
        with mock.patch.dict(os.environ, {'FNL_TEST_SECRET': 'do-not-print'}):
            out = self.run_cli('status')
        self.assertNotIn('do-not-print', ''.join(out[1:]))


def vm_text(free, inactive, speculative, file_backed=None, purgeable=None):
    lines = ['Mach Virtual Memory Statistics: (page size of 16384 bytes)', 'Pages free: %d.' % free,
             'Pages active: 170000.', 'Pages inactive: %d.' % inactive, 'Pages speculative: %d.' % speculative]
    if purgeable is not None:
        lines.append('Pages purgeable: %d.' % purgeable)
    if file_backed is not None:
        lines.append('File-backed pages: %d.' % file_backed)
    return '\n'.join(lines) + '\n'


def fake_run(stdout, returncode=0, error=None):
    def run(argv, **_kwargs):
        if error:
            raise error
        return subprocess.CompletedProcess(argv, returncode, stdout, '')
    return run


def pressure_text(percent):
    return ('The system has 17179869184 (1048576 pages with a page size of 16384).\n'
            'System-wide memory free percentage: %s%%\n' % percent)


def routed_run(vm, pressure=None, memsize='17179869184\n', error=None):
    """Fake `run` answering each program by basename; `pressure` None makes memory_pressure fail."""
    def run(argv, **_kwargs):
        name = os.path.basename(argv[0])
        if name == 'memory_pressure':
            if pressure is None:
                raise error or OSError('no memory_pressure')
            return subprocess.CompletedProcess(argv, 0, pressure, '')
        if name == 'sysctl':
            return subprocess.CompletedProcess(argv, 0, memsize, '')
        return subprocess.CompletedProcess(argv, 0, vm, '')
    return run


class MeasureTest(unittest.TestCase):
    def free_gb(self, text):
        with mock.patch.object(heavy.subprocess, 'run', fake_run(text)):
            return heavy.read_free_gb()

    def kernel_gb(self, pressure, memsize='17179869184\n', vm=None):
        vm = vm if vm is not None else vm_text(4031, 151654, 12391, file_backed=111892, purgeable=2)
        with mock.patch.object(heavy.subprocess, 'run', routed_run(vm, pressure, memsize)):
            return heavy.read_free_gb()

    def test_kernel_figure_is_used_and_allows_the_motivating_case(self):
        vm = vm_text(4031, 151654, 12391, file_backed=111892, purgeable=2)
        self.assertLess(self.free_gb(vm), 3.0)  # the vm_stat estimate alone refuses
        self.assertAlmostEqual(self.kernel_gb(pressure_text(31)), 0.31 * 16, places=6)
        self.assertGreaterEqual(self.kernel_gb(pressure_text(31)), heavy.DEFAULTS['memory_gb'])

    def test_low_kernel_figure_is_refused(self):
        self.assertAlmostEqual(self.kernel_gb(pressure_text(10)), 1.6, places=6)
        self.assertLess(self.kernel_gb(pressure_text(10)), heavy.DEFAULTS['memory_gb'])

    def test_bad_kernel_reading_falls_back_to_vm_stat(self):
        vm = vm_text(1000, 60000, 1000)
        expected = 62000 * 16384 / 2 ** 30
        for pressure, memsize in ((None, '17179869184'), ('garbage', '17179869184'), (pressure_text(101), '17179869184'),
                                  (pressure_text(31), 'many'), (pressure_text(31), '0')):
            self.assertAlmostEqual(self.kernel_gb(pressure, memsize, vm), expected, msg=repr((pressure, memsize)))
        with mock.patch.object(heavy.subprocess, 'run', routed_run(vm, None, error=subprocess.TimeoutExpired('x', 5))):
            self.assertAlmostEqual(heavy.read_free_gb(), expected)

    def test_kernel_programs_run_without_shell_with_a_fixed_path_and_timeout(self):
        calls = []

        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            return routed_run('', pressure_text(31))(argv, **kwargs)
        with mock.patch.object(heavy.subprocess, 'run', run):
            heavy.read_free_gb()
        self.assertEqual([argv[0] for argv, _ in calls], ['/usr/bin/memory_pressure', '/usr/sbin/sysctl'])
        for _, kwargs in calls:
            self.assertEqual(kwargs['timeout'], 5)
            self.assertFalse(kwargs.get('shell', False))
            self.assertEqual(sorted(kwargs['env']), sorted(heavy.run_env.environment()))

    def test_a_purgeable_count_inside_inactive_is_not_added_again(self):
        # Purgeable and file-backed pages contained in inactive: only 152000 distinct pages, below 3 GiB.
        text = vm_text(1000, 150000, 1000, file_backed=50000, purgeable=100000)
        self.assertAlmostEqual(self.free_gb(text), 152000 * 16384 / 2 ** 30)
        self.assertLess(self.free_gb(text), 3.0)

    def test_file_cache_pages_count_as_reclaimable(self):
        # Little inactive memory but a large clean file cache: refused by the old sum, allowed now.
        text = vm_text(1000, 20000, 1000, file_backed=400000, purgeable=20000)
        old = (1000 + 20000 + 1000) * 16384 / 2 ** 30
        self.assertLess(old, 3.0)
        self.assertGreater(self.free_gb(text), 3.0)

    def test_a_machine_with_little_reclaimable_memory_is_still_refused(self):
        text = vm_text(1000, 20000, 500, file_backed=30000, purgeable=100)
        self.assertLess(self.free_gb(text), 3.0)

    def test_the_same_page_is_not_counted_twice(self):
        # File-backed pages already inside inactive + speculative add nothing.
        text = vm_text(1000, 60000, 1000, file_backed=50000, purgeable=0)
        self.assertAlmostEqual(self.free_gb(text), 62000 * 16384 / 2 ** 30)

    def test_old_vm_stat_output_without_the_optional_lines_keeps_the_old_sum(self):
        self.assertAlmostEqual(self.free_gb(vm_text(1000, 60000, 1000)), 62000 * 16384 / 2 ** 30)

    def test_unreadable_vm_stat_is_none(self):
        self.assertIsNone(self.free_gb('nothing useful'))
        self.assertIsNone(self.free_gb(vm_text(1, 2, 3).replace('Pages free', 'Pages gone')))


class QueueViewTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = account(self, Path(temporary.name) / 'home')
        self.root = self.home / '.finolabs' / 'vibecode'
        self.root.mkdir(parents=True, mode=0o700)
        patch = mock.patch.dict(os.environ, {'PATH': os.environ.get('PATH', '')}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        for name, value in (('read_load', lambda: 1.0), ('read_free_gb', lambda: 8.0)):
            patcher = mock.patch.object(heavy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = heavy.main([*argv])
        return code, out.getvalue(), err.getvalue()

    def lock_path(self):
        return self.root / 'heavy.lock'

    def ps(self, stdout, returncode=0, error=None):
        return mock.patch.object(heavy, 'read_waiting_ps', side_effect=error,
                                 return_value=stdout if returncode == 0 else None)

    def lines(self, *commands):
        return ''.join('%d %s\n' % (900 + number, command) for number, command in enumerate(commands))

    def test_count_is_zero_when_no_wrapper_runs(self):
        with self.ps(self.lines('/bin/zsh -l', 'python3 other.py run')):
            self.assertEqual(heavy.waiting_count(), 0)
            self.assertIn('waiting: about 0', self.run_cli('status')[1])

    def test_count_is_one_for_one_waiting_wrapper_and_prints_no_command_text(self):
        secret = 'python3 -I /tmp/skills/heavy_run.py run --label topsecret -- make private-target'
        with self.ps(self.lines(secret, 'python3 -I /tmp/skills/heavy_run.py status')):
            self.assertEqual(heavy.waiting_count(), 1)
            code, out, err = self.run_cli('status')
        self.assertIn('waiting: about 1', out)
        for word in ('topsecret', 'private-target', '/tmp'):
            self.assertNotIn(word, out + err)

    def test_the_holder_is_not_counted_as_waiting(self):
        wrapper = 'python3 -I /x/heavy_run.py run -- sleep 5'
        held = os.open(self.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        import fcntl
        fcntl.flock(held, fcntl.LOCK_EX)
        try:
            with self.ps(self.lines(wrapper, wrapper, wrapper)):
                self.assertIn('waiting: about 2', self.run_cli('status')[1])
        finally:
            os.close(held)

    def fake_programs(self, ps_body, pgrep_body='print(900)', pgrep_code=0):
        """Fake pgrep (names one candidate pid) and ps (prints its lines) as real executables."""
        for name, body in (('pgrep', '%s\nsys.exit(%d)' % (pgrep_body, pgrep_code)), ('ps', ps_body)):
            fake = self.home / name
            fake.write_text('#!%s\nimport sys, time\n%s\n' % (sys.executable, body))
            fake.chmod(0o700)
        return mock.patch.dict(heavy.TOOLS, {'ps': str(self.home / 'ps'), 'pgrep': str(self.home / 'pgrep')})

    def test_oversized_ps_reads_as_unknown_without_printing_its_output(self):
        with self.fake_programs('sys.stdout.write("synthetic-private-command " * 12000)'):
            code, out, err = self.run_cli('status')
        self.assertEqual(code, 0)
        self.assertIn('waiting: unknown', out)
        self.assertNotIn('synthetic-private-command', out + err)
        self.assertNotIn(str(self.home / 'ps'), out + err)

    def test_ps_at_the_byte_limit_still_counts_normally(self):
        with self.fake_programs('sys.stdout.write("900 python3 /x/heavy_run.py run".ljust(256 * 1024))'):
            self.assertEqual(heavy.waiting_count(), 1)

    def test_a_huge_process_list_elsewhere_does_not_hide_the_count(self):
        # The real machine printed 450 KB for a full ps. This ps prints that much unless it is asked for the
        # named pids only, and the fake pgrep rejects any pattern but the fixed one.
        ps_body = ('if sys.argv[1:] != ["-o", "pid=,command=", "-p", "900"]:\n'
                   '    sys.stdout.write("x" * (450 * 1024)); sys.exit(0)\n'
                   'sys.stdout.write("900 python3 /x/heavy_run.py run -- cmd\\n")')
        pgrep_body = ('if sys.argv[1:] != ["-f", r"heavy_run\\.py"]:\n'
                      '    sys.exit(2)\n'
                      'print(900)')
        with self.fake_programs(ps_body, pgrep_body=pgrep_body):
            self.assertEqual(heavy.waiting_count(), 1)

    def test_more_candidates_than_the_cap_read_as_unknown_not_zero(self):
        # 200 candidates still count; 201 is unknown, never a silent cut that could miss the runner.
        for count, expected in ((200, 1), (201, None)):
            pgrep_body = '; '.join('print(%d)' % pid for pid in range(1000, 1000 + count))
            with self.fake_programs('sys.stdout.write("1000 python3 /x/heavy_run.py run -- cmd\\n")',
                                    pgrep_body=pgrep_body):
                self.assertEqual(heavy.waiting_count(), expected)

    def test_ps_failing_with_no_output_reads_as_unknown(self):
        with self.fake_programs('sys.exit(1)'):
            self.assertIsNone(heavy.read_waiting_ps())

    def test_pgrep_exit_one_with_unexpected_output_reads_as_unknown(self):
        with self.fake_programs('print("900 python3 /x/heavy_run.py run")', pgrep_body='print("surprise")',
                                pgrep_code=1):
            self.assertIsNone(heavy.read_waiting_ps())

    def test_no_pgrep_match_counts_zero_without_running_ps(self):
        with self.fake_programs('raise SystemExit("ps must not run")', pgrep_body='', pgrep_code=1):
            self.assertEqual(heavy.waiting_count(), 0)

    def test_a_failing_pgrep_reads_as_unknown(self):
        with self.fake_programs('print("900 python3 /x/heavy_run.py run")', pgrep_body='', pgrep_code=2):
            self.assertIsNone(heavy.waiting_count())

    def test_ps_exit_one_with_output_for_an_ended_pid_still_counts_the_rest(self):
        body = 'sys.stdout.write("900 python3 /x/heavy_run.py run -- cmd\\n"); sys.exit(1)'
        with self.fake_programs(body, pgrep_body='print(900); print(901)'):
            self.assertEqual(heavy.waiting_count(), 1)

    def test_unreadable_ps_reads_as_unknown(self):
        for case in (self.ps('', error=OSError('no ps')), self.ps('', error=TimeoutError()),
                     self.ps('boom', returncode=1),
                     self.ps('', error=subprocess.TimeoutExpired('ps', 5))):
            with case:
                self.assertIsNone(heavy.waiting_count())
                self.assertIn('waiting: unknown', self.run_cli('status')[1])

    def test_only_python_running_the_script_with_run_counts(self):
        listing = self.lines('grep -n heavy_run.py run', 'python3 -I /x/heavy_run.py run -- cmd',
                             '/usr/bin/env python3 /x/heavy_run.py run -- cmd', 'vim heavy_run.py run',
                             'python3 /x/other.py heavy_run.py run', '/bin/zsh -c ls',
                             # Homebrew Python on macOS appears with a capital P in ps.
                             '/opt/homebrew/Cellar/python@3.15/Frameworks/Python.framework/Resources/Python.app/'
                             'Contents/MacOS/Python -I /x/heavy_run.py run -- cmd')
        with self.ps(listing):
            self.assertEqual(heavy.waiting_count(), 3)
            self.assertIn('waiting: about 3', self.run_cli('status')[1])

    def test_own_process_is_not_counted(self):
        with self.ps('%d python3 -I /x/heavy_run.py run -- true\n' % os.getpid()):
            self.assertEqual(heavy.waiting_count(), 0)

    def recording_popen(self):
        real, self.children = subprocess.Popen, []

        def record(*args, **kwargs):
            child = real(*args, **kwargs)
            self.children.append(child)
            return child
        return mock.patch.object(heavy.subprocess, 'Popen', side_effect=record)

    def assert_children_cleaned_up(self, count):
        self.assertEqual(len(self.children), count)
        for child in self.children:
            self.assertIsNotNone(child.returncode)  # reaped
            self.assertTrue(child.stdout.closed)
            with self.assertRaises(ProcessLookupError):
                os.kill(child.pid, 0)

    def test_reader_kills_and_reaps_the_child_on_overflow(self):
        with self.fake_programs('sys.stdout.write("x" * (300 * 1024)); sys.stdout.flush(); time.sleep(30)'), \
                self.recording_popen():
            self.assertIsNone(heavy.read_waiting_ps())
        self.assert_children_cleaned_up(2)

    def test_reader_kills_and_reaps_the_child_on_a_select_timeout(self):
        ticks = iter([0.0] + [100.0] * 50)
        with self.fake_programs('time.sleep(30)', pgrep_body='time.sleep(30)'), self.recording_popen(), \
                mock.patch.object(heavy.time, 'monotonic', side_effect=lambda: next(ticks)):
            with self.assertRaises(TimeoutError):
                heavy.read_waiting_ps()
        self.assert_children_cleaned_up(1)

    def test_reader_cleans_up_when_reading_fails(self):
        with self.fake_programs('time.sleep(30)', pgrep_body='print(900); sys.stdout.flush(); time.sleep(30)'), \
                self.recording_popen():
            real_read = os.read

            def read(fd, size):
                if self.children:  # only the reader's own read, not Popen's start-up pipe
                    raise OSError('read failed')
                return real_read(fd, size)
            with mock.patch.object(heavy.os, 'read', side_effect=read), self.assertRaises(OSError):
                heavy.read_waiting_ps()
        self.assert_children_cleaned_up(1)

    def test_reader_returns_none_for_a_nonzero_exit_and_leaves_no_child(self):
        with self.fake_programs('sys.stdout.write("900 python3 /x/heavy_run.py run\\n"); sys.exit(3)'), \
                self.recording_popen():
            self.assertIsNone(heavy.read_waiting_ps())
        self.assert_children_cleaned_up(2)


if __name__ == '__main__':
    unittest.main()
