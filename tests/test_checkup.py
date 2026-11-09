"""Bounded, read-only evidence for setup Check mode, using only fake host data."""

import datetime
import io
import importlib.util
import json
import os
import struct
import hashlib
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from tests.data_root_fixture import account
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/fnl-setup/scripts/checkup.py"
spec = importlib.util.spec_from_file_location("checkup", SCRIPT)
checkup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkup)


class CheckupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # macOS's temporary directory may itself have symlinked ancestors.
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / "home"
        self.repo = self.base / "repo"
        self.bin = self.base / "bin"
        for path in (self.home, self.repo, self.bin):
            path.mkdir()
        account(self, self.home)
        self.env = {"HOME": str(self.home), "PATH": str(self.bin)}
        self.write(self.repo / ".git/info/exclude", ".finolabs/\n")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def tree(self):
        return {str(p.relative_to(self.base)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
                os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
                for p in self.base.rglob("*")}

    def run_check(self, *args):
        before = self.tree()
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=self.repo,
                                env=self.env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(before, self.tree(), "Check must not change the fixture tree")
        return result.stdout

    def data(self):
        return json.loads(self.run_check("--json"))

    def setup_item(self, name):
        return next(row for row in self.data()["setup"] if row["check"] == name)

    def install_claude(self):
        self.write(self.bin / "claude", "#!/bin/sh\nexit 91\n").chmod(0o755)
        root = self.home / ".claude/plugins/cache/example/finolabs-vibecode/1.0.0"
        self.write(root / ".claude-plugin/plugin.json", json.dumps({
            "name": "finolabs-vibecode", "version": "1.0.0",
            "hooks": "./.claude-plugin/hooks.json"}))
        self.write(root / ".claude-plugin/hooks.json", json.dumps({"hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "never run"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "never run"}]}]}}))
        self.write(self.home / ".claude/plugins/installed_plugins.json", json.dumps({
            "plugins": {"finolabs-vibecode@example": [{"installPath": str(root)}]}}))
        return root

    def folder_marketplace(self, claude_home, version):
        """A directory marketplace: Claude loads the plugin in place, the registry keeps a stale snapshot."""
        live = self.base / "live-checkout"
        self.write(live / ".claude-plugin/plugin.json", json.dumps({
            "name": "finolabs-vibecode", "version": version}))
        self.write(claude_home / "plugins/known_marketplaces.json", json.dumps({
            "example": {"source": {"source": "directory", "path": str(live)},
                        "installLocation": str(live)}}))
        return live

    def plugin_row(self, host="claude"):
        return next(r for r in self.data()["hosts"][host] if r["check"] == "plugin")

    def test_folder_marketplace_that_disagrees_with_the_registry_stays_unverified(self):
        self.install_claude()
        self.folder_marketplace(self.home / ".claude", "2.0.0-dev")
        row = self.plugin_row()
        self.assertEqual(row["status"], "unverified")
        self.assertIn("folder marketplace declares version 2.0.0-dev", row["reason"])
        self.assertIn("registry records 1.0.0", row["reason"])
        hooks = next(r for r in self.data()["hosts"]["claude"] if r["check"] == "hooks")
        self.assertIn("no explicit hook file", hooks["reason"])

    def test_hooks_row_names_the_folder_source_when_the_folder_declares_hooks(self):
        self.install_claude()
        live = self.folder_marketplace(self.home / ".claude", "2.0.0")
        self.write(live / ".claude-plugin/plugin.json", json.dumps({
            "name": "finolabs-vibecode", "version": "2.0.0", "hooks": "./.claude-plugin/hooks.json"}))
        self.write(live / ".claude-plugin/hooks.json", json.dumps({"hooks": {
            "SessionStart": [{"hooks": []}], "Stop": [{"hooks": []}]}}))
        hooks = next(r for r in self.data()["hosts"]["claude"] if r["check"] == "hooks")
        self.assertIn("folder hook file", hooks["reason"])

    def test_folder_marketplace_with_matching_registry_version_adds_no_registry_note(self):
        self.install_claude()
        self.folder_marketplace(self.home / ".claude", "1.0.0")
        self.assertNotIn("registry records", self.plugin_row()["reason"])

    def test_folder_marketplace_with_unreadable_manifest_stays_unverified_not_missing(self):
        self.install_claude()
        live = self.folder_marketplace(self.home / ".claude", "2.0.0")
        (live / ".claude-plugin/plugin.json").write_text("not json")
        row = self.plugin_row()
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["reason"], "install recorded; version 1.0.0")

    def test_folder_marketplace_symlinked_manifest_is_unverified(self):
        self.install_claude()
        live = self.folder_marketplace(self.home / ".claude", "2.0.0")
        manifest = live / ".claude-plugin/plugin.json"
        target = self.base / "linked-manifest.json"
        manifest.rename(target)
        manifest.symlink_to(target)
        self.assertEqual(checkup.read_json(manifest), ("unverified", {}))
        self.assertIsNone(checkup.folder_install(self.home / ".claude/plugins", ["example"]))

    def test_claude_config_dir_selects_the_home_the_session_uses(self):
        other = self.home / ".claude-elsewhere"
        root = other / "plugins/cache/example/finolabs-vibecode/3.0.0"
        self.write(root / ".claude-plugin/plugin.json", json.dumps({
            "name": "finolabs-vibecode", "version": "3.0.0"}))
        self.write(other / "plugins/installed_plugins.json", json.dumps({
            "plugins": {"finolabs-vibecode@example": [{"installPath": str(root)}]}}))
        self.write(self.bin / "claude", "#!/bin/sh\nexit 91\n").chmod(0o755)
        self.env["CLAUDE_CONFIG_DIR"] = str(other)
        self.assertIn("version 3.0.0", self.plugin_row()["reason"])
        self.env["CLAUDE_CONFIG_DIR"] = "relative/path"
        self.assertNotIn("version 3.0.0", self.plugin_row()["reason"])

    def test_other_claude_homes_are_listed_by_folder_name_with_recorded_version(self):
        for name, version in ((".claude-work", "0.5.0"), (".claude-omni", None)):
            home = self.home / name
            if version:
                root = home / "plugins/cache/example/finolabs-vibecode" / version
                self.write(root / ".claude-plugin/plugin.json", json.dumps({
                    "name": "finolabs-vibecode", "version": version}))
                self.write(home / "plugins/installed_plugins.json", json.dumps({
                    "plugins": {"finolabs-vibecode@example": [{"installPath": str(root)}]}}))
            else:
                (home / "plugins").mkdir(parents=True)
        row = self.setup_item("other claude homes")
        self.assertIn(".claude-work: version 0.5.0", row["reason"])
        self.assertIn(".claude-omni: no install record", row["reason"])
        self.assertNotIn(str(self.home), row["reason"])

    def test_other_claude_homes_are_found_among_hundreds_of_home_entries(self):
        for number in range(150):
            (self.home / f"d{number:03}").mkdir()
        root = self.home / ".claude-work/plugins/cache/example/finolabs-vibecode/0.5.0"
        self.write(root / ".claude-plugin/plugin.json", json.dumps({
            "name": "finolabs-vibecode", "version": "0.5.0"}))
        self.write(self.home / ".claude-work/plugins/installed_plugins.json", json.dumps({
            "plugins": {"finolabs-vibecode@example": [{"installPath": str(root)}]}}))
        self.assertIn(".claude-work: version 0.5.0", self.setup_item("other claude homes")["reason"])

    def test_sibling_folders_without_plugins_and_symlinks_are_not_listed(self):
        (self.home / ".claude-science").mkdir()
        (self.home / ".claude-real/plugins").mkdir(parents=True)
        (self.home / ".claude-link").symlink_to(self.home / ".claude-real")
        row = self.setup_item("other claude homes")
        self.assertIn(".claude-real: no install record", row["reason"])
        self.assertNotIn("science", row["reason"])
        self.assertNotIn("link", row["reason"])

    def test_default_home_is_listed_when_the_selected_home_is_elsewhere(self):
        self.install_claude()
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        self.env["CLAUDE_CONFIG_DIR"] = str(elsewhere)
        self.assertIn(".claude: version 1.0.0", self.setup_item("other claude homes")["reason"])

    def test_claude_config_dir_also_selects_the_instruction_file(self):
        other = self.home / ".claude-elsewhere"
        self.write(other / "CLAUDE.md", "Use fnl-coding-router first.\n")
        self.env["CLAUDE_CONFIG_DIR"] = str(other)
        row = next(r for r in self.data()["hosts"]["claude"] if r["check"] == "instructions")
        self.assertEqual(row["status"], "ok")

    def test_other_claude_homes_row_absent_without_any_extra_home(self):
        self.assertFalse(any(r["check"] == "other claude homes" for r in self.data()["setup"]))

    def test_plugin_enablement_states_are_home_labels_and_inert_facts_only(self):
        for name, plugins in ((".claude", {"finolabs-vibecode@one": True}),
                              (".claude-work", {"finolabs-vibecode@another": False}),
                              (".claude-other", {"finolabs-vibecode-extra@one": True})):
            (self.home / name / "plugins").mkdir(parents=True)
            self.write(self.home / name / "settings.json", json.dumps({
                "enabledPlugins": {**plugins, "PRIVATE-other@market": True},
                "PRIVATE-setting": "PRIVATE-project-path"}))
        for args in ((), ("--json",)):
            output = self.run_check(*args)
            self.assertNotIn("PRIVATE", output)
        row = self.setup_item("claude plugin enablement")
        self.assertEqual(row, {"check": "claude plugin enablement", "status": "ok",
                              "reason": ".claude: enabled; .claude-other: absent; .claude-work: disabled"})

    def test_plugin_enablement_missing_invalid_or_unsafe_settings_are_unverified(self):
        path = self.home / ".claude/settings.json"
        self.assertEqual(self.setup_item("claude plugin enablement")["reason"], ".claude: unverified")
        for text in ("PRIVATE malformed", "[]", '{"enabledPlugins": []}',
                     '{"enabledPlugins": {"finolabs-vibecode@one": "PRIVATE"}}',
                     '{"enabledPlugins": {"finolabs-vibecode@one": 1}}',
                     '{"enabledPlugins": {"finolabs-vibecode@one": true, "finolabs-vibecode@two": false}}'):
            with self.subTest(text=text):
                self.write(path, text)
                row = self.setup_item("claude plugin enablement")
                self.assertEqual(row["status"], "unverified")
                self.assertEqual(row["reason"], ".claude: unverified")
        path.unlink()
        path.symlink_to(self.write(self.base / "outside-settings.json", "PRIVATE"))
        self.assertEqual(self.setup_item("claude plugin enablement")["reason"], ".claude: unverified")

    def test_plugin_enablement_absent_key_and_unreadable_file(self):
        path = self.write(self.home / ".claude/settings.json", "{}")
        self.assertEqual(self.setup_item("claude plugin enablement")["reason"], ".claude: absent")
        original = checkup.open_safe
        def denied(target, directory=False):
            if Path(target) == path:
                raise PermissionError("synthetic denial")
            return original(target, directory=directory)
        with mock.patch.object(checkup, "open_safe", side_effect=denied):
            rows = checkup.claude_plugin_enablement(self.home, self.home / ".claude")
        self.assertEqual(rows[0]["reason"], ".claude: unverified")

    def test_plugin_enablement_selected_home_keeps_default_and_hides_external_path(self):
        self.write(self.home / ".claude/settings.json", '{"enabledPlugins": {"finolabs-vibecode@one": true}}')
        other = self.base / "PRIVATE-project"
        self.write(other / "settings.json", '{"enabledPlugins": {"finolabs-vibecode@two": false}}')
        self.env["CLAUDE_CONFIG_DIR"] = str(other)
        row = self.setup_item("claude plugin enablement")
        self.assertEqual(row["reason"], ".claude: enabled; selected home: disabled")
        self.assertNotIn("PRIVATE", json.dumps(row))

    def inventory(self, date):
        return "## Agents on this machine\n\nCoordinator: Codex\n\n" + "\n".join(
            f"| {name} | yes | fake | unverified | {date} |"
            for name in ("Claude Code", "Codex", "Antigravity")) + "\n"

    def test_project_settings_invalid_deprecated_and_ledger_mismatch_never_show_values(self):
        host = self.home / '.finolabs/vibecode/host.md'
        self.write(host, '## Project progress\n- Ledger project: PRIVATE alias\n- Task file: PRIVATE.md\n'
                        '## Project settings\n- aaaaaaaa unknown: PRIVATE\n')
        self.write(host.with_name('ledger.jsonl'), json.dumps(dict(event='start', project='PRIVATE repo other')) + '\n')
        output = self.run_check('--json')
        self.assertNotIn('PRIVATE', output)
        rows = json.loads(output)['setup']
        self.assertTrue(any(r['check'] == 'project settings' and 'invalid' in r['reason'] for r in rows))
        self.assertTrue(any(r['check'] == 'ledger-project mismatch' for r in rows))
        for key in ('ledger', 'tasks'):
            self.assertTrue(any('settings --set ' + key + '=<value>' in r['reason'] for r in rows))
        import project_progress as pp
        host.write_text('## Project progress\n- Ledger project: PRIVATE alias\n## Project settings\n- ' +
                        pp.repository_code(self.repo) + ' ledger: PRIVATE repo other\n')
        self.assertFalse(any(r['check'] == 'ledger-project mismatch' for r in self.data()['setup']))

    def test_ledger_mismatch_requires_similar_project_and_no_entry(self):
        host = self.home / '.finolabs/vibecode/host.md'
        import project_progress as pp
        code = pp.repository_code(self.repo)
        for names, entry, expected in [
                ([], None, False), (['unrelated'], None, False),
                (['PRIVATE-REPO'], None, True), (['REPO'], None, True),
                (['rep'], None, False), (['repo', 'PRIVATE-REPO'], None, False),
                (['PRIVATE-REPO'], 'missing-alias', False)]:
            with self.subTest(names=names, entry=entry):
                self.write(host, '## Project settings\n' +
                           (f'- {code} ledger: {entry}\n' if entry else ''))
                self.write(host.with_name('ledger.jsonl'), ''.join(
                    json.dumps(dict(event='start', project=name)) + '\n' for name in names))
                rows = self.data()['setup']
                self.assertEqual(any(r['check'] == 'ledger-project mismatch' for r in rows), expected)
        # Substring in the other direction also qualifies, with a four-character minimum.
        self.repo = self.repo.rename(self.repo.with_name('private-repo-worktree'))
        self.write(host, '## Project settings\n')
        self.write(host.with_name('ledger.jsonl'), json.dumps(dict(event='start', project='PRIVATE-REPO')) + '\n')
        self.assertTrue(any(r['check'] == 'ledger-project mismatch' for r in self.data()['setup']))

    def test_invalid_progress_section_preserves_checkup_report(self):
        for text in ('## Project progress\n## Project progress\n',
                     '## Project progress\n```markdown\nPRIVATE unfinished\n'):
            with self.subTest(text=text):
                self.write(self.home / '.finolabs/vibecode/host.md', text)
                report = self.data()
                rows = report['setup']
                self.assertTrue(any(r['check'] == 'project progress' and 'invalid' in r['reason'] for r in rows))
                self.assertTrue(any(r['check'] == 'host config' for r in rows))
                self.assertNotIn('inspection unavailable', json.dumps(report))
                self.assertNotIn('PRIVATE', json.dumps(report))

    def test_missing_stale_recent_and_invalid_inventory(self):
        self.assertEqual(self.setup_item("agents inventory")["status"], "missing")
        config = self.home / ".finolabs/vibecode/host.md"
        today = datetime.date.today()
        self.write(config, self.inventory((today - datetime.timedelta(days=31)).isoformat()))
        row = self.setup_item("agents inventory")
        self.assertEqual(row["status"], "missing")
        self.assertIn("stale", row["reason"])
        config.write_text(self.inventory((today - datetime.timedelta(days=30)).isoformat()))
        self.assertEqual(self.setup_item("agents inventory")["status"], "ok")
        config.write_text(self.inventory("unverified"))
        self.assertEqual(self.setup_item("agents inventory")["status"], "unverified")
        config.unlink()
        outside = self.write(self.base / "outside.md", self.inventory(today.isoformat()))
        config.symlink_to(outside)
        self.assertEqual(self.setup_item("agents inventory")["status"], "unverified")

    def test_retired_pointers_in_user_and_project_context(self):
        for suffix, path in (("committee", self.home / ".claude/CLAUDE.md"),
                             ("coordinator-sessions", self.home / ".codex/AGENTS.override.md"),
                             ("knowledge", self.repo / "AGENTS.md"),
                             ("setup-instructions", self.home / ".claude/CLAUDE.md"),
                             ("scan-agents", self.home / ".codex/AGENTS.md"),
                             ("set-mode", self.repo / "AGENTS.md")):
            with self.subTest(name=suffix):
                self.write(path, "Use fnl-" + suffix + ".\n")
                row = self.setup_item("retired skill pointers")
                self.assertEqual(row["status"], "missing")
                self.assertIn("fnl-" + suffix, row["reason"])
                path.unlink()
        self.assertEqual(self.setup_item("retired skill pointers")["status"], "ok")


    def test_missing_host_config(self):
        self.assertEqual(self.setup_item("host config")["status"], "missing")

    def test_instruction_length_is_measured_without_content(self):
        self.write(self.repo / "AGENTS.md", "A synthetic instruction.\n" * 201)
        rows = self.data().get("instructions", {}).get("results", [])
        self.assertTrue(any(r["id"] == "I1" and r["status"] == "fail"
                            and r["file"] == "AGENTS.md" and r["line"] == 201
                            and r["pattern"] == "line-limit" for r in rows))

    def test_missing_agent_skills_block(self):
        self.write(self.repo / "AGENTS.md", "# Project\n")
        self.assertEqual(self.setup_item("agent skills")["status"], "missing")

    def test_required_headings_and_override(self):
        config = self.write(self.base / "custom.md", "## Limits\n")
        self.env["ORCHESTRATION_HOST_CONFIG"] = str(config)
        row = self.setup_item("host config")
        self.assertEqual(row["status"], "missing")
        self.assertIn("Briefs folder", row["reason"])
        self.assertIn("Agent roles", row["reason"])
        self.assertIn("Review posting", row["reason"])
        self.assertIn("Delegate environment", row["reason"])
        config.write_text("\n".join("## " + h for h in sorted(checkup.HEADINGS)))
        self.assertEqual(self.setup_item("host config")["status"], "ok")
        template = (ROOT / "skills/fnl-delegate/references/host-template.md").read_text()
        self.assertEqual(checkup.HEADINGS, set(re.findall(r"^## (.+)$", template, re.M)) - {"Effort preference", "Delegation mode", "Routing", "Agents on this machine", "Quota probe", "Project labels", "Heavy jobs"})
        for heading in ("Agent roles", "Review posting", "Delegate environment"):
            with self.subTest(heading=heading):
                config.write_text("\n".join("## " + h for h in sorted(checkup.HEADINGS - {heading})))
                row = self.setup_item("host config")
                self.assertEqual(row["status"], "missing")
                self.assertEqual(row["reason"], "required headings absent: " + heading)

    def test_assignment_matrix_states_and_fixed_reasons(self):
        config = self.home / ".finolabs/vibecode/host.md"
        legacy = "\n".join("## " + h for h in sorted(checkup.HEADINGS)) + "\n"
        matrix = ("## Assignment matrix\n\n- Consent: yes (2026-11-09)\n- Judge: jev\n"
                  "- codex: levels 1-5; roles code-review\n- claudezz: levels 2-4; roles navigator\n")
        present = "required headings present; values not validated; assignments: "
        self.write(config, legacy)
        row = self.setup_item("host config")
        self.assertEqual(row, {"check": "host config", "status": "ok", "reason": present +
                               "matrix absent; legacy Agent roles and Agent levels in use until 0.3.0"})
        # Valid: the matrix alone decides, so a missing legacy roles heading is no longer required.
        self.write(config, "\n".join("## " + h for h in sorted(checkup.HEADINGS - {"Agent roles"})) + "\n" + matrix)
        self.assertEqual(self.setup_item("host config"), {"check": "host config", "status": "ok", "reason": present +
                         "matrix valid; 2 agents; judge jev; roles assigned: code-review, navigator"})
        self.write(config, legacy + matrix)
        self.assertTrue(self.setup_item("host config")["reason"].endswith(
            "; legacy Agent roles or Agent levels present and ignored"))
        # Invalid, even with a valid legacy section: unset, with each fixed reason and never the offending text.
        self.write(config, legacy + matrix + "- gemini: levels 1-2\n- codex: levels 1-5\n")
        row = self.setup_item("host config")
        self.assertEqual(row["status"], "missing")
        self.assertIn("assignments: matrix invalid (unknown agent, duplicate agent); roles and judge unset, "
                      "reviews not routed, judge falls to the host model", row["reason"])
        self.assertNotIn("gemini", json.dumps(self.data()))
        # Without its own yes consent: unset as well.
        self.write(config, legacy + "## Assignment matrix\n- Consent: no\n- Judge: host\n")
        row = self.setup_item("host config")
        self.assertEqual(row["status"], "missing")
        self.assertIn("assignments: matrix without consent; roles and judge unset", row["reason"])

    def test_template_structure_and_instruction_consent(self):
        template = (ROOT / "skills/fnl-delegate/references/host-template.md").read_text()
        headings = re.findall(r"^## (.+)$", template, re.M)
        expected = ['Delegation mode', 'Routing', 'Agents on this machine', 'Delegate environment',
                    'Agent roles', 'Review posting', 'Quota probe', 'Project labels', 'Limits', 'Heavy jobs',
                    'Effort preference', 'Briefs folder', 'Coordinators and reach', 'Route judgment',
                    'Dispatch marker', 'Claude Code', 'Codex', 'Antigravity']
        self.assertEqual(headings, expected)
        self.assertTrue(all('`' not in heading and len(heading) <= 60 for heading in headings))
        config = template.replace('Instruction check: <on | off>', 'Instruction check: on')
        self.assertTrue(checkup.instruction_consent(config))
        route = template.split('## Route judgment\n', 1)[1].split('\n## ', 1)[0]
        self.assertIn('canonical `## Agent roles`; this legacy heading retains instruction-check consent.', route)
        environment = template.split('## Delegate environment\n', 1)[1].split('\n## ', 1)[0]
        self.assertIn('The `Delegate environment` section accepts only', environment)

    def test_effective_settings_and_enforcement_limits(self):
        self.env.update(FNL_DELEGATION_MODE="auto", FNL_ROUTING="off")
        self.assertIn("delegation mode=auto; routing=off", self.setup_item("effective settings")["reason"])
        rows = self.data()["hosts"]
        for host, expected in (("claude", "continuation reminders"), ("codex", "user trust"),
                               ("agy", "static always-on rule")):
            row = next(r for r in rows[host] if r["check"] == "mode enforcement")
            self.assertEqual(row["status"], "unverified")
            self.assertIn(expected, row["reason"])

    def test_unverified_runtime_never_becomes_ok(self):
        self.install_claude()
        self.write(self.home / ".claude/CLAUDE.md", "Start coding with fnl-coding-router.\n")
        data = self.data()
        for rows in data["hosts"].values():
            for row in rows:
                if row["check"] in {"runtime", "compaction"}:
                    self.assertEqual(row["status"], "unverified")
        self.assertEqual(data["setup"][-1]["status"], "unverified")
        self.assertIn("not proof that it runs", data["principle"])
        rows = {r["check"]: r for r in data["hosts"]["claude"]}
        self.assertEqual(rows["plugin"]["status"], "ok")
        self.assertIn("1.0.0", rows["plugin"]["reason"])
        self.assertEqual(rows["hooks"]["status"], "ok")
        self.assertIn("declarations only", rows["hooks"]["reason"])

    def test_cache_is_not_an_install_record(self):
        root = self.install_claude()
        (self.home / ".claude/plugins/installed_plugins.json").unlink()
        row = self.data()["hosts"]["claude"][1]
        self.assertEqual(row["status"], "unverified")
        self.assertIn("1.0.0", row["reason"])
        self.write(root / ".claude-plugin/hooks.json", '{"hooks":{"SessionStart":[]}}')
        self.assertEqual(self.data()["hosts"]["claude"][2]["status"], "missing")

    def test_precompact_declaration_never_proves_delivery(self):
        root = self.install_claude()
        path = root / ".claude-plugin/hooks.json"
        config = json.loads(path.read_text())
        for declared in (False, True):
            with self.subTest(declared=declared):
                if declared:
                    config["hooks"]["PreCompact"] = [{"hooks": [{"type": "command", "command": "never run"}]}]
                path.write_text(json.dumps(config))
                row = self.data()["hosts"]["claude"][2]
                self.assertEqual(row["status"], "ok")
                self.assertIn("PreCompact declared" if declared else "PreCompact not declared (optional)", row["reason"])
                self.assertIn("delivery unverified", row["reason"])

    def test_antigravity_hook_support_stays_unverified(self):
        self.write(self.home / ".gemini/config/hooks.json", json.dumps({
            "finolabs-vibecode": {"SessionStart": [{"type": "command", "command": "never run"}]}}))
        row = self.data()["hosts"]["agy"][2]
        self.assertEqual(row["status"], "unverified")
        self.assertIn("SessionStart", row["reason"])
        self.assertIn("Stop/PreCompact support unverified", row["reason"])

    def test_manifest_cannot_redirect_hook_reads_outside_plugin(self):
        root = self.install_claude()
        self.write(root / ".claude-plugin/plugin.json", json.dumps({
            "name": "finolabs-vibecode", "version": "1.0.0", "hooks": "../../hooks.json"}))
        row = self.data()["hosts"]["claude"][2]
        self.assertEqual(row["status"], "unverified")
        self.assertIn("outside inspected metadata", row["reason"])

    def test_symlinked_file_and_directory_not_followed(self):
        outside = self.write(self.base / "outside/AGENTS.md", "## Agent skills\nfnl-coding-router\n")
        (self.repo / "AGENTS.md").symlink_to(outside)
        self.assertEqual(self.setup_item("agent skills")["status"], "unverified")
        (self.home / ".codex").symlink_to(outside.parent, target_is_directory=True)
        self.assertEqual(self.data()["hosts"]["codex"][3]["status"], "unverified")
        with mock.patch("os.read", side_effect=AssertionError("must not read target")):
            self.assertEqual(checkup.read(self.repo / "AGENTS.md"), ("unverified", ""))

    def test_only_known_metadata_is_read_and_no_writes(self):
        self.install_claude()
        self.write(self.home / ".env", "never read this")
        self.write(self.home / ".aws/credentials", "never read this")
        before = {p: p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        self.run_check()
        self.assertEqual(before, {p: p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        self.assertEqual(checkup.read(self.home / ".env")[0], "unverified")
        self.assertEqual(checkup.read(self.home / ".aws/credentials")[0], "unverified")

    def test_exit_zero_on_bad_metadata_arguments_and_inspection_error(self):
        self.write(self.home / ".claude/plugins/installed_plugins.json", "invalid json")
        self.run_check()
        self.run_check("--unknown")
        with mock.patch.object(checkup, "collect", side_effect=OSError), \
                mock.patch.object(sys, "argv", [str(SCRIPT)]), mock.patch("builtins.print"):
            self.assertEqual(checkup.main(), 0)

    def test_output_cap_and_json_parity(self):
        self.install_claude()
        text = self.run_check()
        self.assertLessEqual(len(text.splitlines()), 40)
        data = self.data()
        expected = [data["principle"]]
        for host, rows in [*data["hosts"].items(), ("setup", data["setup"])]:
            expected.extend(f'{host} / {r["check"]}: {r["status"]} - {r["reason"]}' for r in rows
                            if host == "setup" or r["check"] not in {"runtime", "compaction"})
        expected.extend(checkup.instruction_lines(data["instructions"]))
        self.assertEqual(text.splitlines(), expected)
        for rows in [*data["hosts"].values(), data["setup"]]:
            self.assertTrue(all(r["status"] in {"ok", "missing", "unverified", "default", "relocated", "invalid"} for r in rows))

    def test_legacy_host_config_does_not_supply_consent(self):
        headings = "\n".join("## " + h for h in sorted(checkup.HEADINGS))
        legacy = self.write(self.home / ".config/finolabs-vibecode/host.md", headings)
        self.env.pop("XDG_CONFIG_HOME", None)
        self.assertEqual(self.setup_item("host config")["status"], "missing")
        self.write(self.home / ".finolabs/vibecode/host.md", "## Limits\n")
        self.assertEqual(self.setup_item("host config")["status"], "missing")
        legacy.unlink()

    def test_review_adoption_inside_the_generated_paragraph(self):
        skill = (ROOT / "skills/fnl-setup/references/core.md").read_text()
        paragraph = next(line for line in skill.splitlines() if line.startswith("This repository uses the finolabs-vibecode skills."))
        self.write(self.repo / "AGENTS.md", "## Agent skills\n\n" + paragraph + "\n")
        self.assertEqual(self.setup_item("review adoption")["status"], "ok")

    def test_repo_adoption_and_user_instruction_pointers(self):
        self.write(self.repo / "CLAUDE.md", "## Agent skills\n\n"
                   "Pull requests follow `fnl-review-gate` \"Pull requests\".\n")
        self.assertEqual(self.setup_item("agent skills")["status"], "ok")
        self.assertEqual(self.setup_item("review adoption")["status"], "ok")
        custom = self.base / "custom-codex"
        self.env["CODEX_HOME"] = str(custom)
        self.write(custom / "AGENTS.md", "Start coding work with fnl-coding-router.\n")
        self.assertEqual(self.data()["hosts"]["codex"][3]["status"], "ok")

    def test_symlinked_path_folder_is_unverified(self):
        target = self.base / "real-bin"
        target.mkdir()
        (self.bin / "linked").symlink_to(target, target_is_directory=True)
        self.env["PATH"] = str(self.bin / "linked")
        self.assertEqual(self.data()["hosts"]["claude"][0]["status"], "unverified")

    def test_worktree_common_exclude(self):
        (self.repo / ".git/info/exclude").unlink()
        (self.repo / ".git/info").rmdir()
        (self.repo / ".git").rmdir()
        common = self.base / "main/.git"
        worktree = common / "worktrees/check"
        self.write(worktree / "commondir", "../..\n")
        self.write(common / "info/exclude", ".finolabs/\n")
        self.write(self.repo / ".git", "gitdir: " + str(worktree) + "\n")
        self.assertEqual(self.setup_item("local exclude")["status"], "ok")

    def index(self, *names):
        data = b"DIRC" + struct.pack(">II", 2, len(names))
        for name in sorted(names):
            raw = name.encode()
            entry = b"\0" * 60 + struct.pack(">H", len(raw)) + raw + b"\0"
            data += entry + b"\0" * (-len(entry) % 8)
        path = self.repo / ".git/index"
        path.write_bytes(data + hashlib.sha1(data).digest())

    def instruction_rows(self, ident=None, pattern=None):
        rows = self.data()["instructions"]["results"]
        return [r for r in rows if (ident is None or r["id"] == ident)
                and (pattern is None or r["pattern"] == pattern)]

    def test_payload_instruction_files_use_account_home_not_environment(self):
        self.consent()
        self.write(self.home / ".claude/CLAUDE.md", "ACCOUNT INSTRUCTION\n")
        decoy = self.base / "decoy"
        self.write(decoy / ".claude/CLAUDE.md", "DECOY INSTRUCTION\n")
        self.env["HOME"] = str(decoy)
        payload = self.run_check("--judge-payload")
        self.assertIn("ACCOUNT INSTRUCTION", payload)
        self.assertNotIn("DECOY INSTRUCTION", payload)

    def consent(self, text="## Route judgment\n- Instruction check: on\n"):
        return self.write(self.home / ".finolabs/vibecode/host.md", text)

    def clean_instruction(self):
        return "# Project\n## Commands\nBuild: `build`\nTest: `test`\nLint: `lint`\nOne test: `test unit`\n"

    def test_all_script_items_have_clean_results(self):
        self.index("AGENTS.md")
        self.write(self.repo / "AGENTS.md", self.clean_instruction())
        rows = self.instruction_rows()
        self.assertEqual({r["id"] for r in rows}, {"I" + str(n) for n in range(1, 15)})
        for ident in range(1, 15):
            self.assertTrue(any(r["id"] == "I" + str(ident) and r["status"] == "ok" for r in rows))
        self.assertEqual([r["pattern"] for r in rows if r["status"] != "ok"], ["custom-byte-limit", "command-execution"])

    def test_i1_exact_thresholds(self):
        path = self.repo / "AGENTS.md"
        for count, expected in ((150, "ok"), (151, "warn"), (200, "warn"), (201, "fail")):
            with self.subTest(count=count):
                self.write(path, "Short line.\n" * count)
                rows = self.instruction_rows("I1")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["status"], expected)

    def test_i2_codex_chain_override_and_nested_cwd(self):
        self.write(self.home / ".codex/AGENTS.md", "normal " * 6000)
        override = self.write(self.home / ".codex/AGENTS.override.md", "x" * 16000)
        self.write(self.repo / "AGENTS.md", "y" * 16000)
        nested = self.repo / "part"
        self.write(nested / "AGENTS.override.md", "z" * 769)
        self.write(nested / "AGENTS.md", "ignored " * 8000)
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(Path, "cwd", return_value=nested):
            data = checkup.collect()
        row = next(r for r in data["instructions"]["results"] if r["pattern"] == "codex-chain")
        self.assertEqual(row["status"], "fail")
        self.assertIn("32769 bytes", row["reason"])
        override.write_text("x" * 15999)
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(Path, "cwd", return_value=nested):
            data = checkup.collect()
        self.assertEqual(next(r for r in data["instructions"]["results"] if r["pattern"] == "codex-chain")["status"], "ok")
        self.env["CODEX_HOME"] = "relative-codex"
        self.assertEqual(self.instruction_rows("I2", "codex-chain")[0]["status"], "ok")
        self.env["CODEX_HOME"] = str(self.base / "custom")
        self.write(self.base / "custom/AGENTS.md", "c" * 17000)
        self.assertEqual(self.instruction_rows("I2", "codex-chain")[0]["status"], "fail")

    def test_i3_antigravity_limits_includes_and_estimate(self):
        self.write(self.home / ".gemini/GEMINI.md", "@[rule](config/rules/large.md)\n")
        self.write(self.home / ".gemini/config/rules/large.md", "---\ntrigger: manual\n---\n" + "a" * 24000)
        rows = self.instruction_rows("I3", "antigravity-file-size")
        self.assertEqual({r["file"] for r in rows}, {"~/.gemini/GEMINI.md", "~/.gemini/config/rules/large.md"})
        for n in range(4):
            self.write(self.repo / f".agents/rules/r{n}.md", "---\ntrigger: always_on\n---\n" + "b" * 21000)
        row = self.instruction_rows("I3", "antigravity-token-estimate")[0]
        self.assertEqual(row["status"], "warn")
        self.assertIn("80000 bytes estimates 20000 tokens", row["reason"])

    def test_i4_refuses_outside_includes_without_opening_or_exporting(self):
        outside = self.write(self.base / "outside/AGENTS.md", "FORBIDDEN OUTSIDE CONTENT")
        (self.repo / "linked").symlink_to(outside.parent, target_is_directory=True)
        targets = [str(outside), "~/AGENTS.md", "../outside/AGENTS.md", "linked/AGENTS.md"]
        self.write(self.repo / "CLAUDE.md", "\n".join("@" + target for target in targets))
        self.consent()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(Path, "cwd", return_value=self.repo), \
                mock.patch.object(checkup, "read", wraps=checkup.read) as reader:
            data = checkup.collect()
        self.assertNotIn(outside, [c.args[0] for c in reader.call_args_list])
        rows = [r for r in data["instructions"]["results"] if r["pattern"] == "outside-root"]
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["line"] for r in rows], [1, 2, 3, 4])
        for output in (self.run_check(), self.run_check("--json"), self.run_check("--judge-payload")):
            for value in [*targets, "FORBIDDEN OUTSIDE CONTENT"]:
                self.assertNotIn(value, output)

    def test_i4_include_names_fences_hosts_missing_and_depth(self):
        self.write(self.repo / "CLAUDE.md", "```\n@../outside/AGENTS.md\n```\n"
                   "~~~text\n@/outside/AGENTS.md\n~~~\n@notes" ".md\n@missing/AGENTS.md\n@a/CLAUDE.md\n@a/CLAUDE.md\n")
        for n in range(1, 6):
            self.write(self.repo.joinpath(*(["a"] * n), "CLAUDE.md"), "@a/CLAUDE.md\n" if n < 5 else "Fifth level.\n")
        self.write(self.home / ".codex/AGENTS.md", "@AGENTS.override.md\n")
        self.write(self.repo / ".agents/rules/example.md", "---\ntrigger: manual\n---\n@GEMINI" ".md\n")
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(Path, "cwd", return_value=self.repo), \
                mock.patch.object(checkup, "read", wraps=checkup.read) as reader:
            data = checkup.collect()
        rows = [r for r in data["instructions"]["results"] if r["id"] == "I4"]
        self.assertNotIn("outside-root", {r["pattern"] for r in rows})
        for pattern in ("include-name", "include-target", "include-depth", "include-syntax"):
            self.assertIn(pattern, {r["pattern"] for r in rows})
        paths = [c.args[0] for c in reader.call_args_list]
        self.assertEqual(paths.count(self.repo / "a/CLAUDE.md"), 1)
        self.assertNotIn(self.repo / "notes.md", paths)
        self.assertNotIn(self.repo.joinpath(*(["a"] * 5), "CLAUDE.md"), paths)
        self.assertEqual(len([r for r in rows if r["pattern"] == "include-depth"]), 1)

    def test_i5_duplicates_and_explicit_source(self):
        line = "A sufficiently long synthetic instruction shared between two files."
        self.write(self.repo / "CLAUDE.md", line + "\n")
        other = self.write(self.repo / "AGENTS.md", line + "\n")
        rows = self.instruction_rows("I5", "duplicate-line")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["line"], 1)
        self.assertNotIn(line, self.run_check("--json"))
        other.write_text("<!-- Source: CLAUDE.md -->\n" + line + "\n")
        self.assertEqual(self.instruction_rows("I5")[0]["status"], "ok")

    def synthetic_secrets(self):
        return [
            ("private-key-header", "-----BEGIN " + "PRIVATE KEY-----"),
            ("access-key-id", "AK" + "IA" + "Q" * 16),
            ("github-token", "gh" + "p_" + "x" * 24),
            ("github-token", "github_" + "pat_" + "x" * 24),
            ("api-key", "s" + "k-" + "x" * 20),
            ("slack-token", "xo" + "xb-" + "x" * 20),
            ("slack-token", "xo" + "xp-" + "x" * 20),
            ("secret-assignment", "password" + " = " + "x" * 8),
            ("secret-assignment", '"token"' + ': "' + "x" * 8 + '"'),
            ("encoded-assignment", "data: " + "Q" * 40),
        ]

    def test_i6_secret_patterns_backups_and_report_hygiene(self):
        for pattern, value in self.synthetic_secrets():
            with self.subTest(pattern=pattern):
                path = self.write(self.repo / "AGENTS.md", "safe line\n" + value + "\n")
                rows = self.instruction_rows("I6")
                self.assertEqual([(r["pattern"], r["line"], r["file"]) for r in rows], [(pattern, 2, "AGENTS.md")])
                for output in (self.run_check(), self.run_check("--json")):
                    self.assertNotIn(value, output)
                path.unlink()
        backup = self.write(self.repo / "AGENTS.md.bak-test", "NEVER\n" * 201 + self.synthetic_secrets()[2][1])
        self.write(self.repo / "AGENTS.md", self.clean_instruction())
        rows = self.instruction_rows()
        self.assertEqual({r["id"] for r in rows if r["file"] == backup.name}, {"I6"})

    def test_i7_paths_only_in_tracked_project_files(self):
        paths = ["/" + "Users/example/private", "/" + "home/example/private", "C:" + "\\example\\private"]
        self.index("AGENTS.md")
        self.write(self.repo / "AGENTS.md", "\n".join(paths))
        self.write(self.repo / "CLAUDE.md", "\n".join(paths))
        self.write(self.home / ".claude/CLAUDE.md", "\n".join(paths))
        rows = self.instruction_rows("I7")
        self.assertEqual([(r["file"], r["line"]) for r in rows], [("AGENTS.md", n) for n in (1, 2, 3)])
        for output in (self.run_check(), self.run_check("--json")):
            for value in paths:
                self.assertNotIn(value, output)

    def test_i8_local_ignore_and_native_suppression(self):
        self.index("AGENTS.md")
        self.write(self.repo / "AGENTS.md", self.clean_instruction())
        self.write(self.repo / "CLAUDE.local.md", "Local only.")
        ignore = self.write(self.repo / ".gitignore", "CLAUDE.local.md\n")
        self.assertEqual(self.instruction_rows("I8", "local-ignore")[0]["status"], "ok")
        self.assertEqual(len(self.instruction_rows("I8", "native-agents-suppressed")), 1)
        self.index("AGENTS.md", "CLAUDE.local.md")
        self.assertEqual(self.instruction_rows("I8", "local-ignore")[0]["status"], "warn")
        self.index("AGENTS.md")
        ignore.write_text("CLAUDE.local.md\n!CLAUDE.local.md\n")
        self.assertEqual(self.instruction_rows("I8", "local-ignore")[0]["status"], "unverified")

    def test_i9_commands_presence(self):
        path = self.write(self.repo / "AGENTS.md", "# Commands\nBuild, test and lint.\n")
        self.assertEqual(self.instruction_rows("I9")[0]["pattern"], "project-commands")
        path.write_text(self.clean_instruction())
        self.assertTrue(any(r["status"] == "ok" for r in self.instruction_rows("I9")))
        path.write_text("`build` `test` `lint` `test unit`\n")
        self.assertTrue(any(r["status"] == "ok" for r in self.instruction_rows("I9")))

    def test_i10_vague_lines_once_per_line(self):
        self.write(self.repo / "AGENTS.md", "Be careful and use best practices.\nDo it properly for clean code.\n")
        rows = self.instruction_rows("I10")
        self.assertEqual([r["line"] for r in rows], [1, 2])
        self.assertTrue(all(r["pattern"] == "vague-phrase" for r in rows))

    def test_i11_emphasis_threshold(self):
        path = self.write(self.repo / "AGENTS.md", "CRITICAL MUST ALWAYS NEVER IMPORTANT\n")
        self.assertEqual(self.instruction_rows("I11")[0]["status"], "ok")
        path.write_text(path.read_text() + "MUST\nMUST\n")
        rows = self.instruction_rows("I11")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["pattern"], rows[0]["line"]), ("emphasis-count", 2))

    def test_i12_trigger_contract_and_nested_files(self):
        path = self.repo / ".agents/rules/example.md"
        for content, expected in (("", "rule-trigger"), ("trigger: other", "rule-trigger"),
                                  ("trigger: model_decision", "rule-description"),
                                  ("trigger: glob", "rule-globs")):
            self.write(path, "---\n" + content + "\n---\n")
            self.assertEqual(self.instruction_rows("I12")[0]["pattern"], expected)
        for content in ("trigger: always_on", "trigger: manual", "trigger: model_decision\ndescription: Purpose",
                        "trigger: glob\nglobs: '*.py'", "trigger: glob\nglob: '*.py'"):
            self.write(path, "---\n" + content + "\n---\n")
            self.assertEqual(self.instruction_rows("I12")[0]["status"], "ok")
        self.write(self.home / ".gemini/config/rules/nested/rule.md", "---\ntrigger: manual\n---\n")
        self.write(self.repo / "nested/GEMINI.md", "Instructions.\n")
        self.write(self.repo / "AGENTS.override.md", self.clean_instruction())
        rows = self.instruction_rows("I12")
        self.assertEqual(len([r for r in rows if r["pattern"] == "nested-instruction"]), 2)
        self.assertEqual(len([r for r in rows if r["pattern"] == "codex-override"]), 1)

    def test_i13_mtime_and_maintainer_comments(self):
        path = self.write(self.repo / "AGENTS.md", "<!-- Maintainer: review periodically -->\nMaintainer: review periodically\n")
        old = datetime.datetime.now().timestamp() - 91 * 86400
        os.utime(path, (old, old))
        rows = self.instruction_rows("I13")
        self.assertEqual({r["pattern"] for r in rows}, {"file-age", "maintainer-note"})
        self.assertEqual(next(r for r in rows if r["pattern"] == "maintainer-note")["line"], 2)
        self.assertIn("mtime", next(r for r in rows if r["pattern"] == "file-age")["reason"])

    def test_i14_retired_check_keeps_its_id(self):
        for suffix in ("knowledge", "setup-instructions", "scan-agents", "set-mode"):
            for path in (self.repo / "AGENTS.md", self.home / ".claude/CLAUDE.md"):
                with self.subTest(name=suffix, file=str(path)):
                    self.write(path, "Use fnl-" + suffix + ".\n")
                    rows = self.instruction_rows("I14")
                    label = "AGENTS.md" if path.parent == self.repo else "~/.claude/CLAUDE.md"
                    self.assertEqual([(r["file"], r["line"], r["pattern"]) for r in rows],
                                     [(label, 1, "retired-skill")])
                    path.write_text("Use fnl-" + suffix + "-extra.\n")
                    self.assertFalse([r for r in self.instruction_rows("I14") if r["pattern"] == "retired-skill"])
                    path.unlink()

    def test_payload_consent_is_separate_scoped_and_fail_closed(self):
        self.write(self.repo / "AGENTS.md", "SAFE LINE\n")
        self.assertEqual(self.run_check("--judge-payload"), "")
        for content in ("## Route judgment\n- Instruction check: off\n", "## Route judgment\n- Routing: on\n",
                        "## Other\n- Instruction check: on\n", "## Route judgment\n```\n- Instruction check: on\n```\n",
                        "## Route judgment\n- Instruction check: on\n- Instruction check: off\n"):
            self.consent(content)
            self.assertEqual(self.run_check("--judge-payload"), "")
        config = self.consent()
        self.assertIn("SAFE LINE", self.run_check("--judge-payload"))
        config.unlink()
        outside = self.write(self.base / "config.md", "## Route judgment\n- Instruction check: on\n")
        config.symlink_to(outside)
        self.assertEqual(self.run_check("--judge-payload"), "")
        config.unlink()
        self.write(self.home / ".config/finolabs-vibecode/host.md", outside.read_text())
        self.assertEqual(self.run_check("--judge-payload"), "")
        self.consent("## Route judgment\n- Instruction check: off\n")
        self.assertEqual(self.run_check("--judge-payload"), "")
        self.env["ORCHESTRATION_HOST_CONFIG"] = str(outside)
        self.assertEqual(self.run_check("--judge-payload"), "")

    def test_payload_filters_whole_secret_file_paths_backups_local_and_scan(self):
        self.consent()
        self.write(self.repo / "AGENTS.md", "SAFE FROM CLEAN FILE\n/" + "home/example/private\n")
        self.write(self.repo / "CLAUDE.md", "OMIT WHOLE FILE\n" + self.synthetic_secrets()[2][1])
        self.write(self.repo / "AGENTS.md.bak-test", "OMIT BACKUP\n")
        self.write(self.repo / "CLAUDE.local.md", "OMIT LOCAL\n")
        self.write(self.home / ".gemini/GEMINI.md", "## Agents on this machine\nOMIT SCAN\n## Actual instructions\nSAFE AFTER SCAN\n")
        payload = self.run_check("--judge-payload")
        self.assertIn("SAFE FROM CLEAN FILE", payload)
        self.assertIn("SAFE AFTER SCAN", payload)
        for omitted in ("OMIT", "private", self.synthetic_secrets()[2][1], "I6", "secret-looking"):
            self.assertNotIn(omitted, payload)

    def test_payload_caps_characters_and_utf8_bytes(self):
        self.consent()
        self.write(self.repo / "AGENTS.md", ("界" * 400 + "\n") * 100)
        payload = self.run_check("--judge-payload")
        self.assertLessEqual(len(payload.encode("utf-8")), 8192)
        self.assertTrue(all(len(line) <= 300 for line in payload.splitlines()))
        self.assertTrue(payload.endswith("[truncated]\n"))

    def test_discovery_bounds_and_output_budget(self):
        self.write(self.repo / "AGENTS.md", "a" * (checkup.MAX_BYTES + 1))
        self.assertEqual(self.instruction_rows("I4", "safe-read")[0]["status"], "unverified")
        self.write(self.repo / "AGENTS.md", "Be careful.\n" * 200)
        for n in range(70):
            self.write(self.repo / f".agents/rules/r{n:02}.md", "---\ntrigger: manual\n---\n")
        data = self.data()["instructions"]
        self.assertEqual(data["files"], 64)
        self.assertTrue(any(r["pattern"] == "discovery-limit" for r in data["results"]))
        output = self.run_check()
        self.assertLessEqual(len(output.splitlines()), 40)
        block = output[output.index("\ninstructions:") + 1:].splitlines()
        self.assertLessEqual(len(block), 13)
        self.assertIn("more; use --json", block[-1])
        self.assertTrue(block[1].startswith("I1: warn"))


    def scan_direct(self):
        return checkup.instruction_scan(self.home, self.home / ".codex", self.repo,
                                        self.repo, self.repo / ".git")

    def test_review_consent_comments_and_suffixes(self):
        self.write(self.repo / "AGENTS.md", "SAFE LINE\n")
        for value in ("on", "on. The user approved, on 2026-01-01, this check.", "on approved"):
            with self.subTest(value=value):
                self.consent("## Route judgment\n- Instruction check: " + value + "\n")
                self.assertIn("SAFE LINE", self.run_check("--judge-payload"))
        for content in ("- Instruction check: off", "- Instruction check: only",
                        "<!--\n- Instruction check: on\n-->",
                        "- Instruction check: on\n- Instruction check: on",
                        "~~~\n- Instruction check: on\n~~~"):
            with self.subTest(content=content):
                self.consent("## Route judgment\n" + content + "\n")
                self.assertEqual(self.run_check("--judge-payload"), "")
        config = self.consent()
        config.write_bytes(b"\xff")
        self.assertEqual(self.run_check("--judge-payload"), "")

    def test_review_directory_limit_only_affects_discovery(self):
        self.write(self.repo / "AGENTS.md", self.clean_instruction())
        for n in range(200):
            (self.repo / f"dir{n:03}").mkdir()
        rows = self.scan_direct()[0]["results"]
        for ident in (1, 7, 8, 10, 11, 13, 14):
            with self.subTest(ident=ident):
                self.assertTrue(all(r["status"] == "ok" for r in rows if r["id"] == f"I{ident}"))
        self.assertEqual({r["id"] for r in rows if r["reason"] == "directory limit"}, {"I4", "I6", "I12"})

    def test_review_secret_shapes_never_leave_file(self):
        samples = [key + " = " + "x" * 8 for key in
                   ("DB_PASSWORD", "DB_PASSWD", "client_secret", "GITHUB_TOKEN", "service_api_key",
                    "service_apikey", "credential_value", "prefixtokensuffix")]
        samples += ["Authorization: " + "Bearer " + "x" * 20,
                    "https://" + "user:pass" + "@" + "host/path"]
        samples += ["gh" + suffix + "_" + "x" * 24 for suffix in "osur"]
        samples += ["digest" + separator + "ab" * 16 for separator in (" = ", ": ", ' "')]
        self.consent()
        for value in samples:
            with self.subTest(shape=value[:12]):
                self.write(self.repo / "AGENTS.md", "OMIT WHOLE FILE\n" + value + "\n")
                block, files, _ = self.scan_direct()
                self.assertTrue(any(r["id"] == "I6" and r["status"] == "fail" for r in block["results"]))
                self.assertEqual(checkup.judge_payload(files), "")
                for output in (json.dumps(block), "\n".join(checkup.instruction_lines(block))):
                    self.assertNotIn(value, output)
                    self.assertNotIn("OMIT WHOLE FILE", output)

    def test_review_duplicate_performance(self):
        text = "".join(f"Synthetic instruction number {n:04}: keep the fixture deterministic.\n" for n in range(3000))
        self.write(self.repo / "AGENTS.md", text)
        self.write(self.repo / "CLAUDE.md", text)
        start = time.perf_counter()
        block = self.scan_direct()[0]
        elapsed = time.perf_counter() - start
        print(f"duplicate performance: {elapsed:.3f}s")
        self.assertLess(elapsed, 2)
        self.assertEqual(sum(r["pattern"] == "duplicate-line" for r in block["results"]), 3000)

    def test_review_expansion_performance_and_cap(self):
        self.write(self.repo / "GEMINI.md", "@[rule](.agents/rules/r0.md)\n" * 60)
        for n in range(4):
            text = f"@[rule](r{n + 1}.md)\n" * 60 if n < 3 else "Leaf content.\n" * 60
            self.write(self.repo / f".agents/rules/r{n}.md", "---\ntrigger: manual\n---\n" + text)
        start = time.perf_counter()
        block = self.scan_direct()[0]
        elapsed = time.perf_counter() - start
        print(f"expansion performance: {elapsed:.3f}s")
        self.assertLess(elapsed, 2)
        rows = [r for r in block["results"] if r["pattern"] == "expansion-limit"]
        self.assertEqual({r["id"] for r in rows}, {"I3", "I4"})
        self.assertTrue(all(r["status"] == "unverified" for r in rows))

    def test_review_text_groups_counts_and_omits_permanent_rows(self):
        self.write(self.repo / "AGENTS.md", "Be careful.\n" * 200 + "MUST " * 6)
        block = self.scan_direct()[0]
        lines = checkup.instruction_lines(block)
        vague = [line for line in lines if line.startswith("I10:")]
        self.assertEqual(len(vague), 1)
        self.assertIn("count=200", vague[0])
        self.assertTrue(any(line.startswith("I11:") for line in lines))
        self.assertEqual(sum(r["id"] == "I10" for r in block["results"]), 200)
        self.assertNotIn("custom-byte-limit", "\n".join(lines))
        self.assertNotIn("command-execution", "\n".join(lines))
        output = self.run_check()
        print(f"sample output: {len(output.splitlines())} lines")
        self.assertLessEqual(len(output.splitlines()), 40)

    def test_review_i9_root_import_wrapper(self):
        self.write(self.repo / "AGENTS.md", self.clean_instruction())
        wrapper = self.write(self.repo / "CLAUDE.md", "\n" + "@" + "AGENTS.md\n\nClaude Code: use the configured hooks.\n")
        self.assertFalse(self.instruction_rows("I9", "project-commands"))
        self.write(self.repo / "AGENTS.md", "No commands here.\n")
        self.assertEqual([r["file"] for r in self.instruction_rows("I9", "project-commands")], ["AGENTS.md"])
        wrapper.write_text("@AGENTS.md\nAdditional project instructions.\n")
        self.assertEqual(len(self.instruction_rows("I9", "project-commands")), 2)

    def test_review_machine_path_urls(self):
        line = "https://example.invalid" + "/home/" + "guide"
        self.assertIsNone(checkup.MACHINE_PATH.search(line))
        self.write(self.repo / "AGENTS.md", line + "\n")
        self.index("AGENTS.md")
        self.assertFalse(self.instruction_rows("I7", "machine-path"))
        self.consent()
        self.assertIn(line, self.run_check("--judge-payload"))

    def test_review_nonprintable_labels(self):
        for control in (chr(0x85), chr(0x7f)):
            path = self.write(self.repo / ("bad" + control) / "AGENTS.md", "Be careful.\n")
            self.write(self.repo / "CLAUDE.md", "@" + path.relative_to(self.repo).as_posix() + "\n")
            block = self.scan_direct()[0]
            nested = [r for r in block["results"] if r["pattern"] == "nested-instruction"]
            self.assertTrue(nested)
            self.assertTrue(all(r["file"] == "<instruction file>" for r in nested))

    def test_review_payload_evidence_locations(self):
        self.consent()
        self.write(self.repo / "AGENTS.md", "First line\nSecond line\n" + "z" * 400 + "\n")
        payload = self.run_check("--judge-payload")
        self.assertTrue(payload.startswith("AGENTS.md:1: First line\nAGENTS.md:2: Second line\n"))
        self.assertIn("AGENTS.md:3: ", payload)
        self.assertTrue(all(len(line) <= 300 for line in payload.splitlines()))

    def test_review_check_steps_are_sequential(self):
        text = (ROOT / "skills/fnl-setup/references/check.md").read_text().split("## Settings")[0]
        self.assertEqual(re.findall(r"^(\d+)\. ", text, re.M), ["1", "2", "3", "4", "5"])

    def test_low_long_identifier_secret_is_filtered(self):
        self.consent()
        self.write(self.repo / "AGENTS.md", "x" * 41 + "_token = " + "q" * 8 + "\n")
        block, files, _ = self.scan_direct()
        self.assertTrue(any(r["pattern"] == "secret-assignment" for r in block["results"]))
        self.assertEqual(checkup.judge_payload(files), "")

    def test_low_additional_machine_homes_are_filtered(self):
        self.consent()
        self.index("AGENTS.md")
        for value in ("/var/" + "home/demo/x", "/usr/" + "home/demo/x", "/" + "root/x", "~demo/x"):
            with self.subTest(path=value):
                self.write(self.repo / "AGENTS.md", value + "\n")
                block, files, _ = self.scan_direct()
                self.assertTrue(any(r["id"] == "I7" and r["pattern"] == "machine-path"
                                    for r in block["results"]))
                self.assertEqual(checkup.judge_payload(files), "")
        for value in ("/rooted/x", "https://example.org/var/" + "home/x"):
            self.assertIsNone(checkup.MACHINE_PATH.search(value))

    def test_rework_machine_path_punctuation(self):
        samples = ["file://" + "/Us" "ers/" + "fixture/x",
                   "dir:" + "/ho" "me/" + "fixture/x",
                   "a," + "/ho" "me/" + "fixture/y",
                   "<code>" + "/Us" "ers/" + "fixture/</code>",
                   "{" + "/ho" "me/" + "fixture/z}"]
        self.consent()
        self.index("AGENTS.md")
        for value in samples:
            with self.subTest(shape=samples.index(value)):
                self.assertIsNotNone(checkup.MACHINE_PATH.search(value))
                self.write(self.repo / "AGENTS.md", value + "\n")
                block, files, _ = self.scan_direct()
                self.assertTrue(any(r["id"] == "I7" and r["pattern"] == "machine-path"
                                    for r in block["results"]))
                self.assertEqual(checkup.judge_payload(files), "")
                self.assertNotIn(value, json.dumps(block))
        self.assertIsNone(checkup.MACHINE_PATH.search("https://example.org" + "/ho" "me/x"))

    def test_rework_indented_consent_is_off(self):
        self.write(self.repo / "AGENTS.md", "SAFE LINE\n")
        for indent in (" ", "    ", "\t"):
            self.consent("## Route judgment\n" + indent + "- Instruction check: on\n")
            self.assertEqual(self.run_check("--judge-payload"), "")

    def test_rework_additional_secret_shapes(self):
        samples = ["np" + "m_" + "x" * 36, "gl" + "pat-" + "x" * 20,
                   "AI" + "za" + "x" * 35,
                   "sk_" + "live_" + "x" * 24, "rk_" + "live_" + "x" * 24,
                   "ey" + "J" + "x" * 7 + "." + "y" * 10 + "." + "z" * 10,
                   "DB_" + "PASS = '" + "x" * 8 + "'",
                   "SERVICE_" + 'PASS: "' + "x" * 8 + '"']
        for value in samples:
            with self.subTest(shape=samples.index(value)):
                self.write(self.repo / "AGENTS.md", "OMIT WHOLE FILE\n" + value + "\n")
                block, files, _ = self.scan_direct()
                self.assertTrue(any(r["id"] == "I6" and r["status"] == "fail"
                                    for r in block["results"]))
                self.assertEqual(checkup.judge_payload(files), "")
                self.assertNotIn(value, json.dumps(block))
                self.assertNotIn(value, "\n".join(checkup.instruction_lines(block)))

    def test_rework_hex_revision_exclusions(self):
        for word in ("sha", "commit", "rev", "hash"):
            for count in (32, 40, 64):
                with self.subTest(word=word, count=count):
                    self.write(self.repo / "AGENTS.md", word + " api_key = " + "a" * count + "\n")
                    rows = self.scan_direct()[0]["results"]
                    self.assertEqual(any(r["pattern"] == "hex-assignment" for r in rows), count != 40)
        self.write(self.repo / "AGENTS.md", "api_key = " + "a" * 40 + "\n")
        self.assertTrue(any(r["pattern"] == "hex-assignment" for r in self.scan_direct()[0]["results"]))

    def test_rework_long_line_collect_and_payload(self):
        value = ("a_" + "password") * 26215
        value = value[:262144]
        self.assertEqual(len(value), 262144)
        self.write(self.repo / "AGENTS.md", value)
        self.consent()
        start = time.perf_counter()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(Path, "cwd", return_value=self.repo):
            data = checkup.collect()
            with mock.patch.object(sys, "argv", [str(SCRIPT), "--judge-payload"]), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(checkup.main(), 0)
                self.assertEqual(output.getvalue(), "")
        elapsed = time.perf_counter() - start
        print(f"long-line collect and payload: {elapsed:.3f}s")
        self.assertLess(elapsed, 2)
        rows = [r for r in data["instructions"]["results"] if r["pattern"] == "line-too-long"]
        self.assertEqual({r["id"] for r in rows}, {"I1", "I6"})
        self.assertTrue(all(r["status"] == "unverified" and r["reason"] == "line too long" for r in rows))
        self.assertNotIn(value, json.dumps(data))

    def test_rework_long_lines_skip_all_patterns(self):
        shapes = {
            "private-key-header": "-----BEGIN " + "A " * 100000,
            "access-key-id": "AK" + "IA" + "A" * 200000,
            "github-token": "github_" + "pat_" + "_" * 200000,
            "api-key": "s" + "k-" + "-" * 200000,
            "slack-token": "xo" + "xb-" + "-" * 200000,
            "bearer-token": "Authorization: " + " " * 200000,
            "url-credentials": "a" * 200000 + "://",
            "hex-assignment": "a" * 200000 + "!",
            "encoded-assignment": ": " + "A" * 200000,
            "npm-token": "np" + "m_" + "x" * 200000,
            "gitlab-token": "gl" + "pat-" + "x" * 200000,
            "google-api-key": "AI" + "za" + "x" * 200000,
            "stripe-key": "sk_" + "live_" + "x" * 200000,
            "jwt": "ey" + "J" + "x" * 200000 + ".",
            "machine-path": "/ho" "me/" + "x" * 200000,
        }
        for name, value in shapes.items():
            with self.subTest(pattern=name):
                self.write(self.repo / "AGENTS.md", "SAFE BUT OMIT\n" + value[:200000])
                self.write(self.repo / "AGENTS.md.bak-test", value[:200000])
                start = time.perf_counter()
                block, files, _ = self.scan_direct()
                self.assertEqual(checkup.judge_payload(files), "")
                elapsed = time.perf_counter() - start
                print(f"long-line {name}: {elapsed:.4f}s")
                self.assertLess(elapsed, 0.1)
                rows = [r for r in block["results"] if r["pattern"] == "line-too-long"]
                self.assertEqual({(r["id"], r["file"]) for r in rows},
                                 {("I1", "AGENTS.md"), ("I6", "AGENTS.md"), ("I6", "AGENTS.md.bak-test")})

    def test_include_cycle_counted_once_across_entry_points(self):
        for name, target in (("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")):
            self.write(self.repo / f".agents/rules/{name}.md",
                       f"---\ntrigger: manual\n---\n@[rule]({target}.md)\n")
        rows = [r for r in self.scan_direct()[0]["results"] if r["pattern"] == "include-cycle"]
        self.assertEqual(len(rows), 2)

    def test_rework_dense_include_performance(self):
        text = "---\ntrigger: manual\n---\n" + "".join(f"@[rule](r{n:02}.md)\n" for n in range(58))
        for n in range(58):
            self.write(self.repo / f".agents/rules/r{n:02}.md", text)
        start = time.perf_counter()
        block = self.scan_direct()[0]
        elapsed = time.perf_counter() - start
        print(f"dense include: {elapsed:.3f}s")
        self.assertLess(elapsed, 1)
        self.assertEqual(block["files"], 58)
        self.assertTrue(any(r["pattern"] == "include-cycle" for r in block["results"]))


if __name__ == "__main__":
    unittest.main()
