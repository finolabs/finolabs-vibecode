"""Bounded, read-only evidence for setup Check mode, using only fake host data."""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
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
        self.env = {"HOME": str(self.home), "PATH": str(self.bin)}
        self.write(self.repo / ".git/info/exclude", ".finolabs/\n")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_check(self, *args):
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=self.repo,
                                env=self.env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
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

    def test_missing_host_config(self):
        self.assertEqual(self.setup_item("host config")["status"], "missing")

    def test_missing_agent_skills_block(self):
        self.write(self.repo / "AGENTS.md", "# Project\n")
        self.assertEqual(self.setup_item("agent skills")["status"], "missing")

    def test_required_headings_and_override(self):
        config = self.write(self.base / "custom.md", "## Limits\n")
        self.env["ORCHESTRATION_HOST_CONFIG"] = str(config)
        row = self.setup_item("host config")
        self.assertEqual(row["status"], "missing")
        self.assertIn("Briefs folder", row["reason"])
        config.write_text("\n".join("## " + h for h in sorted(checkup.HEADINGS)))
        self.assertEqual(self.setup_item("host config")["status"], "ok")
        template = (ROOT / "skills/fnl-delegate/references/host-template.md").read_text()
        self.assertEqual(checkup.HEADINGS, set(re.findall(r"^## (.+)$", template, re.M)) - {"Effort preference", "Delegation mode", "Routing"})

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
            expected.extend(f'{host} / {r["check"]}: {r["status"]} - {r["reason"]}' for r in rows)
        self.assertEqual(text.splitlines(), expected)
        for rows in [*data["hosts"].values(), data["setup"]]:
            self.assertTrue(all(r["status"] in {"ok", "missing", "unverified"} for r in rows))

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


if __name__ == "__main__":
    unittest.main()
