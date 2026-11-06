"""Compaction adds a handover; all other hook output retains its bytes."""
import contextlib
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

from tests.test_handover_state import hs, setup_store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("session_start", ROOT / "scripts/session_start.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class SessionStartTest(unittest.TestCase):
    def run_hook(self, raw, routing="on", reader=None):
        out = io.StringIO()
        quota = mock.Mock()
        quota.worker_guard.return_value = False
        mode = mock.Mock()
        mode.effective.return_value = {"routing": routing}
        handover = mock.Mock()
        handover.read = reader or mock.Mock(return_value="Saved next action\n")
        with mock.patch.dict(sys.modules, {"quota_probe": quota, "mode": mode,
                                          "handover_state": handover}), \
                mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")), \
                contextlib.redirect_stdout(out):
            code = hook.main()
        self.assertEqual(code, 0)
        return out.getvalue().encode(), handover.read

    def baseline(self, routing):
        text = (ROOT / "rules/AGENTS.md").read_text(encoding="utf-8")
        if routing == "off":
            text = "\n".join(line for line in text.splitlines() if "fnl-coding-router" not in line) + "\n"
        return text.encode()

    def test_compact_appends_handover(self):
        raw = json.dumps({"source": "compact", "session_id": "synthetic"}).encode()
        out, reader = self.run_hook(raw)
        self.assertEqual(out, self.baseline("on") + b"\nHandover before compaction\nSaved next action\n")
        reader.assert_called_once_with("synthetic")

    def test_noncompact_invalid_or_oversized_input_keeps_original_bytes(self):
        inputs = [b"", b"{broken", b"\xff", b"null", b"[]", b"1", b'"compact"',
                  b'{"source":"compact"}', b'{"source":"compact","session_id":null}',
                  b'{"source":"compact","session_id":1}', b'{"source":"compact","session_id":""}',
                  b'{"source":"compact","session_id":"synthetic"}' + b" " * 65536]
        inputs += [json.dumps({"source": source, "session_id": "synthetic"}).encode()
                   for source in ("startup", "resume", "clear", "other", None, 0, [], {})]
        for routing in ("on", "off"):
            for raw in inputs:
                with self.subTest(routing=routing, raw=raw[:80]):
                    out, reader = self.run_hook(raw, routing)
                    self.assertEqual(out, self.baseline(routing))
                    reader.assert_not_called()

    def test_read_error_or_empty_handover_adds_nothing(self):
        raw = b'{"source":"compact","session_id":"synthetic"}'
        for reader in (mock.Mock(return_value=""), mock.Mock(side_effect=OSError("private text"))):
            out, _ = self.run_hook(raw, reader=reader)
            self.assertEqual(out, self.baseline("on"))

    def test_real_store_reinjection_and_unsafe_file_suppression(self):
        root = setup_store(self)
        hs.write("synthetic", "Goal\nDecisions\nWork in progress\nNext action\n")
        raw = b'{"source":"compact","session_id":"synthetic"}'
        out, _ = self.run_hook(raw, reader=hs.read)
        self.assertEqual(out, self.baseline("on") + b"\nHandover before compaction\nGoal\nDecisions\nWork in progress\nNext action\n")
        path = root / "state/handover" / hs.filename("synthetic")
        path.chmod(0o666)
        out, _ = self.run_hook(raw, reader=hs.read)
        self.assertEqual(out, self.baseline("on"))

    def test_exact_input_cap_and_stdin_error(self):
        raw = b'{"source":"compact","session_id":"synthetic"}'
        out, _ = self.run_hook(raw + b" " * (65536 - len(raw)))
        self.assertIn(b"Handover before compaction", out)
        # A failed stdin read is also tested with the real hook entry point.
        quota = mock.Mock()
        quota.worker_guard.return_value = False
        mode = mock.Mock()
        mode.effective.return_value = {"routing": "on"}
        out = io.StringIO()
        with mock.patch.dict(sys.modules, {"quota_probe": quota, "mode": mode}), \
                mock.patch.object(sys, "stdin") as stdin, contextlib.redirect_stdout(out):
            stdin.buffer.read.side_effect = OSError("private text")
            self.assertEqual(hook.main(), 0)
        self.assertEqual(out.getvalue().encode(), self.baseline("on"))

    def test_hook_declarations_retain_pre_steward_bytes(self):
        # Baseline main 421b2d0; changing Codex declarations requires renewed trust.
        expected = {"claude": "72844c7d76488bf4b60a78ef28826a86269772c79423c6835197c1562086dc9b",
                    "codex": "9ca626fd3230421f47b945aa7b33cd0582acb2072926a226a0cc3f95fb07861e"}
        for host, digest in expected.items():
            raw = (ROOT / f".{host}-plugin/hooks.json").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
