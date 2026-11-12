"""Test selection from the diff on a synthetic repository."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'select_tests.py'
spec = importlib.util.spec_from_file_location('package_select_tests', SCRIPT)
select_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(select_tests)


class SelectTestsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        home = Path(self.tmp.name) / 'home'
        home.mkdir()
        # A synthetic environment: only the names git needs, never the caller's values beyond PATH.
        self.env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(home),
                    'GIT_CONFIG_NOSYSTEM': '1', 'LC_ALL': 'C'}
        files = {
            'scripts/alpha.py': 'A = 1\n',
            'skills/fnl-one/references/terms.md': 'terms\n',
            'skills/fnl-two/references/terms.md': 'terms\n',
            'docs/notes.md': 'notes\n',
            'docs/orphan.md': 'nobody reads this\n',
            'tests/__init__.py': '',
            'tests/test_alpha.py': 'import alpha\n',
            'tests/test_shared_copy.py': "PATH = 'skills/fnl-two/references/terms.md'\n",
            'tests/test_notes.py': "NOTES = ROOT / 'docs/notes.md'\n",
            'tests/test_other.py': "print('unrelated')\n",
        }
        for relative, text in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git('init', '-q', '-b', 'main')
        self.git('add', '.')
        self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com',
                 'commit', '-qm', 'Create fixture')

    def git(self, *argv):
        return subprocess.run(['git', *argv], cwd=self.repo, env=self.env, capture_output=True,
                              text=True, check=True).stdout

    def select(self, *argv):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), '--base', 'main', *argv], cwd=self.repo,
                              env=self.env, capture_output=True, text=True)

    def test_direct_name_selects_the_module(self):
        (self.repo / 'scripts/alpha.py').write_text('A = 2\n')
        (self.repo / 'docs/notes.md').write_text('changed\n')
        done = self.select()
        self.assertEqual(done.returncode, 0, done.stderr)
        listed = done.stdout.split('\n\n')[0].splitlines()
        self.assertEqual(listed, ['tests.test_alpha', 'tests.test_notes'])

    def test_qualified_and_listed_imports_name_the_module(self):
        found = select_tests.patterns('scripts/alpha.py')
        for text in ('import scripts.alpha\n', 'from scripts.alpha import main\n', 'import beta, alpha\n',
                     'import beta as b, scripts.alpha as a\n', 'from alpha import main\n'):
            with self.subTest(text=text):
                self.assertTrue(any(p.search(text) for p in found))
        for text in ('import alphabet\n', 'from scripts.alphas import x\n', 'import beta, alphanumeric\n'):
            with self.subTest(text=text):
                self.assertFalse(any(p.search(text) for p in found))

    def test_a_deleted_test_module_is_not_scheduled(self):
        (self.repo / 'tests/test_other.py').unlink()
        done = self.select()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn('tests.test_other', done.stdout)

    def test_shared_copy_counts_as_every_copy(self):
        # Mid-edit: only one copy changed; the module names the other copy's path.
        (self.repo / 'skills/fnl-one/references/terms.md').write_text('more terms\n')
        done = self.select()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split('\n\n')[0].splitlines(), ['tests.test_shared_copy'])

    def test_unnamed_change_is_reported(self):
        (self.repo / 'docs/orphan.md').write_text('still nobody\n')
        done = self.select()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('no test names: docs/orphan.md', done.stdout.splitlines())
        self.assertNotIn('tests.test_other', done.stdout)

    def test_changed_test_module_selects_itself(self):
        (self.repo / 'tests/test_other.py').write_text("print('changed')\n")
        done = self.select()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split('\n\n')[0].splitlines(), ['tests.test_other'])

    def test_groups_hold_at_most_two_modules(self):
        for relative in ('scripts/alpha.py', 'skills/fnl-one/references/terms.md', 'docs/notes.md',
                         'tests/test_other.py'):
            (self.repo / relative).write_text('changed\n')
        done = self.select()
        self.assertEqual(done.returncode, 0, done.stderr)
        groups = [line for line in done.stdout.splitlines() if line.startswith('python3 -m unittest ')]
        self.assertEqual(groups, ['python3 -m unittest tests.test_alpha tests.test_notes',
                                  'python3 -m unittest tests.test_other tests.test_shared_copy'])
        self.assertEqual(select_tests.groups(['a', 'b', 'c']), [['a', 'b'], ['c']])

    def test_no_change_prints_nothing_to_run(self):
        done = self.select()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), 'no changed files')

    def test_git_runs_with_fixed_argv_and_no_shell(self):
        reply = subprocess.CompletedProcess([], 0, stdout='scripts/alpha.py\n', stderr='')
        with mock.patch.object(select_tests.subprocess, 'run', return_value=reply) as run:
            self.assertEqual(select_tests.changed_files('origin/main', self.repo), ['scripts/alpha.py'])
        argv = run.call_args.args[0]
        self.assertEqual(argv, ['git', 'diff', '--name-only', '--merge-base', 'origin/main', '--'])
        self.assertFalse(run.call_args.kwargs.get('shell', False))

    def test_option_shaped_base_is_refused(self):
        done = self.select('--base=--output=x')
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, '')

    def test_skill_copy_matches(self):
        copy = ROOT / 'skills/checks/scripts/select_tests.py'
        self.assertEqual(copy.read_bytes(), SCRIPT.read_bytes())


if __name__ == '__main__':
    unittest.main()
