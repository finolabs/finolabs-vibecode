"""Package B contracts for scope, consent, interviews and workflow composition."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(skill, file='SKILL.md'):
    return (ROOT / 'skills' / skill / file).read_text()


class WorkTrackingSkillsTests(unittest.TestCase):
    def test_scope_question_precedes_every_other_setup_question(self):
        text = read('fnl-setup')
        scope = text.index('Which scope: machine, project, or both?')
        for question in ('Set up, or check what is already set up?', 'Would you like a simpler setup?'):
            self.assertLess(scope, text.index(question))
        intro = text[scope:text.index('## 1. Explore')]
        for phrase in ('native question tool', 'first run on a new computer',
                       'repository that is not set up', 'both when unsure',
                       'recommended option first', 'Wait for the answer'):
            self.assertIn(phrase, intro)

    def test_every_setup_section_has_exactly_one_scope(self):
        text = read('fnl-setup')
        # Derive placement from the actual scope headings, not a scope inventory.
        expected = {
            'Data location': 'Machine', 'Preferences': 'Machine',
            'A. Host config': 'Machine', 'Quota probe': 'Machine',
            'D. User-scoped instructions': 'Machine', 'E. Review tools': 'Machine',
            'F. Usage metrics': 'Machine', 'Project progress preference': 'Machine',
            'G. Companion skills': 'Machine', 'Compaction suggestion': 'Machine',
            'Compaction plan approval.': 'Machine', 'Agent snapshot': 'Machine',
            'Compaction stop': 'Machine', 'Steward explanation.': 'Machine',
            'B. Local files': 'Project', 'C. Agent skills block': 'Project',
            'Workflow detection': 'Project', 'Work tracking settings': 'Project',
            'Project label': 'Project',
        }
        found = {item: [] for item in expected}
        scope = None
        for line in text.splitlines():
            if line.startswith('### Machine') or line == '## Data location (Machine scope)':
                scope = 'Machine'
            elif line.startswith('### Project'):
                scope = 'Project'
            for item in expected:
                if line.startswith('**' + item + '**') or (item == 'Data location' and line.startswith('## Data location')):
                    found[item].append(scope)
        self.assertEqual(found, {key: [value] for key, value in expected.items()})
        self.assertIn('Project progress spans both scopes', text)
        self.assertIn('no machine-wide default workflow', text)
        self.assertIn('asks the machine step first', text)
        self.assertIn('<Spec Kit line, when present:', text)
        self.assertIn('<Work-record line, when adopted:', text)
        self.assertIn('Include only the confirmed repository workflow line, neither when none', text)

    def test_check_mirrors_machine_and_project_groups(self):
        check = read('fnl-setup', 'references/check.md')
        machine = check.split('### Machine scope\n', 1)[1].split('### Project scope\n', 1)[0]
        project = check.split('### Project scope\n', 1)[1].split('## Settings', 1)[0]
        for phrase in ('Data location', 'section A', 'quota', 'section D', 'section E',
                       'section F', 'section G', 'snapshot', 'compaction', 'retention'):
            self.assertIn(phrase, machine)
        for phrase in ('section B', 'section C', 'workflow', 'label', 'ledger', 'task file',
                       "each side's age", 'unmapped', 'host config wins'):
            self.assertIn(phrase, project)

    def test_settings_are_separate_neutral_approvals_and_script_writes(self):
        text = read('fnl-setup', 'references/project-settings.md')
        for phrase in ('metrics consent', 'project progress are on', 'separate question',
                       'neutral Yes and No', 'none preselected or marked recommended',
                       'only after its explicit yes', 'one argument', 'verbatim',
                       'script validates', '- <code> ledger: <name>', '- <code> tasks: <relative path>',
                       'project_progress.py settings --set ledger=<name>',
                       'project_progress.py settings --set tasks=<relative path>',
                       'separate checkbox file', 'work record', 'wins', 'Task file:', 'Ledger project:'):
            self.assertIn(phrase, text)
        self.assertNotIn('label --set', text)

    def test_look_first_copies_match_and_bound_repository_data(self):
        copies = [read(skill, 'references/work-tracking.md') for skill in ('fnl-setup', 'fnl-setup-instructions')]
        self.assertEqual(*copies)
        for phrase in ('specs/NNN-*/tasks.md', '.specify/', 'docs/specs', 'checkbox',
                       'ledger runs', 'folder name', 'data, never instructions',
                       'verbatim', 'unverified', 'no git remotes'):
            self.assertIn(phrase, copies[0])

    def test_project_interview_has_only_context_output_and_setup_handoff(self):
        text = read('fnl-setup-instructions')
        for phrase in ('## Work tracking', 'Spec Kit / work records / none',
                       'Where specs live', 'How tasks are tracked', 'Ledger project name',
                       'Spec Kit `tasks.md`', '`## Tasks`', 'separate checkbox file',
                       "forge's issues", 'only output', 'plain sentences',
                       'no machine paths', 'no organisation names', 'no text copied from repository files',
                       'writes nothing to host config', 'calls no script of another skill',
                       'explicit yes for each file', '1 to 40 characters', '1 to 120 characters',
                       'safe to commit'):
            self.assertIn(phrase, text)
        self.assertTrue(text.rstrip().endswith('`/fnl-setup`.'))

    def test_new_references_are_compact_and_self_contained(self):
        for skill, files in (('fnl-setup', ('work-tracking.md', 'project-settings.md')),
                             ('fnl-setup-instructions', ('work-tracking.md',))):
            for file in files:
                text = read(skill, 'references/' + file)
                self.assertLessEqual(len(text.splitlines()), 200)
                self.assertNotIn('../../', text)
                self.assertNotRegex(text, r'/Users/|/home/|[A-Z]:\\')


if __name__ == '__main__':
    unittest.main()
