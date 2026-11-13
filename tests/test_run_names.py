import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FORMAT = "<runner>: <project> <scope> <activity>"


def read(*parts):
    return (ROOT.joinpath(*parts)).read_text()


class RunNamesTest(unittest.TestCase):
    def test_titles_defines_the_run_name_and_its_enforcer(self):
        text = " ".join(read("skills", "tidy", "SKILL.md").split())
        self.assertIn("**Background runs and agents.**", text)
        self.assertIn(FORMAT, text)
        self.assertIn("The enforcer is agent judgment", text)
        self.assertIn("never copied from an issue or pull request title", text)

    def test_dispatching_skills_point_to_it(self):
        for skill in ("delegate", "handoff", "review-gate"):
            text = read("skills", skill, "SKILL.md")
            self.assertIn('`tidy` "Titles"', text, skill)

    def test_titles_start_with_one_emoji_from_the_fixed_set(self):
        skill = (ROOT / "skills/tidy/SKILL.md").read_text()
        table = (ROOT / "skills/tidy/references/titles.md").read_text()
        self.assertIn("`<emoji> <project> <scope>: <activity>`", skill)
        emojis = [line.split("|")[1].strip() for line in table.split("## Emoji", 1)[1].splitlines()
                  if line.startswith("| ") and not line.startswith(("| Emoji", "| ---"))]
        self.assertEqual(len(emojis), len(set(emojis)))
        self.assertEqual(len(emojis), 25)
        for example in ("`🐛 billing-api: fix webhook retries`", "`🔍 docs-site: review PR 12`"):
            self.assertIn(example, skill)
            self.assertIn(example[1], emojis)
        self.assertIn("a slug is ASCII only", table)


if __name__ == "__main__":
    unittest.main()
