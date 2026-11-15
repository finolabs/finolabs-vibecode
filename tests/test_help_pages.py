"""Every skill has a help page, every help page is linked, and the help routes reach tips and troubleshooting."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELP = ROOT / "skills/help"
PAGES = HELP / "references/skills"
# Typed by the user only: their pages say so.
USER_ONLY = {"help", "ask", "setup", "status", "afk", "brb", "pause", "gtg", "update",
             "restore-point", "session-hygiene"}


def skill_names():
    return sorted(p.name for p in (ROOT / "skills").iterdir()
                  if p.is_dir() and not p.name.startswith("fnl-") and (p / "SKILL.md").is_file())


def linked_pages():
    links = set()
    for path in [HELP / "SKILL.md", *sorted((HELP / "references").glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        links.update(re.findall(r"\]\((?:references/)?skills/([a-z][a-z-]*)\.md\)", text))
    return links


class HelpPagesTest(unittest.TestCase):
    def test_every_skill_folder_has_a_page(self):
        pages = sorted(p.stem for p in PAGES.glob("*.md"))
        self.assertEqual(sorted(set(skill_names()) - set(pages)), [], "skills without a help page")
        self.assertEqual(sorted(set(pages) - set(skill_names())), [], "help pages without a skill folder")

    def test_every_page_is_linked(self):
        pages = {p.stem for p in PAGES.glob("*.md")}
        self.assertEqual(sorted(pages - linked_pages()), [], "help pages nobody links to")

    def test_pages_name_the_commands_and_who_types_them(self):
        for name in skill_names():
            text = (PAGES / f"{name}.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith(f"# {name}\n"), name)
            self.assertIn(f"`/finolabs-vibecode:{name}`", text, name)
            self.assertIn(f"`${name}`", text, name)
            self.assertIn("## Tips", text, name)
            self.assertEqual("Typed by the user only." in text, name in USER_ONLY, name)

    def test_tips_and_troubleshooting_are_routed(self):
        skill = (HELP / "SKILL.md").read_text(encoding="utf-8")
        for page in ("tips.md", "troubleshooting.md"):
            self.assertTrue((HELP / "references" / page).is_file(), page)
            self.assertIn(f"](references/{page})", skill)

    def test_troubleshooting_covers_known_problems(self):
        text = (HELP / "references/troubleshooting.md").read_text(encoding="utf-8")
        for needed in ("WSL", "/hooks", "stale", "FNL_UPDATE_CHECK=off"):
            self.assertIn(needed, text)


if __name__ == "__main__":
    unittest.main()
