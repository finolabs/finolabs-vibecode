import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FORMAT = "<runner>: <project> <scope> <activity>"


def read(*parts):
    return (ROOT.joinpath(*parts)).read_text()


class RunNamesTest(unittest.TestCase):
    def test_titles_defines_the_run_name_and_its_enforcer(self):
        text = " ".join(read("skills", "fnl-session-hygiene", "SKILL.md").split())
        self.assertIn("**Background runs and agents.**", text)
        self.assertIn(FORMAT, text)
        self.assertIn("The enforcer is agent judgment", text)
        self.assertIn("never copied from an issue or pull request title", text)

    def test_dispatching_skills_point_to_it(self):
        for skill in ("fnl-delegate", "fnl-handoff", "fnl-review-gate"):
            text = read("skills", skill, "SKILL.md")
            self.assertIn('`fnl-session-hygiene` "Titles"', text, skill)


if __name__ == "__main__":
    unittest.main()
