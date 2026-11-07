"""Package G documentation and script-launch acceptance oracles."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


# Exact argv shapes for existing mechanical workers, scoped to file and function.
# A mention of git, __file__, REFRESH or --version grants no exemption.
MECHANICAL = {
    ('record.py', 'git'): ("['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=" + '/' + "dev/null', '-c', 'core.untrackedCache=false', '-C', str(checkout), *args]", 'child_environment()'),
    ('instructions_write.py', 'git_top'): ("['git', 'rev-parse', '--show-toplevel']", 'env'),
    ('nav_state.py', 'collect_git_evidence'): ("[git, '-c', 'log.showSignature=false', '-c', 'core.fsmonitor=false', '-C', os.path.abspath(repo_root), 'log', '--no-show-signature', '--no-color', '--no-ext-diff', '--no-textconv', '--format=%H%x09%s', f'--since={since}']", 'env'),
    ('post_review.py', 'gh_call'): ('[executable, *args]', 'gh_environment()'),
    ('metrics_hook.py', 'refresh_dashboard'): ("[sys.executable, '-I', str(REFRESH), 'run', *extra, *(['--cwd', cwd] if cwd else [])]", None),
    ('metrics_hook.py', 'start_detached_refresh'): ("[sys.executable, '-I', str(REFRESH), 'run', '--throttle', '10', *(['--cwd', cwd] if cwd else [])]", 'env'),
    ('update_check.py', 'start_fetch'): ("[sys.executable, '-I', str(Path(__file__).resolve()), '--fetch']", None),
    ('check-references.py', 'documents'): ("['git', 'ls-files', '--cached', '-z', '--', ':(glob)skills/*/**/*.md', ':(glob)agents/*.md', ':(glob)rules/*.md', ':(glob)*.md', ':(glob)docs/**/*.md']", None),
    ('check-references.py', 'check_skill_inventory'): ("['git', 'ls-files', '--cached', '-z']", None),
    ('merge_check.py', 'run_gh'): ("['gh', *args]", None),
    ('agent_scan.py', 'inventory'): ("[executable, '--version']", None),
    ('restore_point.py', 'run_git'): ("['git', '-c', 'core.quotePath=false', '-c', 'core.hooksPath=" + '/' + "dev/null', '-c', 'core.fsmonitor=false', *args]", 'env'),
}
OWN_ENV = {'quota_probe.py', 'agent_processes.py'}


def expression(source):
    return ast.dump(ast.parse(source, mode='eval').body) if source is not None else None


def unsafe_launches(source, filename=''):
    """Inspect launch ASTs and local env bindings; unknown launches fail closed."""
    tree = ast.parse(source)
    parents, aliases = {}, {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in {'subprocess', 'os', 'run_env'}:
            for alias in node.names:
                aliases[alias.asname or alias.name] = node.module + '.' + alias.name

    def target(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return target(node.value) + '.' + node.attr
        return ''

    def scope(node):
        while node in parents and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node = parents[node]
        return node

    bad = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        name = target(call.func)
        if not (name in {'subprocess.run', 'subprocess.Popen', 'subprocess.call',
                         'subprocess.check_call', 'subprocess.check_output',
                         'subprocess.getoutput', 'subprocess.getstatusoutput', 'os.system', 'os.popen'}
                or name.startswith(('os.exec', 'os.spawn'))):
            continue
        block = scope(call)
        function = block.name if isinstance(block, (ast.FunctionDef, ast.AsyncFunctionDef)) else ''
        env = next((k.value for k in call.keywords if k.arg == 'env'), None)
        expected = MECHANICAL.get((filename, function))
        command = ast.dump(call.args[0]) if call.args else None
        mechanical = (expected is not None and command == expression(expected[0])
                      and (ast.dump(env) if env is not None else None) == expression(expected[1]))
        # execve's environment is positional, unlike subprocess's env keyword.
        if name in {'os.execve', 'os.execvpe'} and len(call.args) >= 3:
            env = call.args[2]
        if isinstance(env, ast.Name):
            bindings = [node for node in ast.walk(block) if isinstance(node, ast.Assign)
                        and node.lineno < call.lineno and scope(node) is block
                        and any(isinstance(t, ast.Name) and t.id == env.id for t in node.targets)]
            env = max(bindings, key=lambda n: n.lineno).value if bindings else None
        helper = isinstance(env, ast.Call) and target(env.func) == 'run_env.environment'
        if filename in {'run_env.py', 'delegate_env.py'} and isinstance(env, ast.Call) and target(env.func) == 'environment':
            builder = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'environment'), None)
            helper = builder is not None and (filename == 'run_env.py' or any(
                isinstance(n, ast.Return) and isinstance(n.value, ast.Call)
                and target(n.value.func) == 'run_env.environment' for n in ast.walk(builder)))
        own = ((filename, function) == ('quota_probe.py', 'command')
               and env is not None and ast.dump(env) == expression('environment(entry, folder)'))
        own |= ((filename, function) == ('agent_processes.py', '_run')
                and isinstance(env, ast.Dict) and {k.value for k in env.keys if isinstance(k, ast.Constant)} == {'PATH', 'LC_ALL'}
                and len(env.keys) == 2)
        shell = any(k.arg == 'shell' and not (isinstance(k.value, ast.Constant) and k.value.value is False)
                    for k in call.keywords)
        if shell or not (mechanical or helper or own):
            bad.append(call.lineno)
    return bad


class RunHygieneTest(unittest.TestCase):
    def test_log_size_rule_names_both_limits_together(self):
        spec = (ROOT / 'docs/specs/run-hygiene.md').read_text()
        self.assertIn('(over 8 MiB or the 250,000-pair per-pass limit)', spec)

    def test_scripts_start_delegates_and_tests_only_through_run_env(self):
        paths = [*(ROOT / 'scripts').glob('*.py'), *(ROOT / 'skills').glob('*/scripts/*.py')]
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertEqual(unsafe_launches(path.read_text(), path.name), [])

    def test_launch_oracle_catches_new_dynamic_and_literal_commands(self):
        for source in ("import subprocess\nsubprocess.run(['codex','exec'])",
                       "import subprocess\ndef test(argv):\n subprocess.Popen(argv)",
                       "import os\nos.system('python -m unittest')"):
            self.assertTrue(unsafe_launches(source))
        self.assertEqual(unsafe_launches('import run_env,subprocess\nsubprocess.run(argv,env=run_env.environment())'), [])

    def test_launch_oracle_rejects_substring_baits_and_aliases(self):
        for command in ("['codex', '--version']", "['python', 'git']", "[REFRESH, 'codex']",
                        "['python', __file__]", "['sh', '-c', 'gh']"):
            self.assertTrue(unsafe_launches('import subprocess\nsubprocess.run(' + command + ')'))
        for source in ("from subprocess import Popen as start\nstart(argv)",
                       "import subprocess as sp\nsp.run(argv)",
                       "from os import execve as start\nstart(path, argv, inherited)",
                       "import os\nos.execve(path, argv, inherited)",
                       "import run_env, subprocess\ndef bad(argv):\n env = inherited\n subprocess.run(argv, env=env)\ndef unrelated():\n return run_env.environment()"):
            self.assertTrue(unsafe_launches(source))

    def test_mechanical_allowlist_is_scoped_and_exact(self):
        for (filename, function), (argv, env) in MECHANICAL.items():
            source = 'import subprocess\ndef ' + function + '():\n subprocess.run(' + argv
            source += (', env=' + env if env else '') + ')'
            self.assertEqual(unsafe_launches(source, filename), [])
            self.assertTrue(unsafe_launches(source, 'unknown.py'))
            changed = source.replace('subprocess.run(' + argv, "subprocess.run(['codex', 'exec']")
            self.assertTrue(unsafe_launches(changed, filename))
        for source, filename in (("import subprocess\ndef command():\n subprocess.Popen(argv)", 'quota_probe.py'),
                                 ("import subprocess\ndef _run():\n subprocess.Popen(argv)", 'agent_processes.py')):
            self.assertTrue(unsafe_launches(source, filename))

    def test_scoped_exceptions_build_their_own_allowlisted_environments(self):
        self.assertEqual(OWN_ENV, {'quota_probe.py', 'agent_processes.py'})
        paths = [*(ROOT / 'scripts').glob('*.py'), *(ROOT / 'skills').glob('*/scripts/*.py')]
        checked = set()
        for path in paths:
            if path.name not in OWN_ENV:
                continue
            checked.add(path.name)
            tree = ast.parse(path.read_text())
            with self.subTest(path=str(path.relative_to(ROOT))):
                if path.name == 'quota_probe.py':
                    builder = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'environment')
                    # Execute only the builder with synthetic dependencies. It cannot
                    # access the process environment, account files or real data roots.
                    namespace = {'Path': Path, 'SYSTEM_PATH': '/' + 'synthetic/bin',
                                 'dr': SimpleNamespace(account_home=lambda: Path('/' + 'synthetic/home')),
                                 'os': SimpleNamespace(getuid=lambda: 123),
                                 'pwd': SimpleNamespace(getpwuid=lambda uid: SimpleNamespace(pw_name='fixture'))}
                    exec(compile(ast.Module(body=[builder], type_ignores=[]), '<synthetic-builder>', 'exec'), namespace)
                    entry = {'executable': '/' + 'synthetic/bin/agent'}
                    expected = {'HOME', 'PATH', 'USER', 'LANG', 'FNL_METRICS', 'FNL_UPDATE_CHECK'}
                    self.assertEqual(set(namespace['environment'](entry)), expected)
                    self.assertEqual(set(namespace['environment'](entry, '/' + 'synthetic/config')),
                                     expected | {'CLAUDE_CONFIG_DIR'})
                else:
                    builder = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_run')
                    launch = next(n for n in ast.walk(builder) if isinstance(n, ast.Call)
                                  and ast.unparse(n.func) == 'subprocess.Popen')
                    env = next(k.value for k in launch.keywords if k.arg == 'env')
                    self.assertEqual(set(ast.literal_eval(env)), {'PATH', 'LC_ALL'})
        self.assertEqual(checked, OWN_ENV)

    def test_setup_individual_neutral_consent_names_only(self):
        text = (ROOT / 'skills/fnl-setup/references/features/delegation.md').read_text()
        for expected in ('For each present agent family', 'Default none', 'names only, never values',
                         'KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, SESSIONID or SESSID anywhere',
                         'PASS, PASSWD, PASSPHRASE, AUTH, COOKIE, COOKIES, SESSION or PRIVATE as a complete',
                         'underscore-delimited part', 'ask separately',
                         'Let <agent family> receive the value of <VARIABLE_NAME> when it starts?', 'neutral Yes and No with none preselected',
                         'only an explicit Yes', '; approved: yes'):
            self.assertIn(expected, text)

    def test_lesson_report_and_every_dispatch_family(self):
        lesson = (ROOT / 'skills/fnl-session-hygiene/SKILL.md').read_text()
        self.assertIn('Corrected-lesson example: on 2026-11-07 a delegated test assertion dumped the process environment', lesson)
        agents = (ROOT / 'skills/fnl-delegate/references/agents.md').read_text()
        for family in ('claude', 'codex', 'antigravity'):
            self.assertIn('delegate_env.py --family ' + family + ' --', agents)
        for expected in ('brief_check.py', 'agybird runner', 'environment-only',
                         'in-session subagents are not covered', 'never by a hook'):
            self.assertIn(expected, agents)
        for path in (ROOT / 'scripts').glob('*hook*.py'):
            self.assertNotIn('delegate_env', path.read_text())

    def test_new_script_copies_are_explicit_ci_groups(self):
        from tests.test_shared_copies import ci_copy_groups
        groups = ci_copy_groups()
        for name, skills in {'run_env.py': ['fnl-delegate', 'fnl-verification'],
                             'delegate_env.py': ['fnl-delegate'], 'log_scan.py': ['fnl-delegate'],
                             'secret_patterns.py': ['fnl-delegate', 'fnl-handoff'],
                             'brief_check.py': ['fnl-handoff']}.items():
            self.assertIn([f'scripts/{name}', *[f'skills/{s}/scripts/{name}' for s in skills]], groups)

    def test_touched_skill_documents_respect_setup_size_limits(self):
        # Apply the spec's limits to touched skill bodies, feature docs and new reference text.
        for relative in ('fnl-setup/SKILL.md', 'fnl-delegate/SKILL.md', 'fnl-handoff/SKILL.md', 'fnl-session-hygiene/SKILL.md', 'fnl-verification/SKILL.md', 'fnl-setup/references/features/delegation.md'):
            path = ROOT / 'skills' / relative
            text = path.read_text()
            self.assertLessEqual(len(text.encode()), 10000 if path.name == 'SKILL.md' else 8000)
            self.assertLessEqual(len(text.splitlines()), 70 if path.name == 'SKILL.md' else 80)
            self.assertTrue(all(len(line) <= 600 for line in text.splitlines()))


if __name__ == '__main__':
    unittest.main()
