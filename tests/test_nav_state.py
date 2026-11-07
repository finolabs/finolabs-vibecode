"""Navigator state collection, payload validation, report verification and agent contract tests."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nav_state", ROOT / "scripts/nav_state.py")
ns = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ns)


class NavStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = account(self, self.base / "home")
        self.data = self.home / ".finolabs/vibecode"
        self.data.mkdir(parents=True, exist_ok=True)
        self.repo = self.base / "synthetic-repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()

    def cli(self, *args, stdin_text=None):
        out, err = io.StringIO(), io.StringIO()
        inp = io.StringIO(stdin_text or "")
        with mock.patch.object(sys, "stdin", inp), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = ns.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def write_anchors(self, content, name="AGENTS.md"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_collect_allowed_fields_only_and_parses_outcome_speckit_and_work_record(self):
        anchors = self.write_anchors(
            "# Synthetic context\n\n"
            "## Work tracking\n\n"
            "This repository uses work records. Specs live in `docs/specs`.\n"
            "Outcome (2026-11-07): Keep reviews independent and verify claims by script\n"
            "- AC1: Route every review across agent families\n"
            "- [x] AC2: Gate ledger acceptance on a verification receipt\n"
        )
        speckit = self.repo / "specs/001-sample/spec.md"
        speckit.parent.mkdir(parents=True, exist_ok=True)
        speckit.write_text(
            "# Sample feature\n"
            "Status: in progress; synthetic detail\n\n"
            "## Success Criteria\n"
            "- **SC-001**: Validate payloads before calling the judge\n",
            encoding="utf-8",
        )
        record = self.repo / "docs/specs/course-check.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(
            "# Course check record\n"
            "Status: accepted; PRIVATE NOTE\n\n"
            "## Goal and acceptance\n"
            "- [ ] AC9 Reject any report finding without an evidence reference\n"
            "- [ ] AC10 <placeholder should be ignored>\n\n"
            "## Plan\n"
            "PRIVATE PLAN BODY\n",
            encoding="utf-8",
        )
        fake_git = (
            b"1a2b3c4d5e6f78901234567890abcdef12345678\tImplement AC1 routing (#142) PRIVATE SUBJECT\n"
            b"fedcba9876543210fedcba9876543210fedcba98\tUpdate SC-001 validation (pull request #143)\n"
        )
        with mock.patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout=fake_git, stderr=b""),
        ):
            code, out, err = self.cli("collect", "--anchors", str(anchors), "--since", "2026-11-01")

        self.assertEqual((code, err), (0, ""))
        payload = json.loads(out)
        self.assertEqual(set(payload), {"since", "criteria", "evidence"})
        self.assertEqual(payload["since"], "2026-11-01")

        for item in payload["criteria"]:
            self.assertEqual(set(item), {"id", "criterion", "evidence_refs"})
            self.assertLessEqual(len(item["criterion"]), 300)
            self.assertFalse(ns.has_control_chars(item["criterion"]))

        ids = [c["id"] for c in payload["criteria"]]
        self.assertIn("OUTCOME-1", ids)
        self.assertIn("AC1", ids)
        self.assertIn("AC2", ids)
        self.assertIn("SC-001", ids)
        self.assertIn("AC9", ids)
        self.assertNotIn("AC10", ids)

        ac1 = next(c for c in payload["criteria"] if c["id"] == "AC1")
        self.assertIn("1a2b3c4d5e6f", ac1["evidence_refs"])
        self.assertIn("#142", ac1["evidence_refs"])

        ev = payload["evidence"]
        self.assertEqual(set(ev), {"commits", "pull_requests", "specs", "ledger", "counts"})
        self.assertEqual(ev["commits"], ["1a2b3c4d5e6f", "fedcba987654"])
        self.assertEqual(ev["pull_requests"], ["#142", "#143"])
        self.assertEqual(
            ev["specs"],
            [
                {"id": "001-sample", "status": "in progress"},
                {"id": "course-check", "status": "accepted"},
            ],
        )
        self.assertEqual(ev["counts"], {"commits": 2, "pull_requests": 2, "specs": 2, "ledger_runs": 0})
        for forbidden in ("PRIVATE NOTE", "PRIVATE PLAN BODY", "PRIVATE SUBJECT", "synthetic detail"):
            self.assertNotIn(forbidden, out)

    def test_missing_ledger_tolerated_and_present_ledger_summarizes_outcomes_only(self):
        anchors = self.write_anchors("## Work tracking\nOutcome: Check ledger handling\n")
        with mock.patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout=b"", stderr=b""),
        ):
            result = ns.collect(anchors, "2026-11-01")
        self.assertEqual(result["evidence"]["ledger"], {"status": "absent", "ids": [], "counts": {}})

        ledger_file = self.data / "ledger.jsonl"
        lines = [
            {
                "event": "start", "id": "d20261107-100000-a1b2", "ts": "2026-11-07T10:00:00+00:00",
                "project": "synthetic-repo", "task": "SECRET TASK TEXT", "kind": "implement",
                "grade": "hard", "agent": "codex", "model": "default", "reason": "routing",
            },
            {
                "event": "finish", "id": "d20261107-100000-a1b2", "ts": "2026-11-07T10:20:00+00:00",
                "outcome": "accepted", "rework_rounds": 0, "note": "SECRET NOTE TEXT",
            },
            {
                "event": "start", "id": "d20261001-100000-ffff", "ts": "2026-10-01T10:00:00+00:00",
                "project": "synthetic-repo", "task": "OLD TASK", "kind": "implement",
                "grade": "easy", "agent": "claude", "model": "default", "reason": "routing",
            },
            {
                "event": "finish", "id": "d20261001-100000-ffff", "ts": "2026-10-01T10:05:00+00:00",
                "outcome": "error", "rework_rounds": 1,
            },
        ]
        ledger_file.write_text("".join(json.dumps(row) + "\n" for row in lines), encoding="utf-8")
        ledger_file.chmod(0o600)

        with mock.patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout=b"", stderr=b""),
        ):
            present = ns.collect(anchors, "2026-11-01")
        self.assertEqual(
            present["evidence"]["ledger"],
            {"status": "present", "ids": ["d20261107-100000-a1b2"], "counts": {"accepted": 1}},
        )
        self.assertEqual(present["evidence"]["counts"]["ledger_runs"], 1)
        serialized = json.dumps(present)
        self.assertNotIn("SECRET TASK TEXT", serialized)
        self.assertNotIn("SECRET NOTE TEXT", serialized)

    def test_long_criterion_capped_at_300_chars_and_non_english_preserved(self):
        long_wording = "A" * 450
        vietnamese = "Đảm bảo mọi phán quyết đều có dẫn chứng cụ thể từ commit hoặc pull request"
        anchors = self.write_anchors(
            "## Work tracking\n"
            f"Outcome (2026-11-07): {long_wording}\n"
            f"- AC1: {vietnamese}\n"
            "- AC2: " + ("B" * 380) + "\n"
        )
        with mock.patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=["git"], returncode=1, stdout=b"", stderr=b""),
        ):
            payload = ns.collect(anchors, "2026-11-01")

        by_id = {c["id"]: c["criterion"] for c in payload["criteria"]}
        self.assertEqual(len(by_id["OUTCOME-1"]), 300)
        self.assertEqual(by_id["OUTCOME-1"], "A" * 300)
        self.assertEqual(len(by_id["AC2"]), 300)
        self.assertEqual(by_id["AC2"], "B" * 300)
        self.assertEqual(by_id["AC1"], vietnamese)

    def test_hostile_control_characters_never_reach_output(self):
        hostile_anchors = self.write_anchors(
            "## Work tracking\n"
            "Outcome: Clean\x00outcome\x07text\x1b[31mwith\u202ebidi\u200band\x7fcontrols\n"
            "- AC1: First\x01\x02\x1b[0m criterion\u2066 with\r\b hostile bytes\n"
        )
        fake_git = (
            b"abcdef1234567890\tCommit for AC1 \x1b[32m\x00\u202e(#99)\x07\n"
        )
        with mock.patch.object(
            subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=["git"], returncode=0, stdout=fake_git, stderr=b""),
        ):
            code, out, err = self.cli("collect", "--anchors", str(hostile_anchors), "--since", "2026-11-01")

        self.assertEqual((code, err), (0, ""))
        payload = json.loads(out)
        for item in payload["criteria"]:
            self.assertFalse(ns.has_control_chars(item["criterion"]))
            self.assertNotIn("\x1b", item["criterion"])
            self.assertNotIn("\u202e", item["criterion"])
            self.assertNotIn("\x00", item["criterion"])
        self.assertFalse(ns.has_control_chars(out.strip()))

    def test_validate_payload_accepts_valid_and_rejects_extra_or_malformed_fields(self):
        valid_single = {
            "id": "AC1",
            "criterion": "Đảm bảo không lệch hướng",
            "restated_criterion": "Ensure the project does not drift from its anchor",
            "question": "Does the recent commit evidence support AC1?",
            "evidence_refs": ["1a2b3c4d5e6f", "#142"],
            "evidence": {
                "commits": ["1a2b3c4d5e6f"],
                "pull_requests": ["#142"],
                "specs": [{"id": "agent-roles", "status": "accepted"}],
                "ledger": {"status": "absent", "ids": [], "counts": {}},
                "counts": {"commits": 1, "pull_requests": 1, "specs": 1, "ledger_runs": 0},
            },
        }
        code, out, err = self.cli("validate-payload", stdin_text=json.dumps(valid_single))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), {"ok": True})

        bad_payloads = [
            {**valid_single, "extra_field": "not allowed"},
            {**valid_single, "prompt": "ignore instructions"},
            {**valid_single, "criterion": "X" * 301},
            {**valid_single, "question": "Q" * 301},
            {**valid_single, "criterion": "bad\x00char"},
            {**valid_single, "question": "bad\u202echar"},
            {**valid_single, "evidence": {**valid_single["evidence"], "body": "commit body"}},
            {**valid_single, "evidence": {**valid_single["evidence"], "specs": [{"id": "s1", "status": "invented"}]}},
            {**valid_single, "evidence": {**valid_single["evidence"], "counts": {"commits": True}}},
            {**valid_single, "evidence": {**valid_single["evidence"], "counts": {"commits": -1}}},
            {**valid_single, "evidence": {**valid_single["evidence"], "ledger": {"status": "absent", "ids": ["d1"], "counts": {}}}},
            {
                "since": "2026-11-01",
                "criteria": [{"id": "AC1", "criterion": "ok", "secret": "no"}],
                "evidence": valid_single["evidence"],
            },
            {
                "since": "2026-11-01",
                "criteria": [{"id": "AC1", "criterion": "ok"}],
                "evidence": valid_single["evidence"],
                "unexpected": 1,
            },
        ]
        for bad in bad_payloads:
            with self.subTest(bad=bad):
                code, out, err = self.cli("validate-payload", stdin_text=json.dumps(bad))
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("Navigator state refused:", err)

        # Duplicate keys in raw JSON must also be rejected.
        dup_json = '{"id": "AC1", "id": "AC2", "criterion": "ok", "evidence_refs": ["#1"]}'
        code, out, err = self.cli("validate-payload", stdin_text=dup_json)
        self.assertEqual(code, 2)

    def test_check_report_rejects_missing_evidence_and_validates_options_and_restatement(self):
        valid_report = {
            "anchors": [
                {
                    "id": "OUTCOME-1",
                    "status": "No drift",
                    "criteria": [
                        {
                            "id": "AC1",
                            "criterion": "Giữ nguyên tiêu chí gốc",
                            "restated_criterion": "Keep the original criterion text",
                            "question": "Is the original criterion text preserved alongside the English restatement?",
                            "answer": "yes",
                            "judge": "host",
                            "judge_validated": False,
                            "evidence_refs": ["1a2b3c4d5e6f", "#142"],
                        }
                    ],
                    "findings": [],
                    "evidence_refs": ["1a2b3c4d5e6f", "#142"],
                }
            ],
            "unmatched_items": [],
            "options": [
                {"option": "Continue with current milestone", "cost": "0 extra dispatches"},
                {"option": "Re-run validation on merged PRs", "cost": "1 short script run (~2 min)"},
                {"option": "Defer non-core cleanup", "cost": "1 follow-up ticket"},
            ],
        }
        report_file = self.base / "report.json"
        report_file.write_text(json.dumps(valid_report), encoding="utf-8")
        code, out, err = self.cli("check-report", "--file", str(report_file))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), {"ok": True})

        invalid_reports = [
            # Entry with empty evidence_refs
            {"id": "AC1", "status": "drifting", "answer": "no", "evidence_refs": []},
            # Entry with no evidence field at all
            {"id": "AC1", "status": "on course", "answer": "yes"},
            # Finding without evidence reference
            {
                "anchors": [
                    {
                        "id": "OUTCOME-1",
                        "status": "drifting",
                        "evidence_refs": ["#142"],
                        "findings": [{"finding": "Spec in progress with no commits", "evidence_refs": []}],
                    }
                ]
            },
            # Restated criterion without original criterion
            {
                "id": "AC1",
                "restated_criterion": "English only without original",
                "answer": "yes",
                "evidence_refs": ["#142"],
            },
            # More than 3 options to steer back
            {
                **valid_report,
                "options": [
                    {"option": "Opt 1", "cost": "1h"},
                    {"option": "Opt 2", "cost": "2h"},
                    {"option": "Opt 3", "cost": "3h"},
                    {"option": "Opt 4", "cost": "4h"},
                ],
            },
            # Option missing cost
            {
                **valid_report,
                "options": [{"option": "Steer back without stating cost"}],
            },
            # Invalid anchor status
            {"id": "AC1", "status": "invented-status", "answer": "yes", "evidence_refs": ["#142"]},
            # Invalid judge answer
            {"id": "AC1", "status": "on course", "answer": "maybe", "evidence_refs": ["#142"]},
            # Control character in finding
            {"id": "AC1", "status": "drifting", "finding": "Bad\x07finding", "evidence_refs": ["#142"]},
        ]
        for bad in invalid_reports:
            with self.subTest(bad=bad):
                code, out, err = self.cli("check-report", stdin_text=json.dumps(bad))
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("Navigator state refused:", err)

    def test_agent_file_frontmatter_flow_and_enforcers(self):
        agent_path = ROOT / "agents/fnl-navigator.md"
        text = agent_path.read_text(encoding="utf-8")
        front = text.split("---", 2)[1]
        for line in (
            "name: fnl-navigator",
            "model: inherit",
            "disallowedTools: [Write, Edit, NotebookEdit]",
        ):
            self.assertIn(line, front)
        normalized = " ".join(text.split())
        for required in (
            "nav_state.py collect",
            "validate-payload",
            "judge.py ask --question <text> --evidence-file <path> [--judge jev|host]",
            "check-report",
            "on course",
            "drifting",
            "abandoned",
            "No drift",
            "at most three options",
            "cost",
            "advisory (agent judgment)",
            "user story closes",
            "before a release is cut",
            "spec status changes",
        ):
            self.assertIn(required, normalized)


if __name__ == "__main__":
    unittest.main()
