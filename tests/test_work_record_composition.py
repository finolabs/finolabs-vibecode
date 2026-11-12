"""The workflow adapters compose the work record without a new trigger."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(skill, file):
    return (ROOT / 'skills' / skill / file).read_text()


class WorkRecordCompositionTests(unittest.TestCase):
    def test_record_composes_under_existing_trigger(self):
        text = read('coding-router', 'references/workflows/none.md')
        self.assertIn('references/work-record.md', text)
        self.assertIn('MIN depth never creates one', text)
        self.assertIn('no new trigger', text)
        steps = re.findall(r'^([1-6])\. (.+)$', text, re.M)
        self.assertEqual(len(steps), 6)
        for (number, body), section in zip(steps, ('Goal and acceptance', 'Plan', 'Tasks', 'Tasks', 'Evidence', 'Evidence')):
            self.assertIn(section, body, number)
        self.assertIn('no work record', read('coding-router', 'references/workflows/speckit.md'))
        pack = read('coding-router', 'references/workflows/mattpocock.md')
        for phrase in ('work record', 'Goal and acceptance', 'Plan', 'Tasks', 'Evidence', 'issue tracker'):
            self.assertIn(phrase, pack)


if __name__ == '__main__':
    unittest.main()
