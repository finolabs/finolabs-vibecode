"""Tests for scripts/check-references.py: a clean tree passes, each planted break is caught."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = "scripts/check-references.py"

# (file, text to replace, replacement, expected message fragment)
BREAKS = [
    ("scripts/mode.py", '"suggest"', '"manual"', "mode.py copies differ"),
    ("skills/fnl-setup/scripts/mode.py", '"suggest"', '"manual"', "mode.py copies differ"),
    ("skills/fnl-status/SKILL.md", '"Budget and liveness"', '"Budget and live"',
     '`fnl-delegate` has no section "Budget and live"'),
    ("skills/fnl-delegate/SKILL.md", "`fnl-handoff`: write", "`fnl-handof`: write",
     "unknown skill or agent `fnl-handof`"),
    ("skills/fnl-delegate/references/host-template.md", '"When an agent coordinates"', '"When coordinating"',
     '`agents.md` has no section "When coordinating"'),
    ("skills/fnl-session-hygiene/SKILL.md", "(references/titles.md)", "(references/title.md)",
     "link target references/title.md does not exist"),
    ("skills/fnl-delegate/references/ledger.md", "--rework-rounds 1", "--rework 1",
     "ledger.py has no option --rework"),
    ("skills/fnl-delegate/references/ledger.md", "--reason fallback-quota", "--reason fallback-quotas",
     "--reason fallback-quotas is not one of"),
    ("skills/fnl-delegate/references/ledger.md", "--reason fallback-quota", "--reason FALLBACK",
     "--reason FALLBACK is not one of"),
    ("skills/fnl-delegate/references/dispatch.md", "## Heavy-job lock", "## Heavy job lock",
     '`references/dispatch.md` has no section "Heavy-job lock"'),
    ("skills/fnl-delegate/references/ledger.md", 'python3 -I "$L" open', 'python3 -I "$L" opn',
     "ledger.py has no subcommand opn"),
    ("skills/fnl-delegate/references/ledger.md", 'python3 -I "$L" open', 'python3 -I "$L" open --outcome accepted',
     "ledger.py open takes no option --outcome"),
    ("skills/fnl-delegate/references/ledger.md", "--model gpt-6.1-sol", "--model gpt-6.1-sol --rework-rounds 1",
     "ledger.py start takes no option --rework-rounds"),
    ("skills/fnl-status/SKILL.md", "`python3 -I <ledger.py> open`", "`python3 -I <ledger.py> opn`",
     "ledger.py has no subcommand opn"),
    ("skills/fnl-advisor/SKILL.md", "`--kind advise`", "`--kind advice`",
     "--kind advice is not one of"),
    ("skills/fnl-delegate/references/route-judgment.md", "`--route-by table`", "`--route-by tables`",
     "--route-by tables is not one of"),
    ("skills/fnl-delegate/references/host-template.md", "--max-turns <n>", "--max-turnz <n>",
     "--max-turnz is not described in agents.md"),
    ("agents/fnl-verifier.md", '`fnl-verification` ("Accepting someone else\'s work")', '`fnl-verification` ("No such heading")',
     '`fnl-verification` has no section "No such heading"'),
    ("skills/fnl-status/SKILL.md", '`fnl-delegate` "Ledger"', "`fnl-delegate`'s \"Nope\"",
     '`fnl-delegate` has no section "Nope"'),
    ("skills/fnl-delegate/references/ledger.md", 'python3 -I "$L" open', "python3 -I $L open --outcom accepted",
     "ledger.py has no option --outcom"),
    ("skills/fnl-delegate/references/models.md", "Review by 2026-12-01.", "Review by 01/12/2026.",
     "needs a line"),
]

FENCED_HEADING = ("skills/fnl-status/SKILL.md", '`fnl-delegate` "Ledger"', '`fnl-handoff` "Budget"',
                  '`fnl-handoff` has no section "Budget"')


# A prose line that names the script in one span and a subcommand in another.
TWO_SPANS = ("skills/fnl-delegate/references/ledger.md", "Record every dispatch with `scripts/ledger.py`",
             "Record every dispatch with `scripts/ledger.py` (`ledger.py summary` reports it)")


class CheckReferencesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        for name in ["skills", "agents", "rules", "scripts", "docs"]:
            if (ROOT / name).exists():
                shutil.copytree(ROOT / name, self.root / name)
        for path in ROOT.iterdir():
            if path.is_file() and (path.suffix == ".md" or path.name == "LICENSE"):
                shutil.copy(path, self.root / path.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True, capture_output=True)

    def tearDown(self):
        self.dir.cleanup()

    def check(self):
        return subprocess.run([sys.executable, "-I", str(self.root / CHECKER), str(self.root)],
                              capture_output=True, text=True)

    def test_clean_tree_passes(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_script_path_beside_a_subcommand_span_passes(self):
        rel, old, new = TWO_SPANS
        path = self.root / rel
        path.write_text(path.read_text().replace(old, new, 1))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_skill_lists_match_folders(self):
        for relative in ("README.md", "skills/fnl-ask/references/map.md"):
            path = self.root / relative
            original = path.read_text()
            for replacement, expected in (("", "skill folder fnl-advisor missing from skill list"),
                                          ("| `fnl-missing` | Missing. |", "listed skill fnl-missing has no folder")):
                with self.subTest(file=relative, replacement=replacement):
                    row = next(line for line in original.splitlines() if line.startswith("| `fnl-advisor` |"))
                    path.write_text(original.replace(row, replacement, 1))
                    try:
                        result = self.check()
                    finally:
                        path.write_text(original)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn(expected, result.stdout)

    def test_retired_names_fail_outside_released_sections_and_mapping(self):
        for suffix in ("committee", "coordinator-sessions", "knowledge"):
            for relative in ("scripts/session_start.py", "skills/fnl-advisor/SKILL.md", "CHANGELOG.md"):
                with self.subTest(name=suffix, file=relative):
                    path = self.root / relative
                    original = path.read_text()
                    line = "\nRetired: fnl-" + suffix + "\n"
                    path.write_text(original.replace("## [Unreleased]", "## [Unreleased]" + line, 1)
                                    if relative == "CHANGELOG.md" else original + line)
                    try:
                        result = self.check()
                    finally:
                        path.write_text(original)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn("retired skill name fnl-" + suffix, result.stdout)

    def test_retired_names_pass_in_dated_releases_only(self):
        path = self.root / "CHANGELOG.md"
        original = path.read_text()
        for date, expected in ((" - 2026-11-01", 0), ("", 1)):
            with self.subTest(date=date):
                path.write_text(original + "\n## [0.1.4]" + date
                                + "\n\nRetired: `fnl-" + "committee`\n")
                result = self.check()
                self.assertEqual(result.returncode, expected, result.stdout)

    def test_retired_name_mapping_passes_in_unreleased(self):
        path = self.root / "CHANGELOG.md"
        text = path.read_text()
        path.write_text(text.replace("### Changed", "### Changed\n\n- `fnl-" + "committee` → `fnl-advisor`", 1))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_untracked_retired_names_do_not_fail(self):
        for ignored in (False, True):
            with self.subTest(ignored=ignored):
                if ignored:
                    (self.root / ".gitignore").write_text("local-context.md\n")
                (self.root / "local-context.md").write_text("`fnl-" + "committee`\n")
                result = self.check()
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_each_break_is_caught(self):
        for rel, old, new, message in BREAKS + [FENCED_HEADING]:
            with self.subTest(file=rel, message=message):
                path = self.root / rel
                original = path.read_text()
                self.assertIn(old, original, "the planted break no longer matches the file")
                path.write_text(original.replace(old, new, 1))
                try:
                    result = self.check()
                finally:
                    path.write_text(original)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stdout)


if __name__ == "__main__":
    unittest.main()
