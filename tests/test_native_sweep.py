import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = "through the host's native question tool when the session has one"
YES = "Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes."
QUESTIONS = {
    "fnl-setup/SKILL.md": (
        "On a bare invocation", "Before the mode choice", "**Beginner path.**",
        "**Preferences**", "**Compaction suggestion**",
    ),
    "fnl-setup/references/check.md": ("4. Offer one small smoke task",),
    "fnl-setup/references/route-judge.md": ("Ask", "Ask a second, separate question"),
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
                    paragraph = content.split(start, 1)[1].split("\n", 1)[0]
                    self.assertIn(NATIVE, paragraph)
            if path.endswith("route-judge.md"):
                continue  # loaded by fnl-setup/SKILL.md, which states the fallback
            with self.subTest(path=path, rule="fallback"):
                self.assertIn("Ask in text", content)
                self.assertIn("tool is refused or fails", content)
                self.assertIn("free text", content)
                self.assertIn("advisory", content)

    def test_detailed_or_quick_choice_uses_the_native_form(self):
        content = text("skills", "fnl-setup", "SKILL.md")
        choice = content.split("Otherwise let the user choose the mode", 1)[1].split("**detailed**", 1)[0]
        self.assertIn(NATIVE, choice)

    def test_approvals_are_neutral(self):
        for path, start in (
            ("fnl-setup/SKILL.md", "**Beginner path.**"),
            ("fnl-setup/SKILL.md", "**Preferences**"),
            ("fnl-setup/SKILL.md", "Antigravity records the same events as Codex"),
            ("fnl-setup/references/check.md", "4. Offer one small smoke task"),
            ("fnl-setup/references/route-judge.md", "Ask"),
            ("fnl-setup/references/route-judge.md", "Ask a second, separate question"),
            ("fnl-setup/SKILL.md", "**Compaction suggestion**"),
            ("fnl-update/SKILL.md", "2. If the user only asked"),
            ("fnl-status/SKILL.md", "When the argument is `purge`"),
            ("fnl-status/SKILL.md", "Their consent record stays"),
        ):
            with self.subTest(path=path, question=start):
                paragraph = text("skills", path).split(start, 1)[1].split("\n", 1)[0]
                self.assertIn(YES, paragraph)


if __name__ == "__main__":
    unittest.main()
