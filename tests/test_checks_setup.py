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

    def test_launchers_and_inline_code_make_the_stored_section_unset(self):
        module = self.module()
        code_ = self.code()
        for argv in REFUSED:
            with self.subTest(argv=argv):
                encoded = json.dumps(argv, separators=(',', ':'))
                self.host.write_text(PREFIX.decode() + '\n## Checks\n\n- %s: lint = ["make","lint"]\n- %s: test = %s\n'
                                     % (code_, code_, encoded))
                self.assertEqual(module.checks_for(code_), ([], 'invalid'))

    def test_twenty_checks_are_accepted(self):
        checks = [f'c{number}=["true"]' for number in range(20)]
        self.preview(*checks)

    # Preview, digest, apply

    def test_preview_then_apply_writes_only_the_section(self):
        before = self.host.read_bytes()
        digest = self.preview('lint=["npm","run","lint"]', 'test=["python3","-m","unittest"]')
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        code, _, err = self.cli('apply', '--yes', '--digest', digest[:12])
        self.assertEqual(code, 0, err)
        raw = self.host.read_bytes()
        self.assertTrue(raw.startswith(before))
        code_ = self.code()
        self.assertIn(('\n## Checks\n\n- %s: lint = ["npm","run","lint"]\n'
                       '- %s: test = ["python3","-m","unittest"]\n' % (code_, code_)).encode(), raw)
        self.assertEqual(next(self.host.parent.glob('host.md.bak-*')).read_bytes(), before)
        self.assertFalse(self.plan.exists())
        module = self.module()
        self.assertEqual(module.checks_for(code_),
                         ([('lint', ['npm', 'run', 'lint']), ('test', ['python3', '-m', 'unittest'])], None))
        code, out, _ = self.cli('show', '--root', str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn('lint = ["npm","run","lint"]', out)

    def test_apply_needs_yes_and_a_matching_digest(self):
        digest = self.preview('test=["make","test"]')
        before = self.host.read_bytes()
        for args in (('apply', '--digest', digest), ('apply', '--yes', '--digest', '0' * 12),
                     ('apply', '--yes', '--digest', digest[:8])):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args)[0], 1)
        self.assertEqual(self.host.read_bytes(), before)

    def test_apply_refuses_an_expired_preview_or_a_changed_host(self):
        digest = self.preview('test=["make","test"]')
        with mock.patch('time.time', return_value=time.time() + 3601):
            self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        digest = self.preview('test=["make","test"]')
        self.host.write_bytes(PREFIX + b'\n## Later\nx\n')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 1)
        self.assertNotIn(b'## Checks', self.host.read_bytes())

    def test_a_symlinked_host_is_refused(self):
        real = self.home / 'real-host.md'
        real.write_bytes(PREFIX)
        self.host.unlink()
        self.host.symlink_to(real)
        code, _, err = self.cli('preview', '--root', str(self.repo), '--check', 'test=["make","test"]')
        self.assertEqual(code, 1)
        self.assertEqual(real.read_bytes(), PREFIX)

    def test_other_repositories_are_kept_and_remove_takes_only_this_one(self):
        digest = self.preview('test=["make","test"]', root=self.other)
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        digest = self.preview('lint=["make","lint"]')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        module = self.module()
        self.assertEqual(module.checks_for(self.code(self.other)), ([('test', ['make', 'test'])], None))
        self.assertEqual(module.checks_for(self.code()), ([('lint', ['make', 'lint'])], None))
        digest = self.preview('lint=["make","lint"]', 'test=["make","test"]')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        self.assertEqual(module.checks_for(self.code())[0], [('lint', ['make', 'lint']), ('test', ['make', 'test'])])
        code, out, err = self.cli('remove', '--root', str(self.repo))
        self.assertEqual(code, 0, err)
        digest = out.split('Digest: ')[1].splitlines()[0]
        self.assertIn(b'- %s: lint' % self.code().encode(), self.host.read_bytes())
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        self.assertEqual(module.checks_for(self.code()), ([], 'no entry'))
        self.assertEqual(module.checks_for(self.code(self.other)), ([('test', ['make', 'test'])], None))
        code, out, _ = self.cli('remove', '--root', str(self.other))
        digest = out.split('Digest: ')[1].splitlines()[0]
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
        self.assertNotIn(b'## Checks', self.host.read_bytes())
        self.assertEqual(module.checks_for(self.code()), ([], 'absent'))

    # Reader

    def test_reader_unsets_an_invalid_section_and_never_repairs_it(self):
        module = self.module()
        code_ = self.code()
        good = '- %s: test = ["make","test"]\n' % code_
        cases = {
            'shell string': '- %s: test = "make test"\n' % code_,
            'bad name': '- %s: Test = ["make"]\n' % code_,
            'duplicate': good + good,
            'shell': '- %s: test = ["sh","-c","make"]\n' % code_,
            'unknown line': good + 'note: hi\n',
            'too many': ''.join('- %s: c%d = ["true"]\n' % (code_, n) for n in range(21)),
            'long': '- %s: test = ["%s"]\n' % (code_, 'x' * 1100),
        }
        for label, body in cases.items():
            with self.subTest(label):
                text = PREFIX.decode() + '\n## Checks\n\n' + body + '\n## After\n- other: ' + label + '\n'
                self.host.write_text(text)
                self.assertEqual(module.checks_for(code_), ([], 'invalid'))
                code, _, _ = self.cli('preview', '--root', str(self.repo), '--check', 'test=["make","test"]')
                self.assertEqual(code, 1)
                self.assertEqual(self.host.read_text(), text)
        self.host.write_text('## Checks\n' + good + '\n## Checks\n' + good)
        self.assertEqual(module.checks_for(code_), ([], 'invalid'))
        self.host.write_text('```\n## Checks\n' + good.replace('make', 'x') + '```\n\n## Checks\n' + good)
        self.assertEqual(module.checks_for(code_), ([('test', ['make', 'test'])], None))
        self.host.unlink()
        self.assertEqual(module.checks_for(code_), ([], 'absent'))

    # Project settings beside the section

    def test_project_settings_read_and_write_unchanged_beside_checks(self):
        code_ = self.code()
        settings = '## Project settings\n\n- %s parallel: 4\n\n' % code_
        self.host.write_text(PREFIX.decode() + '\n' + settings)
        digest = self.preview('test=["make","test"]')
        self.assertEqual(self.cli('apply', '--yes', '--digest', digest)[0], 0)
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
        self.assertEqual(self.module().checks_for(code_), ([('test', ['make', 'test'])], None))
        self.assertEqual(writer.project_settings(after), {(code_, 'parallel'): '5'})

    def test_no_command_and_no_network(self):
        source = SCRIPT.read_text()
        for word in ('subprocess', 'socket', 'urllib', 'http.client', 'os.system', 'os.exec', 'os.spawn', 'os.popen'):
            self.assertNotIn(word, source)


if __name__ == '__main__':
    unittest.main()
