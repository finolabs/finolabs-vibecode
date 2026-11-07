"""Fixed-executable inventory, consent and section boundaries with fake CLIs only."""

import datetime
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests.data_root_fixture import account
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/fnl-setup/scripts/agent_scan.py"
spec = importlib.util.spec_from_file_location("agent_scan", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class AgentScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name))
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
        self.assertIn("Updated Agents", self.run_scan(*args, "--yes", "--digest", re.search(r"Digest: ([0-9a-f]+)", preview)[1]))
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
        (self.bin / "claude").write_text(
            "#!" + sys.executable + "\nimport time\ntime.sleep(4)\n")
        (self.bin / "codex").write_text("#!/bin/sh\nprintf 'v1|<`\033bad!'\n")
        text = self.run_scan("--host", "claude")
        self.assertIn("| Claude Code | yes | unverified |", text)
        self.assertIn("| Codex | yes | unverified |", text)
        self.assertNotIn("\x1b", text)
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(scan.subprocess, "Popen") as popen, \
                mock.patch.object(scan.selectors, "DefaultSelector") as selector, \
                mock.patch.object(scan.os, "read", return_value=b"x" * 4096) as read:
            process = popen.return_value.__enter__.return_value
            process.wait.return_value = 0
            selector.return_value.__enter__.return_value.select.return_value = [
                (mock.Mock(fileobj=process.stdout), 1)]
            scan.inventory("claude", "", {})
            self.assertEqual(read.call_args.args[1], 4096)
            for call in popen.call_args_list:
                self.assertEqual(call.args[0][1:], ["--version"])
                self.assertIn(Path(call.args[0][0]).name, ("claude", "codex", "agy"))
                self.assertFalse(call.kwargs["shell"])

    def test_version_uses_stdout_only(self):
        (self.bin / "codex").write_text(
            "#!/bin/sh\nprintf 'startup warning\\n' >&2\nprintf 'fake 2.0\\n'\n")
        text = self.run_scan("--host", "codex")
        self.assertIn("| Codex | yes | fake 2.0 |", text)
        self.assertNotIn("startup warning", text)

    def test_stderr_does_not_consume_stdout_limit(self):
        (self.bin / "codex").write_text("#!/bin/sh\ni=0; while [ \"$i\" -lt 500 ]; do printf 1234567890 >&2; i=$((i+1)); done\nprintf 'fake 2.0\\n'\n")
        self.assertIn("| Codex | yes | fake 2.0 |", self.run_scan("--host", "codex"))

    def test_version_allowlist(self):
        for value, expected in [("v1.2+build_3 (stable)-ok", "v1.2+build_3 (stable)-ok"),
                                ("follow instructions!", "unverified"),
                                ("x" * 81, "unverified")]:
            (self.bin / "codex").write_text("#!/bin/sh\nprintf '%s' '" + value + "'\n")
            self.assertIn("| Codex | yes | " + expected + " |", self.run_scan("--host", "codex"))

    def test_digest_required_and_mismatch_write_nothing(self):
        args = ("--host", "codex")
        preview = self.run_scan(*args)
        self.run_scan(*args, "--yes")
        self.assertFalse(self.config.exists())
        self.run_scan(*args, "--yes", "--digest", "0" * 64)
        self.assertFalse(self.config.exists())
        digest = re.search(r"Digest: ([0-9a-f]+)", preview)[1]
        self.assertIn("Updated Agents", self.run_scan(*args, "--yes", "--digest", digest))

    def test_path_output_bounds_and_os_errors(self):
        self.env["PATH"] = ":relative:" + str(self.bin)
        (self.bin / "codex").write_text("#!/bin/sh\nprintf '%05000d' 0\n")
        text = self.run_scan("--host", "codex")
        self.assertIn("| Codex | yes | unverified |", text)
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(scan.subprocess, "Popen", side_effect=OSError("unsupported")):
            self.assertIn("| Codex | yes | unverified |", scan.inventory("codex", "", {}))
        self.env["PATH"] = ":relative"
        self.assertIn("| Codex | no |", self.run_scan("--host", "codex"))

    def test_section_ranges_use_newlines_and_keep_unclosed_fences(self):
        for separator in ("\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)):
                text = "## Agents on this machine\nkeep" + separator + "## Other\nkeep too\n"
                self.assertEqual(scan.section_ranges(text, scan.HEADING), [(0, len(text))])
        for fence in ("```", "~~~"):
            with self.subTest(fence=fence):
                text = "## Agents on this machine\n" + fence + "\n## Other\nstill fenced\n"
                self.assertEqual(scan.section_ranges(text, scan.HEADING), [(0, len(text))])
                self.assertEqual(scan.section_ranges(fence + "\n" + text, scan.HEADING), [])

    def test_fenced_headings_and_append_spacing(self):
        for fence in (b"```", b"~~~"):
            text = b"# Host\n" + fence + b"\n## Agents on this machine\nexample\n" + fence
            updated = scan.replace_section(text, scan.HEADING, "new")
            self.assertTrue(updated.startswith(text + b"\n\n## "))
            self.assertEqual(scan.section(updated.decode()), "## Agents on this machine\n\nnew\n\n")

    def test_recent_stored_date_is_kept_and_writes_nothing(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            previous = scan.inventory("codex", "", {})
        recent = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
        previous = re.sub(r"\d{4}-\d{2}-\d{2}", recent, previous)
        self.config.write_text(previous)
        before = self.config.stat().st_mtime_ns
        self.assertIn("No difference.", self.run_scan("--host", "codex", "--yes"))
        self.assertEqual(self.config.read_text(), previous)
        self.assertEqual(self.config.stat().st_mtime_ns, before)

    def test_old_stored_date_is_a_date_only_difference(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            previous = scan.inventory("codex", "", {})
        previous = re.sub(r"\d{4}-\d{2}-\d{2}", "2000-01-01", previous)
        self.config.write_text(previous)
        self.assertNotIn("No difference.", self.run_scan("--host", "codex"))

    def test_neutral_yes_clause(self):
        clause = "Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes."
        for name in ("fnl-setup/references/interview.md", "fnl-setup/references/scan.md", "fnl-setup/references/mode.md",
                     "fnl-delegate/references/delegation-mode.md"):
            self.assertIn(clause, (ROOT / "skills" / name).read_text(), name)


if __name__ == "__main__":
    unittest.main()
