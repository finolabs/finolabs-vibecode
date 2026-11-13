"""Keep user questions in the user's language, including reference-only asks."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RULE = (
    "Talk to the user in the language they are using, including questions and "
    "option labels; keep command names, flags, file paths, skill names and other "
    "technical names unchanged."
)
ADVISORY = "**Advisory (agent judgment):** " + RULE
# These skills ask or offer choices without mentioning the native question tool.
OTHER_ASKING_SKILLS = {
    "advisor", "commit-messages", "handoff", "plugin-packaging",
    "tidy", "checks", "versioning",
}


class UserLanguageTests(unittest.TestCase):
    def test_asking_skills_state_the_advisory_rule_once(self):
        for skill in sorted((ROOT / "skills").iterdir()):
            if not (skill / "SKILL.md").is_file():
                continue
            content = (skill / "SKILL.md").read_text()
            content += "\n" + "\n".join(
                path.read_text() for path in sorted((skill / "references").rglob("*.md"))
            )
            if "native question tool" in content or skill.name in OTHER_ASKING_SKILLS:
                with self.subTest(skill=skill.name):
                    self.assertIn(ADVISORY, content)
                    self.assertEqual(content.count(RULE), 1)

    def test_plain_language_copies_match_and_use_the_users_language(self):
        paths = [ROOT / "skills" / name / "references" / "plain-language.md"
                 for name in ("help", "setup")]
        self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
        self.assertIn("beginner register in the user's language", paths[0].read_text())
        ci = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
        pair = ", ".join('"' + path.relative_to(ROOT).as_posix() + '"' for path in paths)
        self.assertIn("[" + pair + "]", ci)


if __name__ == "__main__":
    unittest.main()
