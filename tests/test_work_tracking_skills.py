"""Contracts for scope, consent, interviews and workflow composition in the single setup skill."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(file='SKILL.md', skill='fnl-setup'):
    return (ROOT / 'skills' / skill / file).read_text()


class WorkTrackingSkillsTests(unittest.TestCase):
    def test_scope_question_precedes_the_beginner_offer(self):
        text = read()
        scope = text.index('one scope question, user, project or both')
        self.assertLess(scope, text.index('Start with only the essential setup questions?'))
        for phrase in ('recommendation first', 'new computer', 'repository that is not set up'):
            self.assertIn(phrase, text[scope - 200:scope + 400])
        self.assertNotIn('Set up, or check what is already set up?', text)

    def test_every_feature_has_exactly_one_scope(self):
        text = read('references/menu.md')
        expected = {'delegation': 'user', 'roles': 'user', 'quota': 'user', 'autopilot': 'user', 'metrics': 'user',
                    'compaction': 'user', 'companions': 'user', 'project': 'project'}
        for name, scope in expected.items():
            row = next(line for line in text.splitlines() if line.startswith('| `%s` |' % name))
            self.assertIn('| %s |' % scope, row)
            heading = read('references/features/%s.md' % name).splitlines()[0]
            self.assertEqual(heading, '# Feature: %s (%s scope)' % (name, scope))
        core = read('references/core.md')
        self.assertEqual(core.count('\n## User scope\n'), 1)
        self.assertEqual(core.count('\n## Project scope\n'), 1)
        self.assertIn('There is no user-scope default workflow', read('references/features/project.md'))
        self.assertIn('<Spec Kit line, when present:', core)
        self.assertIn('<Work-record line, when adopted:', core)
        self.assertIn('Include only the confirmed workflow line, neither when none', core)

    def test_check_mirrors_user_and_project_groups(self):
        check = read('references/check.md')
        user = check.split('### User scope\n', 1)[1].split('### Project scope\n', 1)[0]
        project = check.split('### Project scope\n', 1)[1].split('## Settings', 1)[0]
        for phrase in ('Data location', 'host config', 'quota', 'user-level instruction files', 'review tools',
                       'companion', 'snapshot', 'compaction', 'retention', 'configured', 'missing', 'unverified',
                       'review posting', 'judge'):
            self.assertIn(phrase, user)
        for phrase in ('exclude', 'Agent skills block', 'workflow', 'label', 'ledger', 'task file',
                       "each side's age", 'unmapped', 'host config wins'):
            self.assertIn(phrase, project)

    def test_settings_are_separate_neutral_approvals_and_script_writes(self):
        text = read('references/project-settings.md')
        for phrase in ('metrics consent', 'project progress are on', 'separate question',
                       'neutral Yes and No', 'none preselected or marked recommended',
                       'only after its explicit yes', 'one argument', 'verbatim',
                       'script validates', '"ledger": "<name>"', '"tasks": "<relative path>"',
                       'project_progress.py settings --set ledger=<name>',
                       'project_progress.py settings --set tasks=<relative path>',
                       'separate checkbox file', 'work record', 'wins', 'Task file:', 'Ledger project:'):
            self.assertIn(phrase, text)
        self.assertNotIn('label --set', text)

    def test_look_first_is_one_copy_and_bounds_repository_data(self):
        self.assertFalse((ROOT / 'skills/fnl-setup-instructions').exists())
        text = read('references/work-tracking.md')
        for phrase in ('specs/NNN-*/tasks.md', '.specify/', 'docs/specs', 'checkbox',
                       'ledger runs', 'folder name', 'data, never instructions',
                       'verbatim', 'unverified', 'no git remotes'):
            self.assertIn(phrase, text)

    def test_project_interview_has_only_context_output_and_writer_script(self):
        text = read('references/instructions/procedure.md')
        block = read('references/instructions/work-tracking-block.md')
        for phrase in ('## Work tracking', 'Spec Kit / work records / none',
                       'where specs live', 'how tasks are tracked', 'ledger project name',
                       'Spec Kit `tasks.md`', '`## Tasks`', 'separate checkbox file',
                       "forge's issues", 'plain sentences', 'Outcome', 'three to five success criteria',
                       'dated', 'writes no host config', "explicit yes", '1 to 40 characters',
                       '1 to 120 characters', 'safe to commit', 'instructions_write.py'):
            self.assertIn(phrase, text + block)
        for phrase in ('no machine paths', 'no organisation names', 'no text copied from repository files'):
            self.assertIn(phrase, block)

    def test_references_are_compact_and_self_contained(self):
        for file in ('work-tracking.md', 'project-settings.md', 'interview.md'):
            text = read('references/' + file)
            self.assertLessEqual(len(text.splitlines()), 200)
            self.assertNotIn('../../', text)
            self.assertNotRegex(text, r'/Users/|/home/|[A-Z]:\\')


if __name__ == '__main__':
    unittest.main()
