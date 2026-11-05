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
DEFAULTS = {"delegation_mode": "suggest", "routing": "on", "auto_gate": "off"}


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

    def mode_action(self, *args):
        result = subprocess.run([sys.executable, "-I", str(READER), *args], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_show_sources_and_env_override(self):
        self.assertIn("source: default", self.mode_action("show"))
        self.config.write_text("## Delegation mode\nmanual\n## Routing\noff\n")
        self.assertIn("source: host config", self.mode_action("show"))
        self.env["FNL_DELEGATION_MODE"] = "auto"
        output = self.mode_action("show")
        self.assertIn("Delegation mode: auto (source: FNL_DELEGATION_MODE)", output)
        self.assertIn("overrides the file; writing the file has no effect", output)
        self.env["FNL_ROUTING"] = "invalid"
        self.assertIn("Routing: on (source: FNL_ROUTING (invalid; default used))", self.mode_action("show"))

    def test_set_requires_yes_and_preserves_other_sections(self):
        prefix = b"# Host\r\n\r\n## Limits\r\nretain \xc3\xa9\r\n\r\n"
        middle = b"## Agents on this machine\r\nkeep table\r\n\r\n"
        suffix = b"## Other\r\nlast byte"
        self.config.write_bytes(prefix + b"## Delegation mode\r\nmanual\r\n\r\n" + middle +
                                b"## Routing\r\non\r\n\r\n" + suffix)
        before = self.config.read_bytes()
        args = ("set", "--delegation-mode", "auto", "--routing", "off")
        self.assertIn("manual -> auto", self.mode_action(*args))
        self.assertEqual(before, self.config.read_bytes())
        self.assertIn("Updated host settings", self.mode_action(*args, "--yes"))
        after = self.config.read_bytes()
        self.assertTrue(after.startswith(prefix))
        self.assertTrue(after.endswith(suffix))
        self.assertIn(middle, after)
        self.assertEqual(self.values(), {"delegation_mode": "auto", "routing": "off", "auto_gate": "off"})
        self.assertIn("No difference", self.mode_action(*args, "--yes"))

    def test_set_new_file_and_refuse_symlinks(self):
        self.assertIn("Updated", self.mode_action("set", "--routing", "off", "--yes"))
        self.assertTrue(self.config.exists())
        target = self.home / "target.md"
        target.write_text("# preserve\n")
        self.config.unlink()
        self.config.symlink_to(target)
        self.assertIn("unsafe path", self.mode_action("set", "--routing", "off", "--yes"))
        self.assertEqual(target.read_text(), "# preserve\n")
        self.config.unlink()
        self.config.parent.rmdir()
        self.config.parent.symlink_to(self.home, target_is_directory=True)
        self.assertIn("unsafe path", self.mode_action("set", "--routing", "off", "--yes"))
        self.assertFalse((self.home / "host.md").exists())


    def test_auto_gate_requires_config_opt_in_and_shows_source(self):
        self.env["FNL_AUTO_GATE"] = "on"
        self.assertIn("Auto gate: off (source: default)", self.mode_action("show"))
        self.assertIn("Preview only", self.mode_action("set", "--auto-gate", "on"))
        self.assertFalse(self.config.exists())
        self.assertIn("Updated", self.mode_action("set", "--auto-gate", "on", "--yes"))
        self.assertIn("Auto gate: on (source: host config)", self.mode_action("show"))
        for value in ("off", "0", "false", "no", "OFF", "False"):
            self.env["FNL_AUTO_GATE"] = value
            self.assertIn("Auto gate: off (source: FNL_AUTO_GATE)", self.mode_action("show"))
        self.env["FNL_AUTO_GATE"] = "invalid"
        self.assertEqual(self.values()["auto_gate"], "on")

    def test_shared_copies_match(self):
        for name, copies in (
            ("mode.py", ("fnl-delegate", "fnl-setup", "fnl-set-mode")),
            ("auto_gate.py", ("fnl-delegate",)),
        ):
            for skill in copies:
                with self.subTest(name=name, skill=skill):
                    self.assertEqual((ROOT / "scripts" / name).read_bytes(),
                                     (ROOT / "skills" / skill / "scripts" / name).read_bytes())

    def test_missing_file_defaults(self):
        self.assertEqual(self.values(), DEFAULTS)

    def test_file_then_env_precedence(self):
        self.config.write_text("## Delegation mode\nmanual\n## Routing\noff\n")
        self.assertEqual(self.values(), {"delegation_mode": "manual", "routing": "off", "auto_gate": "off"})
        self.env.update(FNL_DELEGATION_MODE="auto", FNL_ROUTING="on")
        self.assertEqual(self.values(), {"delegation_mode": "auto", "routing": "on", "auto_gate": "off"})

    def test_legacy_config_counts_only_while_the_new_file_is_absent(self):
        legacy = self.home / ".config/finolabs-vibecode/host.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("## Delegation mode\nauto\n## Routing\noff\n")
        self.assertEqual(self.values(), {"delegation_mode": "auto", "routing": "off", "auto_gate": "off"})
        self.env["XDG_CONFIG_HOME"] = str(self.home / "xdg")
        self.assertEqual(self.values(), DEFAULTS)
        del self.env["XDG_CONFIG_HOME"]
        self.config.write_text("## Limits\n")
        self.assertEqual(self.values(), DEFAULTS)

    def test_override_path(self):
        custom = self.home / "custom.md"
        custom.write_text("## Delegation mode\nauto\n## Routing\noff\n")
        self.env["ORCHESTRATION_HOST_CONFIG"] = str(custom)
        self.assertEqual(self.values(), {"delegation_mode": "auto", "routing": "off", "auto_gate": "off"})

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
