"""Per-repository check list: detection without running anything, the stored argument form, and the digest-bound write."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/fnl-setup/scripts'
SCRIPT = SCRIPTS / 'checks_setup.py'
PREFIX = b'# Host\n\n## Other\nkeep \xc3\xa9\n'

WORKFLOW = """name: CI
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install
        run: npm ci
      - name: Lint code
        run: npm run lint
      - run: |
          python3 -m unittest discover -s tests
      - run: |
          echo one
          echo two
      - name: Folded
        run: >
          python3 scripts/check.py
          --strict
      - name: Pipe
        run: npm test | tee out.txt
      - name: Expression
        run: echo ${{ github.sha }}
      - name: In folder
        working-directory: web
        run: npm test
      - name: Continued
        run: |
          make check \\
            VERBOSE=1
"""

SHELLS = ['sh', 'bash', 'zsh', 'dash', 'ksh', 'fish', 'csh', 'tcsh', 'pwsh', 'powershell', 'cmd']
LAUNCHERS = ['env', 'xargs', 'nohup', 'nice', 'timeout', 'time', 'sudo', 'doas', 'exec', 'eval', 'command',
             'busybox', 'script', 'watch']
INTERPRETERS = ['python', 'python3', 'node', 'deno', 'bun', 'perl', 'ruby', 'php']
REFUSED = ([['env', 'env', 'sh', '-c', 'true'], ['env', '-S', 'sh -c true'], ['python3', '-c', '...'],
            ['npx', '-c', 'eslint .'], ['npx', 'eslint', '--call', 'x'], ['/usr/bin/BASH', 'x'],
            ['C:\\Windows\\cmd.exe', '/c', 'x'], ['python3.12', '-c', 'x'], ['python3', '-Ic', 'x'],
            ['node', '--eval=x'], ['python3', '-cprint(1)']]
           + [[name, 'x'] for name in SHELLS + LAUNCHERS]
           + [['/usr/bin/' + name, 'tests/x', flag, 'x'] for name in INTERPRETERS for flag in ('-c', '-e', '--eval', '-r')])
ALLOWED = [['python3', '-m', 'pytest', '-q'], ['npx', 'eslint', '.'], ['node', '--test'], ['make', 'test'],
           ['python3', '-m', 'unittest', 'discover', '-s', 'tests'], ['ruby', '-Itest', 'test/all.rb']]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChecksSetupTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.finolabs/tmp'  # git-ignored; keeps test files inside the checkout
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / 'home')
        patch = mock.patch.dict(os.environ, {'HOME': str(self.home)}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.host = self.home / '.finolabs/vibecode/host.md'
        self.host.parent.mkdir(parents=True, exist_ok=True)
        self.host.write_bytes(PREFIX)
        self.plan = self.host.parent / 'state/checks-setup/preview.json'
        self.repo = base / 'repo'
        (self.repo / '.git').mkdir(parents=True)
        self.other = base / 'other'
        (self.other / '.git').mkdir(parents=True)

    def module(self):
        self.assertTrue(SCRIPT.is_file(), 'checks_setup.py is missing')
        return load('checks_setup_test', SCRIPT)

    def cli(self, *args):
        writer = self.module()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch('subprocess.run', side_effect=AssertionError('command run')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('command run')), \
                mock.patch('os.system', side_effect=AssertionError('command run')):
            code = writer.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def preview(self, *checks, root=None):
        args = ['preview', '--root', str(root or self.repo)]
        for item in checks:
            args += ['--check', item]
        code, out, err = self.cli(*args)
        self.assertEqual(code, 0, err)
        return out.split('Digest: ')[1].splitlines()[0]

    def code(self, root=None):
        progress = load('project_progress_for_checks', SCRIPTS / 'project_progress.py')
        return progress.repository_code(root or self.repo)

    # Detection

    def write_sources(self):
        workflows = self.repo / '.github/workflows'
        workflows.mkdir(parents=True)
        (workflows / 'ci.yml').write_text(WORKFLOW)
        (self.repo / 'package.json').write_text(json.dumps(
            {'scripts': {'start': 'node app.js', 'build': 'tsc', 'test': 'jest', 'lint': 'eslint .'}}))
        (self.repo / 'pyproject.toml').write_text('[project]\nname = "x"\n\n[tool.pytest.ini_options]\naddopts = "-q"\n')
        (self.repo / 'Makefile').write_text('all: build\n\ntest:\n\tpytest\n\nlint: deps\n\truff .\n\nclean:\n\trm -rf x\nCHECK := 1\n')

    def test_detect_reads_each_source_and_runs_nothing(self):
        self.write_sources()
        code, out, err = self.cli('detect', '--root', str(self.repo), '--json')
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(data['sources'], ['.github/workflows/ci.yml', 'package.json', 'pyproject.toml', 'Makefile'])
        checks = [(item['name'], item['argv']) for item in data['checks']]
        self.assertEqual(checks, [
            ('npm-lint', ['npm', 'run', 'lint']),
            ('npm-test', ['npm', 'run', 'test']),
            ('npm-build', ['npm', 'run', 'build']),
            ('pytest', ['python3', '-m', 'pytest']),
            ('make-test', ['make', 'test']),
            ('make-lint', ['make', 'lint']),
        ])
        where = {'file': '.github/workflows/ci.yml', 'job': 'test'}
        self.assertEqual(data['ci'], [dict(where, line=line) for line in (
            'npm ci', 'npm run lint', 'python3 -m unittest discover -s tests', 'echo one',
            'python3 scripts/check.py', 'npm test | tee out.txt', 'echo ${{ github.sha }}', 'npm test',
            'make check \\')])
        self.assertEqual(data['skipped'], [])

    def test_detect_human_output_names_sources_and_ci_evidence(self):
        self.write_sources()
        code, out, _ = self.cli('detect', '--root', str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn('Source: .github/workflows/ci.yml', out)
        self.assertIn('Check: npm-lint = ["npm","run","lint"]', out)
        self.assertIn('\nfound in CI, add with --check if you want it\n', out)
        self.assertIn('  .github/workflows/ci.yml (job test): npm test | tee out.txt\n', out)
        self.assertNotIn('Check: lint-code', out)
        self.assertIn('Nothing was run.', out)

    def ci_only(self, workflow):
        workflows = self.repo / '.github/workflows'
        workflows.mkdir(parents=True, exist_ok=True)
        (workflows / 'ci.yml').write_text(workflow)
        code, out, err = self.cli('detect', '--root', str(self.repo), '--json')
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(data['checks'], [])
        return data['ci']

    def test_a_folded_run_is_evidence_and_never_a_check(self):
        ci = self.ci_only('jobs:\n  test:\n    steps:\n      - name: Folded\n        run: >-\n'
                          '          pytest\n          --strict\n')
        self.assertEqual(ci, [{'file': '.github/workflows/ci.yml', 'job': 'test', 'line': 'pytest'}])

    def test_a_compact_steps_sequence_is_evidence_and_never_a_check(self):
        ci = self.ci_only('jobs:\n  build:\n    steps:\n    - run: npm test\n    - name: Make\n      run: make test\n'
                          '  lint:\n    steps:\n    -   run: "ruff check ."\n')
        self.assertEqual(ci, [{'file': '.github/workflows/ci.yml', 'job': 'build', 'line': 'npm test'},
                              {'file': '.github/workflows/ci.yml', 'job': 'build', 'line': 'make test'},
                              {'file': '.github/workflows/ci.yml', 'job': 'lint', 'line': 'ruff check .'}])

    def test_a_working_directory_run_is_evidence_and_never_a_check(self):
        ci = self.ci_only('defaults:\n  run:\n    working-directory: web\njobs:\n  test:\n    defaults:\n      run:\n'
                          '        working-directory: app\n    steps:\n      - run: npm test\n'
                          '      - run: make test\n        working-directory: api\n')
        self.assertEqual([item['line'] for item in ci], ['npm test', 'make test'])

    def test_ci_evidence_is_truncated_and_cleaned(self):
        ci = self.ci_only('jobs:\n  "odd job":\n    steps:\n      - run: ' + 'x' * 200 + '\n'
                          '      - run: env sh -c "true"\n      - run: "a\\u001bb"\n')
        self.assertEqual([item['line'] for item in ci], ['x' * 120, 'env sh -c "true"', 'a?b'])
        self.assertEqual({item['job'] for item in ci}, {None})

    def test_detect_package_manager_follows_the_lockfile(self):
        (self.repo / 'package.json').write_text(json.dumps({'scripts': {'typecheck': 'tsc --noEmit', 'test': 'vitest'}}))
        (self.repo / 'pnpm-lock.yaml').write_text('lockfileVersion: 9\n')
        data = json.loads(self.cli('detect', '--root', str(self.repo), '--json')[1])
        self.assertEqual([item['argv'] for item in data['checks']],
                         [['pnpm', 'run', 'test'], ['pnpm', 'run', 'typecheck']])

    def python_checks(self, files):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        code, out, err = self.cli('detect', '--root', str(self.repo), '--json')
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        return [item['argv'] for item in data['checks']], data['skipped']

    def test_pytest_is_chosen_from_each_declaration(self):
        pytest = ['python3', '-m', 'pytest']
        cases = {
            'project dependencies': {'pyproject.toml': '[project]\nname = "x"\ndependencies = ["requests", "PyTest>=8"]\n'},
            'optional dependencies': {'pyproject.toml': '[project]\nname = "x"\n[project.optional-dependencies]\n'
                                                        'test = ["pytest[testing] ; python_version>\'3\'"]\n'},
            'dependency groups': {'pyproject.toml': '[dependency-groups]\ndev = [{include-group = "x"}, "pytest~=8.0"]\n'},
            'poetry dependencies': {'pyproject.toml': '[tool.poetry.dependencies]\npython = "^3.11"\npytest = "^8"\n'},
            'poetry group': {'pyproject.toml': '[tool.poetry.group.dev.dependencies]\nPytest = {version = "^8"}\n'},
            'ini options': {'pyproject.toml': '[tool.pytest.ini_options]\naddopts = "-q"\n'},
            'pytest.ini': {'pytest.ini': '[pytest]\naddopts = -q\n'},
            'setup.cfg': {'setup.cfg': '[metadata]\nname = x\n\n[tool:pytest]\naddopts = -q\n'},
        }
        for label, files in cases.items():
            with self.subTest(label):
                for path in list(self.repo.iterdir()):
                    if path.is_file():
                        path.unlink()
                self.assertEqual(self.python_checks(files), ([pytest], []))

    def test_a_pytest_plugin_or_a_tests_folder_alone_declares_no_runner(self):
        files = {'pyproject.toml': '[project]\nname = "x"\ndependencies = ["pytest-cov", "pytestx"]\n'
                                   '[tool.poetry.dependencies]\npytest-mock = "*"\n',
                 'setup.cfg': '[pytest_extra]\n', 'pytest.ini': '[tool:other]\n',
                 'tests/test_x.py': 'def test_x():\n    assert True\n'}
        checks, skipped = self.python_checks(files)
        self.assertEqual(checks, [])
        self.assertEqual(skipped, [{'where': 'pyproject.toml', 'reason': 'test runner not declared'}])

    def test_detect_unittest_only_from_explicit_unittest_evidence(self):
        files = {'pyproject.toml': '[project]\nname = "x"\n',
                 'tests/test_a.py': 'import os\n', 'tests/test_b.py': 'import os\nfrom unittest import mock\n'}
        self.assertEqual(self.python_checks(files),
                         ([['python3', '-m', 'unittest', 'discover', '-s', 'tests']], []))

    def test_detect_skips_symlinked_and_oversized_sources(self):
        outside = self.repo.parent / 'outside.json'
        outside.write_text(json.dumps({'scripts': {'test': 'x'}}))
        (self.repo / 'package.json').symlink_to(outside)
        (self.repo / 'Makefile').write_text('test:\n\t' + 'x' * (300 * 1024) + '\n')
        data = json.loads(self.cli('detect', '--root', str(self.repo), '--json')[1])
        self.assertEqual(data['checks'], [])
        self.assertEqual(data['sources'], [])
        self.assertEqual({item['where'] for item in data['skipped']}, {'package.json', 'Makefile'})

    def test_detect_with_nothing_found(self):
        code, out, _ = self.cli('detect', '--root', str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn('No checks found', out)

    # Stored argument form

    def test_preview_refuses_shell_strings_and_bad_input(self):
        before = self.host.read_bytes()
        bad = [
            ['--check', 'test="npm test"'],
            ['--check', 'test=npm test'],
            ['--check', 'test=["sh","-c","npm test"]'],
            ['--check', 'test=["/bin/bash","-lc","npm test"]'],
            ['--check', 'test=["env","CI=1","zsh","-c","x"]'],
            ['--check', 'test=[]'],
            ['--check', 'test=["npm",1]'],
            ['--check', 'test=["npm","te\\nst"]'],
            ['--check', 'Test=["npm","test"]'],
            ['--check', '-test=["npm","test"]'],
            ['--check', 'a' * 33 + '=["npm","test"]'],
            ['--check', 'test=["' + 'x' * 1100 + '"]'],
            ['--check', 'test=["npm","test"]', '--check', 'test=["npm","lint"]'],
            [arg for number in range(21) for arg in ('--check', f'c{number}=["true"]')],
            [],
        ]
        for args in bad:
            with self.subTest(args=args[:4]):
                code, out, err = self.cli('preview', '--root', str(self.repo), *args)
                self.assertEqual(code, 1)
                self.assertIn('refused', err)
                self.assertNotIn('Digest', out)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertFalse(self.plan.exists())

    def test_launchers_and_inline_code_are_refused_at_preview(self):
        before = self.host.read_bytes()
        for argv in REFUSED:
            with self.subTest(argv=argv):
                code, out, err = self.cli('preview', '--root', str(self.repo), '--check', 'test=' + json.dumps(argv))
                self.assertEqual(code, 1)
                self.assertNotIn('Digest', out)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertFalse(self.plan.exists())
        for argv in ALLOWED:
            with self.subTest(argv=argv):
                self.preview('test=' + json.dumps(argv))

    def test_launchers_and_inline_code_are_refused_at_detection(self):
        module = self.module()

        def planted(root_fd, sources, checks, skipped):
            checks.extend(('c', argv) for argv in REFUSED + [['make', 'test']])

        with mock.patch.object(module, 'detect_makefile', planted):
            data = module.detect(str(self.repo))
        self.assertEqual(data['checks'], [{'name': 'c', 'argv': ['make', 'test']}])
        self.assertEqual(len(data['skipped']), len(REFUSED))
        self.assertEqual({item['reason'] for item in data['skipped']}, {'runs a shell, a launcher or inline code'})

    def test_launchers_and_inline_code_make_the_stored_file_unset(self):
        import hashlib
        module = self.module()
        code_ = self.code()
        folder = self.repo / '.finolabs/vibecode'
        folder.mkdir(parents=True, mode=0o700)
        os.chmod(self.repo / '.finolabs', 0o700)
        for argv in REFUSED:
            with self.subTest(argv=argv):
                raw = json.dumps({'version': 1, 'checks': [{'name': 'lint', 'argv': ['make', 'lint']},
                                                           {'name': 'test', 'argv': argv}],
                                  'local_receipt': False}).encode()
                (folder / 'checks.json').write_bytes(raw)
                os.chmod(folder / 'checks.json', 0o600)
                module.cl.write_approved(code_, hashlib.sha256(raw).hexdigest())
                self.assertEqual(module.checks_for(code_, root=self.repo), ([], 'invalid'))

    def test_twenty_checks_are_accepted(self):
        checks = [f'c{number}=["true"]' for number in range(20)]
        self.preview(*checks)

    # Preview, digest, apply

    def test_preview_states_the_trust_boundary_before_approval(self):
        code, out, err = self.cli('preview', '--check', 'lint=["npm","run","lint"]')
        self.assertEqual(code, 0, err)
        for phrase in ('Review every array before you approve', 'best-effort guard, not a sandbox',
                       'an allowed program can still start a shell', 'a repository cannot change the stored list'):
            self.assertIn(phrase, out)

    def test_preview_is_private_and_apply_takes_a_digest_prefix(self):
        digest = self.preview('lint=["npm","run","lint"]', 'test=["python3","-m","unittest"]')
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        code, _, err = self.cli('apply', '--yes', '--digest', digest[:12])
        self.assertEqual(code, 0, err)
        self.assertFalse(self.plan.exists())
        self.assertEqual(self.module().checks_for(self.code(), root=self.repo),
                         ([('lint', ['npm', 'run', 'lint']), ('test', ['python3', '-m', 'unittest'])], None))

    def test_apply_needs_yes_and_a_matching_digest(self):
        digest = self.preview('test=["make","test"]')
        before = self.host.read_bytes()
        for args in (('apply', '--digest', digest), ('apply', '--yes', '--digest', '0' * 12),
                     ('apply', '--yes', '--digest', digest[:8])):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args)[0], 1)
        self.assertEqual(self.host.read_bytes(), before)

    def test_apply_refuses_an_expired_preview(self):
        digest = self.preview('test=["make","test"]')
        with mock.patch('time.time', return_value=time.time() + 3601):
            self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertFalse((self.repo / '.finolabs/vibecode/checks.json').exists())

    # Project settings beside the section

    def test_project_settings_read_and_write_unchanged_beside_checks(self):
        code_ = self.code()
        settings = '## Project settings\n\n- %s parallel: 4\n\n' % code_
        self.host.write_text(PREFIX.decode() + '\n' + settings + '## Checks\n\n- %s: test = ["make","test"]\n' % code_)
        text = self.host.read_text()
        self.assertIn(settings, text)
        for path in (SCRIPTS / 'project_progress.py', ROOT / 'scripts/project_progress.py',
                     ROOT / 'skills/fnl-status/scripts/project_progress.py',
                     ROOT / 'skills/fnl-delegate/scripts/parallel_slots.py', ROOT / 'scripts/parallel_slots.py',
                     ROOT / 'skills/fnl-status/scripts/parallel_slots.py'):
            with self.subTest(path=str(path.relative_to(ROOT))):
                reader = load('settings_reader_' + path.parent.parent.name + path.stem, path)
                self.assertEqual(reader.project_settings(text), {(code_, 'parallel'): '4'})
        writer = load('project_progress_writer', SCRIPTS / 'project_progress.py')
        self.assertTrue(writer.set_setting(self.repo, 'parallel', '5'))
        after = self.host.read_text()
        self.assertIn('## Project settings\n\n- %s parallel: 5\n' % code_, after)
        self.assertEqual(self.module().checks_for(code_, root=self.repo), ([], 'no entry'))
        self.assertEqual(writer.project_settings(after), {(code_, 'parallel'): '5'})

    def test_no_command_but_fixed_git_queries_and_no_network(self):
        source = SCRIPT.read_text()
        for word in ('socket', 'urllib', 'http.client', 'os.system', 'os.exec', 'os.spawn', 'os.popen', 'Popen',
                     'shell=True'):
            self.assertNotIn(word, source)
        # The hook commands ask git where hooks live; that one helper is the only launch.
        self.assertEqual(source.count('subprocess.run('), 1)
        self.assertIn("def git_query(root, *args):\n", source)

    # The local-receipt mode

    def test_receipt_mode_is_its_own_previewed_yes_and_states_the_risk(self):
        digest = self.preview('test=["make","test"]')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        before = self.host.read_bytes()
        code, out, err = self.cli('receipt', 'on', '--root', str(self.repo))
        self.assertEqual(code, 0, err)
        for phrase in ('self-reported', 'gives a reviewer nothing they can check', 'one person works on',
                       'never from a --changed run'):
            self.assertIn(phrase, out)
        self.assertEqual(self.host.read_bytes(), before)
        value = out.split('Digest: ')[1].splitlines()[0]
        self.assertEqual(self.cli('apply', '--yes', '--digest', value)[0], 0)
        code_ = self.code()
        self.assertEqual(self.host.read_bytes(), before)
        reader = load('checks_list_mode', SCRIPTS / 'checks_list.py')
        self.assertTrue(reader.receipt_mode(code_, root=self.repo))
        self.assertEqual(self.module().checks_for(code_, root=self.repo), ([('test', ['make', 'test'])], None))
        # A new list keeps the mode; its digest changes, so an older receipt no longer matches.
        digest = self.preview('lint=["make","lint"]')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        self.assertTrue(reader.receipt_mode(code_, root=self.repo))
        code, out, _ = self.cli('receipt', 'off', '--root', str(self.repo))
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertFalse(reader.receipt_mode(code_, root=self.repo))

    def test_receipt_mode_is_off_by_default_and_needs_a_list(self):
        reader = load('checks_list_default', SCRIPTS / 'checks_list.py')
        self.assertFalse(reader.receipt_mode(self.code(), root=self.repo))
        code, out, _ = self.cli('receipt', 'on', '--root', str(self.repo))
        self.assertEqual(code, 1)
        self.assertNotIn('Digest', out)

    def test_remove_also_turns_the_mode_off(self):
        digest = self.preview('test=["make","test"]')
        self.cli('apply', '--yes', '--digest', digest)
        _, out, _ = self.cli('receipt', 'on', '--root', str(self.repo))
        self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])
        _, out, _ = self.cli('remove', '--root', str(self.repo))
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertFalse((self.repo / '.finolabs/vibecode/checks.json').exists())
        self.assertFalse(load('checks_list_removed', SCRIPTS / 'checks_list.py').receipt_mode(self.code(), root=self.repo))

    def test_the_mode_name_is_reserved(self):
        code, _, _ = self.cli('preview', '--root', str(self.repo), '--check', 'local-receipt=["make"]')
        self.assertEqual(code, 1)


CHANGED = 'changed since it was approved'


class ProjectFileTest(unittest.TestCase):
    """The project-scoped list: <main checkout>/.finolabs/vibecode/checks.json, bound to an approved digest."""

    setUp, module, cli, preview, code = (ChecksSetupTest.setUp, ChecksSetupTest.module, ChecksSetupTest.cli,
                                         ChecksSetupTest.preview, ChecksSetupTest.code)

    def reader(self):
        return load('checks_list_project', SCRIPTS / 'checks_list.py')

    def project(self, root=None):
        return (root or self.repo) / '.finolabs/vibecode/checks.json'

    def approved(self, root=None):
        return self.host.parent / 'state/checks-approved' / (self.code(root) + '.json')

    def save(self, *checks, root=None):
        digest = self.preview(*checks, root=root)
        code, out, err = self.cli('apply', '--yes', '--digest', digest)
        self.assertEqual(code, 0, err)
        return out

    def legacy(self, *lines):
        self.host.write_text(PREFIX.decode() + '\n## Checks\n\n' + ''.join(lines) + '\n')

    def approve(self, root=None):
        """Record the current file's bytes as approved, as an apply would."""
        import hashlib
        self.reader().write_approved(self.code(root), hashlib.sha256(self.project(root).read_bytes()).hexdigest())

    def test_apply_writes_the_project_file_and_its_digest_and_leaves_host_identical(self):
        before = self.host.read_bytes()
        code, out, err = self.cli('preview', '--root', str(self.repo), '--check', 'lint=["make","lint"]',
                                  '--check', 'test=["make","test"]')
        self.assertEqual(code, 0, err)
        self.assertIn('Target: ' + str(self.project()), out)
        self.assertNotIn('host.md', out)
        self.assertIn('Undo: ', out)
        self.assertFalse(self.project().exists())
        digest = out.split('Digest: ')[1].splitlines()[0]
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(list(self.host.parent.glob('host.md.bak-*')), [])
        data = json.loads(self.project().read_text())
        self.assertEqual(data, {'version': 1, 'checks': [{'name': 'lint', 'argv': ['make', 'lint']},
                                                         {'name': 'test', 'argv': ['make', 'test']}],
                                'local_receipt': False})
        self.assertEqual(stat.S_IMODE(self.project().stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.project().parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.repo / '.finolabs').stat().st_mode), 0o700)
        import hashlib
        record = json.loads(self.approved().read_text())
        self.assertEqual(set(record), {'sha256', 'approved'})
        self.assertEqual(record['sha256'], hashlib.sha256(self.project().read_bytes()).hexdigest())
        self.assertEqual(stat.S_IMODE(self.approved().stat().st_mode), 0o600)
        reader = self.reader()
        expected = [('lint', ['make', 'lint']), ('test', ['make', 'test'])]
        self.assertEqual(reader.checks_for(self.code(), root=self.repo), (expected, None))
        self.assertEqual(self.module().checks_for(self.code(), root=self.repo), (expected, None))
        self.assertFalse(reader.receipt_mode(self.code(), root=self.repo))
        code, out, _ = self.cli('show', '--root', str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn('lint = ["make","lint"]', out)

    def test_two_repositories_keep_separate_files_and_remove_touches_only_one(self):
        self.save('test=["make","test"]', root=self.other)
        self.save('lint=["make","lint"]')
        reader = self.reader()
        self.assertEqual(reader.checks_for(self.code(self.other), root=self.other), ([('test', ['make', 'test'])], None))
        self.assertEqual(reader.checks_for(self.code(), root=self.repo), ([('lint', ['make', 'lint'])], None))
        self.save('lint=["make","lint"]', 'test=["make","test"]')
        backups = list(self.project().parent.glob('checks.json.bak-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.assertEqual(json.loads(backups[0].read_text())['checks'], [{'name': 'lint', 'argv': ['make', 'lint']}])
        host = self.host.read_bytes()
        code, out, err = self.cli('remove', '--root', str(self.repo))
        self.assertEqual(code, 0, err)
        self.assertNotIn('host.md', out)
        self.assertTrue(self.project().exists())
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertFalse(self.project().exists())
        self.assertFalse(self.approved().exists())
        self.assertTrue(list(self.project().parent.glob('checks.json.bak-*')))
        self.assertEqual(self.host.read_bytes(), host)
        self.assertEqual(reader.checks_for(self.code(), root=self.repo), ([], 'no entry'))
        self.assertEqual(reader.checks_for(self.code(self.other), root=self.other), ([('test', ['make', 'test'])], None))
        self.assertTrue(self.approved(self.other).exists())

    def linked_worktree(self):
        """A linked worktree laid out as git lays it out, without running git."""
        gitdir = self.repo / '.git/worktrees/side'
        gitdir.mkdir(parents=True)
        (gitdir / 'commondir').write_text('../..\n')
        linked = self.repo.parent / 'linked'
        linked.mkdir()
        (linked / '.git').write_text('gitdir: %s\n' % gitdir)
        (gitdir / 'gitdir').write_text(str(linked / '.git') + '\n')
        return linked

    def test_a_linked_worktree_uses_the_main_checkouts_file(self):
        linked = self.linked_worktree()
        self.assertEqual(self.code(linked), self.code())
        code, out, err = self.cli('preview', '--root', str(linked), '--check', 'test=["make","test"]')
        self.assertEqual(code, 0, err)
        self.assertIn('Target: ' + str(self.project()), out)
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertTrue(self.project().exists())
        self.assertFalse((linked / '.finolabs').exists())
        reader = self.reader()
        self.assertEqual(reader.checks_for(self.code(linked), root=linked), ([('test', ['make', 'test'])], None))
        self.assertEqual(reader.checks_for(self.code(), root=self.repo), ([('test', ['make', 'test'])], None))
        self.assertIn('.finolabs/', (self.repo / '.git/info/exclude').read_text())

    def test_a_checkout_with_borrowed_metadata_cannot_read_another_repositorys_list(self):
        self.save('test=["make","test"]')
        reader = self.reader()
        real = self.linked_worktree()
        intruders = []
        # A back-pointer that names another checkout.
        mismatched = self.repo.parent / 'mismatched'
        mismatched.mkdir()
        (mismatched / '.git').write_text('gitdir: %s\n' % (self.repo / '.git/worktrees/side'))
        intruders.append(mismatched)
        # A metadata folder of its own whose commondir names this repository.
        fake = self.repo.parent / 'fake'
        gitdir = fake / 'meta/worktrees/x'
        gitdir.mkdir(parents=True)
        (gitdir / 'commondir').write_text(str(self.repo / '.git') + '\n')
        (gitdir / 'gitdir').write_text(str(fake / '.git') + '\n')
        (fake / '.git').write_text('gitdir: %s\n' % gitdir)
        intruders.append(fake)
        self.assertEqual(reader.checks_for(self.code(real), root=real), ([('test', ['make', 'test'])], None))
        for intruder in intruders:
            with self.subTest(intruder=intruder.name):
                self.assertNotEqual(self.code(intruder), self.code())
                self.assertEqual(reader.layout(intruder)[0], intruder)
                self.assertEqual(reader.checks_for(self.code(intruder), root=intruder), ([], 'no entry'))
                self.assertEqual(reader.checks_for(self.code(), root=intruder), ([], 'invalid code'))

    def test_the_file_wins_over_a_legacy_entry(self):
        code_ = self.code()
        self.save('lint=["make","lint"]')
        self.legacy('- %s: test = ["make","test"]\n' % code_, '- %s: local-receipt = on\n' % code_)
        reader = self.reader()
        self.assertEqual(reader.checks_for(code_, root=self.repo), ([('lint', ['make', 'lint'])], None))
        self.assertFalse(reader.receipt_mode(code_, root=self.repo))

    def test_a_failed_exclude_line_is_reported_after_the_file_is_saved(self):
        digest = self.preview('unit=["make","unit"]')
        module = self.module()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(module, 'add_exclude', side_effect=OSError('disk')):
            code = module.main(['apply', '--yes', '--digest', digest])
        self.assertEqual(code, 1)
        self.assertIn('the check file was saved', err.getvalue())
        self.assertIn('.git/info/exclude could not be changed', err.getvalue())
        self.assertEqual(self.reader().checks_for(self.code(), root=self.repo), ([('unit', ['make', 'unit'])], None))

    def test_a_legacy_section_is_never_read(self):
        code_ = self.code()
        reader = self.reader()
        for receipt in (True, False):
            with self.subTest(receipt=receipt):
                self.legacy('- %s: test = ["make","test"]\n' % code_,
                            *(['- %s: local-receipt = on\n' % code_] if receipt else []))
                self.assertEqual(reader.checks_for(code_, root=self.repo), ([], 'no entry'))
                self.assertFalse(reader.receipt_mode(code_, root=self.repo))
                reader.write_receipt(code_, 'a' * 40, reader.list_digest([['test', ['make', 'test']]]))
                self.assertIsNone(reader.receipt_status(code_, 'a' * 40, root=self.repo))
                code, out, _ = self.cli('show', '--root', str(self.repo))
                self.assertEqual(code, 0)
                self.assertIn('no checks (no entry)', out)
                code, out, _ = self.cli('receipt', 'on', '--root', str(self.repo))
                self.assertEqual(code, 1)
                self.assertNotIn('Digest', out)

    def test_saving_over_a_missing_file_ignores_a_legacy_section(self):
        code_ = self.code()
        self.legacy('- %s: test = ["make","test"]\n' % code_, '- %s: local-receipt = on\n' % code_)
        before = self.host.read_bytes()
        code, out, err = self.cli('preview', '--root', str(self.repo), '--check', 'unit=["make","unit"]')
        self.assertEqual(code, 0, err)
        self.assertNotIn('host.md', out)
        self.assertIn('local receipt off', out)
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertFalse(json.loads(self.project().read_text())['local_receipt'])
        self.assertFalse(self.reader().receipt_mode(code_, root=self.repo))
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(list(self.host.parent.glob('host.md.bak-*')), [])

    def test_host_md_is_byte_identical_after_save_mode_and_remove(self):
        code_ = self.code()
        self.legacy('- %s: test = ["make","test"]\n' % code_, '- %s: local-receipt = on\n' % code_)
        before = self.host.read_bytes()
        self.save('unit=["make","unit"]')
        self.assertEqual(self.host.read_bytes(), before)
        for state in ('on', 'off'):
            code, out, err = self.cli('receipt', state, '--root', str(self.repo))
            self.assertEqual(code, 0, err)
            self.assertNotIn('host.md', out)
            self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
            self.assertEqual(self.host.read_bytes(), before)
        code, out, err = self.cli('remove', '--root', str(self.repo))
        self.assertEqual(code, 0, err)
        self.assertNotIn('host.md', out)
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertFalse(self.project().exists())
        self.assertFalse(self.approved().exists())
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(list(self.host.parent.glob('host.md.bak-*')), [])
        self.assertEqual(self.reader().checks_for(code_, root=self.repo), ([], 'no entry'))

    def test_a_stale_remove_preview_changes_nothing(self):
        self.save('test=["make","test"]')
        out = self.cli('remove', '--root', str(self.repo))[1]
        self.project().write_bytes(self.reader().render_project([['lint', ['make', 'lint']]], False))
        self.approve()
        file, approval = self.project().read_bytes(), self.approved().read_bytes()
        code, _, err = self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])
        self.assertEqual(code, 1)
        self.assertIn('changed since the preview', err)
        self.assertEqual(self.project().read_bytes(), file)
        self.assertEqual(self.approved().read_bytes(), approval)
        self.assertEqual(self.reader().checks_for(self.code(), root=self.repo), ([('lint', ['make', 'lint'])], None))
        # A file that appears after a remove previewed over none is left alone with its approval.
        self.project().unlink()
        out = self.cli('remove', '--root', str(self.repo))[1]
        self.project().write_bytes(file)
        os.chmod(self.project(), 0o600)
        code, _, _ = self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])
        self.assertEqual(code, 1)
        self.assertEqual(self.project().read_bytes(), file)
        self.assertEqual(self.approved().read_bytes(), approval)

    def test_an_invalid_file_reads_as_unset_for_that_repository_only(self):
        self.save('test=["make","test"]', root=self.other)
        code_ = self.code()
        self.legacy('- %s: test = ["make","test"]\n' % code_)
        good = {'version': 1, 'checks': [{'name': 'test', 'argv': ['make', 'test']}], 'local_receipt': False}
        cases = {
            'unknown key': dict(good, extra=1),
            'wrong version': dict(good, version=2),
            'bool version': dict(good, version=True),
            'shell': dict(good, checks=[{'name': 'test', 'argv': ['sh', '-c', 'make']}]),
            'bad name': dict(good, checks=[{'name': 'Test', 'argv': ['make']}]),
            'extra check key': dict(good, checks=[{'name': 'test', 'argv': ['make'], 'cwd': '/'}]),
            'no checks': dict(good, checks=[]),
            'string mode': dict(good, local_receipt='on'),
        }
        reader = self.reader()
        self.project().parent.mkdir(parents=True, mode=0o700)
        raws = {label: json.dumps(value).encode() for label, value in cases.items()}
        raws['duplicate key'] = b'{"version": 1, "version": 1, "checks": [], "local_receipt": false}'
        raws['not json'] = b'{'
        for label, raw in raws.items():
            with self.subTest(label):
                self.project().write_bytes(raw)
                os.chmod(self.project(), 0o600)
                self.approve()
                self.assertEqual(reader.checks_for(code_, root=self.repo), ([], 'invalid'))
                self.assertFalse(reader.receipt_mode(code_, root=self.repo))
                self.assertEqual(self.project().read_bytes(), raw)
                self.assertEqual(reader.checks_for(self.code(self.other), root=self.other),
                                 ([('test', ['make', 'test'])], None))

    def test_a_symlinked_file_or_folder_is_refused(self):
        code_ = self.code()
        self.save('test=["make","test"]')
        self.legacy('- %s: lint = ["make","lint"]\n' % code_)
        reader = self.reader()
        real = self.repo.parent / 'elsewhere.json'
        real.write_bytes(self.project().read_bytes())
        os.chmod(real, 0o600)
        self.project().unlink()
        self.project().symlink_to(real)
        self.assertEqual(reader.checks_for(code_, root=self.repo), ([], 'unreadable'))
        code, _, _ = self.cli('preview', '--root', str(self.repo), '--check', 'unit=["make","unit"]')
        self.assertEqual(code, 1)
        self.assertTrue(self.project().is_symlink())
        self.project().unlink()
        folder = self.repo.parent / 'folder'
        (self.repo / '.finolabs/vibecode').rename(folder)
        (self.repo / '.finolabs/vibecode').symlink_to(folder)
        (folder / 'checks.json').write_bytes(real.read_bytes())
        os.chmod(folder / 'checks.json', 0o600)
        self.assertEqual(reader.checks_for(code_, root=self.repo), ([], 'unreadable'))
        self.assertFalse(reader.receipt_mode(code_, root=self.repo))
        code, _, _ = self.cli('preview', '--root', str(self.repo), '--check', 'unit=["make","unit"]')
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((folder / 'checks.json').read_text())['checks'][0]['name'], 'test')

    def test_the_exclude_line_is_added_once_and_never_to_gitignore(self):
        (self.repo / '.gitignore').write_text('node_modules/\n')
        info = self.repo / '.git/info'
        info.mkdir()
        (info / 'exclude').write_text('# local\n*.log')
        code, out, err = self.cli('preview', '--root', str(self.repo), '--check', 'test=["make","test"]')
        self.assertEqual(code, 0, err)
        self.assertIn('.git/info/exclude', out)
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertEqual((info / 'exclude').read_text(), '# local\n*.log\n.finolabs/\n')
        code, out, _ = self.cli('preview', '--root', str(self.repo), '--check', 'lint=["make","lint"]')
        self.assertNotIn('.git/info/exclude', out)
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertEqual((info / 'exclude').read_text(), '# local\n*.log\n.finolabs/\n')
        self.assertEqual((self.repo / '.gitignore').read_text(), 'node_modules/\n')

    def test_an_unapproved_file_runs_nothing_and_turns_the_mode_off(self):
        self.save('test=["make","test"]')
        _, out, _ = self.cli('receipt', 'on', '--root', str(self.repo))
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        reader = self.reader()
        code_ = self.code()
        self.assertTrue(reader.receipt_mode(code_, root=self.repo))
        original = self.project().read_bytes()
        data = json.loads(original)
        data['checks'][0]['argv'].append('--all')
        edited = json.dumps(data).encode()
        cases = {'edited after approval': (edited, True), 'no approved digest': (original, False)}
        for label, (raw, keep_approval) in cases.items():
            with self.subTest(label):
                self.project().write_bytes(raw)
                if not keep_approval:
                    self.approved().unlink()
                self.assertEqual(reader.checks_for(code_, root=self.repo), ([], CHANGED))
                self.assertFalse(reader.receipt_mode(code_, root=self.repo))
                self.assertIsNone(reader.receipt_status(code_, 'a' * 40, root=self.repo))
                code, out, _ = self.cli('show', '--root', str(self.repo))
                self.assertIn(CHANGED, out)
                self.assertIn('/fnl-setup add checks', out)

    def test_receipt_mode_lives_in_the_file(self):
        self.save('test=["make","test"]')
        host = self.host.read_bytes()
        code, out, err = self.cli('receipt', 'on', '--root', str(self.repo))
        self.assertEqual(code, 0, err)
        self.assertIn('self-reported', out)
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertTrue(json.loads(self.project().read_text())['local_receipt'])
        self.assertTrue(self.reader().receipt_mode(self.code(), root=self.repo))
        self.save('lint=["make","lint"]')
        self.assertTrue(self.reader().receipt_mode(self.code(), root=self.repo))
        _, out, _ = self.cli('receipt', 'off', '--root', str(self.repo))
        self.assertEqual(self.cli('apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertFalse(self.reader().receipt_mode(self.code(), root=self.repo))
        self.assertEqual(self.host.read_bytes(), host)

    def test_apply_refuses_a_file_changed_after_the_preview(self):
        self.save('test=["make","test"]')
        digest = self.preview('lint=["make","lint"]')
        self.project().write_bytes(b'{}')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.project().read_bytes(), b'{}')
        self.project().unlink()
        self.approved().unlink()
        digest = self.preview('lint=["make","lint"]')
        self.project().write_bytes(b'{}')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(self.project().read_bytes(), b'{}')

    def test_there_is_no_migrate_command_and_the_writer_never_opens_host_md(self):
        self.legacy('- %s: test = ["make","test"]\n' % self.code())
        before = self.host.read_bytes()
        code, out, _ = self.cli('migrate', '--root', str(self.repo))
        self.assertEqual(code, 1)
        self.assertNotIn('Digest', out)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertFalse(self.project().exists())
        self.assertNotIn('host.md', SCRIPT.read_text())


class HookTest(unittest.TestCase):
    """The optional pre-push hook: resolved hooks folder, preview, digest, backup, no silent overwrite."""

    def setUp(self):
        scratch = ROOT / '.finolabs/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / 'home')
        self.env = {'HOME': str(self.home), 'PATH': os.defpath + ':/usr/local/bin:/opt/homebrew/bin'}
        patch = mock.patch.dict(os.environ, self.env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        (self.home / '.finolabs/vibecode').mkdir(parents=True)
        self.repo = base / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        (self.repo / 'README.md').write_text('x\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com', 'commit', '-qm', 'Start')
        self.hooks = Path(self.git('rev-parse', '--absolute-git-dir')).resolve() / 'hooks'
        self.hooks.mkdir(exist_ok=True)
        self.script = base / 'plugin/skills/fnl-checks/scripts/checks.py'
        self.script.parent.mkdir(parents=True)
        self.script.write_text('# synthetic\n')

    def git(self, *argv, cwd=None):
        env = dict(self.env, GIT_CONFIG_NOSYSTEM='1')
        return subprocess.run(['git', *argv], cwd=cwd or self.repo, env=env, capture_output=True, text=True,
                              check=True).stdout.strip()

    def cli(self, *args):
        writer = load('checks_setup_hook_test', SCRIPT)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def install(self, root=None, *extra):
        code, out, err = self.cli('hook', 'install', '--root', str(root or self.repo),
                                  '--checks-script', str(self.script), *extra)
        self.assertEqual(code, 0, err)
        return out, out.split('Digest: ')[1].splitlines()[0]

    def test_install_previews_then_writes_an_executable_hook(self):
        out, digest = self.install()
        for phrase in ('Hooks folder: ' + str(self.hooks), 'every worktree of this repository',
                       'git push --no-verify', 'run --changed', str(self.script), 'Existing pre-push hook: none'):
            self.assertIn(phrase, out)
        self.assertFalse((self.hooks / 'pre-push').exists())
        self.assertEqual(self.cli('hook', 'apply', '--digest', digest)[0], 1)
        self.assertEqual(self.cli('hook', 'apply', '--yes', '--digest', '0' * 12)[0], 1)
        code, out, err = self.cli('hook', 'apply', '--yes', '--digest', digest)
        self.assertEqual(code, 0, err)
        hook = self.hooks / 'pre-push'
        text = hook.read_text()
        self.assertTrue(text.startswith('#!/bin/sh\n'))
        self.assertIn("'%s' run --changed" % self.script, text)
        self.assertEqual(hook.stat().st_mode & 0o777, 0o755)

    def test_an_existing_different_hook_needs_a_second_flag_and_is_backed_up(self):
        hook = self.hooks / 'pre-push'
        hook.write_text('#!/bin/sh\necho mine\n')
        out, digest = self.install()
        self.assertIn('Existing pre-push hook: a different hook', out)
        self.assertEqual(self.cli('hook', 'apply', '--yes', '--digest', digest)[0], 1)
        self.assertEqual(hook.read_text(), '#!/bin/sh\necho mine\n')
        code, _, err = self.cli('hook', 'apply', '--yes', '--replace-existing', '--digest', digest)
        self.assertEqual(code, 0, err)
        self.assertIn('run --changed', hook.read_text())
        backups = list(self.hooks.glob('pre-push.bak-*'))
        self.assertEqual([b.read_text() for b in backups], ['#!/bin/sh\necho mine\n'])

    def test_a_hook_changed_after_the_preview_is_refused(self):
        _, digest = self.install()
        (self.hooks / 'pre-push').write_text('#!/bin/sh\necho later\n')
        self.assertEqual(self.cli('hook', 'apply', '--yes', '--replace-existing', '--digest', digest)[0], 1)
        self.assertEqual((self.hooks / 'pre-push').read_text(), '#!/bin/sh\necho later\n')

    def test_a_custom_hooks_path_is_refused_and_left_alone(self):
        self.git('config', 'core.hooksPath', 'custom-hooks')
        code, out, err = self.cli('hook', 'install', '--root', str(self.repo), '--checks-script', str(self.script))
        self.assertEqual(code, 1)
        self.assertIn('core.hooksPath', err)
        self.assertNotIn('Digest', out)
        self.assertEqual(self.git('config', '--get', 'core.hooksPath'), 'custom-hooks')

    def test_a_linked_worktree_resolves_to_the_shared_hooks_folder(self):
        linked = Path(self.temp.name).resolve() / 'linked'
        self.git('worktree', 'add', '-q', str(linked), '-b', 'side')
        out, digest = self.install(linked)
        self.assertIn('Hooks folder: ' + str(self.hooks), out)
        self.assertIn('This checkout is a linked worktree', out)
        self.assertEqual(self.cli('hook', 'apply', '--yes', '--digest', digest)[0], 0)
        self.assertTrue((self.hooks / 'pre-push').is_file())

    def test_remove_takes_out_only_this_plugins_hook_with_a_backup(self):
        _, digest = self.install()
        self.cli('hook', 'apply', '--yes', '--digest', digest)
        installed = (self.hooks / 'pre-push').read_text()
        code, out, err = self.cli('hook', 'remove', '--root', str(self.repo))
        self.assertEqual(code, 0, err)
        self.assertTrue((self.hooks / 'pre-push').exists())
        self.assertEqual(self.cli('hook', 'apply', '--yes', '--digest', out.split('Digest: ')[1].splitlines()[0])[0], 0)
        self.assertFalse((self.hooks / 'pre-push').exists())
        self.assertEqual([b.read_text() for b in self.hooks.glob('pre-push.bak-*')], [installed])
        (self.hooks / 'pre-push').write_text('#!/bin/sh\necho mine\n')
        self.assertEqual(self.cli('hook', 'remove', '--root', str(self.repo))[0], 1)
        self.assertEqual((self.hooks / 'pre-push').read_text(), '#!/bin/sh\necho mine\n')

    def apply_racing(self, digest, change, *extra):
        """Apply, while `change()` runs right after apply's own check of the hook: a concurrent writer."""
        writer = load('checks_setup_race_test', SCRIPT)
        real, calls = writer.read_hook, []

        def racing(fd):
            found = real(fd)
            if not calls:
                change()
            calls.append(found)
            return found
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(writer, 'read_hook', racing), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(['hook', 'apply', '--yes', *extra, '--digest', digest])
        self.assertTrue(calls, 'apply never read the hook')
        return code, err.getvalue()

    def test_a_hook_created_between_preview_and_apply_is_not_clobbered(self):
        _, digest = self.install()
        hook = self.hooks / 'pre-push'
        code, err = self.apply_racing(digest, lambda: hook.write_bytes(b'#!/bin/sh\necho racing\n'))
        self.assertEqual(code, 1)
        self.assertIn('appeared', err)
        self.assertEqual(hook.read_bytes(), b'#!/bin/sh\necho racing\n')
        self.assertEqual([p.name for p in self.hooks.iterdir() if p.name.startswith('.pre-push-')], [])

    def test_a_hook_changed_between_preview_and_remove_is_refused(self):
        _, digest = self.install()
        self.assertEqual(self.cli('hook', 'apply', '--yes', '--digest', digest)[0], 0)
        hook = self.hooks / 'pre-push'
        code, out, err = self.cli('hook', 'remove', '--root', str(self.repo))
        self.assertEqual(code, 0, err)
        changed = hook.read_bytes() + b'echo racing\n'
        code, err = self.apply_racing(out.split('Digest: ')[1].splitlines()[0], lambda: hook.write_bytes(changed))
        self.assertEqual(code, 1)
        self.assertIn('changed since the preview', err)
        self.assertEqual(hook.read_bytes(), changed)
        self.assertEqual(list(self.hooks.glob('pre-push.bak-*')), [])

    def test_a_hook_changed_between_preview_and_replace_is_refused(self):
        hook = self.hooks / 'pre-push'
        hook.write_bytes(b'#!/bin/sh\necho mine\n')
        _, digest = self.install()
        code, err = self.apply_racing(digest, lambda: hook.write_bytes(b'#!/bin/sh\necho racing\n'),
                                      '--replace-existing')
        self.assertEqual(code, 1)
        self.assertIn('changed since the preview', err)
        self.assertEqual(hook.read_bytes(), b'#!/bin/sh\necho racing\n')

    def assert_untouched_refusal(self, code, err):
        self.assertEqual(code, 1)
        self.assertIn('changed since the preview', err)
        self.assertEqual(list(self.hooks.glob('pre-push.bak-*')), [])
        self.assertEqual([p.name for p in self.hooks.iterdir() if p.name.startswith('.pre-push-')], [])

    def test_an_empty_previewed_hook_replaced_by_a_symlink_is_refused(self):
        hook = self.hooks / 'pre-push'
        hook.write_bytes(b'')
        _, digest = self.install()
        target = self.hooks.parent / 'elsewhere'
        target.write_bytes(b'#!/bin/sh\necho elsewhere\n')

        def to_symlink():
            hook.unlink()
            hook.symlink_to(target)
        code, err = self.apply_racing(digest, to_symlink, '--replace-existing')
        self.assert_untouched_refusal(code, err)
        self.assertTrue(hook.is_symlink())
        self.assertEqual(target.read_bytes(), b'#!/bin/sh\necho elsewhere\n')

    def test_an_empty_previewed_hook_whose_re_read_fails_is_refused(self):
        hook = self.hooks / 'pre-push'
        hook.write_bytes(b'')
        _, digest = self.install()
        writer = load('checks_setup_read_error_test', SCRIPT)
        real, calls = writer.read_hook, []

        def failing(fd):
            calls.append(1)
            if len(calls) > 1:
                raise OSError('synthetic read error')
            return real(fd)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(writer, 'read_hook', failing), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(['hook', 'apply', '--yes', '--replace-existing', '--digest', digest])
        self.assertEqual(len(calls), 2)
        self.assert_untouched_refusal(code, err.getvalue())
        self.assertEqual(hook.read_bytes(), b'')

    def test_an_unsafe_checks_script_path_is_refused(self):
        odd = self.script.parent / "it's" / 'checks.py'
        odd.parent.mkdir()
        odd.write_text('# synthetic\n')
        other = self.script.parent / 'other.py'
        other.write_text('# synthetic\n')
        link = self.script.parent / 'link' / 'checks.py'
        link.parent.mkdir()
        link.symlink_to(self.script)
        for path in (odd, other, link, self.script.parent / 'missing' / 'checks.py', Path('checks.py')):
            with self.subTest(path=str(path)):
                code, out, _ = self.cli('hook', 'install', '--root', str(self.repo), '--checks-script', str(path))
                self.assertEqual(code, 1)
                self.assertNotIn('Digest', out)


class CiWorkflowTest(unittest.TestCase):
    """The previewed workflow writer: one new file from the stored list, a digest, a backup, no silent overwrite."""

    setUp, module, cli, preview, code = (ChecksSetupTest.setUp, ChecksSetupTest.module, ChecksSetupTest.cli,
                                         ChecksSetupTest.preview, ChecksSetupTest.code)

    def store(self, *checks):
        digest = self.preview(*checks)
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)

    def ci(self, *extra):
        code, out, err = self.cli('ci', 'preview', '--root', str(self.repo), *extra)
        self.assertEqual(code, 0, err)
        return out, out.split('Digest: ')[1].splitlines()[0]

    def apply_ci(self, digest, *extra):
        return self.cli('ci', 'apply', '--yes', '--digest', digest, *extra)

    def workflow_text(self, out):
        return out.split('--- workflow ---\n')[1].split('--- end ---\n')[0]

    @property
    def target(self):
        return self.repo / '.github/workflows/fnl-checks.yml'

    def test_preview_shows_the_cheaper_workflow_and_apply_writes_exactly_it(self):
        self.store('unit=["python3","-m","unittest","discover","-s","tests"]', 'lint=["make","lint"]')
        host = self.host.read_bytes()
        out, digest = self.ci()
        self.assertFalse(self.target.exists())
        text = self.workflow_text(out)
        for phrase in ("pull_request:", "push:\n    branches: ['main']", "'**/*.md'", "'docs/**'", "'LICENSE'",
                       "group: ${{ github.workflow }}-${{ github.ref }}", 'cancel-in-progress: true',
                       'schedule:', 'workflow_dispatch:', 'permissions:\n  contents: read',
                       "run: 'python3 -m unittest discover -s tests'", "run: 'make lint'", "name: 'unit'"):
            self.assertIn(phrase, text)
        self.assertLess(text.index("name: 'unit'"), text.index("name: 'lint'"))
        for phrase in ('Target: .github/workflows/fnl-checks.yml', 'through its shell', 'never commits',
                       'review the file and commit it yourself', 'stays pending', 'pinning action versions',
                       'runs the repository\'s code in the cloud'):
            self.assertIn(phrase, out)
        again, digest = self.ci()
        self.assertEqual(self.workflow_text(again), text)  # deterministic text
        code, done, err = self.apply_ci(digest)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.target.read_text(), text)
        self.assertIn('commit', done)
        self.assertEqual(self.host.read_bytes(), host)
        self.assertEqual(self.apply_ci(digest)[0], 1)  # one preview, one write

    def test_run_lines_are_shell_quoted_and_yaml_single_quoted(self):
        self.store('pick=["python3","-m","pytest","-k","it\'s a b"]')
        text = self.workflow_text(self.ci()[0])
        self.assertIn("run: 'python3 -m pytest -k ''it''\"''\"''s a b'''", text)

    def test_cache_follows_a_known_ecosystem_and_its_lockfile(self):
        self.store('unit=["python3","-m","pytest"]')
        text = self.workflow_text(self.ci()[0])
        self.assertIn('actions/setup-python', text)
        self.assertNotIn('cache:', text)
        (self.repo / 'requirements.txt').write_text('pytest\n')
        text = self.workflow_text(self.ci()[0])
        self.assertIn('cache: pip', text)
        self.assertIn("cache-dependency-path: 'requirements.txt'", text)
        self.store('lint=["npm","run","lint"]')
        (self.repo / 'package-lock.json').write_text('{}')
        text = self.workflow_text(self.ci()[0])
        self.assertIn('actions/setup-node', text)
        self.assertIn('cache: npm', text)
        self.assertIn("run: 'npm ci'", text)
        self.assertNotIn('setup-python', text)
        self.store('lint=["make","lint"]')
        text = self.workflow_text(self.ci()[0])
        self.assertNotIn('actions/setup-', text)
        self.assertNotIn('cache', text)

    def test_refuses_without_a_stored_list(self):
        code, out, err = self.cli('ci', 'preview', '--root', str(self.repo))
        self.assertEqual(code, 1)
        self.assertIn('no stored checks', err)
        self.assertFalse((self.repo / '.github').exists())

    def test_refuses_names_and_paths_outside_the_workflows_folder(self):
        self.store('lint=["make","lint"]')
        for path in ('.github/workflows/Bad.yml', '.github/workflows/x.yaml', '../x.yml', '.github/x.yml',
                     '.github/workflows/sub/x.yml', '.github/workflows/-x.yml', str(self.repo / 'x.yml'),
                     '.github/workflows/../workflows/x.yml', '.github/workflows/' + 'a' * 42 + '.yml'):
            with self.subTest(path=path):
                code, out, _ = self.cli('ci', 'preview', '--root', str(self.repo), '--path', path)
                self.assertEqual(code, 1)
                self.assertNotIn('Digest', out)
        out, _ = self.ci('--path', '.github/workflows/cheap-ci.yml')
        self.assertIn('Target: .github/workflows/cheap-ci.yml', out)

    def test_symlink_components_are_refused(self):
        self.store('lint=["make","lint"]')
        elsewhere = self.home / 'elsewhere'
        (elsewhere / 'workflows').mkdir(parents=True)
        (self.repo / '.github').symlink_to(elsewhere)
        self.assertEqual(self.cli('ci', 'preview', '--root', str(self.repo))[0], 1)
        (self.repo / '.github').unlink()
        (self.repo / '.github').mkdir()
        (self.repo / '.github/workflows').symlink_to(elsewhere / 'workflows')
        self.assertEqual(self.cli('ci', 'preview', '--root', str(self.repo))[0], 1)
        (self.repo / '.github/workflows').unlink()
        (self.repo / '.github/workflows').mkdir()
        self.target.symlink_to(elsewhere / 'target.yml')
        self.assertEqual(self.cli('ci', 'preview', '--root', str(self.repo))[0], 1)
        self.assertEqual(list((elsewhere / 'workflows').iterdir()), [])
        self.assertFalse((elsewhere / 'target.yml').exists())

    def test_folders_replaced_by_a_symlink_after_the_preview_are_refused(self):
        self.store('lint=["make","lint"]')
        _, digest = self.ci()
        elsewhere = self.home / 'elsewhere'
        (elsewhere / 'workflows').mkdir(parents=True)
        (self.repo / '.github').symlink_to(elsewhere)
        self.assertEqual(self.apply_ci(digest)[0], 1)
        self.assertEqual(list((elsewhere / 'workflows').iterdir()), [])

    def test_an_existing_file_needs_replace_and_is_backed_up(self):
        self.store('lint=["make","lint"]')
        self.target.parent.mkdir(parents=True)
        self.target.write_text('name: mine\n')
        other = self.target.parent / 'ci.yml'
        other.write_text('name: other\n')
        out, digest = self.ci()
        self.assertIn('a different file', out)
        code, _, err = self.apply_ci(digest)
        self.assertEqual(code, 1)
        self.assertIn('--replace-existing', err)
        self.assertEqual(self.target.read_text(), 'name: mine\n')
        code, _, err = self.apply_ci(digest, '--replace-existing')
        self.assertEqual(code, 0, err)
        self.assertIn("run: 'make lint'", self.target.read_text())
        backups = list((self.host.parent / 'state/checks-ci/backups').iterdir())
        self.assertEqual([b.read_text() for b in backups], ['name: mine\n'])
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.assertEqual(other.read_text(), 'name: other\n')
        self.assertEqual(sorted(p.name for p in self.target.parent.iterdir()), ['ci.yml', 'fnl-checks.yml'])

    def test_a_file_changed_or_created_after_the_preview_is_left_alone(self):
        self.store('lint=["make","lint"]')
        _, digest = self.ci()
        self.target.parent.mkdir(parents=True)
        self.target.write_text('name: racing\n')
        code, _, err = self.apply_ci(digest, '--replace-existing')
        self.assertEqual(code, 1)
        self.assertEqual(self.target.read_text(), 'name: racing\n')
        _, digest = self.ci()
        self.target.write_text('name: later\n')
        self.assertEqual(self.apply_ci(digest, '--replace-existing')[0], 1)
        self.assertEqual(self.target.read_text(), 'name: later\n')
        self.assertEqual([p.name for p in self.target.parent.iterdir()], ['fnl-checks.yml'])

    def test_a_file_appearing_at_publish_is_not_clobbered(self):
        self.store('lint=["make","lint"]')
        _, digest = self.ci()
        writer = self.module()
        real = writer.read_existing

        def racing(fd, name):
            found = real(fd, name)
            Path(self.target).write_text('name: racing\n')
            return found

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(writer, 'read_existing', racing), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(['ci', 'apply', '--yes', '--digest', digest])
        self.assertEqual(code, 1)
        self.assertIn('appeared', err.getvalue())
        self.assertEqual(self.target.read_text(), 'name: racing\n')
        self.assertEqual([p.name for p in self.target.parent.iterdir()], ['fnl-checks.yml'])

    def test_a_dependency_file_voids_the_preview_only_when_the_workflow_would_differ(self):
        self.store('unit=["python3","-m","unittest","discover","-s","tests"]')
        (self.repo / 'requirements.txt').write_text('first==1\n')
        out, digest = self.ci()
        (self.repo / 'requirements.txt').write_text('second==2\n')  # contents are not part of the workflow
        code, _, err = self.apply_ci(digest)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.target.read_text(), self.workflow_text(out))
        self.target.unlink()
        _, digest = self.ci()
        (self.repo / 'requirements.txt').unlink()  # the install step would disappear
        self.assertEqual(self.apply_ci(digest)[0], 1)
        self.assertFalse(self.target.exists())

    def test_a_list_changed_after_the_preview_is_refused(self):
        self.store('lint=["make","lint"]')
        _, digest = self.ci()
        self.store('test=["make","test"]')
        self.assertEqual(self.apply_ci(digest)[0], 1)
        self.assertFalse(self.target.exists())

    def test_apply_needs_yes_and_a_matching_digest(self):
        self.store('lint=["make","lint"]')
        _, digest = self.ci()
        self.assertEqual(self.cli('ci', 'apply', '--digest', digest)[0], 1)
        self.assertEqual(self.apply_ci('0' * 12)[0], 1)
        with mock.patch('time.time', return_value=time.time() + 3601):
            self.assertEqual(self.apply_ci(digest)[0], 1)
        self.assertFalse(self.target.exists())

    def test_expressions_and_unprintable_lines_are_refused(self):
        for argv in (['make', '${{ secrets.TOKEN }}'], ['make', 'a‮b']):
            with self.subTest(argv=argv):
                self.store('lint=' + json.dumps(argv))
                code, out, _ = self.cli('ci', 'preview', '--root', str(self.repo))
                self.assertEqual(code, 1)
                self.assertNotIn('Digest', out)

    def test_a_bad_branch_is_refused(self):
        self.store('lint=["make","lint"]')
        out, _ = self.ci('--branch', 'trunk')
        self.assertIn("branches: ['trunk']", out)
        for branch in ("a'b", 'a..b', '-x', 'a b', ''):
            with self.subTest(branch=branch):
                self.assertEqual(self.cli('ci', 'preview', '--root', str(self.repo), '--branch', branch)[0], 1)


if __name__ == '__main__':
    unittest.main()
