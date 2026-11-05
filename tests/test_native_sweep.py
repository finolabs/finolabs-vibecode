import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = "through the host's native question tool when the session has one"
YES = "neutral Yes and No choices"


def text(*parts):
    return ROOT.joinpath(*parts).read_text()


class NativeSweepTest(unittest.TestCase):
    def test_remaining_questions_use_the_native_form(self):
        for path in (("skills", "fnl-setup", "SKILL.md"), ("skills", "fnl-setup", "references", "check.md"),
                     ("skills", "fnl-status", "SKILL.md"), ("skills", "fnl-update", "SKILL.md")):
            self.assertIn(NATIVE, text(*path), path)

    def test_approvals_are_neutral(self):
        for path in (("skills", "fnl-setup", "SKILL.md"), ("skills", "fnl-status", "SKILL.md"),
                     ("skills", "fnl-update", "SKILL.md")):
            self.assertIn(YES, text(*path), path)


if __name__ == "__main__":
    unittest.main()
