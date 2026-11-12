"""The compaction reminder is constant, non-blocking and independent of input."""

import json
import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts/precompact.py"
REMINDER = (b"The summary must keep: the goal and acceptance criteria, settled decisions with their dates, "
            b"work in progress, open background runs and pull requests, the next action, and whether a "
            b"handover was saved with handover_state.py.\n")


class PreCompactTest(unittest.TestCase):
    def test_any_input_exits_zero_with_only_the_reminder(self):
        self.assertTrue(HOOK.is_file(), "PreCompact reminder is missing")
        for raw in (b"", b"{malformed\xff", b"x" * (2 * 1024 * 1024)):
            with self.subTest(size=len(raw)):
                result = subprocess.run([sys.executable, "-I", str(HOOK)], input=raw,
                                        capture_output=True, timeout=5)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, REMINDER, b""))
                self.assertNotRegex(result.stdout.decode(), r"[/\\]|[A-Za-z]:")

    def test_no_input_files_or_network_are_read(self):
        code = compile(HOOK.read_bytes(), str(HOOK), "exec")
        with mock.patch("builtins.open") as files, mock.patch.object(os, "open") as fds, \
                mock.patch.object(os, "read") as reads, mock.patch.object(socket, "socket") as network, \
                mock.patch.object(sys, "stdin") as stdin, mock.patch.object(os, "write") as output:
            exec(code, {"__name__": "__main__"})
            for blocked in (files, fds, reads, network, stdin):
                self.assertEqual(blocked.mock_calls, [])
            output.assert_called_once_with(1, REMINDER)

    def test_exception_exits_zero_silently(self):
        # Run the entry point with an output failure, including a closed pipe.
        code = ("import os, runpy, sys\n"
                "def fail(*args): raise BrokenPipeError('synthetic')\n"
                "os.write = fail\n"
                "runpy.run_path(sys.argv[1], run_name='__main__')\n")
        result = subprocess.run([sys.executable, "-I", "-c", code, str(HOOK)],
                                capture_output=True, timeout=5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))

    def test_host_declarations_run_the_shared_script(self):
        for host, variable in (("claude", "CLAUDE_PLUGIN_ROOT"), ("codex", "CODEX_PLUGIN_ROOT")):
            config = json.loads((ROOT / f".{host}-plugin/hooks.json").read_text())
            hook = config["hooks"]["PreCompact"][0]["hooks"][0]
            self.assertFalse(hook.get("async", False))
            self.assertIn("/scripts/precompact.py", hook["command"])
            result = subprocess.run(["sh", "-c", hook["command"]], input=b"{}",
                                    env={"PATH": os.defpath, variable: str(ROOT)},
                                    capture_output=True, timeout=5)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, REMINDER, b""))
