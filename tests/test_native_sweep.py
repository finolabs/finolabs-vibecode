import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = "through the host's native question tool when the session has one"
YES = "Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes."
QUESTIONS = {
    "fnl-setup/SKILL.md": ("A bare run says", "Offer the beginner path"),
    "fnl-setup/references/mode.md": ("2. Ask the preferences question",),
    "fnl-setup/references/features/metrics.md": ("Write the Antigravity metrics hook?",),
    "fnl-setup/references/features/compaction.md": (
        "Would you like help setting a native compaction threshold?", "Apply this compaction plan?",
        "Would you like a local hook", "Apply this compaction stop preview?",
    ),
    "fnl-setup/references/check.md": ("4. Offer one small smoke task",),
    "fnl-setup/references/features/roles.md": ("Which judge", "May Check send lines"),
    "fnl-update/SKILL.md": ("2. If the user only asked",),
    "fnl-status/SKILL.md": ("When the argument is `purge`", "Their consent record stays"),
}


def text(*parts):
    return ROOT.joinpath(*parts).read_text()


class NativeSweepTest(unittest.TestCase):
    def test_remaining_questions_use_the_native_form(self):
        for path, starts in QUESTIONS.items():
            content = text("skills", path)
            for start in starts:
                with self.subTest(path=path, question=start):
                    self.assertIn(start, content)
                    if path.startswith("fnl-setup/"):
                        setup = text("skills/fnl-setup/SKILL.md")
                        self.assertIn("references/interview.md", setup)
                        contract = text("skills/fnl-setup/references/interview.md")
                        self.assertIn("native question tool", contract)
                    else:
                        contract = content
                        paragraph = content.split(start, 1)[1].split("\n", 1)[0]
                        self.assertIn(NATIVE, paragraph)
                    self.assertIn("Ask in text", contract)
                    self.assertIn("tool is refused or fails", contract)
                    self.assertIn("free text", contract)
                    self.assertIn("advisory", contract)

    def test_detailed_or_quick_choice_uses_the_native_form(self):
        content = text("skills", "fnl-setup", "SKILL.md")
        choice = content.split("Otherwise **detailed**", 1)[1].split("## Menu", 1)[0]
        self.assertIn("**quick**", choice)
        self.assertIn("native question tool", content)
        self.assertIn("references/interview.md", content)

    def test_approvals_are_neutral(self):
        for path, starts in QUESTIONS.items():
            for start in starts:
                with self.subTest(path=path, question=start):
                    content = text("skills", path)
                    self.assertIn(start, content)
                    if path.startswith("fnl-setup/"):
                        contract = text("skills/fnl-setup/references/interview.md")
                        self.assertIn("neutral Yes and No choices with none preselected or marked recommended", contract)
                        self.assertIn("a default, a timeout or an auto-selected option never counts as the yes", contract)
                    else:
                        paragraph = content.split(start, 1)[1].split("\n", 1)[0]
                        self.assertIn(YES, paragraph)


if __name__ == "__main__":
    unittest.main()
