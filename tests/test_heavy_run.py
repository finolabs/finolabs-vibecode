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

    def test_killed_wrapper_with_a_surviving_grandchild_keeps_the_lock(self):
        launcher = 'import subprocess, sys; subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.0)"], close_fds=False)'
        wrapper = self.spawn('run', '--', sys.executable, '-c', launcher)
        time.sleep(0.2)
        wrapper.kill()
        wrapper.wait()
        self.assertEqual(heavy.lock_state(), 'held')
        for _ in range(100):
            if heavy.lock_state() == 'free':
                break
            time.sleep(0.05)
        self.assertEqual(heavy.lock_state(), 'free')
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
        text = self.run_cli('status')[1]
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


if __name__ == '__main__':
    unittest.main()
