"""Bounded, read-only evidence for setup Check mode, using only fake host data."""

import datetime
import importlib.util
import json
import os
import struct
import hashlib
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

    def inventory(self, date):
        return "## Agents on this machine\n\nCoordinator: Codex\n\n" + "\n".join(
            f"| {name} | yes | fake | unverified | {date} |"
            for name in ("Claude Code", "Codex", "Antigravity")) + "\n"

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
                             ("knowledge", self.repo / "AGENTS.md")):
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
        config.write_text("\n".join("## " + h for h in sorted(checkup.HEADINGS)))
        self.assertEqual(self.setup_item("host config")["status"], "ok")
        template = (ROOT / "skills/fnl-delegate/references/host-template.md").read_text()
        self.assertEqual(checkup.HEADINGS, set(re.findall(r"^## (.+)$", template, re.M)) - {"Effort preference", "Delegation mode", "Routing", "Agents on this machine"})

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
            self.assertTrue(all(r["status"] in {"ok", "missing", "unverified"} for r in rows))

    def test_legacy_host_config_counts_only_while_new_file_is_absent(self):
        headings = "\n".join("## " + h for h in sorted(checkup.HEADINGS))
        legacy = self.write(self.home / ".config/finolabs-vibecode/host.md", headings)
        self.env.pop("XDG_CONFIG_HOME", None)
        self.assertEqual(self.setup_item("host config")["status"], "ok")
        self.write(self.home / ".finolabs/vibecode/host.md", "## Limits\n")
        self.assertEqual(self.setup_item("host config")["status"], "missing")
        legacy.unlink()

    def test_review_adoption_inside_the_generated_paragraph(self):
        skill = (ROOT / "skills/fnl-setup/SKILL.md").read_text()
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
                   "~~~text\n@/outside/AGENTS.md\n~~~\n@notes.md\n@missing/AGENTS.md\n@a/CLAUDE.md\n@a/CLAUDE.md\n")
        for n in range(1, 6):
            self.write(self.repo.joinpath(*(["a"] * n), "CLAUDE.md"), "@a/CLAUDE.md\n" if n < 5 else "Fifth level.\n")
        self.write(self.home / ".codex/AGENTS.md", "@AGENTS.override.md\n")
        self.write(self.repo / ".agents/rules/example.md", "---\ntrigger: manual\n---\n@GEMINI.md\n")
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
        self.write(self.repo / "AGENTS.md", "Use fnl-" + "knowledge" + ".\n")
        rows = self.instruction_rows("I14")
        self.assertEqual([(r["file"], r["line"], r["pattern"]) for r in rows], [("AGENTS.md", 1, "retired-skill")])

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
        self.assertIn("SAFE LINE", self.run_check("--judge-payload"))
        self.consent("## Route judgment\n- Instruction check: off\n")
        self.assertEqual(self.run_check("--judge-payload"), "")
        self.env["ORCHESTRATION_HOST_CONFIG"] = str(outside)
        self.assertIn("SAFE LINE", self.run_check("--judge-payload"))

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


if __name__ == "__main__":
    unittest.main()
