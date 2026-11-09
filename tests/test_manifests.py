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
            self.assertIn(prefix + "fnl-setup scan", json.dumps(doc))
            self.assertIn(prefix + "fnl-setup mode", json.dumps(doc))

    def test_skill_counts_are_computed_from_the_folders(self):
        # The one place a skill count is checked: the manifests' descriptions and README state it,
        # every other text names no number, so adding a skill folder changes only those files.
        skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
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

    def test_agents_match_the_folders(self):
        agents = {p.stem for p in (ROOT / "agents").glob("fnl-*.md")}
        self.assertEqual(agents, {"fnl-reviewer", "fnl-security-reviewer", "fnl-navigator"})
        readme = (ROOT / "README.md").read_text()
        ask = (ROOT / "skills/fnl-help/references/map.md").read_text()
        display = (ROOT / "agents/openai.yaml").read_text()
        for doc in self.docs:
            self.assertIn("skills and 3 agents", doc["description"])
        for agent in agents:
            for public_text in (readme, ask, display, *(doc["description"] for doc in self.docs)):
                self.assertIn(agent, public_text)

    def test_afk_is_a_user_only_thin_alias(self):
        path = ROOT / "skills/fnl-afk/SKILL.md"
        _, frontmatter, body = path.read_text().split("---", 2)
        fields = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
        self.assertEqual(fields["name"], path.parent.name)
        self.assertEqual(fields["disable-model-invocation"], "true")
        self.assertEqual(fields["argument-hint"], '"[start|stop]"')
        brb_body = (ROOT / "skills/fnl-brb/SKILL.md").read_text().split("---", 2)[2]
        self.assertEqual(body.replace("# Away from keyboard", "# Be right back"), brb_body)

    def test_gtg_is_a_user_only_thin_alias_of_pause(self):
        main = ROOT / "skills/fnl-pause/SKILL.md"
        alias = ROOT / "skills/fnl-gtg/SKILL.md"
        fields = {}
        for path in (main, alias):
            _, frontmatter, body = path.read_text().split("---", 2)
            fields[path.parent.name] = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
            self.assertEqual(fields[path.parent.name]["name"], path.parent.name)
            self.assertEqual(fields[path.parent.name]["disable-model-invocation"], "true")
        self.assertEqual(fields["fnl-pause"]["argument-hint"], fields["fnl-gtg"]["argument-hint"])
        self.assertLess(len(main.read_text().splitlines()), 70)
        self.assertIn("Dependency: `fnl-pause`", alias.read_text())

    def test_ask_is_a_user_only_thin_alias_of_help(self):
        main = ROOT / "skills/fnl-help/SKILL.md"
        alias = ROOT / "skills/fnl-ask/SKILL.md"
        fields = {}
        for path in (main, alias):
            _, frontmatter, _ = path.read_text().split("---", 2)
            fields[path.parent.name] = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
            self.assertEqual(fields[path.parent.name]["name"], path.parent.name)
            self.assertEqual(fields[path.parent.name]["disable-model-invocation"], "true")
        body = alias.read_text().split("---", 2)[2]
        self.assertIn("Dependency: `fnl-help`", body)
        self.assertIn("This alias holds no rules of its own.", body)
        self.assertFalse((alias.parent / "references").exists())
        self.assertIn("answers questions about this plugin", fields["fnl-help"]["description"])
        self.assertNotIn("fnl-ask", (ROOT / "README.md").read_text().split("## Skills", 1)[0])

    def test_new_alias_and_pause_descriptions_are_valid_yaml_scalars(self):
        # A plain YAML scalar cannot contain ": "; the unquoted descriptions that already ship are older.
        for name in ("fnl-afk", "fnl-gtg", "fnl-pause", "fnl-help", "fnl-ask"):
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
