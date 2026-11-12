import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = "through the host's native question tool when the session has one"
YES = "Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes."
QUESTIONS = {
    "setup/SKILL.md": ("A bare run says", "Offer the beginner path"),
    "setup/references/mode.md": ("2. Ask the preferences question",),
    "setup/references/features/metrics.md": ("Let Antigravity record plugin usage for your private dashboard?",),
    "setup/references/features/compaction.md": (
        "Choose when Claude Code or Codex shortens a long conversation to make room?", "Save the shown limit for shortening future conversations?",
        "Set up Antigravity to ask for a fresh session when a saved conversation grows too large?", "Save the shown Antigravity session stop and its size limit?",
    ),
    "setup/references/check.md": ("4. Offer one small smoke task",),
    "setup/references/features/roles.md": ("Who should help check whether task evidence meets a requirement?", "Let your AI provider review your saved instructions during setup checks?"),
    "update/SKILL.md": ("2. If the user only asked",),
    "status/SKILL.md": ("When the argument is `purge`", "Their consent record stays"),
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
                    if path.startswith("setup/"):
                        setup = text("skills/setup/SKILL.md")
                        self.assertIn("references/interview.md", setup)
                        contract = text("skills/setup/references/interview.md")
                        self.assertIn("native question tool", contract)
                    else:
                        contract = content
                        paragraph = content.split(start, 1)[1].split("\n", 1)[0]
                        self.assertIn(NATIVE, paragraph)
                    self.assertIn("Ask in text", contract)
                    self.assertIn("tool is refused or fails", contract)
                    self.assertIn("free text", contract)
                    self.assertIn("advisory", contract)

    def test_advanced_or_quick_choice_uses_the_native_form(self):
        content = text("skills", "setup", "SKILL.md")
        choice = content.split("Otherwise **Advanced**", 1)[1].split("## Menu", 1)[0]
        self.assertIn("**Quick**", choice)
        self.assertIn("native question tool", content)
        self.assertIn("references/interview.md", content)

    def test_approvals_are_neutral(self):
        for path, starts in QUESTIONS.items():
            for start in starts:
                with self.subTest(path=path, question=start):
                    content = text("skills", path)
                    self.assertIn(start, content)
                    if path.startswith("setup/"):
                        contract = text("skills/setup/references/interview.md")
                        self.assertIn("neutral Yes and No choices with none preselected or marked recommended", contract)
                        self.assertIn("a default, a timeout or an auto-selected option never counts as the yes", contract)
                    else:
                        paragraph = content.split(start, 1)[1].split("\n", 1)[0]
                        self.assertIn(YES, paragraph)


if __name__ == "__main__":
    unittest.main()
