"""Package F: companion data and advisory consent boundaries, without installing anything."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / 'skills/fnl-setup'
REFS = SETUP / 'references'
COMPANIONS = {'agybird', 'vietnamizer', 'typesafe-ai', 'diagram-design', 'markmap'}
CHOICES = ('writing Vietnamese for readers', 'delegating work to Antigravity',
           'drawing architecture or flow diagrams', 'mind maps and outlines', 'none of these')


def table(text, heading):
    body = text.split(heading + '\n', 1)[1].strip().split('\n\n', 1)[0]
    return [[cell.strip() for cell in line.strip('|').split('|')] for line in body.splitlines()[2:]]


class CompanionQuestionsTest(unittest.TestCase):
    def test_every_companion_has_checked_install_and_question_data(self):
        text = (REFS / 'companions.md').read_text()
        installs = table(text, '## Sources and install commands')
        questions = table(text, '## Questions and selection data')
        self.assertEqual({row[0].strip('`') for row in installs}, COMPANIONS)
        self.assertEqual({row[0].strip('`') for row in questions}, COMPANIONS)
        self.assertEqual(len(installs), 5)
        self.assertEqual(len(questions), 5)
        for row in installs:
            self.assertEqual(len(row), 5)
            _, source, pin, command, checked = row
            self.assertIn('https://github.com/', source)
            self.assertIn('MIT', source)
            self.assertTrue(pin.startswith('v') or pin == 'none (no release/tag)')
            self.assertRegex(command, r'`DISABLE_TELEMETRY=1 npx skills@1\.5\.20 add https://github\.com/')
            self.assertIn('--skill ' + row[0].strip('`'), command)
            if pin.startswith('v'):
                self.assertIn('/tree/' + pin, command)
            self.assertRegex(checked, r'^\d{4}-\d{2}-\d{2}$')
        selected = []
        for name, question, condition, note in questions:
            self.assertTrue(question.endswith('?'))
            self.assertTrue(condition)
            self.assertIn('Fallback:', note)
            if name == '`typesafe-ai`':
                self.assertEqual(condition, 'Advanced only; never selected by Quick')
            else:
                self.assertIn(condition, CHOICES[:-1])
                selected.append(condition)
            self.assertGreater(len(note), 40)
        self.assertEqual(set(selected), set(CHOICES[:-1]))
        self.assertTrue(all(len(line) <= 600 for line in text.splitlines()))

    def test_quick_has_exactly_one_selection_and_at_most_four_followups(self):
        procedure = (REFS / 'features/companions.md').read_text()
        quick = procedure.split('## Quick (row 22)', 1)[1].split('## Advanced', 1)[0]
        self.assertEqual(procedure.count('What do you do with this plugin?'), 1)
        self.assertEqual(quick.count('multi-select question'), 1)
        for choice in CHOICES:
            self.assertIn(choice, quick)
        for rule in ('at most four', 'five companion questions', 'none preselected',
                     'setup_features.py decline companions --yes', 'records nothing',
                     '`add companions` always asks again', 'never combine'):
            self.assertIn(rule, procedure)
        skill = (SETUP / 'SKILL.md').read_text()
        self.assertIn('Quick opens `companions` directly', skill)
        self.assertIn('beginner skips companion questions', skill)

    def test_advanced_interviews_before_the_same_neutral_offer(self):
        procedure = (REFS / 'features/companions.md').read_text()
        advanced = procedure.split('## Advanced', 1)[1]
        for rule in ('skips the Quick selection', 'what it does for this user', 'concrete example in their stack',
                     'what it costs or sends', 'fallback', 'then the same offer', 'row 24'):
            self.assertIn(rule, advanced)
        for rule in ('Show me how to install', 'Not now', 'only prints', 'records nothing',
                     'native question tool', 'install everything', 'Install nothing yourself'):
            self.assertIn(rule, procedure)
        contract = (REFS / 'interview.md').read_text()
        for rule in ('none preselected', 'a default, a timeout or an auto-selected option never counts as the yes'):
            self.assertIn(rule, contract)

    def test_no_executable_script_installs_a_companion(self):
        # Inspect code as data; never execute the printed installation commands.
        pattern = r'(?:npx\s+.*skills.*\badd|plugin\s+(?:install|add))\s+.*(?:agybird|vietnamizer|typesafe-ai|diagram-design|markmap)'
        scripts = [*ROOT.joinpath('scripts').rglob('*.py'), *ROOT.joinpath('skills').rglob('scripts/*.py')]
        for path in scripts:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotRegex(node.value, pattern, str(path))
                if isinstance(node, ast.Call):
                    literals = ' '.join(child.value for child in ast.walk(node)
                                        if isinstance(child, ast.Constant) and isinstance(child.value, str))
                    self.assertNotRegex(literals, pattern, str(path))
        for path in [*ROOT.joinpath('scripts').rglob('*.sh'), *ROOT.joinpath('skills').rglob('*.sh')]:
            self.assertNotRegex(path.read_text(), pattern, str(path))
        procedure = (REFS / 'features/companions.md').read_text()
        self.assertIn('Never execute an install command', procedure)


if __name__ == '__main__':
    unittest.main()
