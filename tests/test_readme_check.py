"""readme_check.py: the script items of plugin-packaging references/readme.md."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/plugin-packaging/scripts/readme_check.py"
spec = importlib.util.spec_from_file_location("readme_check", SCRIPT)
readme_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readme_check)

DESCRIPTION = "2 skills and 1 agent for demo work."
README = """<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/icon-dark.svg">
    <img src="assets/icon.svg" alt="Demo icon: a square" width="88">
  </picture>
</p>

<h1 align="center">demo-plugin</h1>

<p align="center"><strong>Demo things.</strong><br>
Demo skills for Claude Code and Codex. Nothing is enforced.</p>

<p align="center">
  <a href="https://github.com/example-org/demo-plugin/releases/latest"><img src="https://img.shields.io/github/v/release/example-org/demo-plugin" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/example-org/demo-plugin" alt="License: MIT"></a>
  <a href="https://github.com/example-org/demo-plugin/actions/workflows/ci.yml"><img src="https://github.com/example-org/demo-plugin/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="#claude-code"><img src="https://img.shields.io/badge/Claude%20Code-plugin-1F6FEB" alt="Claude Code plugin"></a>
  <a href="#codex"><img src="https://img.shields.io/badge/Codex-plugin-1F6FEB" alt="Codex plugin"></a>
</p>

## What you get

- **Demo.** It demos. (`alpha`)

## Install at a glance

```text
/plugin marketplace add example-org/demo-plugin
/plugin install demo-plugin@demo-plugin
```

## Start here (you)

1. Ask your assistant to install it.

## For AI agents: install and set up

1. Find your host. Done when it is listed.

## Skills

The plugin has 2 skills.

| Skill | Use it when |
| --- | --- |
| `alpha` | Alpha work. |
| `beta` | Beta work. |

### Agents

| Agent | Use it when |
| --- | --- |
| `demo-reviewer` | Reviews. |

## Supported platforms

macOS and Linux.

## Install

### Claude Code

```bash
claude plugin marketplace add example-org/demo-plugin
```

### Codex

