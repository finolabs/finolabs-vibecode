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

    def test_retired_agent_procedure_is_self_contained(self):
        self.assertFalse((ROOT / "agents/fnl-steward.md").exists())
        self.assertFalse((ROOT / "agents/fnl-verifier.md").exists())
        folder = ROOT / "skills/session-hygiene"
        self.assertEqual((folder / "scripts/context_steward.py").read_bytes(),
                         (ROOT / "scripts/context_steward.py").read_bytes())
        hygiene = (folder / "SKILL.md").read_text().split("## Context pressure", 1)[1].split("\n## ", 1)[0]
        hygiene += (folder / "references/context-settings.md").read_text()
        for phrase in ("prepare", "context_steward.py", "handover_state.py", "judge.py",
                       "host enforces", "advisory, agent judgment", "unverified on every host", "standalone",
                       "Only when the script says `compact`", "then run `context_steward.py check` again",
                       "small host model", "unvalidated"):
            self.assertIn(phrase, hygiene)
        self.assertNotIn("fnl-steward", hygiene)
        delegate = (ROOT / "skills/delegate/SKILL.md").read_text()
        self.assertNotIn("fnl-verifier", delegate)
        self.assertNotIn("fnl-steward", delegate)
        self.assertIn("route reviews with `review_route.py`", delegate)

    def test_public_docs_and_spec_index_describe_local_handover(self):
        privacy = (ROOT / "PRIVACY.md").read_text()
        paragraph = next(p for p in privacy.split("\n\n") if "state/handover" in p)
        for phrase in ("0600", "0700", "user's own text", "never sent", "24-hour", "20", "8 KiB"):
            self.assertIn(phrase, paragraph)
        changelog = (ROOT / "CHANGELOG.md").read_text().split("## [Unreleased]", 1)[1]
        self.assertIn("steward", changelog)
        self.assertIn("compaction-steward.md", (ROOT / "docs/specs/index.md").read_text())
