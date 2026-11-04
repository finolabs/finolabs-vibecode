"""Fixed-executable inventory, consent and section boundaries with fake CLIs only."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/fnl-scan-agents/scripts/agent_scan.py"
spec = importlib.util.spec_from_file_location("agent_scan", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class AgentScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.config = self.home / ".finolabs/vibecode/host.md"
        self.config.parent.mkdir(parents=True)
        self.env = {"HOME": str(self.home), "PATH": str(self.bin)}
        for name in ("claude", "codex"):
            path = self.bin / name
            path.write_text('#!/bin/sh\n[ "$#" = 1 ] && [ "$1" = --version ] || exit 91\nprintf "fake 1.0\\n"\n')
            path.chmod(0o755)

    def run_scan(self, *args):
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], env=self.env,
                                capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout.splitlines()), 40)
        return result.stdout

    def test_two_agents_consent_models_and_second_run(self):
        prefix, suffix = b"# Host\r\n\r\n## Limits\r\nkeep exactly\r\n\r\n", b"## Other\r\nuntouched\r\n"
        self.config.write_bytes(prefix + b"## Agents on this machine\r\n\r\nold\r\n\r\n" + suffix)
        before = self.config.read_bytes()
        args = ("--host", "codex", "--models", "codex=confirmed-model")
        preview = self.run_scan(*args)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertIn("| Claude Code | yes | fake 1.0 | unverified |", preview)
        self.assertIn("| Codex | yes | fake 1.0 | confirmed-model |", preview)
        self.assertIn("| Antigravity | no | unverified | unverified |", preview)
        self.assertIn("Updated Agents", self.run_scan(*args, "--yes"))
        after = self.config.read_bytes()
        self.assertTrue(after.startswith(prefix))
        self.assertTrue(after.endswith(suffix))
        self.assertIn("No difference.", self.run_scan("--host", "codex"))
        self.assertEqual(after, self.config.read_bytes())

    def test_large_old_section_still_has_bounded_preview(self):
        self.config.write_text("## Agents on this machine\n" + "old\n" * 100)
        text = self.run_scan("--host", "codex")
        self.assertIn("replacing current section", text)
        self.assertIn("| Antigravity | no |", text)
        self.assertEqual(self.config.read_text().count("old"), 100)

    def test_explicit_host_and_symlink_refusal(self):
        self.assertNotIn("Coordinator:", self.run_scan())
        target = self.home / "target.md"
        target.write_text("# keep\n")
        self.config.symlink_to(target)
        self.assertIn("unsafe path", self.run_scan("--host", "claude", "--yes"))
        self.assertEqual(target.read_text(), "# keep\n")
        self.config.unlink()
        self.config.parent.rmdir()
        self.config.parent.symlink_to(self.bin, target_is_directory=True)
        self.assertIn("unsafe path", self.run_scan("--host", "claude", "--yes"))
        self.assertFalse((self.bin / "host.md").exists())

    def test_timeout_untrusted_version_and_fixed_commands(self):
        with mock.patch.object(scan.shutil, "which", side_effect=lambda n: "/fixed/" + n), \
                mock.patch.object(scan.subprocess, "run") as run:
            run.side_effect = [subprocess.TimeoutExpired("claude", 3),
                               subprocess.CompletedProcess([], 0, b"v1\n|<`\x1b" + b"x" * 250, b""),
                               subprocess.CompletedProcess([], 1, b"failed", b"")]
            text = scan.inventory("claude", "", {})
            self.assertEqual([c.args[0] for c in run.call_args_list],
                             [["/fixed/" + n, "--version"] for n in ("claude", "codex", "agy")])
            for call in run.call_args_list:
                self.assertEqual(call.kwargs["timeout"], 3)
                self.assertFalse(call.kwargs["shell"])
            self.assertEqual(len(text.splitlines()), 10)
            self.assertNotIn("\x1b", text)
            self.assertNotIn("<", text)
            version = next(l for l in text.splitlines() if l.startswith("| Codex")).split("|")[3].strip()
            self.assertLessEqual(len(version), 200)


if __name__ == "__main__":
    unittest.main()
