"""checks.py: run the stored list in order through heavy_run.py, narrow with --changed, and the local receipt."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/fnl-checks/scripts'
SCRIPT = SCRIPTS / 'checks.py'

FAKE_HEAVY = """import json, subprocess, sys
args = sys.argv[1:]
with open(%r, 'a') as log:
    log.write(json.dumps(args) + '\\n')
command = args[args.index('--') + 1:]
sys.exit(subprocess.call(command))
"""

MARK = """import sys
with open(sys.argv[1], 'a') as log:
    log.write(sys.argv[2] + '\\n')
sys.exit(int(sys.argv[3]))
"""


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChecksRunTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.finolabs/tmp'  # git-ignored; keeps test files inside the checkout
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / 'home')
        # A synthetic environment: only the names the commands need.
        self.env = {'HOME': str(self.home), 'PATH': os.defpath + ':/usr/local/bin:/opt/homebrew/bin'}
        patch = mock.patch.dict(os.environ, self.env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.host = self.home / '.finolabs/vibecode/host.md'
        self.host.parent.mkdir(parents=True, exist_ok=True)
        self.host.write_text('# Host\n')
        self.log = base / 'heavy.log'
        self.marks = base / 'marks.log'
        self.fake = base / 'fake_heavy_run.py'
        self.fake.write_text(FAKE_HEAVY % str(self.log))
        self.repo = base / 'repo'
        files = {'mark.py': MARK, 'scripts/alpha.py': 'A = 1\n', 'docs/notes.md': 'notes\n',
                 'tests/__init__.py': '', 'tests/test_alpha.py': ("import unittest\nALPHA = 'scripts/alpha.py'\n\n\n"
                                         "class Alpha(unittest.TestCase):\n    def test_named(self):\n        pass\n"),
                 'tests/test_other.py': "print('unrelated')\n"}
        for relative, text in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git('init', '-q', '-b', 'main')
        self.git('add', '.')
        self.commit('Create fixture')
        cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, cwd)

    def git(self, *argv):
        env = dict(self.env, GIT_CONFIG_NOSYSTEM='1')
        return subprocess.run(['git', *argv], cwd=self.repo, env=env, capture_output=True, text=True,
                              check=True).stdout.strip()

    def commit(self, message):
        self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com', 'commit', '-qm', message)

    def module(self):
        self.assertTrue(SCRIPT.is_file(), 'checks.py is missing')
        module = load('checks_test', SCRIPT)
        module.HEAVY = self.fake
        return module

    def code(self):
        return load('project_progress_for_checks_run', SCRIPTS / 'project_progress.py').repository_code(self.repo)

    def mark(self, name, exit_code=0):
        return [sys.executable, 'mark.py', str(self.marks), name, str(exit_code)]

    def store(self, *checks, receipt=False):
        code = self.code()
        lines = ''.join('- %s: %s = %s\n' % (code, name, json.dumps(argv, separators=(',', ':')))
                        for name, argv in checks)
        if receipt:
            lines += '- %s: local-receipt = on\n' % code
        self.host.write_text('# Host\n\n## Checks\n\n' + lines + '\n')

    def run_cli(self, module, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = module.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def launched(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def marked(self):
        return self.marks.read_text().split() if self.marks.exists() else []

    def receipt(self):
        return self.home / '.finolabs/vibecode/state/checks-receipts' / (self.code() + '.json')

    # The run

    def test_the_launch_form_is_heavy_run_with_an_isolated_interpreter_and_no_shell(self):
        module = load('checks_form', SCRIPT)
        self.assertEqual(module.HEAVY, SCRIPTS / 'heavy_run.py')
        self.assertTrue(module.HEAVY.is_file())
        self.assertEqual(module.launch_argv('lint', ['make', 'lint']),
                         [sys.executable, '-I', str(SCRIPTS / 'heavy_run.py'), 'run', '--label', 'check lint',
                          '--', 'make', 'lint'])

    def test_run_launches_each_check_in_order_through_heavy_run(self):
        self.store(('first', self.mark('first')), ('second', self.mark('second')))
        code, out, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.marked(), ['first', 'second'])
        self.assertEqual([args[:4] for args in self.launched()],
                         [['run', '--label', 'check first', '--'], ['run', '--label', 'check second', '--']])
        self.assertEqual(self.launched()[0][4:], self.mark('first'))
        self.assertIn('2 checks passed', out)

    def test_run_stops_at_the_first_failure_and_names_it(self):
        self.store(('a', self.mark('a')), ('b', self.mark('b', 3)), ('c', self.mark('c')))
        code, out, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 1)
        self.assertEqual(self.marked(), ['a', 'b'])
        self.assertIn('check b failed with exit code 3', out + err)

    def test_run_without_a_stored_list_refuses_and_runs_nothing(self):
        code, out, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 2)
        self.assertIn('no checks', out + err)
        self.assertEqual(self.launched(), [])

    def test_an_invalid_stored_list_runs_nothing(self):
        self.host.write_text('# Host\n\n## Checks\n\n- %s: test = ["sh","-c","x"]\n' % self.code())
        code, _, _ = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 3)
        self.assertEqual(self.launched(), [])

    def test_show_prints_the_list_and_the_mode(self):
        self.store(('lint', ['make', 'lint']), receipt=True)
        code, out, err = self.run_cli(self.module(), 'show')
        self.assertEqual(code, 0, err)
        self.assertIn('lint = ["make","lint"]', out)
        self.assertIn('local receipt: on', out)
        self.assertEqual(self.launched(), [])

    # --changed

    def unittest_check(self):
        return [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests']

    def test_changed_narrows_python_test_modules_and_runs_the_rest_whole(self):
        self.store(('unit', self.unittest_check()), ('other', self.mark('other')))
        self.git('checkout', '-qb', 'work')
        (self.repo / 'scripts/alpha.py').write_text('A = 2\n')
        self.git('add', '.')
        self.commit('Change alpha')
        code, out, err = self.run_cli(self.module(), 'run', '--changed', '--base', 'main')
        self.assertEqual(code, 0, err)
        launched = [args[args.index('--') + 1:] for args in self.launched()]
        self.assertEqual(launched, [[sys.executable, '-m', 'unittest', 'tests.test_alpha'], self.mark('other')])
        self.assertEqual(self.marked(), ['other'])

    def test_changed_skips_python_tests_no_module_names_and_says_why(self):
        self.store(('unit', self.unittest_check()), ('other', self.mark('other')))
        self.git('checkout', '-qb', 'work')
        (self.repo / 'docs/notes.md').write_text('changed\n')
        self.git('add', '.')
        self.commit('Change notes')
        code, out, err = self.run_cli(self.module(), 'run', '--changed', '--base', 'main')
        self.assertEqual(code, 0, err)
        self.assertIn('skipped unit: no Python test module names a changed file', out)
        self.assertEqual(self.marked(), ['other'])

    def test_changed_with_nothing_changed_skips_every_check(self):
        self.store(('other', self.mark('other')))
        code, out, err = self.run_cli(self.module(), 'run', '--changed', '--base', 'main')
        self.assertEqual(code, 0, err)
        self.assertIn('skipped other: no changed files', out)
        self.assertEqual(self.launched(), [])

    def test_changed_refuses_an_unknown_or_unsafe_base(self):
        self.store(('other', self.mark('other')))
        for base in ('no-such-ref', '--output=x', 'a..b'):
            with self.subTest(base=base):
                code, _, _ = self.run_cli(self.module(), 'run', '--changed', '--base=' + base)
                self.assertEqual(code, 2)
        self.assertEqual(self.launched(), [])

    # The local receipt

    def test_a_passing_whole_run_on_a_clean_tree_writes_the_receipt(self):
        self.store(('a', self.mark('a')), receipt=True)
        module = self.module()
        code, out, err = self.run_cli(module, 'run')
        self.assertEqual(code, 0, err)
        record = json.loads(self.receipt().read_text())
        checks_list = load('checks_list_for_run', SCRIPTS / 'checks_list.py')
        self.assertEqual({k: record[k] for k in ('kind', 'code', 'head', 'digest')},
                         {'kind': 'checks', 'code': self.code(), 'head': self.git('rev-parse', 'HEAD'),
                          'digest': checks_list.list_digest([('a', self.mark('a'))])})
        self.assertEqual(self.receipt().stat().st_mode & 0o777, 0o600)
        self.assertIn('local receipt written', out)

    def test_a_dirty_tree_writes_no_receipt_and_says_why(self):
        self.store(('a', self.mark('a')), receipt=True)
        (self.repo / 'untracked.txt').write_text('x\n')
        code, out, _ = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 0)
        self.assertFalse(self.receipt().exists())
        self.assertIn('no local receipt: the working tree is not clean', out)

    def test_a_moved_head_writes_no_receipt(self):
        self.store(('a', self.mark('a')), receipt=True)
        module = self.module()
        original = module.run_one

        def moving(name, argv, root):
            result = original(name, argv, root)
            self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com',
                     'commit', '-q', '--allow-empty', '-m', 'Move')
            return result

        module.run_one = moving
        code, out, _ = self.run_cli(module, 'run')
        self.assertEqual(code, 0)
        self.assertFalse(self.receipt().exists())
        self.assertIn('no local receipt: the head moved during the run', out)

    def test_a_narrowed_run_writes_no_receipt(self):
        self.store(('a', self.mark('a')), receipt=True)
        self.git('checkout', '-qb', 'work')
        (self.repo / 'docs/notes.md').write_text('changed\n')
        self.git('add', '.')
        self.commit('Change notes')
        code, out, _ = self.run_cli(self.module(), 'run', '--changed', '--base', 'main')
        self.assertEqual(code, 0)
        self.assertFalse(self.receipt().exists())
        self.assertIn('no local receipt: a --changed run covers only part of the list', out)

    def test_a_failing_check_writes_no_receipt(self):
        self.store(('a', self.mark('a', 1)), receipt=True)
        code, out, _ = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 1)
        self.assertFalse(self.receipt().exists())
        self.assertIn('no local receipt: a check failed', out)

    def gate(self):
        """A check whose result flips with a flag file outside the repository: same list, same head."""
        script = self.temp_base() / 'gate.py'
        script.write_text('import os, sys\nsys.exit(1 if os.path.exists(sys.argv[1]) else 0)\n')
        flag = self.temp_base() / 'fail.flag'
        return [sys.executable, str(script), str(flag)], flag

    def temp_base(self):
        return Path(self.temp.name).resolve()

    def test_a_failed_full_rerun_removes_the_receipt_and_the_merge_check_blocks(self):
        argv, flag = self.gate()
        self.store(('gate', argv), receipt=True)
        self.git('remote', 'add', 'origin', 'https://github.com/acme/demo.git')
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        self.assertTrue(self.receipt().exists())
        merge_check = load('merge_check_for_rerun', ROOT / 'skills/fnl-review-gate/scripts/merge_check.py')
        head = self.git('rev-parse', 'HEAD')
        self.assertEqual(merge_check.local_receipt(head, 'acme/demo'), (True, 'matches'))
        flag.write_text('x\n')
        code, out, _ = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 1)
        self.assertFalse(self.receipt().exists())
        pr = {'state': 'OPEN', 'headRefOid': head, 'author': {'login': 'owner'}, 'comments': [], 'reviews': [],
              'statusCheckRollup': [], 'mergeStateStatus': 'CLEAN', 'body': ''}
        ok, lines = merge_check.evaluate(pr, lambda who: True, adopted=False,
                                         local_receipt=merge_check.local_receipt, repo='acme/demo')
        self.assertFalse(ok)
        self.assertIn('BLOCK checks: none reported; local receipt: no local receipt', lines)

    def test_a_full_run_removes_the_old_receipt_before_the_first_check(self):
        self.store(('a', self.mark('a')), receipt=True)
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        self.assertTrue(self.receipt().exists())
        module = self.module()
        original, seen = module.run_one, []

        def watching(name, argv, root):
            seen.append(self.receipt().exists())
            return original(name, argv, root)

        module.run_one = watching
        self.assertEqual(self.run_cli(module, 'run')[0], 0)
        self.assertEqual(seen, [False])
        self.assertTrue(self.receipt().exists())

    def test_a_dirty_full_run_also_drops_the_old_receipt(self):
        self.store(('a', self.mark('a')), receipt=True)
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        (self.repo / 'untracked.txt').write_text('x\n')
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        self.assertFalse(self.receipt().exists())

    def test_a_changed_run_neither_writes_nor_removes_the_receipt(self):
        argv, flag = self.gate()
        self.store(('gate', argv), receipt=True)
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        before = self.receipt().read_bytes()
        flag.write_text('x\n')
        self.git('checkout', '-qb', 'work')
        (self.repo / 'docs/notes.md').write_text('changed\n')
        self.git('add', '.')
        self.commit('Change notes')
        code, _, _ = self.run_cli(self.module(), 'run', '--changed', '--base', 'main')
        self.assertEqual(code, 1)
        self.assertEqual(self.receipt().read_bytes(), before)

    # One full run at a time
    BUSY = "checks: refused: another full run of this repository's checks is in progress\n"

    def lock_path(self):
        return self.home / '.finolabs/vibecode/state/checks-receipts' / (self.code() + '.lock')

    def test_a_second_full_run_refuses_while_the_first_is_in_progress(self):
        argv, flag = self.gate()
        self.store(('gate', argv), receipt=True)
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)  # an old receipt exists
        flag.write_text('x\n')  # run A will fail
        first = self.module()
        original, inner = first.run_one, []

        def during(name, check, root):
            # A has removed the old receipt and is running its check; B starts now and must refuse.
            second = self.module()
            inner.append(self.run_cli(second, 'run'))
            inner.append(len(self.launched()))
            return original(name, check, root)

        first.run_one = during
        code, _, _ = self.run_cli(first, 'run')
        self.assertEqual(code, 1)
        (b_code, b_out, b_err), launches = inner
        self.assertEqual((b_code, b_err), (2, self.BUSY))
        self.assertEqual(launches, 1)  # B launched nothing; only A's first run before it
        self.assertFalse(self.receipt().exists())
        self.assertEqual(self.lock_path().stat().st_mode & 0o777, 0o600)

    def test_sequential_runs_each_take_the_lock_and_a_failed_rerun_leaves_no_receipt(self):
        argv, flag = self.gate()
        self.store(('gate', argv), receipt=True)
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        self.assertTrue(self.receipt().exists())
        flag.write_text('x\n')
        code, _, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 1, err)
        self.assertNotIn('in progress', err)
        self.assertFalse(self.receipt().exists())

    def test_a_held_lock_refuses_before_removing_the_receipt_or_launching(self):
        import fcntl
        self.store(('a', self.mark('a')), receipt=True)
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        before = self.receipt().read_bytes()
        launches = len(self.launched())
        with open(self.lock_path(), 'a') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, _, err = self.run_cli(self.module(), 'run')
            self.assertEqual((code, err), (2, self.BUSY))
            self.assertEqual(self.receipt().read_bytes(), before)
            self.assertEqual(len(self.launched()), launches)
            # --changed takes no lock.
            code, out, err = self.run_cli(self.module(), 'run', '--changed', '--base', 'main')
            self.assertEqual(code, 0, err)

    def test_an_unsafe_lock_file_refuses(self):
        self.store(('a', self.mark('a')), receipt=True)
        self.assertEqual(self.run_cli(self.module(), 'run')[0], 0)
        lock = self.lock_path()
        lock.unlink()
        lock.symlink_to(self.temp_base() / 'elsewhere.lock')
        code, _, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 2)
        self.assertIn('checks: refused:', err)
        self.assertFalse((self.temp_base() / 'elsewhere.lock').exists())

    def test_with_the_mode_off_no_receipt_is_written_or_mentioned(self):
        self.store(('a', self.mark('a')))
        code, out, _ = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 0)
        self.assertFalse(self.receipt().exists())
        self.assertNotIn('receipt', out)

    def test_every_launch_uses_the_allowlisted_environment(self):
        self.store(('a', self.mark('a')))
        module = self.module()
        seen = []
        real = subprocess.run

        def spy(argv, **kwargs):
            seen.append((argv[:1], sorted(kwargs.get('env', {'<inherited>': ''}))))
            self.assertNotIn('shell', kwargs)
            return real(argv, **kwargs)

        with mock.patch.dict(os.environ, {'SYNTHETIC_SECRET_TOKEN': 'not-real'}), \
                mock.patch.object(module.subprocess, 'run', side_effect=spy):
            self.assertEqual(self.run_cli(module, 'run')[0], 0)
        self.assertTrue(seen)
        for _, names in seen:
            self.assertNotIn('SYNTHETIC_SECRET_TOKEN', names)
            self.assertNotIn('<inherited>', names)


if __name__ == '__main__':
    unittest.main()
