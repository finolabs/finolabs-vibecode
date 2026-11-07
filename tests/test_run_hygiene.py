"""Package G documentation and script-launch acceptance oracles."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def unsafe_launches(source):
    """Grep candidates, then inspect their enclosing functions to follow argv wrappers.

    Unknown/dynamic argv launches fail closed; only explicitly mechanical tools
    and plugin refresh/update workers are outside delegate/test-command scope.
    """
    if not re.search(r'subprocess\.|os\.(?:exec|spawn|system)', source):
        return []
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    bad = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        target = ast.unparse(call.func)
        if not (target in {'subprocess.run', 'subprocess.Popen', 'subprocess.call', 'subprocess.check_call',
                           'subprocess.check_output', 'os.system'} or target.startswith(('os.exec', 'os.spawn'))):
            continue
        block = call
        while block in parents and not isinstance(block, (ast.FunctionDef, ast.AsyncFunctionDef)):
            block = parents[block]
        command = ast.unparse(call.args[0]) if call.args else ''
        local = ast.unparse(block)
        safe = any(word in command for word in ('REFRESH', '__file__', "'git'", '"git"', "'gh'", "'--version'"))
        safe |= command.startswith('[git,')
        safe |= ('executable' in command and 'gh_environment()' in local and 'def gh_call(' in source)
        has_helper = ('run_env.environment(' in ast.unparse(call) or
                      (('env=environment(' in ast.unparse(call) or 'env=env' in ast.unparse(call)) and
                       (('import run_env' in source and 'run_env.environment(' in source)
                        or ('def environment(' in source and 'BASE_NAMES =' in source))))
        if not safe and not has_helper:
            bad.append(call.lineno)
    return bad


class RunHygieneTest(unittest.TestCase):
    def test_scripts_start_delegates_and_tests_only_through_run_env(self):
        paths = [*(ROOT / 'scripts').glob('*.py'), *(ROOT / 'skills').glob('*/scripts/*.py')]
        for path in paths:
            if path.name in {'quota_probe.py', 'agent_processes.py'}:
                continue  # The two scoped CLAUDE.md exceptions own their allowlists.
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertEqual(unsafe_launches(path.read_text()), [])

    def test_launch_oracle_catches_new_dynamic_and_literal_commands(self):
        for source in ("import subprocess\nsubprocess.run(['codex','exec'])",
                       "import subprocess\ndef test(argv):\n subprocess.Popen(argv)",
                       "import os\nos.system('python -m unittest')"):
            self.assertTrue(unsafe_launches(source))
        self.assertEqual(unsafe_launches('import run_env,subprocess\nsubprocess.run(argv,env=run_env.environment())'), [])

    def test_setup_individual_neutral_consent_names_only(self):
        text = (ROOT / 'skills/fnl-setup/references/features/delegation.md').read_text()
        for expected in ('For each present agent family', 'Default none', 'names only, never values',
                         'KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, PASS, AUTH, COOKIE, SESSION or PRIVATE', 'ask separately',
                         'Pass <VARIABLE_NAME> to <agent family>?', 'neutral Yes and No with none preselected',
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
