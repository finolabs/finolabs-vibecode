"""The steward table and its advisory instructions implement option B."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("context_steward", ROOT / "scripts/context_steward.py")
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


class ContextStewardTest(unittest.TestCase):
    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["context_steward.py", *args]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cs.main()
        return code, out.getvalue(), err.getvalue()

    def test_every_row_and_exact_eighty_and_hundred_percent_boundaries(self):
        for boundary in ("yes", "no", "unknown"):
            for used, expected in ((0, "ok"), (79, "ok"), (80, "prepare"), (99, "prepare"),
                                   (100, "wait" if boundary == "no" else "compact"),
                                   (1000, "wait" if boundary == "no" else "compact")):
                with self.subTest(used=used, boundary=boundary):
                    result = cs.check(used, 100, 100, boundary)
                    self.assertEqual(result["action"], expected)
                    self.assertEqual(set(result), {"action", "reason"})
                    self.assertEqual(len(result["reason"].splitlines()), 1)
                    code, out, err = self.cli("check", "--used", str(used), "--window", "100",
                                              "--threshold", "100", "--boundary", boundary)
                    self.assertEqual((code, err), (0, ""))
                    self.assertEqual(len(out.splitlines()), 1)
                    self.assertEqual(json.loads(out), result)
        self.assertEqual(cs.check(80, 1000, 101)["action"], "ok")
        self.assertEqual(cs.check(81, 1000, 101)["action"], "prepare")
        self.assertEqual(cs.check(800, 1000, 1000)["action"], "prepare")

    def test_invalid_numbers_boundaries_and_fixed_cli_errors(self):
        for name in ("used", "window", "threshold"):
            for value in (-1, 1.5, True, "1", None):
                args = dict(used=0, window=100, threshold=100)
                args[name] = value
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    cs.check(**args)
        for args in ((0, 0, 1), (1001, 100, 100), (0, 100, 0), (0, 100, 101)):
            with self.assertRaises(ValueError):
                cs.check(*args)
        for boundary in ("maybe", "", None, [], True):
            with self.assertRaises(ValueError):
                cs.check(100, 100, 100, boundary)
        for name in ("used", "window", "threshold"):
            for value in ("private-input", "1.5", "true", "-1"):
                args = {"used": "0", "window": "100", "threshold": "100"}
                args[name] = value
                argv = [item for key, val in args.items() for item in ("--" + key, val)]
                self.assertEqual(self.cli("check", *argv),
                                 (2, "", "Context steward refused: invalid input.\n"))
        for args in ((), ("check",), ("private-input",),
                     ("check", "--used", "100", "--window", "100", "--threshold", "100", "--boundary", "private-input")):
            self.assertEqual(self.cli(*args), (2, "", "Context steward refused: invalid input.\n"))

    def test_default_boundary_is_unknown_and_threshold_is_required(self):
        code, out, err = self.cli("check", "--used", "100", "--window", "100", "--threshold", "100")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), cs.check(100, 100, 100, "unknown"))
        self.assertEqual(self.cli("check", "--used", "100", "--window", "100"),
                         (2, "", "Context steward refused: invalid input.\n"))

    def test_agent_frontmatter_and_enforcers(self):
        text = (ROOT / "agents/fnl-steward.md").read_text()
        front = text.split("---", 2)[1]
        for line in ("name: fnl-steward", "model: inherit", "disallowedTools: [Write, Edit, NotebookEdit]"):
            self.assertIn(line, front)
        for phrase in ("fast", "host config", "context_steward.py", "typesafe-ai", "unknown",
                       "spend guard", "validated reply", "supplied summary", "starts no session"):
            self.assertIn(phrase, " ".join(text.split()))
        hygiene = (ROOT / "skills/fnl-session-hygiene/SKILL.md").read_text().split("## Context pressure", 1)[1].split("\n## ", 1)[0]
        for phrase in ("fnl-steward", "prepare", "context_steward.py", "handover_state.py",
                       "host enforces", "advisory (agent judgment)", "unverified on every host", "standalone"):
            self.assertIn(phrase, hygiene)
        for path in ("fnl-delegate/SKILL.md", "fnl-setup/references/features/compaction.md"):
            text = (ROOT / "skills" / path).read_text()
            paragraph = next(p for p in text.split("\n\n") if "fnl-steward" in p)
            self.assertIn("advisory (agent judgment)", paragraph)

    def test_public_docs_and_spec_index_describe_local_handover(self):
        privacy = (ROOT / "PRIVACY.md").read_text()
        paragraph = next(p for p in privacy.split("\n\n") if "state/handover" in p)
        for phrase in ("0600", "0700", "user's own text", "never sent", "24-hour", "20", "8 KiB"):
            self.assertIn(phrase, paragraph)
        self.assertIn("fnl-steward", (ROOT / "README.md").read_text())
        changelog = (ROOT / "CHANGELOG.md").read_text().split("## [Unreleased]", 1)[1]
        self.assertIn("steward", changelog)
        self.assertIn("compaction-steward.md", (ROOT / "docs/specs/index.md").read_text())