```bash
codex plugin add demo-plugin@demo-plugin
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [the skills](#skills).

## License

MIT. See [LICENSE](LICENSE).
"""


def manifest(folder):
    return {"name": "demo-plugin", "version": "0.1.0", "description": DESCRIPTION,
            "repository": "https://github.com/example-org/demo-plugin", "license": "MIT"}


class ReadmeCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        files = {
            "README.md": README,
            "LICENSE": "MIT License\n\nCopyright (c) 2026 Example\n",
            "CONTRIBUTING.md": "# Contributing\n",
            "assets/icon.svg": "<svg/>", "assets/icon-dark.svg": "<svg/>",
            ".github/workflows/ci.yml": "name: CI\n",
            "skills/alpha/SKILL.md": "---\nname: alpha\n---\n",
            "skills/beta/SKILL.md": "---\nname: beta\n---\n",
            "agents/demo-reviewer.md": "---\nname: demo-reviewer\n---\n",
            ".claude-plugin/plugin.json": json.dumps(manifest(".claude-plugin")),
            ".codex-plugin/plugin.json": json.dumps(manifest(".codex-plugin")),
            ".claude-plugin/marketplace.json": json.dumps(
                {"name": "demo-plugin", "plugins": [{"name": "demo-plugin", "description": DESCRIPTION}]}),
        }
        for name, text in files.items():
            self.write(name, text)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def edit(self, old, new):
        text = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.write("README.md", text.replace(old, new, 1))

    def run_check(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = readme_check.main(["readme_check.py", str(self.root)])
        return code, out.getvalue().splitlines()

    def fails(self, item):
        code, lines = self.run_check()
        found = [line for line in lines if line.startswith(f"FAIL {item} ")]
        self.assertEqual(code, 1, lines)
        self.assertTrue(found, lines)
        return found

    def test_a_conforming_readme_passes_every_item(self):
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)
        self.assertEqual([l for l in lines if l.startswith("FAIL")], [])
        self.assertEqual(len([l for l in lines if l.startswith("PASS")]), len(readme_check.ITEMS))
        self.assertIn("EXTERNAL https://github.com/example-org/demo-plugin/releases/latest", lines)

    def test_missing_and_misordered_sections(self):
        self.edit("## Start here (you)", "## Begin")
        self.assertIn("FAIL S1 missing section: start-here", self.fails("S1"))
        self.setUp()
        self.edit("## Contributing", "## Privacy\n\nNone.\n\n## Contributing")
        self.edit("## What you get", "## License\n\nMIT, see [LICENSE](LICENSE).\n\n## What you get")
        self.assertTrue(any("out of order" in l for l in self.fails("S1")))

    def test_privacy_is_required_once_privacy_md_exists(self):
        self.write("PRIVACY.md", "# Privacy\n")
        self.assertIn("FAIL S1 missing section: privacy", self.fails("S1"))

    def test_title_must_name_the_plugin(self):
        self.edit('<h1 align="center">demo-plugin</h1>', '<h1 align="center">Something</h1>')
        self.fails("S2")

    def test_badges_name_the_repository_and_existing_workflows(self):
        self.edit("github/license/example-org/demo-plugin", "github/license/other/demo-plugin")
        self.assertTrue(any("other/demo-plugin" in l for l in self.fails("B2")))
        self.setUp()
        self.write(".github/workflows/ci.yml", "")
        (self.root / ".github/workflows/ci.yml").unlink()
        self.fails("B2")

    def test_badge_anchor_and_alt(self):
        self.edit('href="#codex"', 'href="#nowhere"')
        self.fails("B1")

    def test_host_badges_match_manifests_and_house_colour(self):
        (self.root / ".codex-plugin/plugin.json").unlink()
        self.assertTrue(any("Codex, which has no manifest" in l for l in self.fails("B3")))
        self.setUp()
        self.write(".github/readme-standard.json", json.dumps({"badge_color": "7FE2CE"}))
        self.fails("B3")

    def test_counts_match_shipped_folders(self):
        self.write("skills/gamma/SKILL.md", "---\nname: gamma\n---\n")
        self.assertTrue(any("2 skills; 3 ship" in l for l in self.fails("C1")))
        self.assertIn("FAIL C2 skill gamma has no table row", self.fails("C2"))

    def test_excluded_aliases_are_not_counted(self):
        self.write("skills/old-alpha/SKILL.md", "---\nname: old-alpha\n---\n")
        self.write(".github/readme-standard.json", json.dumps({"exclude_skills": ["old-*"]}))
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_a_table_row_that_does_not_ship(self):
        self.edit("| `beta` | Beta work. |", "| `beta` | Beta work. |\n| `ghost` | Gone. |")
        self.assertIn("FAIL C2 skills table lists ghost, which does not ship", self.fails("C2"))

    def test_command_rows_may_carry_the_plugin_prefix(self):
        self.write("commands/run.md", "# run\n")
        self.edit("## Supported platforms", "### Commands\n\n| Command | Use it when |\n| --- | --- |\n| `/demo-plugin:run` | Run. |\n\n## Supported platforms")
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_every_host_has_an_install_subsection(self):
        self.edit("### Codex\n", "### Other\n")
        self.assertIn("FAIL H1 Install has no subsection for Codex", self.fails("H1"))

    def test_install_commands_name_this_plugin_and_its_catalogs(self):
        self.edit("codex plugin add demo-plugin@demo-plugin", "codex plugin add other@demo-plugin")
        self.fails("H2")
        self.setUp()
        self.edit("claude plugin marketplace add example-org/demo-plugin", "claude plugin marketplace add example-org/plugins")
        self.fails("H2")
        self.write(".github/readme-standard.json", json.dumps({"catalog": {"repository": "example-org/plugins"}}))
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_descriptions_agree(self):
        self.write(".claude-plugin/marketplace.json", json.dumps(
            {"name": "demo-plugin", "plugins": [{"name": "demo-plugin", "description": "Other words."}]}))
        self.fails("D1")

    def test_license_agrees_with_the_license_file(self):
        self.write("LICENSE", "Apache License\nVersion 2.0, January 2004\n")
        self.assertTrue(any("LICENSE is Apache-2.0" in l for l in self.fails("L1")))

    def test_images_need_alt_text_and_files(self):
        self.edit('alt="Demo icon: a square"', 'alt=""')
        self.fails("I1")
        self.setUp()
        (self.root / "assets/icon-dark.svg").unlink()
        self.assertIn("FAIL I1 missing file: assets/icon-dark.svg", self.fails("I1"))

    def test_light_dark_pairs_use_two_files_and_responsive_pictures_pass(self):
        self.edit('srcset="assets/icon-dark.svg"', 'srcset="assets/icon.svg"')
        self.fails("I2")
        self.setUp()
        self.edit("## Supported platforms", '<picture>\n  <source media="(max-width: 600px)" srcset="assets/icon.svg">\n  <img src="assets/icon-dark.svg" alt="Small">\n</picture>\n\n## Supported platforms')
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_links_resolve_to_files_and_anchors(self):
        self.edit("[the skills](#skills)", "[the skills](#nothing)")
        self.fails("K1")
        self.setUp()
        (self.root / "CONTRIBUTING.md").unlink()
        self.fails("K1")

    def test_placeholders_outside_code(self):
        self.edit("- **Demo.** It demos.", "- **Demo.** TODO write this.")
        self.fails("P1")
        self.setUp()
        self.edit("- **Demo.** It demos.", "- **Demo.** It demos `TODO` items.")
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_translated_headings_through_the_override(self):
        self.edit("## What you get", "## Bạn nhận được gì")
        self.fails("S1")
        self.write(".github/readme-standard.json", json.dumps({"sections": {"what-you-get": "Bạn nhận được gì"}}))
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_a_repository_without_manifests_skips_the_plugin_items(self):
        for folder in (".claude-plugin", ".codex-plugin"):
            for path in (self.root / folder).iterdir():
                path.unlink()
        code, lines = self.run_check()
        self.assertIn("N/A C1 no plugin manifest", lines)
        self.assertEqual(code, 0, lines)

    def bad_input(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = readme_check.main(["readme_check.py", str(self.root)])
        self.assertEqual(code, 2, err.getvalue())
        return err.getvalue()

    def test_malformed_overrides_are_bad_input_naming_the_key(self):
        for config, key in (({"sections": ["x"]}, "sections"),
                            ({"sections": {"install": "Install("}}, "sections.install"),
                            ({"sections": {"nowhere": "X"}}, "sections.nowhere"),
                            ({"exclude_skills": None}, "exclude_skills"),
                            ({"exclude_skills": [1]}, "exclude_skills"),
                            ({"catalog": "example-org/plugins"}, "catalog"),
                            ({"badge_color": 7}, "badge_color")):
            with self.subTest(config=config):
                self.write(".github/readme-standard.json", json.dumps(config))
                self.assertIn(key, self.bad_input())
        self.write(".github/readme-standard.json", "not json")
        self.bad_input()

    def test_a_manifest_with_a_null_interface_is_read(self):
        data = manifest(".codex-plugin")
        data["interface"] = None
        self.write(".codex-plugin/plugin.json", json.dumps(data))
        (self.root / ".claude-plugin/plugin.json").unlink()
        code, lines = self.run_check()
        self.assertIn(code, (0, 1), lines)

    def test_a_repository_without_manifests_needs_only_header_what_you_get_and_install(self):
        for folder in (".claude-plugin", ".codex-plugin"):
            for path in (self.root / folder).iterdir():
                path.unlink()
        self.write("README.md", "<h1>demo-plugin</h1>\n\n## What you get\n\nThings.\n\n## Install\n\nCopy it.\n")
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)
        self.write("README.md", "<h1>demo-plugin</h1>\n\n## Install\n\nCopy it.\n\n## What you get\n\nThings.\n")
        self.fails("S1")

    def test_other_license_file_names(self):
        (self.root / "LICENSE").unlink()
        self.write("LICENSE.md", "MIT License\n")
        self.edit("MIT. See [LICENSE](LICENSE).", "MIT. See [LICENSE.md](LICENSE.md).")
        self.edit('<a href="LICENSE">', '<a href="LICENSE.md">')
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_root_relative_links_and_encoded_anchors(self):
        self.write("docs/guide.md", "# Guide\n\n## Bắt đầu\n")
        self.edit("[the skills](#skills)", "[the guide](/docs/guide.md#b%E1%BA%AFt-%C4%91%E1%BA%A7u) and <a href=\"docs/guide.md#nope\">x</a>")
        found = self.fails("K1")
        self.assertEqual(found, ["FAIL K1 missing anchor: docs/guide.md#nope"])

    def test_an_unreadable_linked_document_fails_only_that_link(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/latin.md").write_bytes(b"# \xe9t\xe9\n")
        (self.root / "docs/dir.md").mkdir()
        self.edit("[the skills](#skills)", "[a](docs/latin.md#x) [b](docs/dir.md#y)")
        self.assertEqual(len(self.fails("K1")), 2)

    def test_links_in_angle_brackets_may_hold_spaces(self):
        self.write("docs/my guide.md", "# Guide\n")
        self.edit("[the skills](#skills)", "[the guide](<docs/my guide.md>)")
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)
        self.edit("[the guide](<docs/my guide.md>)", "[the guide](<docs/no guide.md>)")
        self.fails("K1")

    def test_html_comments_are_not_scanned(self):
        self.edit("## Supported platforms", "<!--\nTODO later\n<img src=\"gone.png\">\n-->\n\n## Supported platforms")
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_one_row_may_name_several_skills(self):
        self.edit("| `alpha` | Alpha work. |\n| `beta` | Beta work. |", "| `alpha`, `beta` | Both. |")
        code, lines = self.run_check()
        self.assertEqual(code, 0, lines)

    def test_missing_readme_is_bad_input(self):
        (self.root / "README.md").unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(readme_check.main(["readme_check.py", str(self.root)]), 2)

    def test_the_script_has_no_network_or_process_access(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for name in ("socket", "urllib.request", "http.client", "subprocess", "os.system"):
            self.assertNotIn(name, source)


if __name__ == "__main__":
    unittest.main()
