"""Read-only upgrade-note checks over synthetic host configs; nothing is written or run."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'skills/setup/scripts'))
spec = importlib.util.spec_from_file_location('upgrade_state', ROOT / 'skills/setup/scripts/upgrade_state.py')
us = importlib.util.module_from_spec(spec)
spec.loader.exec_module(us)


class UpgradeStateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.home = account(self, self.base / 'home')
        self.host = self.home / '.finolabs/vibecode/host.md'
        self.host.parent.mkdir(parents=True)

    def state(self, name, text=None):
        if text is not None:
            self.host.write_text(text)
        before = self.host.read_bytes() if self.host.exists() else None
        code = us.main([name])
        self.assertEqual(self.host.read_bytes() if self.host.exists() else None, before)
        return code

    def test_legacy_sections_and_lines_are_open_until_deleted(self):
        cases = {'no-checks-section': '## Checks\n- repo: x\n',
                 'no-project-settings': '## Project settings\n- repo: parallel=4\n',
                 'no-project-labels': '## Project labels\n- repo: Demo\n',
                 'no-global-lines': '## Project progress\n- Project progress: on\n- Ledger project: demo\n',
                 'no-parallel-lines': '## Limits\n- Parallel dispatches: at most 6 at one time.\n'}
        for name, text in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.state(name, '## Routing\non\n' + text), us.OPEN)
                self.assertEqual(self.state(name, '## Routing\non\n## Limits\n- Machine role: laptop\n'), us.DONE)
        # A fenced example is not a section, and Task file: alone counts as a global line.
        self.assertEqual(self.state('no-checks-section', '```\n## Checks\n```\n'), us.DONE)
        self.assertEqual(self.state('no-global-lines', 'Task file: tasks.md\n'), us.OPEN)

    def test_missing_host_config_has_nothing_left_over(self):
        self.assertFalse(self.host.exists())
        self.assertEqual(self.state('no-checks-section'), us.DONE)
        self.assertEqual(self.state('matrix'), us.NOT_APPLICABLE)
        self.assertEqual(self.state('levels'), us.OPEN)

    def test_matrix_levels_and_afk(self):
        self.assertEqual(self.state('matrix', '## Agent roles\n- code review: codex\n'), us.OPEN)
        self.assertEqual(self.state('matrix', '## Assignment matrix\n## Agent levels\n'), us.OPEN)
        self.assertEqual(self.state('matrix', '## Assignment matrix\n- Judge: host\n'), us.DONE)
        self.assertEqual(self.state('matrix', '## Routing\non\n'), us.NOT_APPLICABLE)
        self.assertEqual(self.state('levels', '## Agent levels\n'), us.DONE)
        self.assertEqual(self.state('levels', '## Assignment matrix\n'), us.DONE)
        self.assertEqual(self.state('levels', '## Routing\n'), us.OPEN)
        self.assertEqual(self.state('afk', '## afk\n- Merge: no\n'), us.DONE)
        self.assertEqual(self.state('afk', '## Routing\n'), us.OPEN)
        self.assertEqual(self.state('afk-decisions', '## afk\n- Merge: no\n'), us.OPEN)
        self.assertEqual(self.state('afk-decisions', '## afk\n- Excerpts leave the machine: no\n'), us.DONE)
        self.assertEqual(self.state('afk-decisions', '## Routing\n- Excerpts leave the machine: no\n'), us.OPEN)
        # The old heading is no longer read, so it satisfies neither state.
        self.assertEqual(self.state('afk', '## Autopilot\n- Merge: no\n'), us.OPEN)
        self.assertEqual(self.state('afk-decisions', '## Autopilot\n- Excerpts leave the machine: no\n'), us.OPEN)

    def test_afk_section_is_open_until_the_old_heading_is_gone(self):
        self.assertEqual(self.state('afk-section', '## Autopilot\n- Merge: no\n'), us.OPEN)
        self.assertEqual(self.state('afk-section', '## Autopilot\n- Merge: no\n\n## afk\n- Merge: no\n'), us.OPEN)
        self.assertEqual(self.state('afk-section', '## Routing\non\n## afk\n- Merge: no\n'), us.DONE)
        # Never set up: nothing to move. A fenced example is not a section.
        self.assertEqual(self.state('afk-section', '## Routing\non\n'), us.NOT_APPLICABLE)
        self.assertEqual(self.state('afk-section', '## afk\n- Merge: no\n```\n## Autopilot\n```\n'), us.DONE)

    def test_several_states_combine(self):
        self.host.write_text('## Project settings\n')
        self.assertEqual(us.main(['no-project-settings', 'no-global-lines']), us.OPEN)
        self.host.write_text('Task file: x\n')
        self.assertEqual(us.main(['no-project-settings', 'no-global-lines']), us.OPEN)
        self.host.write_text('## Routing\n')
        self.assertEqual(us.main(['no-project-settings', 'no-global-lines']), us.DONE)
        self.assertEqual(us.main(['matrix', 'no-checks-section']), us.DONE)
        self.assertEqual(us.main(['matrix', 'matrix']), us.NOT_APPLICABLE)
        self.assertEqual(us.main(['matrix', 'other']), us.UNKNOWN)

    def test_unknown_input_and_unreadable_config_are_unknown(self):
        for argv in ([], ['other'], ['matrix', 'x'], ['matrix'] * 9):
            with self.subTest(argv=argv):
                self.assertEqual(us.main(argv), us.UNKNOWN)
        self.host.write_bytes(b'\xff\xfe')
        self.assertEqual(us.main(['no-checks-section']), us.UNKNOWN)
        with mock.patch.object(us.dr, 'consent_root', return_value=None):
            self.assertEqual(us.main(['matrix']), us.UNKNOWN)

    def test_legacy_names_are_fixed_strings(self):
        text = ('## Checks\n## Project settings\n## Project labels\n- Ledger project: secret-name\n'
                '## Limits\n- Parallel per family: claude=2\n')
        self.assertEqual(us.legacy(text), ['## Checks', '## Project settings', '## Project labels',
                                           'Ledger project:/Task file: lines', 'Parallel lines in ## Limits'])
        self.assertEqual(us.legacy('## Limits\n- Machine role: laptop\n'), [])

    def test_repository_checks_follow_the_approved_list_of_the_current_repository(self):
        outside = self.base / 'plain'
        outside.mkdir()
        with mock.patch.object(os, 'getcwd', return_value=str(outside)):
            self.assertEqual(us.main(['repo-checks']), us.NOT_APPLICABLE)
        repo = self.base / 'repo'
        (repo / '.git').mkdir(parents=True)
        import checks_list
        with mock.patch.object(os, 'getcwd', return_value=str(repo)):
            with mock.patch.object(checks_list, 'checks_for', return_value=([], 'no entry')):
                self.assertEqual(us.main(['repo-checks']), us.OPEN)
            with mock.patch.object(checks_list, 'checks_for', return_value=([('test', ['make', 'test'])], None)):
                self.assertEqual(us.main(['repo-checks']), us.DONE)


if __name__ == '__main__':
    unittest.main()
