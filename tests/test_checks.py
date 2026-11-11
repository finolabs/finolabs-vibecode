"""checks.py: run the stored list in order through heavy_run.py, narrow with --changed, and the local receipt."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
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
LEDGER = ROOT / 'skills/fnl-delegate/scripts/ledger.py'

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
        self.store_file(*checks, receipt=receipt)

    def legacy(self, *checks, receipt=False):
        """A `## Checks` section as 0.2.4 wrote it in host.md; it is never read."""
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
        import hashlib
        self.store_file(('test', ['make', 'test']))
        raw = json.dumps({'version': 1, 'checks': [{'name': 'test', 'argv': ['sh', '-c', 'x']}],
                          'local_receipt': False}).encode()
        (self.repo / '.finolabs/vibecode/checks.json').write_bytes(raw)
        load('checks_list_invalid', SCRIPTS / 'checks_list.py').write_approved(self.code(),
                                                                              hashlib.sha256(raw).hexdigest())
        code, _, _ = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 3)
        self.assertEqual(self.launched(), [])

    def test_a_legacy_section_in_host_md_runs_nothing(self):
        for receipt in (False, True):
            with self.subTest(receipt=receipt):
                self.legacy(('a', self.mark('a')), receipt=receipt)
                module = self.module()
                code, out, err = self.run_cli(module, 'run')
                self.assertEqual(code, 2)
                self.assertIn('no checks (no entry)', out + err)
                self.assertEqual(self.launched(), [])
                self.assertFalse(self.receipt().exists())
                code, out, _ = self.run_cli(module, 'show')
                self.assertEqual(code, 0)
                self.assertNotIn('local receipt: on', out)

    def test_show_prints_the_list_and_the_mode(self):
        self.store(('lint', ['make', 'lint']), receipt=True)
        code, out, err = self.run_cli(self.module(), 'show')
        self.assertEqual(code, 0, err)
        self.assertIn('lint = ["make","lint"]', out)
        self.assertIn('local receipt: on', out)
        self.assertEqual(self.launched(), [])

    # The project file

    def store_file(self, *checks, receipt=False, approve=True):
        """Write the project file as checks_setup.py apply does: 0700 folders, a 0600 file, its approved digest and
        the exclude line that keeps it out of the working tree's status."""
        import hashlib
        reader = load('checks_list_store', SCRIPTS / 'checks_list.py')
        raw = reader.render_project([[name, argv] for name, argv in checks], receipt)
        folder = self.repo / '.finolabs/vibecode'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.repo / '.finolabs', 0o700)
        os.chmod(folder, 0o700)
        (folder / 'checks.json').write_bytes(raw)
        os.chmod(folder / 'checks.json', 0o600)
        if approve:
            reader.write_approved(self.code(), hashlib.sha256(raw).hexdigest())
        exclude = self.repo / '.git/info/exclude'
        exclude.parent.mkdir(exist_ok=True)
        exclude.write_text('.finolabs/\n')
        return raw

    def test_run_reads_the_approved_project_file(self):
        self.legacy(('legacy', self.mark('legacy')), receipt=True)
        self.store_file(('first', self.mark('first')), ('second', self.mark('second')))
        code, out, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.marked(), ['first', 'second'])

    def test_a_receipt_is_written_from_the_project_file(self):
        self.store_file(('a', self.mark('a')), receipt=True)
        code, out, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 0, err)
        self.assertIn('local receipt written', out)
        self.assertTrue(self.receipt().exists())

    def test_a_file_committed_on_a_branch_runs_nothing(self):
        self.store_file(('a', self.mark('a')), receipt=True)
        self.git('checkout', '-qb', 'side')
        (self.repo / '.finolabs/vibecode/checks.json').write_bytes(
            load('checks_list_branch', SCRIPTS / 'checks_list.py').render_project([['a', self.mark('b')]], True))
        self.git('add', '-f', '.finolabs/vibecode/checks.json')
        self.commit('Supply a check list')
        self.git('checkout', '-q', 'main')
        self.git('checkout', '-q', 'side')
        module = self.module()
        code, out, err = self.run_cli(module, 'run')
        self.assertEqual(code, 3)
        self.assertIn('changed since it was approved', out + err)
        self.assertIn('/fnl-setup add checks', out + err)
        self.assertEqual(self.launched(), [])
        self.assertFalse(self.receipt().exists())
        code, out, _ = self.run_cli(module, 'show')
        self.assertIn('changed since it was approved', out)
        self.assertNotIn('local receipt: on', out)

    def test_an_unapproved_file_runs_nothing(self):
        self.store_file(('a', self.mark('a')), approve=False)
        code, out, err = self.run_cli(self.module(), 'run')
        self.assertEqual(code, 3)
        self.assertIn('changed since it was approved', out + err)
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
        self.assertEqual(launched, [[*self.unittest_check(), '--pattern', 'test_alpha.py'], self.mark('other')])
        self.assertEqual(self.marked(), ['other'])

    def change_alpha(self):
        self.git('checkout', '-qb', 'work')
        (self.repo / 'scripts/alpha.py').write_text('A = 2\n')
        self.git('add', '.')
        self.commit('Change alpha')

    def changed_launches(self, check):
        self.log.unlink(missing_ok=True)
        self.store(('unit', check))
        code, _, err = self.run_cli(self.module(), 'run', '--changed', '--base', 'main')
        return code, err, [args[args.index('--') + 1:] for args in self.launched()]

    def test_changed_narrows_only_the_supported_unittest_forms(self):
        self.change_alpha()
        py = sys.executable
        narrowed = [py, '-m', 'unittest', 'discover', '-s', 'tests', '--pattern', 'test_alpha.py']
        # The stored-list guard refuses any `-p...` argument after an interpreter, so the -p forms are checked
        # on the selector itself below; the forms a list can hold run end to end.
        code, err, launched = self.changed_launches([py, '-m', 'unittest', 'discover', '-s', 'tests'])
        self.assertEqual(code, 0, err)
        self.assertEqual(launched, [narrowed])
        module = self.module()
        for tail in (['discover', '-s', 'tests'], ['discover', '-s', 'tests', '-p', 'test_*.py'],
                     ['discover', '-p', 'test_*.py', '-s', 'tests']):
            with self.subTest(selector=tail):
                self.assertTrue(module.narrowable([py, '-m', 'unittest', *tail]))

    def test_changed_runs_every_other_unittest_form_whole(self):
        self.change_alpha()
        py = sys.executable
        for tail in ([], ['discover'], ['discover', '-s', 'other_tests'], ['tests.test_alpha', 'tests.test_other'],
                     ['discover', '-v'], ['-v'], ['discover', '-s', 'tests', '-s', 'tests'], ['discover', '-t', '.'],
                     ['discover', 'tests'], ['discover', '-s'], ['tests.test_alpha']):
            with self.subTest(tail=tail):
                check = [py, '-m', 'unittest', *tail]
                _, _, launched = self.changed_launches(check)
                self.assertEqual(launched, [check])
        module = self.module()
        for tail in (['discover', '-s', 'tests', '-p', 'check_*.py'], ['discover', '-p', '*_test.py'],
                     ['discover', '-p', 'test_*.py', '-p', 'test_*.py'], ['discover', '-p'],
                     ['discover', '--pattern', 'test_*.py'], ['discover', '-s', 'other_tests'], [], ['discover'],
                     ['discover', '-p', 'test_*.py'],
                     ['tests.test_alpha', 'tests.test_other'], ['discover', '-v'], ['-v']):
            with self.subTest(selector=tail):
                self.assertFalse(module.narrowable([py, '-m', 'unittest', *tail]))
        self.assertFalse(module.narrowable(['make', '-m', 'unittest']))

    def test_changed_runs_whole_when_discovery_would_find_tests_the_selector_cannot_see(self):
        self.change_alpha()
        check = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests']
        layouts = {
            'a test package': ('tests/security/__init__.py', ''),
            'a test in a sub-folder': ('tests/security/test_failure.py', 'import unittest\n'),
            'a test*.py name outside test_*.py': ('tests/testsecurity.py', 'import unittest\n'),
        }
        for name, (path, text) in layouts.items():
            with self.subTest(name):
                target = self.repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
                _, _, launched = self.changed_launches(check)
                self.assertEqual(launched, [check])
                if target.parent != self.repo / 'tests':
                    shutil.rmtree(target.parent)  # discovery may have left a __pycache__ there
                else:
                    target.unlink()
        _, _, launched = self.changed_launches(check)
        self.assertEqual(launched, [[*check, '--pattern', 'test_alpha.py']])

    def test_changed_keeps_the_import_context_of_the_whole_run(self):
        self.change_alpha()
        (self.repo / 'helper.py').write_text("raise RuntimeError('the root helper was imported')\n")
        (self.repo / 'tests/helper.py').write_text("VALUE = 'tests'\n")
        test = self.repo / 'tests/test_alpha.py'
        test.write_text("import helper\nassert helper.VALUE == 'tests'\nassert __name__ == 'test_alpha'\n"
                        + test.read_text())
        code, err, launched = self.changed_launches(self.unittest_check())
        self.assertEqual(code, 0, err)
        self.assertEqual(launched, [[*self.unittest_check(), '--pattern', 'test_alpha.py']])

    def test_narrowing_replaces_a_stored_pattern_rather_than_adding_a_second(self):
        module = self.module()
        stored = [sys.executable, '-m', 'unittest', 'discover', '-p', 'test_*.py', '-s', 'tests']
        self.assertEqual(module.discovery_without_pattern(stored),
                         [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'])

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
        self.assertNotIn('receipt', out.replace(str(ROOT), ''))  # the checkout's own path may contain the word

    # A dispatch receipt: `run --dispatch <id>` writes the verification receipt `ledger.py finish` reads

    def ledger(self, *args):
        return subprocess.run([sys.executable, '-I', str(LEDGER), *args], capture_output=True, text=True,
                              env=self.env)

    def dispatch(self, checkout):
        done = self.ledger('start', '--project', 'demo', '--task', 'add parser', '--kind', 'implement', '--grade',
                           'medium', '--agent', 'codex', '--model', 'm1', '--budget', '40', '--checkout', str(checkout))
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def accept(self, ident, checkout):
        return self.ledger('finish', ident, '--outcome', 'accepted', '--checkout', str(checkout))

    def verification(self, ident):
        return self.home / '.finolabs/vibecode/state/verification' / (ident + '.json')

    def test_a_dispatch_run_writes_the_receipt_the_ledger_accepts_with_the_mode_off(self):
        self.store(('a', self.mark('a')), ('b', self.mark('b')))
        ident = self.dispatch(self.repo)
        refused = self.accept(ident, self.repo)
        self.assertNotEqual(refused.returncode, 0)
        code, out, err = self.run_cli(self.module(), 'run', '--dispatch', ident)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.marked(), ['a', 'b'])
        record = json.loads(self.verification(ident).read_text())
        self.assertEqual((record['id'], record['head'], record['tests'], record['mechanical'], record['criteria']),
                         (ident, self.git('rev-parse', 'HEAD'), 'passed', 'passed', []))
        self.assertEqual(self.verification(ident).stat().st_mode & 0o777, 0o600)
        self.assertIn('verification receipt written for ' + ident, out)
        self.assertFalse(self.receipt().exists())  # the local merge receipt keeps its own opt-in mode
        done = self.accept(ident, self.repo)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_dispatch_run_in_a_linked_worktree_binds_that_checkout(self):
        self.store(('a', self.mark('a')))
        tree = self.repo.parent / 'task-tree'
        self.git('worktree', 'add', '-q', '-b', 'task', str(tree))
        ident = self.dispatch(tree)
        os.chdir(tree)
        code, out, err = self.run_cli(self.module(), 'run', '--dispatch', ident)
        self.assertEqual(code, 0, err)
        self.assertNotEqual(self.accept(ident, self.repo).returncode, 0)  # another checkout of the same repository
        done = self.accept(ident, tree)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_failed_or_dirty_dispatch_run_drops_an_earlier_receipt_and_writes_none(self):
        self.store(('a', self.mark('a')))
        ident = self.dispatch(self.repo)
        self.assertEqual(self.run_cli(self.module(), 'run', '--dispatch', ident)[0], 0)
        self.assertTrue(self.verification(ident).exists())
        (self.repo / 'untracked.txt').write_text('x\n')
        code, out, _ = self.run_cli(self.module(), 'run', '--dispatch', ident)
        self.assertEqual(code, 0)
        self.assertFalse(self.verification(ident).exists())
        self.assertIn('no verification receipt: the working tree is not clean', out)
        (self.repo / 'untracked.txt').unlink()
        self.assertEqual(self.run_cli(self.module(), 'run', '--dispatch', ident)[0], 0)
        self.store(('a', self.mark('a', 1)))
        code, out, _ = self.run_cli(self.module(), 'run', '--dispatch', ident)
        self.assertEqual(code, 1)
        self.assertFalse(self.verification(ident).exists())
        self.assertIn('no verification receipt: a check failed', out)
        self.assertNotEqual(self.accept(ident, self.repo).returncode, 0)

    def test_a_dispatch_run_with_a_moved_head_writes_no_receipt(self):
        self.store(('a', self.mark('a')))
        ident = self.dispatch(self.repo)
        module = self.module()
        original = module.run_one

        def moving(name, argv, root):
            result = original(name, argv, root)
            self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com',
                     'commit', '-q', '--allow-empty', '-m', 'Move')
            return result

        module.run_one = moving
        code, out, _ = self.run_cli(module, 'run', '--dispatch', ident)
        self.assertEqual(code, 0)
        self.assertFalse(self.verification(ident).exists())
        self.assertIn('no verification receipt: the head moved during the run', out)

    def test_a_dispatch_run_refuses_a_narrowed_run_or_an_invalid_id_and_runs_nothing(self):
        self.store(('a', self.mark('a')))
        for args in (('--dispatch', 'd20261101-000000-abcd', '--changed'), ('--dispatch', '../x'),
                     ('--dispatch', 'd20261101-000000-ABCD')):
            with self.subTest(args=args):
                code, _, err = self.run_cli(self.module(), 'run', *args)
                self.assertEqual(code, 2)
                self.assertIn('checks: refused:', err)
        self.assertEqual(self.launched(), [])

    def test_a_dispatch_run_without_an_approved_list_runs_nothing_and_writes_nothing(self):
        ident = self.dispatch(self.repo)
        code, _, _ = self.run_cli(self.module(), 'run', '--dispatch', ident)
        self.assertEqual(code, 2)
        self.assertFalse(self.verification(ident).exists())

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


