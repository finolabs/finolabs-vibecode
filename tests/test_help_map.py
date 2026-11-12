"""The help map lists every shipped script and setup feature, so it cannot drift from the folders."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "skills/help/references/map.md"


class HelpMapTest(unittest.TestCase):
    def setUp(self):
        self.text = MAP.read_text(encoding="utf-8")

    def test_every_script_name_is_listed_with_an_existing_path(self):
        scripts = sorted(list((ROOT / "scripts").iterdir()) + list((ROOT / "skills").glob("*/scripts/*")))
        names = {path.name for path in scripts if path.is_file() and not path.name.startswith(".")}
        listed = re.findall(r"^\| `((?:scripts|skills/[a-z][a-z-]*/scripts)/([^`/]+))` \|", self.text, re.M)
        for path, _ in listed:
            self.assertTrue((ROOT / path).is_file(), f"map lists {path}, which does not exist")
        listed_names = [name for _, name in listed]
        self.assertEqual(sorted(set(listed_names)), sorted(listed_names), "a script name is listed twice")
        self.assertEqual(sorted(names - set(listed_names)), [], "scripts missing from the map")

    def test_every_setup_feature_is_listed(self):
        features = sorted(p.stem for p in (ROOT / "skills/setup/references/features").glob("*.md"))
        missing = [f for f in features if f"`/setup add {f}`" not in self.text]
        self.assertEqual(missing, [], "setup features missing from the map")

    def test_a_route_answers_which_agent_takes_which_work(self):
        rows = [line for line in self.text.splitlines() if line.startswith("| Which agent takes which work")]
        self.assertEqual(len(rows), 1)
        for needed in ("route_pick.py", "/setup add roles"):
            self.assertIn(needed, rows[0])

    def test_new_skills_are_in_the_skill_table(self):
        for name in ("help", "ask", "pause", "gtg", "afk", "clarify"):
            self.assertRegex(self.text, rf"(?m)^\| `{name}` \|")


if __name__ == "__main__":
    unittest.main()
