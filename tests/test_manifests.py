"""The three host manifests agree, and the plugin description meets the catalog standard."""
import json
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

    def test_release_surface_counts_and_agents_match_the_folders(self):
        skills = list((ROOT / "skills").glob("*/SKILL.md"))
        agents = {p.stem for p in (ROOT / "agents").glob("fnl-*.md")}
        self.assertEqual(len(skills), 17)
        self.assertEqual(agents, {"fnl-reviewer", "fnl-security-reviewer", "fnl-navigator"})
        readme = (ROOT / "README.md").read_text()
        ask = (ROOT / "skills/fnl-ask/references/map.md").read_text()
        display = (ROOT / "agents/openai.yaml").read_text()
        for doc in self.docs:
            self.assertIn("17 skills and 3 agents", doc["description"])
        for agent in agents:
            for public_text in (readme, ask, display, *(doc["description"] for doc in self.docs)):
                self.assertIn(agent, public_text)

    def test_description_length_fits_the_catalog_standard(self):
        # The shared catalog (finolabs/plugins) lists 120-160 characters and repeats them exactly.
        n = len(self.docs[0]["description"])
        self.assertTrue(120 <= n <= 160, n)


if __name__ == "__main__":
    unittest.main()
