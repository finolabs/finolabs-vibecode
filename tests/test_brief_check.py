"""Rule and line diagnostics never echo a brief match."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import brief_check


class BriefCheckTest(unittest.TestCase):
    def brief(self):
        return '\n'.join('## ' + name + '\n' + (brief_check.ENV_RULE if name == 'Constraints' else 'none')
                         for name in brief_check.HEADINGS)

    def test_missing_heading_and_rule_refuse(self):
        self.assertEqual(brief_check.lint(self.brief()), [])
        self.assertIn(('rule_1_heading', 1), brief_check.lint(self.brief().replace('## Task', 'Task')))
        self.assertIn('rule_1_environment', [e[0] for e in brief_check.lint(self.brief().replace('never print', 'print'))])

    def test_repeated_private_markers_lint_in_bounded_time(self):
        from tests.scan_timing import timed_scan
        marker = '-----' + 'BEGIN '
        text = self.brief() + '\n' + (marker * (1024 * 1024 // len(marker) + 1))[:1024 * 1024]
        errors = timed_scan(self, lambda: bool(brief_check.lint(text)))
        self.assertFalse(errors, 'unexpected lint findings; content suppressed')

    def test_template_and_constraint_extension(self):
        text = (ROOT / 'skills/fnl-handoff/references/brief-template.md').read_text().split('```\n', 1)[1].split('\n```', 1)[0]
        self.assertEqual(brief_check.lint(text), [])
        self.assertIn('never read env or credential files; ' + brief_check.ENV_RULE, text)

    def test_secret_diagnostic_contains_only_rule_and_line(self):
        planted = 'sk' + '-' + 'fixture' * 4
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'brief.md'
            text = self.brief() + '\n' + planted
            path.write_text(text)
            output = io.StringIO()
            with mock.patch.object(sys, 'argv', ['brief_check.py', str(path)]), contextlib.redirect_stdout(output):
                self.assertEqual(brief_check.main(), 1)
            self.assertEqual(output.getvalue(), f'rule_4_secret line={len(text.splitlines())}\n')


if __name__ == '__main__':
    unittest.main()
