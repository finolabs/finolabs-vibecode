"""The three host manifests agree, and the plugin description meets the catalog standard."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = [ROOT / d / "plugin.json" for d in (".claude-plugin", ".codex-plugin", ".antigravity-plugin")]


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.docs = [json.loads(p.read_text()) for p in MANIFESTS]

    def test_name_version_and_description_match_across_hosts(self):
        for key in ("name", "version", "description"):
            self.assertEqual(len({d[key] for d in self.docs}), 1, key)

    def test_starter_text_uses_current_setup_commands(self):
        for path, doc in zip(MANIFESTS, self.docs):
            text = json.dumps(doc)
            for suffix in ("setup-instructions", "scan-agents", "set-mode"):
                self.assertNotIn("fnl-" + suffix, text, str(path))
        for prefix, doc in zip(("$", "/"), self.docs[1:]):
            self.assertIn(prefix + "setup scan", json.dumps(doc))
            self.assertIn(prefix + "setup mode", json.dumps(doc))

    def test_skill_counts_are_computed_from_the_folders(self):
        # The one place a skill count is checked: the manifests' descriptions and README state it,
        # every other text names no number, so adding a skill folder changes only those files.
        # The fnl- folders are the older names of the renamed skills (thin aliases) and are counted apart.
        every = sorted((ROOT / "skills").glob("*/SKILL.md"))
        skills = [path for path in every if not path.parent.name.startswith("fnl-")]
        aliases = len(every) - len(skills)
        user_only = sum(1 for path in skills
                        if "\ndisable-model-invocation: true\n" in path.read_text().split("---", 2)[1])
        total, model = len(skills), len(skills) - user_only
        for path, doc in zip(MANIFESTS, self.docs):
            found = re.findall(r"\b(\d+) skills\b", doc["description"])
            self.assertEqual(found, [str(total)], str(path))
        readme = (ROOT / "README.md").read_text()
        self.assertEqual(re.findall(r"\b(\d+) skill folders\b", readme), [str(total)])
        self.assertIn(f"**{total} skill folders**: {model} model-invoked skills and {user_only} marked user-only",
                      readme)
        self.assertEqual(re.findall(r"\b(\d+) alias folders\b", readme), [str(aliases)])

    def test_every_older_fnl_name_is_a_user_only_thin_alias(self):
        skills = sorted(p.parent for p in (ROOT / "skills").glob("*/SKILL.md") if not p.parent.name.startswith("fnl-"))
        aliases = sorted(p.parent.name for p in (ROOT / "skills").glob("fnl-*/SKILL.md"))
        self.assertEqual(aliases, ["fnl-" + p.name for p in skills])
        for skill in skills:
            alias = ROOT / "skills" / ("fnl-" + skill.name)
            _, frontmatter, body = (alias / "SKILL.md").read_text().split("---", 2)
            fields = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
            target = dict(line.split(": ", 1) for line in
                          (skill / "SKILL.md").read_text().split("---", 2)[1].strip().splitlines() if ": " in line)
            self.assertEqual(fields["name"], alias.name)
            self.assertEqual(fields["disable-model-invocation"], "true")
            self.assertEqual(fields.get("argument-hint"), target.get("argument-hint"), alias.name)
            self.assertIn(f"Dependency: `{skill.name}`. Load and follow it with the same arguments", body)
            self.assertIn("This alias holds no rules of its own.", body)
            self.assertEqual(sorted(p.name for p in alias.iterdir()), ["SKILL.md"])

    def test_agents_match_the_folders(self):
        agents = {p.stem for p in (ROOT / "agents").glob("fnl-*.md")}
        self.assertEqual(agents, {"fnl-reviewer", "fnl-security-reviewer", "fnl-navigator"})
        readme = (ROOT / "README.md").read_text()
        ask = (ROOT / "skills/help/references/map.md").read_text()
        display = (ROOT / "agents/openai.yaml").read_text()
        for doc in self.docs:
            self.assertIn("skills and 3 agents", doc["description"])
        for agent in agents:
            for public_text in (readme, ask, display, *(doc["description"] for doc in self.docs)):
                self.assertIn(agent, public_text)

    def test_afk_is_a_user_only_thin_alias(self):
        path = ROOT / "skills/afk/SKILL.md"
        _, frontmatter, body = path.read_text().split("---", 2)
        fields = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
        self.assertEqual(fields["name"], path.parent.name)
        self.assertEqual(fields["disable-model-invocation"], "true")
        self.assertEqual(fields["argument-hint"], '"[start|stop]"')
        brb_body = (ROOT / "skills/brb/SKILL.md").read_text().split("---", 2)[2]
        self.assertEqual(body.replace("# Away from keyboard", "# Be right back"), brb_body)

    def test_gtg_is_a_user_only_thin_alias_of_pause(self):
        main = ROOT / "skills/pause/SKILL.md"
        alias = ROOT / "skills/gtg/SKILL.md"
        fields = {}
        for path in (main, alias):
            _, frontmatter, body = path.read_text().split("---", 2)
            fields[path.parent.name] = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
            self.assertEqual(fields[path.parent.name]["name"], path.parent.name)
            self.assertEqual(fields[path.parent.name]["disable-model-invocation"], "true")
        self.assertEqual(fields["pause"]["argument-hint"], fields["gtg"]["argument-hint"])
        self.assertLess(len(main.read_text().splitlines()), 70)
        self.assertIn("Dependency: `pause`", alias.read_text())

    def test_ask_is_a_user_only_thin_alias_of_help(self):
        main = ROOT / "skills/help/SKILL.md"
        alias = ROOT / "skills/ask/SKILL.md"
        fields = {}
        for path in (main, alias):
            _, frontmatter, _ = path.read_text().split("---", 2)
            fields[path.parent.name] = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
            self.assertEqual(fields[path.parent.name]["name"], path.parent.name)
            self.assertEqual(fields[path.parent.name]["disable-model-invocation"], "true")
        body = alias.read_text().split("---", 2)[2]
        self.assertIn("Dependency: `help`", body)
        self.assertIn("This alias holds no rules of its own.", body)
        self.assertFalse((alias.parent / "references").exists())
        self.assertIn("answers questions about this plugin", fields["help"]["description"])
        intro = (ROOT / "README.md").read_text().split("## Skills", 1)[0]
        for spelled in ("`ask`", "/ask", "$ask"):
            self.assertNotIn(spelled, intro)

    def test_verification_is_a_user_only_thin_alias_of_checks(self):
        alias = ROOT / "skills/verification/SKILL.md"
        _, frontmatter, body = alias.read_text().split("---", 2)
        fields = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
        self.assertEqual((fields["name"], fields["disable-model-invocation"]), ("verification", "true"))
        self.assertIn("Dependency: `checks`", body)
        self.assertIn("This alias holds no rules of its own.", body)
        self.assertEqual(sorted(p.name for p in alias.parent.iterdir()), ["SKILL.md"])
        main = (ROOT / "skills/checks/SKILL.md").read_text().split("---", 2)[1]
        self.assertIn("name: checks", main)
        self.assertNotIn("disable-model-invocation", main)

    def test_new_alias_and_pause_descriptions_are_valid_yaml_scalars(self):
        # A plain YAML scalar cannot contain ": "; the unquoted descriptions that already ship are older.
        older = [p.parent.name for p in (ROOT / "skills").glob("fnl-*/SKILL.md")]
        for name in ("afk", "gtg", "pause", "help", "ask", *older):
            text = (ROOT / "skills" / name / "SKILL.md").read_text()
            line = next(l for l in text.split("---", 2)[1].splitlines() if l.startswith("description: "))
            value = line[len("description: "):]
            if not (value.startswith('"') and value.endswith('"')):
                self.assertNotIn(": ", value, name)

    def test_description_length_fits_the_catalog_standard(self):
        # The shared catalog (finolabs/plugins) lists 120-160 characters and repeats them exactly.
        n = len(self.docs[0]["description"])
        self.assertTrue(120 <= n <= 160, n)


if __name__ == "__main__":
    unittest.main()