def run_record(identifier, workflow, event, started, updated, **extra):
    record = {'databaseId': identifier, 'event': event, 'headBranch': 'feature', 'conclusion': 'success',
              'createdAt': started, 'updatedAt': updated, 'startedAt': started, 'workflowName': workflow}
    record.update(extra)
    return record


RUNS = [
    run_record(1, 'CI', 'pull_request', '2026-11-01T10:00:00Z', '2026-11-01T10:04:10Z'),  # 5 minutes
    run_record(2, 'CI', 'push', '2026-11-01T11:00:00Z', '2026-11-01T11:02:00Z'),  # exactly 2 minutes
    run_record(3, 'Docs', 'pull_request', '2026-11-02T09:00:00Z', '2026-11-02T09:00:01Z'),  # 1 minute
    run_record(4, 'CI', 'pull_request', '2026-11-03T10:00:00.250Z', '2026-11-03T10:09:30Z'),  # 10 minutes
]
FILES = {'1': ['README.md', 'docs/guide.md'], '2': ['src/app.py', 'README.md'], '3': ['LICENSE', 'docs/x/y.png']}


class UsageTest(unittest.TestCase):
    """checks.py usage: minutes from a run list the agent produced; no network call and no process."""

    def setUp(self):
        scratch = ROOT / '.finolabs/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()

    def write(self, name, value):
        path = self.base / name
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return str(path)

    def usage(self, *args):
        self.assertTrue(SCRIPT.is_file(), 'checks.py is missing')
        module = load('checks_usage_test', SCRIPT)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch('subprocess.run', side_effect=AssertionError('process started')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('process started')), \
                mock.patch('socket.socket', side_effect=AssertionError('network call')):
            code = module.main(['usage', *args])
        return code, out.getvalue(), err.getvalue()

    def test_a_run_with_no_workflow_name_is_counted_under_a_label(self):
        runs = [*RUNS, run_record(5, '', 'push', '2026-11-04T10:00:00Z', '2026-11-04T10:03:00Z')]
        code, out, err = self.usage('--from', self.write('runs.json', runs))
        self.assertEqual(code, 0, err)
        self.assertIn('runs: 5', out)
        self.assertIn('minutes: 21', out)
        self.assertIn('(unnamed workflow)', out)

    def test_ambiguous_changed_path_keys_are_malformed(self):
        runs = self.write('runs.json', RUNS)
        for name, text in (('duplicate', '{"1":["src/app.py"],"1":["README.md"]}'),
                           ('non-canonical', '{"1":["src/app.py"],"01":["README.md"]}')):
            with self.subTest(name):
                code, out, _ = self.usage('--from', runs, '--files-from', self.write('paths.json', text))
                self.assertEqual(code, 3)
                self.assertEqual(out, '')

    def test_totals_round_each_run_up_and_split_by_workflow_and_event(self):
        code, out, err = self.usage('--from', self.write('runs.json', RUNS))
        self.assertEqual(code, 0, err)
        self.assertIn('runs: 4', out)
        self.assertIn('minutes: 18', out)
        self.assertIn('  CI: 17', out)
        self.assertIn('  Docs: 1', out)
        self.assertIn('  pull_request: 16', out)
        self.assertIn('  push: 2', out)
        self.assertNotIn('document-only', out)
        self.assertNotIn('days left', out)

    def test_document_only_share_follows_the_paths_ignore_rule(self):
        code, out, err = self.usage('--from', self.write('runs.json', RUNS),
                                    '--files-from', self.write('files.json', FILES))
        self.assertEqual(code, 0, err)
        # Runs 1 and 3 changed documents only (6 of 18 minutes); run 2 touched code; run 4 has no paths listed.
        self.assertIn('document-only: 2 runs, 6 minutes (33% of minutes)', out)
        self.assertIn('1 run without changed paths', out)

    def test_document_rule_matches_the_workflow_paths_ignore(self):
        module = load('checks_usage_rule', SCRIPT)
        for paths, expected in ((['README.md'], True), (['a/b/c.md'], True), (['docs/a/b.py'], True),
                                (['LICENSE'], True), (['sub/LICENSE'], False), (['README.MD'], False),
                                (['docsx/a.md', 'x.py'], False), ([], False), (['src/docs/a.py'], False)):
            with self.subTest(paths=paths):
                self.assertEqual(module.cl.document_only(paths), expected)

    def test_limit_prints_days_left_at_the_observed_rate(self):
        code, out, err = self.usage('--from', self.write('runs.json', RUNS), '--limit-minutes', '2000')
        self.assertEqual(code, 0, err)
        # The runs span 2026-11-01T10:00 to 2026-11-03T10:09:30, about 2 days: 9 minutes a day, 1982 left.
        self.assertIn('limit: 2000 minutes, 1982 left', out)
        self.assertIn('days left', out)
        code, out, _ = self.usage('--from', self.write('runs.json', RUNS), '--limit-minutes', '10')
        self.assertEqual(code, 0)
        self.assertIn('limit reached', out)

    def test_malformed_input_exits_3_with_one_line(self):
        bad = [
            '{"not": "a list"}', 'not json', json.dumps([{'databaseId': 1}]),
            json.dumps([run_record(1, 'CI', 'push', '2026-11-01 10:00:00', '2026-11-01T10:01:00Z')]),
            json.dumps([run_record(1, 'CI', 'push', '2026-11-01T10:00:00+07:00', '2026-11-01T10:01:00Z')]),
            json.dumps([run_record(1, 'CI', 'push', '2026-11-01T10:05:00Z', '2026-11-01T10:01:00Z')]),
            json.dumps([run_record(True, 'CI', 'push', '2026-11-01T10:00:00Z', '2026-11-01T10:01:00Z')]),
            json.dumps([RUNS[0], RUNS[0]]),
            json.dumps([run_record(1, 'CI', 'push', '2026-11-01T10:00:00Z', '2026-11-01T10:01:00Z', extra=1)]),
            json.dumps([run_record(1, 'CI', 'push', '2026-13-01T10:00:00Z', '2026-11-01T10:01:00Z')]),
        ]
        for index, text in enumerate(bad):
            with self.subTest(text=text[:60]):
                code, out, err = self.usage('--from', self.write(f'bad{index}.json', text))
                self.assertEqual(code, 3)
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertEqual(out, '')
        code, _, err = self.usage('--from', self.write('runs.json', RUNS),
                                  '--files-from', self.write('files.json', {'1': 'README.md'}))
        self.assertEqual(code, 3)

    def test_input_is_capped_in_size_and_runs(self):
        many = [run_record(n, 'CI', 'push', '2026-11-01T10:00:00Z', '2026-11-01T10:01:00Z') for n in range(5001)]
        self.assertEqual(self.usage('--from', self.write('many.json', many))[0], 3)
        self.assertEqual(self.usage('--from', self.write('many.json', many[:5000]))[0], 0)
        self.assertEqual(self.usage('--from', self.write('big.json', ' ' * (5 * 1024 * 1024 + 1) + '[]'))[0], 3)

    def test_empty_list_and_missing_file(self):
        code, out, _ = self.usage('--from', self.write('none.json', []))
        self.assertEqual(code, 0)
        self.assertIn('runs: 0', out)
        self.assertEqual(self.usage('--from', str(self.base / 'missing.json'))[0], 2)


if __name__ == '__main__':
    unittest.main()
