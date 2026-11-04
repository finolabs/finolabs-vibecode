"""Settings and hook behavior, using synthetic host files only."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
READER = ROOT / "skills/fnl-delegate/scripts/mode.py"
HOOK = ROOT / "scripts/session_start.py"
DEFAULTS = {"delegation_mode": "suggest", "routing": "on"}


class DelegationModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.config = self.home / ".finolabs/vibecode/host.md"
        self.config.parent.mkdir(parents=True)
        self.env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "")}

    def run_script(self, script=READER, env=None):
        result = subprocess.run([sys.executable, "-I", str(script)], env=env or self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def values(self):
        return json.loads(self.run_script())

    def test_missing_file_defaults(self):
        self.assertEqual(self.values(), DEFAULTS)

    def test_file_then_env_precedence(self):
        self.config.write_text("## Delegation mode\nmanual\n## Routing\noff\n")
        self.assertEqual(self.values(), {"delegation_mode": "manual", "routing": "off"})
        self.env.update(FNL_DELEGATION_MODE="auto", FNL_ROUTING="on")
        self.assertEqual(self.values(), {"delegation_mode": "auto", "routing": "on"})

    def test_legacy_config_counts_only_while_the_new_file_is_absent(self):
        legacy = self.home / ".config/finolabs-vibecode/host.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("## Delegation mode\nauto\n## Routing\noff\n")
        self.assertEqual(self.values(), {"delegation_mode": "auto", "routing": "off"})
        self.env["XDG_CONFIG_HOME"] = str(self.home / "xdg")
        self.assertEqual(self.values(), DEFAULTS)
        del self.env["XDG_CONFIG_HOME"]
        self.config.write_text("## Limits\n")
        self.assertEqual(self.values(), DEFAULTS)

    def test_override_path(self):
        custom = self.home / "custom.md"
        custom.write_text("## Delegation mode\nauto\n## Routing\noff\n")
        self.env["ORCHESTRATION_HOST_CONFIG"] = str(custom)
        self.assertEqual(self.values(), {"delegation_mode": "auto", "routing": "off"})

    def test_invalid_values_default_without_falling_through(self):
        self.config.write_text("## Delegation mode\nauto\n## Routing\noff\n")
        for value in ("invalid", "", "AUTO"):
            with self.subTest(value=value):
                self.env.update(FNL_DELEGATION_MODE=value, FNL_ROUTING=value)
                self.assertEqual(self.values(), DEFAULTS)
        self.env.pop("FNL_DELEGATION_MODE")
        self.env.pop("FNL_ROUTING")
        self.config.write_text("## Delegation mode\ninvalid\n## Routing\ninvalid\n")
        self.assertEqual(self.values(), DEFAULTS)

    def test_settings_require_second_level_headings(self):
        self.config.write_text("# Delegation mode\nauto\n# Routing\noff\n")
        self.assertEqual(self.values(), DEFAULTS)

    def test_corrupt_duplicate_and_multiline_values_default(self):
        for data in (b"\xff", b"## Delegation mode\nauto\n## Delegation mode\nmanual\n",
                     b"## Routing\noff\nextra\n"):
            with self.subTest(data=data):
                self.config.write_bytes(data)
                self.assertEqual(self.values(), DEFAULTS)

    def test_symlink_file_and_parent_are_not_followed(self):
        target = self.home / "target.md"
        target.write_text("## Delegation mode\nauto\n## Routing\noff\n")
        self.config.symlink_to(target)
        self.assertEqual(self.values(), DEFAULTS)
        self.config.unlink()
        linked = self.home / "linked"
        linked.symlink_to(target.parent, target_is_directory=True)
        self.env["ORCHESTRATION_HOST_CONFIG"] = str(linked / target.name)
        self.assertEqual(self.values(), DEFAULTS)

    def test_unreadable_file_defaults(self):
        spec = importlib.util.spec_from_file_location("mode_test", READER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(module.os, "open", side_effect=PermissionError):
            self.assertEqual(module.effective(), DEFAULTS)

    def test_routing_off_removes_only_router_instruction(self):
        self.config.write_text("## Routing\noff\n")
        text = self.run_script(HOOK)
        self.assertNotIn("fnl-coding-router", text)
        self.assertIn("fnl-delegate", text)

    def test_routing_on_and_corrupt_host_keep_instruction(self):
        for data in (b"## Routing\non\n", b"\xff", b"## Routing\ninvalid\n"):
            with self.subTest(data=data):
                self.config.write_bytes(data)
                self.assertIn("fnl-coding-router", self.run_script(HOOK))

    def test_environment_controls_hook_and_invalid_override_fails_open(self):
        self.config.write_text("## Routing\non\n")
        self.env["FNL_ROUTING"] = "off"
        self.assertNotIn("fnl-coding-router", self.run_script(HOOK))
        self.config.write_text("## Routing\noff\n")
        self.env["FNL_ROUTING"] = "invalid"
        self.assertIn("fnl-coding-router", self.run_script(HOOK))

    def test_host_hook_commands_obey_switch_and_exit_zero(self):
        for host, variable in (("claude", "CLAUDE_PLUGIN_ROOT"), ("codex", "CODEX_PLUGIN_ROOT")):
            config = json.loads((ROOT / f".{host}-plugin/hooks.json").read_text())
            commands = [h["command"] for g in config["hooks"]["SessionStart"] for h in g["hooks"]
                        if "session_start.py" in h["command"]]
            self.assertEqual(len(commands), 1)
            for value in ("on", "off", "invalid"):
                with self.subTest(host=host, routing=value):
                    self.config.write_text(f"## Routing\n{value}\n")
                    result = subprocess.run(["sh", "-c", commands[0]], input="{}", text=True,
                                            capture_output=True, env={**self.env, variable: str(ROOT)}, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual("fnl-coding-router" in result.stdout, value != "off")

    def test_hook_fails_open_when_reader_unavailable(self):
        copy = self.home / "plugin/scripts/session_start.py"
        copy.parent.mkdir(parents=True)
        copy.write_bytes(HOOK.read_bytes())
        self.assertIn("fnl-coding-router", self.run_script(copy))


if __name__ == "__main__":
    unittest.main()
