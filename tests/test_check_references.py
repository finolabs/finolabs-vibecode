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
    ("skills/fnl-delegate/references/dispatch.md", "--reason fallback-quota", "--reason fallback-quotas",
     "--reason fallback-quotas is not one of"),
    ("skills/fnl-delegate/references/host-template.md", "--max-turns <n>", "--max-turnz <n>",
     "--max-turnz is not described in agents.md"),
]


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

    def tearDown(self):
        self.dir.cleanup()

    def check(self):
        return subprocess.run([sys.executable, "-I", str(self.root / CHECKER), str(self.root)],
                              capture_output=True, text=True)

    def test_clean_tree_passes(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_each_break_is_caught(self):
        for rel, old, new, message in BREAKS:
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
