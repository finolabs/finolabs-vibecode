"""Environment-boundary tests use synthetic mappings and compare names only."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_env
import delegate_env


class RunEnvironmentTest(unittest.TestCase):
    def test_only_allowlisted_names_and_explicit_form_names(self):
        source = {k: 'synthetic' for k in (*run_env.BASE_NAMES, 'EXTRA', 'ACCOUNT_TOKEN', 'CLAUDE_CONFIG_DIR')}
        env = run_env.environment(source)
        self.assertEqual(set(env), set(run_env.BASE_NAMES))
        env = run_env.environment(source, ['EXTRA'], {'CLAUDE_CONFIG_DIR': '/' + 'synthetic/config'})
        self.assertEqual(set(env), {*run_env.BASE_NAMES, 'EXTRA', 'CLAUDE_CONFIG_DIR'})
        self.assertEqual(set(run_env.environment({})), set())
        with self.assertRaises(ValueError):
            run_env.environment(source, explicit={'OTHER': 'value'})

    def test_host_names_default_none_and_approval_is_individual(self):
        for text in ('', '## Other\nanything\n', '## Delegate environment\n- codex: none\n'):
            self.assertEqual(delegate_env.names_from_host(text, 'codex'), [])
        text = ('## Delegate environment\n- codex: BUILD_MODE\n'
                '- claude: ACCOUNT_TOKEN; approved: yes\n## Other\nignored\n')
        self.assertEqual(delegate_env.names_from_host(text, 'codex'), ['BUILD_MODE'])
        self.assertEqual(delegate_env.names_from_host(text, 'claude'), ['ACCOUNT_TOKEN'])
        with self.assertRaises(ValueError):
            delegate_env.names_from_host(text.replace('; approved: yes', ''), 'codex')

    def test_names_controls_duplicates_and_malformed_section_refuse(self):
        bad = ['lower', 'A-B', 'A*', 'A=value', 'A' * 65, 'LD_PRELOAD', 'DYLD_INSERT_LIBRARIES',
               'BASH_ENV', 'ENV', 'NODE_OPTIONS', 'PYTHONPATH', 'PERL5OPT', 'RUBYOPT',
               'GIT_CONFIG_COUNT', 'HTTPS_PROXY', 'SSL_CERT_FILE', 'A\n- codex: A',
               'none\n- codex: BUILD_MODE', 'PATH', 'CLAUDE_CONFIG_DIR', 'ACCOUNT_PASSWORD']
        for name in bad:
            with self.subTest(case=bad.index(name)), self.assertRaises(ValueError):
                delegate_env.names_from_host('## Delegate environment\n- codex: ' + name + '\n', 'codex')
        for text in ('## Delegate environment\ncomment\n',
                     '## Delegate environment\n## Delegate environment\n',
                     '## Delegate environment\n## Delegate environment',
                     '## Delegate environment\n- unknown: BUILD_MODE\n',
                     '## Delegate environment\n- codex: BUILD_MODE; approved: no\n'):
            with self.assertRaises(ValueError):
                delegate_env.names_from_host(text, 'codex')

    def test_child_sees_only_allowlisted_names_from_synthetic_source(self):
        source = {'PATH': os.defpath, 'HOME': '/' + 'synthetic', 'LANG': 'C',
                  'TMPDIR': tempfile.gettempdir(), 'FNL_DISPATCH_ID': 'synthetic',
                  'EXTRA': 'synthetic', 'BUILD_MODE': 'synthetic', 'ACCOUNT_TOKEN': 'synthetic'}
        host = '## Delegate environment\n- codex: BUILD_MODE\n'
        env = delegate_env.environment('codex', source, host)
        self.assertEqual(set(env), {*run_env.BASE_NAMES, 'BUILD_MODE'})
        # Python may add locale/runtime names; no values are emitted or compared.
        code = ('import os,sys; allowed={"PATH","HOME","LANG","TMPDIR","FNL_DISPATCH_ID",'
                '"BUILD_MODE","LC_CTYPE","__CF_USER_TEXT_ENCODING"}; '
                'sys.exit(0 if set(os.environ) <= allowed and "BUILD_MODE" in os.environ else 1)')
        child = subprocess.run([sys.executable, '-I', '-c', code], env=env, capture_output=True)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(child.stdout, b'')
        with mock.patch.object(delegate_env, 'prepare_logs'), \
                mock.patch.object(delegate_env.subprocess, 'call', return_value=0) as call, \
                mock.patch.object(delegate_env.dr, 'read_data', return_value=host.encode()), \
                mock.patch.dict(os.environ, source, clear=True), \
                mock.patch.object(sys, 'argv', ['delegate_env.py', '--family', 'codex', '--', 'synthetic-command']):
            self.assertEqual(delegate_env.main(), 0)
            self.assertEqual(set(call.call_args.kwargs['env']), {*run_env.BASE_NAMES, 'BUILD_MODE'})

    def test_dispatch_cli_reads_canonical_host_and_starts_a_real_child(self):
        import log_scan
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            home = account(self, root / 'home')
            config = home / '.finolabs/vibecode/host.md'
            config.parent.mkdir(parents=True)
            config.write_text('## Delegate environment\n- codex: BUILD_MODE\n')
            logs = root / 'logs'
            source = {name: 'synthetic' for name in ('FNL_DISPATCH_ID', 'EXTRA', 'BUILD_MODE', 'ACCOUNT_TOKEN')}
            source.update(PATH=os.defpath, HOME=str(home), LANG='C', TMPDIR=str(root))
            code = ('import os,sys; expected={"PATH","HOME","LANG","TMPDIR","FNL_DISPATCH_ID",'
                    '"BUILD_MODE","LC_CTYPE","__CF_USER_TEXT_ENCODING"}; '
                    'sys.exit(0 if set(os.environ) <= expected and "BUILD_MODE" in os.environ else 1)')
            argv = ['delegate_env.py', '--family', 'codex', '--', sys.executable, '-I', '-c', code]
            with mock.patch.dict(os.environ, source, clear=True), mock.patch.object(sys, 'argv', argv), \
                    mock.patch.object(log_scan, 'run_log_folder', return_value=logs):
                self.assertEqual(delegate_env.main(), 0)
            self.assertEqual(logs.stat().st_mode & 0o777, 0o700)
            logs.chmod(0o755)
            output = io.StringIO()
            with mock.patch.object(sys, 'argv', argv), \
                    mock.patch.object(log_scan, 'run_log_folder', return_value=logs), \
                    mock.patch.object(delegate_env.subprocess, 'call') as call, contextlib.redirect_stderr(output):
                self.assertEqual(delegate_env.main(), 2)
            self.assertEqual(output.getvalue(), 'delegate_env: refused\n')
            call.assert_not_called()

    def test_template_strictly_parses_for_each_family(self):
        text = (ROOT / 'skills/fnl-delegate/references/host-template.md').read_text()
        for family in delegate_env.FAMILIES:
            self.assertEqual(delegate_env.names_from_host(text, family), [])


if __name__ == '__main__':
    unittest.main()
