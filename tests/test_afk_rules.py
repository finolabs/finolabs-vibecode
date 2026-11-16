"""afk's generated rule table and the size of its procedure (docs/specs/afk-autonomy.md E, acceptance 8)."""
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_afk import ROOT, AfkBase

RULES = ROOT / 'skills/afk/references/rules.md'
LIMIT = 8704  # 8.5 KB: SKILL.md plus references/lease-rules.md


class RuleTableTest(AfkBase):
    def rules(self):
        afk = self.load()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch.object(afk, 'private_folder', side_effect=AssertionError):
            self.assertEqual(afk.main(['rules']), 0)  # reads no setup, lease or state
        return out.getvalue(), afk

    def test_the_reference_equals_the_generated_table(self):
        output, _ = self.rules()
        self.assertEqual(RULES.read_text(), output, 'run: python3 -I skills/delegate/scripts/afk.py rules > ' + str(RULES.relative_to(ROOT)))

    def test_the_table_is_built_from_the_data_check_reads(self):
        output, afk = self.rules()
        for name in (*afk.CREDENTIAL_COMMANDS, *afk.FLOOR_NAMES, *afk.ENV_EXCEPTIONS, *afk.DEFAULT_NAMES,
                     *afk.CATEGORIES, *afk.HARD, *afk.KINDS, *afk.PROJECT_KEYS):
            with self.subTest(name=name):
                self.assertIn(f'`{name}`', output)
        for row in afk.__doc__.split('| Rule | Enforcer |')[1].split('\n\n')[0].splitlines()[2:]:
            self.assertIn(row, output)

    def test_the_procedure_stays_within_its_size(self):
        size = sum(len((ROOT / 'skills/afk' / name).read_bytes()) for name in ('SKILL.md', 'references/lease-rules.md'))
        self.assertLessEqual(size, LIMIT)

    def test_the_procedure_points_to_the_table(self):
        for name in ('SKILL.md', 'references/lease-rules.md', 'references/decide.md', 'references/merge-gate.md'):
            with self.subTest(name=name):
                self.assertIn('rules.md', (ROOT / 'skills/afk' / name).read_text())
        setup = (ROOT / 'skills/setup/references/features/afk.md').read_text()
        self.assertIn('afk.py rules', setup)
        self.assertLess(setup.index('Open (recommended)'), setup.index('Which AI apps'))


if __name__ == '__main__':
    unittest.main()
