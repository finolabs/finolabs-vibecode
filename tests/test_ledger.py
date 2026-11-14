"""Tests for skills/delegate/scripts/ledger.py, run through its CLI."""

import importlib.util
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests.data_root_fixture import account
from unittest import mock

LEDGER = Path(__file__).resolve().parent.parent / "skills/delegate/scripts/ledger.py"
START = ["start", "--project", "demo", "--task", "add parser", "--kind", "implement",
         "--grade", "medium", "--agent", "codex", "--model", "m1", "--budget", "40"]


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.home = account(self, Path(self.dir.name) / "home")
        self.path = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.path.parent.mkdir(parents=True)
        self.env = {"HOME": str(self.home), "ORCHESTRATION_LEDGER": str(self.path)}

    def tearDown(self):
        self.dir.cleanup()

    def run_ledger(self, *args, check=True):
        result = subprocess.run([sys.executable, "-I", str(LEDGER), *args],
                                capture_output=True, text=True, env=self.env)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_log_scan_records_only_status_and_preserves_head_and_receipt_gate(self):
        logs = Path(self.dir.name).resolve() / '.finolabs' / 'logs'
        logs.mkdir(parents=True, mode=0o700)
        path = logs / 'run.log'
        import importlib.util
        spec = importlib.util.spec_from_file_location('hygiene_ledger', LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        import log_scan
        for raw, status in ((b'ordinary output', 'no_findings'),
                            (('sk' + '-' + 'fixture' * 4).encode(), 'findings'),
                            (b'\x00fixture', 'not_scanned')):
            path.write_bytes(raw)
            dispatch = self.run_ledger(*START).stdout.strip()
            args = ledger.build_parser().parse_args(['finish', dispatch, '--outcome', 'accepted',
                '--head', 'a' * 40, '--log-path', str(path), '--accept-unverified', '--reason', 'Synthetic fixture'])
            output, warning = io.StringIO(), io.StringIO()
            with mock.patch.object(log_scan, 'run_log_folder', return_value=logs), \
                    mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output), \
                    contextlib.redirect_stderr(warning):
                args.func(args)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(warning.getvalue(), '' if status == 'no_findings' else
                             'ledger: log_scan: ' + status + '\n')
            done = self.records()[-1]
            self.assertEqual(done['log_scan'], status)
            self.assertEqual(done['head'], 'a' * 40)
            self.assertNotIn('fixturefixture', self.path.read_text())
        dispatch = self.run_ledger(*START).stdout.strip()
        args = ledger.build_parser().parse_args(['finish', dispatch, '--outcome', 'accepted',
                                                '--log-path', str(path), '--head', 'a' * 40])
        count = len(self.records())
        with mock.patch.object(log_scan, 'run_log_folder', return_value=logs), self.assertRaises(SystemExit):
            args.func(args)
        self.assertEqual(len(self.records()), count)

    def test_open_log_folder_refusal_names_the_fix_and_keeps_the_mode(self):
        logs = Path(self.dir.name).resolve() / '.finolabs' / 'logs'
        logs.mkdir(parents=True, mode=0o700)
        path = logs / 'run.log'
        path.write_text('ordinary')
        logs.chmod(0o755)
        spec = importlib.util.spec_from_file_location('hygiene_ledger', LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        import log_scan
        args = ledger.build_parser().parse_args(['finish', 'missing', '--outcome', 'error', '--log-path', str(path)])
        with mock.patch.object(log_scan, 'run_log_folder', return_value=logs), \
                mock.patch.object(ledger, 'load') as load, self.assertRaises(SystemExit) as stopped:
            args.func(args)
        load.assert_not_called()
        self.assertEqual(stopped.exception.code, 'ledger: log refused; ' + log_scan.FOLDER_REFUSED)
        self.assertNotIn(str(logs), stopped.exception.code)
        self.assertEqual(logs.stat().st_mode & 0o777, 0o755)
        path.unlink()
        logs.chmod(0o700)
        alias = logs / 'alias.log'
        alias.symlink_to(logs / 'gone.log')
        args = ledger.build_parser().parse_args(['finish', 'missing', '--outcome', 'error', '--log-path', str(alias)])
        with mock.patch.object(log_scan, 'run_log_folder', return_value=logs), self.assertRaises(SystemExit) as stopped:
            args.func(args)
        self.assertEqual(stopped.exception.code, ledger.LOG_REFUSED)
        self.assertNotIn(str(logs), stopped.exception.code)

    def test_log_path_refuses_outside_symlink_hardlink_and_scans_before_ledger_read(self):
        logs = Path(self.dir.name).resolve() / '.finolabs' / 'logs'
        logs.mkdir(parents=True, mode=0o700)
        path = logs / 'run.log'
        path.write_text('ordinary')
        alias = logs / 'alias.log'
        alias.symlink_to(path)
        outside = Path(self.dir.name).resolve() / 'outside.log'
        outside.write_text('ordinary')
        spec = importlib.util.spec_from_file_location('hygiene_ledger', LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        import log_scan
        for bad in (alias, outside):
            args = ledger.build_parser().parse_args(['finish', 'missing', '--outcome', 'error', '--log-path', str(bad)])
            with mock.patch.object(log_scan, 'run_log_folder', return_value=logs), \
                    mock.patch.object(ledger, 'load') as load, self.assertRaises(SystemExit):
                args.func(args)
            load.assert_not_called()
        alias.unlink()
        os.link(path, alias)
        args = ledger.build_parser().parse_args(['finish', 'missing', '--outcome', 'error', '--log-path', str(path)])
        with mock.patch.object(log_scan, 'run_log_folder', return_value=logs), self.assertRaises(SystemExit):
            args.func(args)

    def test_low_oversized_ledger_has_one_error_line(self):
        with self.path.open("wb") as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
        for args in (("summary",), ("finish", "missing", "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture"), ("open",)):
            with self.subTest(command=args[0]):
                result = self.run_ledger(*args, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, "ledger: unsafe file\n")
                self.assertEqual(result.stdout, "")

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def set_mode(self, mode):
        (self.path.parent / "host.md").write_text(f"## Delegation mode\n\n{mode}\n")

    def test_manual_refuses_cross_family_without_user_route(self):
        self.set_mode("manual")
        result = self.run_ledger(*START, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "Delegation mode is manual: another agent family needs --route-by user\n")
        self.assertFalse(self.path.exists())

    def test_manual_accepts_user_route_and_own_family(self):
        self.set_mode("manual")
        self.run_ledger(*START, "--route-by", "user")
        for agent, coordinator in (("claude", "claude"), ("claude-session", "claude"),
                                   ("subagent", "claude"), ("codex", "codex")):
            with self.subTest(agent=agent, coordinator=coordinator):
                args = [agent if a == "codex" else a for a in START]
                self.run_ledger(*args, "--coordinator", coordinator)
        self.assertEqual(len(self.records()), 5)

    def test_nonmanual_and_unresolved_modes_allow_dispatch(self):
        for mode in ("suggest", "auto", "invalid", None):
            with self.subTest(mode=mode):
                host = self.path.parent / "host.md"
                if mode is None:
                    host.unlink(missing_ok=True)
                else:
                    self.set_mode(mode)
                self.run_ledger(*START)
        self.assertEqual(len(self.records()), 4)

    def test_manual_environment_override_is_honoured(self):
        self.set_mode("suggest")
        self.env["FNL_DELEGATION_MODE"] = "manual"
        result = self.run_ledger(*START, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.path.exists())

    def test_missing_mode_script_fails_open(self):
        self.set_mode("manual")
        scripts = Path(self.dir.name) / "scripts"
        scripts.mkdir()
        for name in ("ledger.py", "data_root.py"):
            shutil.copy(LEDGER.parent / name, scripts / name)
        result = subprocess.run([sys.executable, "-I", str(scripts / "ledger.py"), *START],
                                capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.records()), 1)

    def test_the_five_grades_are_accepted_and_an_ultra_hard_run_is_summarised(self):
        ids = {}
        for grade in ("easy", "medium", "hard", "very-hard", "ultra-hard"):
            args = [a if a != "medium" else grade for a in START]
            ids[grade] = self.run_ledger(*args).stdout.strip()
        self.assertNotEqual(self.run_ledger(*[a if a != "medium" else "extreme" for a in START], check=False).returncode, 0)
        self.run_ledger("finish", ids["ultra-hard"], "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture")  # a summary counts finished runs only
        rows = json.loads(self.run_ledger("summary", "--json").stdout)
        self.assertEqual([(r["grade"], r["n"]) for r in rows], [("ultra-hard", 1)])
        self.assertIn("ultra-hard", self.run_ledger("summary").stdout)

    def test_start_writes_a_start_line_and_prints_its_id(self):
        dispatch_id = self.run_ledger(*START).stdout.strip()
        [rec] = self.records()
        self.assertEqual(rec["event"], "start")
        self.assertEqual(rec["id"], dispatch_id)
        self.assertEqual(rec["budget_min"], 40)
        self.assertEqual(rec["reason"], "routing")
        self.assertEqual(rec["route_by"], "table")

    def test_start_prints_the_run_label_on_stderr_and_only_the_id_on_stdout(self):
        for agent, model, runner in (("codex", "gpt-6.1-sol", "codex sol"), ("claude", "claude-opus-5-5", "claude opus"),
                                     ("antigravity", "gemini-3-flash", "agy flash"), ("subagent", "sonnet", "claude sonnet"),
                                     ("antigravity", "gemini-3.8-flash-high", "agy flash"),
                                     ("antigravity", "gemini-4-argon-medium", "agy argon"),
                                     ("antigravity", "claude-opus-5-5-low", "agy opus"),
                                     ("claude", "claude-sonnet-5-5-xhigh", "claude sonnet"),
                                     ("codex", None, "codex")):
            argv = ["start", "--project", "demo", "--task", "PR 7  code review", "--kind", "review", "--grade", "easy",
                    "--coordinator", "claude", "--agent", agent, "--reason", "routing", "--route-by", "table",
                    "--budget", "5"] + (["--model", model] if model else [])
            result = self.run_ledger(*argv)
            self.assertRegex(result.stdout, r"^d\d{8}-\d{6}-[0-9a-f]{4}\n$")
            self.assertEqual(result.stderr, "label: %s: demo PR 7 code review\n" % runner)

    def test_start_hashes_session_environment(self):
        self.env["CLAUDE_CODE_SESSION_ID"] = "abc-123"
        result = self.run_ledger(*START)
        [rec] = self.records()
        self.assertEqual(rec["coord_session"], hashlib.sha256(b"abc-123").hexdigest()[:12])
        self.assertRegex(rec["coord_session"], r"^[0-9a-f]{12}$")
        self.assertNotIn("abc-123", self.path.read_text() + result.stdout + result.stderr)

    def test_start_records_null_when_session_unknown_or_unusable(self):
        for value in (None, "", "a" * 129, "bad session", "bad/session", "bad\n", "\u00e9", "bad.session"):
            if value is None:
                self.env.pop("CLAUDE_CODE_SESSION_ID", None)
            else:
                self.env["CLAUDE_CODE_SESSION_ID"] = value
            result = self.run_ledger(*START)
            self.assertIsNone(self.records()[-1]["coord_session"])
            self.assertEqual(result.stderr, "label: codex: demo add parser\n")

    def test_start_accepts_session_boundaries(self):
        for value in ("A", "Z9_-" * 32):
            self.env["CLAUDE_CODE_SESSION_ID"] = value
            self.run_ledger(*START)
            self.assertEqual(self.records()[-1]["coord_session"],
                             hashlib.sha256(value.encode()).hexdigest()[:12])

    def test_the_session_id_is_never_a_command_line_option(self):
        result = self.run_ledger("start", "--help")
        self.assertNotIn("--session", result.stdout)

    def test_open_and_summary_read_mixed_session_records(self):
        old = self.run_ledger(*START).stdout.strip()
        [legacy] = self.records()
        legacy.pop("coord_session", None)
        self.path.write_text(json.dumps(legacy) + "\n")
        self.env["CLAUDE_CODE_SESSION_ID"] = "abc-123"
        new = self.run_ledger(*START).stdout.strip()
        self.assertIn("coord_session", self.records()[-1])
        opened = self.run_ledger("open")
        self.assertEqual(opened.stderr, "")
        for dispatch in (old, new):
            self.assertIn(dispatch, opened.stdout)
            self.run_ledger("finish", dispatch, "--outcome", "error")
        summary = self.run_ledger("summary", "--json")
        self.assertEqual(summary.stderr, "")
        [row] = json.loads(summary.stdout)
        self.assertEqual((row["n"], row["error"]), (2, 2))
        self.assertEqual(self.run_ledger("open").stdout, "")

    def test_finish_binds_implementation_head_to_start_agent(self):
        dispatch_id = self.run_ledger(*START).stdout.strip()
        invalid = self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--head", "invalid", check=False)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(len(self.records()), 1)
        self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--head", "a" * 40,
                        "--accept-unverified", "--reason", "Head binding fixture")
        finish = self.records()[-1]
        self.assertEqual((finish["head"], finish["agent"]), ("a" * 40, "codex"))
        self.assertEqual(finish["log_scan"], "not_scanned")

    def test_review_dispatch_cannot_claim_implementation_head(self):
        args = ["review" if a == "implement" else a for a in START]
        dispatch_id = self.run_ledger(*args).stdout.strip()
        self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--head", "a" * 40,
                        "--accept-unverified", "--reason", "Head binding fixture")
        finish = self.records()[-1]
        # The reviewed head is kept apart: it never binds authorship for review routing.
        self.assertEqual(finish["reviewed_head"], "a" * 40)
        self.assertNotIn("head", finish)
        self.assertNotIn("agent", finish)
        advise = self.run_ledger(*["advise" if a == "implement" else a for a in START]).stdout.strip()
        result = self.run_ledger("finish", advise, "--outcome", "rejected", "--head", "a" * 40, check=False)
        self.assertIn("only implementation and review dispatches", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.records()[-1]["event"], "start")

    # A review dispatch is accepted on its posted review, not on a test receipt.

    REVIEW_URL = "https://github.com/example-org/demo-app/pull/12#issuecomment-345678"

    def start_kind(self, kind):
        return self.run_ledger(*[kind if a == "implement" else a for a in START]).stdout.strip()

    def test_review_accept_needs_no_receipt_and_records_a_given_url_as_a_flag(self):
        plain = self.start_kind("review")
        self.run_ledger("finish", plain, "--outcome", "accepted", "--head", "b" * 40)
        finish = self.records()[-1]
        self.assertEqual((finish["outcome"], finish["reviewed_head"]), ("accepted", "b" * 40))
        self.assertNotIn("review_posted", finish)
        self.assertNotIn("accept_unverified", finish)
        posted = self.start_kind("review")
        self.run_ledger("finish", posted, "--outcome", "accepted", "--review-url", self.REVIEW_URL)
        finish = self.records()[-1]
        self.assertIs(finish["review_posted"], True)
        self.assertNotIn("issuecomment", self.path.read_text())  # the URL itself is never stored
        [row] = json.loads(self.run_ledger("summary", "--json").stdout)
        self.assertEqual((row["kind"], row["accepted"], row["accepted_unverified"]), ("review", 1, 0))

    def test_review_url_is_pattern_checked_and_only_for_an_accepted_review(self):
        review = self.start_kind("review")
        for bad in ("http://github.com/example-org/demo-app/pull/12#issuecomment-345678",
                    "https://github.com.example/example-org/demo-app/pull/12#issuecomment-345678",
                    "https://github.com/example-org/demo-app/pull/12",
                    "https://github.com/example-org/demo-app/issues/12#issuecomment-345678",
                    "https://github.com/example-org/demo-app/pull/12#issuecomment-345678 extra",
                    "https://github.com/example-org/demo-app/pull/12#issuecomment-345678\n"):
            with self.subTest(url=bad):
                result = self.run_ledger("finish", review, "--outcome", "accepted", "--review-url", bad, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid review URL", result.stderr)
        rejected = self.run_ledger("finish", review, "--outcome", "rejected", "--review-url", self.REVIEW_URL,
                                   check=False)
        self.assertIn("only with an accepted review", rejected.stderr)
        implement = self.run_ledger(*START).stdout.strip()
        other = self.run_ledger("finish", implement, "--outcome", "accepted", "--review-url", self.REVIEW_URL,
                                "--accept-unverified", "--reason", "Synthetic fixture", check=False)
        self.assertIn("only with an accepted review", other.stderr)
        self.assertEqual([r["event"] for r in self.records()], ["start", "start"])

    def test_other_kinds_still_need_a_receipt_to_be_accepted(self):
        for kind in ("implement", "advise", "committee"):
            with self.subTest(kind=kind):
                dispatch = self.start_kind(kind)
                done = self.run_ledger("finish", dispatch, "--outcome", "accepted", check=False)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn("passing verify receipt", done.stderr)
                self.assertEqual(self.records()[-1]["event"], "start")

    def test_reason_goes_with_any_outcome_and_is_kept_only_as_a_digest(self):
        for outcome in ("rejected", "error", "cancelled", "stalled"):
            with self.subTest(outcome=outcome):
                dispatch = self.run_ledger(*START).stdout.strip()
                self.run_ledger("finish", dispatch, "--outcome", outcome, "--reason", "Synthetic reason text")
                finish = self.records()[-1]
                self.assertEqual(finish["reason_id"], hashlib.sha256(b"Synthetic reason text").hexdigest())
                self.assertNotIn("accept_unverified", finish)
        review = self.start_kind("review")
        self.run_ledger("finish", review, "--outcome", "accepted", "--reason", "Synthetic reason text")
        self.assertEqual(len(self.records()[-1]["reason_id"]), 64)
        self.assertNotIn("Synthetic reason text", self.path.read_text())
        dispatch = self.run_ledger(*START).stdout.strip()
        for bad in (" ", "x" * 4097):
            result = self.run_ledger("finish", dispatch, "--outcome", "rejected", "--reason", bad, check=False)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.records()[-1]["event"], "start")

    def test_open_lists_unfinished_runs_with_age_against_budget(self):
        dispatch_id = self.run_ledger(*START).stdout.strip()
        out = self.run_ledger("open").stdout
        self.assertIn(dispatch_id, out)
        self.assertIn("/40 min", out)
        self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture")
        self.assertEqual(self.run_ledger("open").stdout, "")

    def test_open_can_be_limited_to_one_project(self):
        mine = self.run_ledger(*START).stdout.strip()
        other = self.run_ledger(*[("other" if value == "demo" else value) for value in START]).stdout.strip()
        everything = self.run_ledger("open").stdout
        self.assertIn(mine, everything)
        self.assertIn(other, everything)
        scoped = self.run_ledger("open", "--project", "demo").stdout
        self.assertIn(mine, scoped)
        self.assertNotIn(other, scoped)
        self.assertEqual(self.run_ledger("open", "--project", "nothing").stdout, "")

    def test_finish_needs_a_start_and_happens_once(self):
        missing = self.run_ledger("finish", "d-missing", "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture", check=False)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("no start line", missing.stderr)
        dispatch_id = self.run_ledger(*START).stdout.strip()
        self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture", "--rework-rounds", "1")
        again = self.run_ledger("finish", dispatch_id, "--outcome", "rejected", check=False)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already has a finish line", again.stderr)

    def test_start_rejects_unknown_choices(self):
        bad = self.run_ledger(*[a if a != "codex" else "nobody" for a in START], check=False)
        self.assertNotEqual(bad.returncode, 0)

    def test_route_by_is_groupable_without_changing_default_summary(self):
        for route, rework in (("judge", 0), ("judge", 1), ("table", 0)):
            dispatch_id = self.run_ledger(*START, "--route-by", route).stdout.strip()
            self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture", "--rework-rounds", str(rework))
        spec = importlib.util.spec_from_file_location("judge_ledger", LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        with mock.patch.dict(os.environ, self.env):
            rows = ledger.summary_rows(keys=("route_by",))
            self.assertEqual([(r["route_by"], r["n"], r["first_pass"]) for r in rows],
                             [("judge", 2, .5), ("table", 1, 1)])
            with self.assertRaises(ValueError):
                ledger.summary_rows(keys=("task",))
        self.assertEqual(ledger.SUMMARY_KEYS, ("agent", "model", "kind", "grade"))
        [default] = json.loads(self.run_ledger("summary", "--json").stdout)
        self.assertNotIn("route_by", default)
        self.assertEqual(default["n"], 3)

    def test_summary_counts_first_pass_and_fallbacks(self):
        first = self.run_ledger(*START).stdout.strip()
        second = self.run_ledger(*START, "--reason", "fallback-quota").stdout.strip()
        self.run_ledger("finish", first, "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture")
        self.run_ledger("finish", second, "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture", "--rework-rounds", "2")
        row = self.run_ledger("summary").stdout.splitlines()[1].split()
        self.assertEqual(row[:5], ["codex", "m1", "implement", "medium", "2"])
        self.assertEqual(row[5:9], ["50%", "100%", "0", "1"])

    def test_summary_json_reports_the_same_counts_with_quota_and_error(self):
        ids = [self.run_ledger(*START).stdout.strip() for _ in range(3)]
        self.run_ledger("finish", ids[0], "--outcome", "accepted", "--accept-unverified", "--reason", "Synthetic fixture")
        self.run_ledger("finish", ids[1], "--outcome", "quota")
        self.run_ledger("finish", ids[2], "--outcome", "error")
        [row] = json.loads(self.run_ledger("summary", "--json").stdout)
        self.assertEqual((row["agent"], row["kind"], row["n"], row["quota"], row["error"]), ("codex", "implement", 3, 1, 1))
        self.assertAlmostEqual(row["first_pass"], 1 / 3)

    def test_summary_without_finished_runs_says_so(self):
        self.run_ledger(*START)
        self.assertIn("no finished dispatches", self.run_ledger("summary").stdout)

    def test_malformed_lines_are_skipped(self):
        self.path.write_text("not json\n")
        result = self.run_ledger("open")
        self.assertIn("malformed line 1", result.stderr)

    def test_json_lines_that_are_not_objects_are_skipped(self):
        self.path.write_text('["start"]\n42\n')
        result = self.run_ledger("open")
        self.assertIn("malformed line 1", result.stderr)
        self.assertIn("malformed line 2", result.stderr)

    def test_objects_that_are_not_records_are_skipped(self):
        self.path.write_text('{}\n{"id": "d1"}\n{"event": "start", "id": "d2"}\n{"event": "finish", "id": "d3"}\n')
        for command in ("open", "summary"):
            result = self.run_ledger(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            for n in (1, 2, 3, 4):
                self.assertIn(f"malformed line {n}", result.stderr)

    def test_accepted_refuses_without_receipt_and_does_not_finish(self):
        dispatch = self.run_ledger(*START).stdout.strip()
        done = self.run_ledger("finish", dispatch, "--outcome", "accepted", check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("passing verify receipt", done.stderr)
        self.assertEqual(len(self.records()), 1)

    def test_head_binding_cannot_bypass_receipt_gate(self):
        dispatch = self.run_ledger(*START).stdout.strip()
        done = self.run_ledger("finish", dispatch, "--outcome", "accepted",
                               "--head", "a" * 40, check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("passing verify receipt", done.stderr)
        self.assertEqual(len(self.records()), 1)

    def test_head_binding_accepts_matching_receipt_and_refuses_another_head(self):
        checkout = Path(self.dir.name) / "checkout"
        checkout.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True,
                                  text=True, check=True).stdout.strip()
        git("init", "-q")
        git("config", "user.name", "Synthetic Author")
        git("config", "user.email", "author@example.com")
        git("commit", "--allow-empty", "-qm", "Create fixture")
        head = git("rev-parse", "HEAD")
        dispatch = self.run_ledger(*START, "--checkout", str(checkout)).stdout.strip()
        criteria = Path(self.dir.name) / "criteria.json"
        criteria.write_text("[]")
        done = subprocess.run([sys.executable, "-I", str(LEDGER.parent / "record.py"),
            "verify", "--id", dispatch, "--head", head, "--tests", "passed", "--mechanical", "passed",
            "--criteria-file", str(criteria), "--checkout", str(checkout)],
            capture_output=True, text=True, env=self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        mismatch = self.run_ledger("finish", dispatch, "--outcome", "accepted", "--head", "0" * 40,
                                   "--checkout", str(checkout), check=False)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("passing verify receipt", mismatch.stderr)
        self.assertEqual(len(self.records()), 1)
        self.run_ledger("finish", dispatch, "--outcome", "accepted", "--head", head,
                        "--checkout", str(checkout))
        finish = self.records()[-1]
        self.assertEqual((finish["head"], finish["verified_head"], finish["agent"]),
                         (head, head, "codex"))
        self.assertFalse(finish["accept_unverified"])

    def test_matching_head_receipt_passes_but_stale_failed_or_other_checkout_refuses(self):
        checkout = Path(self.dir.name) / "checkout"
        checkout.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True,
                                  text=True, check=True).stdout.strip()
        git("init", "-q")
        git("config", "user.name", "Synthetic Author")
        git("config", "user.email", "author@example.com")
        (checkout / "file").write_text("before")
        git("add", ".")
        git("commit", "-qm", "Create fixture")
        head = git("rev-parse", "HEAD")
        dispatch = self.run_ledger(*START, "--checkout", str(checkout)).stdout.strip()
        record = LEDGER.parent / "record.py"
        criteria = Path(self.dir.name) / "criteria.json"
        criteria.write_text("[]")
        def receipt(mechanical="passed"):
            done = subprocess.run([sys.executable, "-I", str(record), "verify", "--id", dispatch,
                "--head", git("rev-parse", "HEAD"), "--tests", "passed", "--mechanical", mechanical,
                "--criteria-file", str(criteria), "--checkout", str(checkout)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
        def finish(path=checkout):
            return self.run_ledger("finish", dispatch, "--outcome", "accepted", "--checkout", str(path), check=False)
        receipt("failed")
        self.assertNotEqual(finish().returncode, 0)
        receipt()
        self.assertNotEqual(finish(LEDGER.parents[3]).returncode, 0)
        (checkout / "file").write_text("after")
        git("commit", "-qam", "Change fixture")
        self.assertNotEqual(finish().returncode, 0)
        receipt()
        self.assertEqual(finish().returncode, 0)
        self.assertEqual(self.records()[-1]["verified_head"], git("rev-parse", "HEAD"))
        self.assertNotEqual(head, self.records()[-1]["verified_head"])

    def test_escape_requires_reason_and_is_private_and_counted(self):
        dispatch = self.run_ledger(*START).stdout.strip()
        for args in [("--accept-unverified",), ("--accept-unverified", "--reason", " ")]:
            done = self.run_ledger("finish", dispatch, "--outcome", "accepted", *args, check=False)
            self.assertNotEqual(done.returncode, 0)
        self.run_ledger("finish", dispatch, "--outcome", "accepted", "--accept-unverified", "--reason", "No runnable checks")
        rec = self.records()[-1]
        self.assertTrue(rec["accept_unverified"])
        self.assertEqual(len(rec["reason_id"]), 64)
        self.assertNotIn("No runnable checks", self.path.read_text())
        [row] = json.loads(self.run_ledger("summary", "--json").stdout)
        self.assertEqual(row["accepted_unverified"], 1)

    def test_all_other_outcomes_need_no_verification(self):
        for outcome in ("rejected", "timeout", "stalled", "error", "blocked", "needs-permission", "quota", "cancelled"):
            dispatch = self.run_ledger(*START).stdout.strip()
            self.run_ledger("finish", dispatch, "--outcome", outcome)
            self.assertNotIn("accept_unverified", self.records()[-1])

    # The routing query's record: --install, --work-type, --level and pick_rank.

    def write_matrix_host(self):
        from tests.test_route_pick import host
        (self.path.parent / "host.md").write_text(host())

    def start_picked(self, agent, model, *extra):
        argv = ["start", "--project", "demo", "--task", "add page", "--kind", "implement", "--grade", "hard",
                "--agent", agent, "--model", model, "--budget", "30", "--work-type", "frontend", "--level", "3", *extra]
        return self.run_ledger(*argv)

    def test_pick_rank_one_records_fields_and_prints_no_warning(self):
        self.write_matrix_host()
        result = self.start_picked("claude", "claude-opus-5-5")
        self.assertRegex(result.stdout, r"^d\d{8}-\d{6}-[0-9a-f]{4}\n$")
        self.assertEqual(result.stderr, "label: claude opus: demo add page\n")
        rec = self.records()[-1]
        self.assertEqual((rec["work_type"], rec["level"], rec["pick_rank"]), ("frontend", 3, 1))
        self.assertNotIn("install", rec)

    def test_install_is_compared_in_place_of_the_agent(self):
        self.write_matrix_host()
        result = self.start_picked("claude-session", "claude-opus-5-5", "--install", "claudework")
        self.assertEqual(result.stderr, "off the preferred order: rank 2\nlabel: claude opus: demo add page\n")
        rec = self.records()[-1]
        self.assertEqual((rec["agent"], rec["install"], rec["pick_rank"]), ("claude-session", "claudework", 2))
        other = self.start_picked("claude", "claude-sonnet-5-5", "--install", "claudework")
        self.assertEqual(other.stderr.splitlines()[0], "off the preferred set: model not listed for claudework")
        self.assertEqual(self.records()[-1]["pick_rank"], 0)

    def test_pick_rank_uses_the_dispatching_coordinator(self):
        from tests.test_route_pick import host
        (self.path.parent / "host.md").write_text(host(agy="no"))
        argv = ["start", "--project", "demo", "--task", "t", "--kind", "implement", "--grade", "easy", "--budget", "5",
                "--agent", "antigravity", "--work-type", "transcription", "--level", "2", "--route-by", "table", "--reason", "routing"]
        self.run_ledger(*argv, "--coordinator", "codex")
        self.assertEqual(self.records()[-1]["pick_rank"], 2)
        self.run_ledger(*argv, "--coordinator", "claude")
        self.assertEqual(self.records()[-1]["pick_rank"], 0)

    def test_pick_rank_zero_warns_and_never_refuses(self):
        self.write_matrix_host()
        result = self.start_picked("antigravity", "gemini-3-flash")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr.splitlines()[0], "off the preferred set: antigravity not listed for frontend")
        self.assertEqual(self.records()[-1]["pick_rank"], 0)
        dropped = self.start_picked("codex", "m1", "--level", "5")
        self.assertEqual(dropped.stderr.splitlines()[0], "off the preferred set: codex: level 5 outside 1-4")

    def test_no_pick_rank_without_type_and_level_or_without_a_matrix(self):
        self.run_ledger(*START)
        self.assertFalse({"install", "work_type", "level", "pick_rank"} & self.records()[-1].keys())
        self.write_matrix_host()
        self.run_ledger(*START, "--work-type", "frontend")
        self.assertNotIn("pick_rank", self.records()[-1])
        (self.path.parent / "host.md").unlink()
        result = self.start_picked("claude", "m1")
        self.assertEqual(result.stderr, "label: claude: demo add page\n")
        rec = self.records()[-1]
        self.assertEqual((rec["work_type"], rec["level"]), ("frontend", 3))
        self.assertNotIn("pick_rank", rec)

    def test_a_failed_pick_leaves_the_rank_out_and_records_the_dispatch(self):
        self.write_matrix_host()
        spec = importlib.util.spec_from_file_location("pick_ledger", LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        import route_pick
        args = ledger.build_parser().parse_args(["start", "--project", "demo", "--task", "add page", "--kind", "advise",
                                                 "--grade", "hard", "--agent", "claude", "--budget", "30",
                                                 "--work-type", "frontend", "--level", "3"])
        output, warning = io.StringIO(), io.StringIO()
        with mock.patch.object(route_pick, "answer", side_effect=RuntimeError("synthetic")), \
                mock.patch.dict(os.environ, self.env), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(warning):
            args.func(args)
        self.assertRegex(output.getvalue(), r"^d\d{8}-\d{6}-[0-9a-f]{4}\n$")
        self.assertEqual(warning.getvalue().splitlines()[0], "label: claude: demo add page")
        self.assertNotIn("pick_rank", self.records()[-1])

    def test_new_options_reject_values_outside_their_lists(self):
        for extra in (["--install", "Claude Work"], ["--install", "other"], ["--work-type", "cooking"],
                      ["--level", "0"], ["--level", "6"]):
            with self.subTest(extra=extra):
                result = self.run_ledger(*START, *extra, check=False)
                self.assertEqual(result.returncode, 2)
        self.assertFalse(self.path.exists())
        spec = importlib.util.spec_from_file_location("lists_ledger", LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        import assignments
        self.assertEqual(ledger.WORK_TYPES, list(assignments.TYPES))
        self.assertEqual(ledger.INSTALL.pattern, assignments.NAME.pattern)

    def write_starts(self, entries):
        lines = []
        for n, (agent, extra) in enumerate(entries):
            rec = {"event": "start", "id": f"d{n}", "ts": "2026-11-10T01:00:00+00:00", "project": "demo",
                   "task": "t", "kind": "implement", "grade": "hard", "agent": agent, "model": "m",
                   "reason": "routing", **extra}
            lines.append(json.dumps(rec))
        self.path.write_text("\n".join(lines) + "\n")

    def test_summary_shows_rank_shares_over_ranked_dispatches_only(self):
        self.write_starts([("codex", {"pick_rank": 1}), ("codex", {"pick_rank": 1}), ("codex", {"pick_rank": 2}),
                           ("codex", {"pick_rank": 0}), ("codex", {}), ("codex", {"work_type": "frontend"}),
                           ("claude-session", {"install": "claudework", "pick_rank": 1}),
                           ("antigravity", {}), ("antigravity", {})])
        output = self.run_ledger("summary").stdout.splitlines()
        self.assertEqual(output[0], "ledger: no finished dispatches match")
        start = output.index("preferred order (shares over dispatches with a pick rank)")
        rows = {line.split()[0]: line.split()[1:] for line in output[start + 2:]}
        self.assertEqual(rows["codex"], ["4", "50%", "25%", "25%", "2"])
        self.assertEqual(rows["claudework"], ["1", "100%", "0%", "0%", "0"])
        self.assertEqual(rows["antigravity"], ["0", "-", "-", "-", "2"])
        self.assertEqual(self.run_ledger("summary", "--json").stdout, "[]\n")

    def test_summary_of_older_records_is_unchanged(self):
        self.write_starts([("codex", {}), ("codex", {"work_type": "frontend", "level": 3})])
        self.assertEqual(self.run_ledger("summary").stdout, "ledger: no finished dispatches match\n")
        self.run_ledger("finish", "d0", "--outcome", "rejected")
        output = self.run_ledger("summary").stdout
        self.assertNotIn("preferred order", output)
        self.assertEqual(len(output.splitlines()), 2)


class LedgerLocationTest(unittest.TestCase):
    """The default file: the finolabs home, or the older XDG file while only that one exists."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = Path(self.dir.name) / "home"
        self.xdg = Path(self.dir.name) / "xdg"
        self.home.mkdir()
        account(self, self.home)
        env = {k: v for k, v in os.environ.items() if k != "ORCHESTRATION_LEDGER"}
        self.env = {**env, "HOME": str(self.home), "XDG_STATE_HOME": str(self.xdg)}

    def start(self):
        return subprocess.run([sys.executable, "-I", str(LEDGER), *START], capture_output=True, text=True, env=self.env, check=True)

    def test_a_new_machine_writes_to_the_finolabs_home_in_private_folders(self):
        self.start()
        ledger = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.assertTrue(ledger.is_file())
        self.assertFalse(self.xdg.exists())
        for folder in (self.home / ".finolabs", self.home / ".finolabs/vibecode"):
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700, folder)

    def test_an_existing_older_ledger_cannot_redirect_storage(self):
        old = self.xdg / "finolabs-vibecode/ledger.jsonl"
        old.parent.mkdir(parents=True)
        old.write_text("")
        self.start()
        self.assertEqual(old.read_text(), "")
        self.assertTrue((self.home / ".finolabs").exists())
        new = self.home / ".finolabs/vibecode/ledger.jsonl"
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text("")
        self.start()
        self.assertEqual(len(new.read_text().splitlines()), 1)
        self.assertEqual(old.read_text(), "")


class AwayLedgerTest(unittest.TestCase):
    """Away decisions: decision, question_denied and decision_review lines beside dispatch history."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = account(self, Path(self.dir.name) / "home")
        self.path = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.path.parent.mkdir(parents=True)
        spec = importlib.util.spec_from_file_location("away_ledger", LEDGER)
        self.ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ledger)

    DISPATCHES = [
        {"event": "start", "id": "d1", "ts": "2026-11-09T01:00:00+00:00", "project": "demo", "task": "parser",
         "kind": "implement", "grade": "medium", "agent": "codex", "model": "m1", "reason": "routing", "route_by": "table"},
        {"event": "finish", "id": "d1", "ts": "2026-11-09T01:30:00+00:00", "outcome": "accepted", "rework_rounds": 0},
        {"event": "start", "id": "d2", "ts": "2026-11-09T02:00:00+00:00", "project": "demo", "task": "advice",
         "kind": "advise", "grade": "easy", "agent": "claude", "model": "m2", "reason": "routing", "route_by": "table"},
        {"event": "finish", "id": "d2", "ts": "2026-11-09T02:10:00+00:00", "outcome": "rejected", "rework_rounds": 1},
    ]
    AWAY = [
        {"event": "decision", "id": "q20261109-010000-aaaa", "ts": "2026-11-09T01:00:00+00:00", "project": "demo",
         "lease_start": 1000.0, "rung": "jev", "settled": "no", "by": "jev", "probability": 0.6, "precedents": 2, "topic": "schema"},
        {"event": "decision", "id": "q20261109-010000-aaaa", "ts": "2026-11-09T01:01:00+00:00", "project": "demo",
         "lease_start": 1000.0, "rung": "advisor", "settled": "yes", "by": "codex", "option": 2, "of": 3,
         "dispatch": "d20261109-010100-abcd", "model": "m1", "precedents": 2, "topic": "schema"},
        {"event": "decision", "id": "q20261109-020000-bbbb", "ts": "2026-11-09T02:00:00+00:00", "project": "demo",
         "lease_start": 1000.0, "rung": "jev", "settled": "yes", "by": "jev", "option": 1, "of": 2, "probability": 0.9,
         "precedents": 0, "topic": "naming"},
        {"event": "decision", "id": "q20261109-030000-cccc", "ts": "2026-11-09T03:00:00+00:00", "project": "demo",
         "lease_start": 1000.0, "rung": "park", "settled": "yes", "by": "claude", "precedents": 0, "topic": "deploy"},
        {"event": "decision", "id": "q20261110-010000-dddd", "ts": "2026-11-10T01:00:00+00:00", "project": "demo",
         "lease_start": 9000.0, "rung": "host", "settled": "yes", "by": "claude", "option": 1, "of": 2, "model": "m3",
         "precedents": 1, "topic": "tests"},
        {"event": "question_denied", "ts": "2026-11-09T01:05:00+00:00", "lease_start": 1000.0},
        {"event": "question_denied", "ts": "2026-11-09T01:06:00+00:00", "lease_start": 1000.0},
        {"event": "decision_review", "id": "q20261109-010000-aaaa", "ts": "2026-11-09T09:00:00+00:00", "verdict": "kept"},
        {"event": "decision_review", "id": "q20261109-010000-aaaa", "ts": "2026-11-09T09:05:00+00:00", "verdict": "reversed"},
        {"event": "decision_review", "id": "q20261109-020000-bbbb", "ts": "2026-11-09T09:06:00+00:00", "verdict": "kept"},
    ]

    def write(self, records, extra=""):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in records) + extra)
        self.path.chmod(0o600)

    def run_quiet(self, function, *args, **kwargs):
        errors, output = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(output):
            value = function(*args, **kwargs)
        return value, output.getvalue(), errors.getvalue()

    def test_load_keeps_its_two_maps_and_skips_away_lines_silently(self):
        self.write(self.DISPATCHES)
        before, _, _ = self.run_quiet(self.ledger.load)
        self.write(self.DISPATCHES[:2] + self.AWAY + self.DISPATCHES[2:])
        after, _, errors = self.run_quiet(self.ledger.load)
        self.assertIsInstance(after, tuple)
        self.assertEqual(len(after), 2)
        self.assertEqual(after, before)
        self.assertEqual(errors, "")
        # A truly malformed line still reports, and an away line missing its fields is no dispatch.
        self.write(self.DISPATCHES + self.AWAY, extra="{broken\n")
        after, _, errors = self.run_quiet(self.ledger.load)
        self.assertEqual(after, before)
        self.assertEqual(errors, "ledger: skipping malformed line %d\n" % (len(self.DISPATCHES + self.AWAY) + 1))

    def test_away_reader_returns_only_the_three_new_event_types(self):
        self.write(self.DISPATCHES + self.AWAY + [{"event": "decision"}, {"event": "other"}], extra="{broken\n")
        records, _, errors = self.run_quiet(self.ledger.load_away)
        self.assertEqual(errors, "")
        self.assertEqual(records, self.AWAY)
        self.path.unlink()
        self.assertEqual(self.ledger.load_away(), [])

    def test_dispatch_summary_numbers_are_unchanged_by_away_lines(self):
        self.write(self.DISPATCHES)
        rows = self.ledger.summary_rows()
        picks = self.ledger.pick_rows()
        self.write(self.AWAY[:3] + self.DISPATCHES + self.AWAY[3:])
        self.assertEqual(self.ledger.summary_rows(), rows)
        self.assertEqual(self.ledger.pick_rows(), picks)
        args = self.ledger.build_parser().parse_args(["summary", "--json"])
        _, output, _ = self.run_quiet(args.func, args)
        self.assertEqual(json.loads(output), json.loads(json.dumps(rows)))

    def test_away_section_per_lease(self):
        self.write(self.DISPATCHES + self.AWAY)
        leases = self.ledger.away_rows()
        self.assertEqual([lease["lease_start"] for lease in leases], [1000.0, 9000.0])
        first, second = leases
        self.assertEqual(first["decisions"], 3)
        self.assertEqual(first["by_rung"], {"advisor": 1, "jev": 1, "park": 1})
        self.assertEqual(first["by_advisor"], {"codex m1": 1})
        self.assertEqual(first["jev_p"], {"n": 2, "min": 0.6, "median": 0.75, "max": 0.9})
        self.assertEqual((first["parked"], first["denied"]), (1, 2))
        # The later review of one id replaces the earlier one: one reversed of two reviewed.
        self.assertEqual((first["reviewed"], first["reversed"]), (2, 1))
        self.assertEqual(first["no_precedent"], 2)
        self.assertEqual((second["decisions"], second["by_rung"], second["denied"], second["reviewed"]),
                         (1, {"host": 1}, 0, 0))
        args = self.ledger.build_parser().parse_args(["summary"])
        _, output, _ = self.run_quiet(args.func, args)
        self.assertIn("away decisions per lease", output)
        self.assertIn("advisor 1, jev 1, park 1", output)
        self.assertIn("reversed 1 of 2 reviewed", output)
        for word in ("schema", "naming"):
            self.assertNotIn(word, output)  # topic labels stay in the ledger file

    def test_summary_with_only_away_lines_prints_both_sections_honestly(self):
        self.write(self.AWAY)
        args = self.ledger.build_parser().parse_args(["summary"])
        _, output, _ = self.run_quiet(args.func, args)
        self.assertIn("ledger: no finished dispatches match", output)
        self.assertIn("away decisions per lease", output)


class StaleLedgerTest(unittest.TestCase):
    """`stale` previews open records past their budget and `stale --close --digest` closes exactly those."""

    def setUp(self):
        scratch = Path(__file__).resolve().parent.parent / ".finolabs" / "tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.dir = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name).resolve()
        base.chmod(0o755)
        self.home = account(self, base / "home")
        self.path = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.path.parent.mkdir(parents=True, mode=0o700)
        self.home.joinpath(".finolabs").chmod(0o700)
        self.logs = base / "work" / ".finolabs" / "logs"
        spec = importlib.util.spec_from_file_location("stale_ledger", LEDGER)
        self.ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ledger)
        import log_scan
        patch = mock.patch.object(log_scan, "run_log_folder", return_value=self.logs)
        patch.start()
        self.addCleanup(patch.stop)
        # `stale` acts on this repository's ledger project; these tests stand in a checkout named `demo`.
        self.resolve = self.ledger.this_project
        patch = mock.patch.object(self.ledger, "this_project", return_value="demo")
        self.project = patch.start()
        self.addCleanup(patch.stop)

    def start(self, ident, minutes_ago, budget, project="demo"):
        from datetime import datetime, timedelta, timezone
        ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
        return {"event": "start", "id": ident, "ts": ts, "project": project, "task": "t", "kind": "implement",
                "grade": "easy", "coordinator": "claude", "agent": "codex", "model": "m", "reason": "routing",
                "budget_min": budget}

    def write(self, records):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in records))
        self.path.chmod(0o600)

    def log(self, ident, text):
        self.logs.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.logs.chmod(0o700)
        (self.logs / (ident + ".log")).write_text(text)

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def finishes(self):
        return {r["id"]: r for r in self.records() if r["event"] == "finish"}

    def stale(self, *argv):
        args = self.ledger.build_parser().parse_args(["stale", *argv])
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                args.func(args)
            except (SystemExit, ValueError) as error:
                code = error.code if isinstance(error, SystemExit) else 1
        return code, out.getvalue(), err.getvalue()

    def preview_digest(self):
        code, out, err = self.stale()
        self.assertEqual(code, 0, err)
        return out, [line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("Digest: ")][0]

    def test_inside_budget_and_finished_records_are_never_listed_or_closed(self):
        done = {"event": "finish", "id": "d20261101-000000-dddd", "ts": "2026-11-01T01:00:00+00:00",
                "outcome": "rejected", "rework_rounds": 0}
        self.write([self.start("d20261101-000000-aaaa", 1500, 30), self.start("d20261101-000000-bbbb", 10, 30),
                    self.start("d20261101-000000-cccc", 500, None), self.start("d20261101-000000-dddd", 900, 30),
                    done])
        out, digest = self.preview_digest()
        self.assertIn("d20261101-000000-aaaa", out)
        for ident in ("bbbb", "cccc", "dddd"):
            self.assertNotIn("d20261101-000000-" + ident, out)
        self.assertEqual(len(self.records()), 5)  # the preview writes no ledger line
        code, _, err = self.stale("--close", "--digest", digest[:12])
        self.assertEqual(code, 0, err)
        self.assertEqual(set(self.finishes()), {"d20261101-000000-aaaa", "d20261101-000000-dddd"})

    # Scope: `stale` sees only this repository's project unless --all-projects widens the preview.

    MINE, OTHER = "d20261101-000000-a101", "d20261101-000000-a102"

    def write_two_projects(self):
        self.write([self.start(self.MINE, 1500, 30), self.start(self.OTHER, 1500, 30, project="other-app")])

    def test_stale_previews_and_closes_only_this_repositorys_project(self):
        self.write_two_projects()
        out, digest = self.preview_digest()
        self.assertIn(self.MINE, out)
        self.assertNotIn(self.OTHER, out)
        self.assertNotIn("other-app", out)
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        self.assertEqual(set(self.finishes()), {self.MINE})

    def test_all_projects_widens_the_preview_with_a_warning_and_binds_the_scope(self):
        self.write_two_projects()
        code, out, err = self.stale("--all-projects")
        self.assertEqual(code, 0, err)
        self.assertIn(self.ledger.ALL_PROJECTS_WARNING, out)
        self.assertIn(self.MINE, out)
        self.assertIn(self.OTHER, out)
        self.assertIn("stale --close --all-projects --digest", out)
        digest = [line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("Digest: ")][0]
        before = self.path.read_bytes()
        code, _, _ = self.stale("--close", "--digest", digest)  # the scope is part of what the digest binds
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.stale("--close", "--all-projects", "--digest", digest)[0], 0)
        self.assertEqual(set(self.finishes()), {self.MINE, self.OTHER})

    def test_a_one_project_preview_closes_only_from_that_project(self):
        self.write_two_projects()
        _, digest = self.preview_digest()
        before = self.path.read_bytes()
        code, _, _ = self.stale("--close", "--all-projects", "--digest", digest)
        self.assertNotEqual(code, 0)
        self.project.return_value = "other-app"  # the same preview, closed from another repository's checkout
        code, _, _ = self.stale("--close", "--digest", digest)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.project.return_value = "demo"
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        self.assertEqual(set(self.finishes()), {self.MINE})

    def test_an_unresolved_project_refuses_without_all_projects(self):
        self.write_two_projects()
        self.project.return_value = None
        code, out, _ = self.stale()
        self.assertNotEqual(code, 0)
        self.assertNotIn("Digest:", out)
        with self.assertRaises(ValueError) as refused:
            self.ledger.stale_preview()
        self.assertIn("--all-projects", str(refused.exception))
        self.assertEqual(self.stale("--all-projects")[0], 0)

    def test_the_project_resolves_as_status_does_from_the_checkout_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder).resolve() / "demo-repo"
            (repo / "sub").mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
            self.assertEqual(self.resolve(cwd=str(repo / "sub")), "demo-repo")
            self.assertIsNone(self.resolve(cwd=folder))  # outside any repository

    # The dispatch wrapper's `ended` line: read by load, open and stale, never a finish, ignored by summary.

    def ended(self, ident, code):
        return {"event": "ended", "id": ident, "ts": "2026-11-01T00:00:00+00:00", "exit": code}

    def test_ended_lines_fill_their_own_map_and_are_never_finishes(self):
        ident = "d20261101-000000-c001"
        self.write([self.start(ident, 30, 60), self.ended(ident, 2), {"event": "ended", "id": ident}])
        err, ended = io.StringIO(), {}
        with contextlib.redirect_stderr(err):
            starts, finishes = self.ledger.load(ended)
            plain = self.ledger.load()
        self.assertEqual((set(starts), finishes), ({ident}, {}))
        self.assertEqual(ended[ident]["exit"], 2)
        self.assertEqual(plain, (starts, finishes))  # callers that pass no map see the two maps unchanged
        self.assertNotIn("malformed line 2", err.getvalue())
        self.assertIn("malformed line 3", err.getvalue())  # an ended line without its keys is still malformed
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.ledger.cmd_open(self.ledger.build_parser().parse_args(["open"]))
        [line] = out.getvalue().splitlines()
        self.assertTrue(line.startswith(ident))
        self.assertTrue(line.endswith("ended exit=2"))

    def test_summary_ignores_ended_lines(self):
        done, running = "d20261101-000000-c002", "d20261101-000000-c003"
        finish = {"event": "finish", "id": done, "ts": "2026-11-02T00:00:00+00:00", "outcome": "rejected",
                  "rework_rounds": 0}
        self.write([self.start(done, 3000, 30), self.ended(done, 0), finish,
                    self.start(running, 3000, 30), self.ended(running, 1)])
        [row] = self.ledger.summary_rows()
        self.assertEqual((row["n"], row["accepted"], row["error"]), (1, 0, 0))

    def test_an_ended_run_is_due_without_waiting_for_twice_its_budget(self):
        ids = {name: "d20261101-000000-" + name for name in ("c101", "c102", "c103", "c104")}
        self.write([self.start(ids["c101"], 1500, 800), self.ended(ids["c101"], 3),    # ended nonzero: error
                    self.start(ids["c102"], 1500, 800), self.ended(ids["c102"], 0),    # ended 0: cancelled
                    self.start(ids["c103"], 1500, 800),                                # no ended line: waits 2x budget
                    self.start(ids["c104"], 120, 30), self.ended(ids["c104"], 1)])     # ended, under 24 hours
        self.log(ids["c101"], "exit=0\n")  # the ended line wins; the log is not read
        out, digest = self.preview_digest()
        listed = {ident for ident in ids.values() if ident in out}
        self.assertEqual(listed, {ids["c101"], ids["c102"]})
        self.assertIn("ended exit=3  -> error", out)
        self.assertIn("ended exit=0  -> cancelled", out)
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        finishes = self.finishes()
        self.assertEqual(set(finishes), {ids["c101"], ids["c102"]})
        self.assertEqual(finishes[ids["c101"]]["outcome"], "error")
        self.assertEqual(finishes[ids["c102"]]["outcome"], "cancelled")
        self.assertIn("run ended exit 0; no verdict recorded", finishes[ids["c102"]]["note"])
        for finish in finishes.values():
            self.assertNotEqual(finish["outcome"], "accepted")

    def test_older_than_hours_lowers_the_floor_for_an_ended_run_even_inside_its_budget(self):
        ident = "d20261101-000000-c201"
        self.write([self.start(ident, 120, 600), self.ended(ident, 1)])
        code, out, _ = self.stale()
        self.assertEqual(code, 0)
        self.assertNotIn(ident, out)
        code, out, err = self.stale("--older-than-hours", "1")
        self.assertEqual(code, 0, err)
        self.assertIn(ident, out)
        digest = [line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("Digest: ")][0]
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        self.assertEqual(self.finishes()[ident]["outcome"], "error")

    def test_nothing_past_budget_prints_so_and_writes_no_preview(self):
        self.write([self.start("d20261101-000000-bbbb", 10, 30)])
        code, out, _ = self.stale()
        self.assertEqual(code, 0)
        self.assertIn("no open records past the stale threshold", out)
        self.assertNotIn("Digest:", out)

    def test_by_default_a_record_is_stale_past_twice_its_budget_and_at_least_24_hours(self):
        ids = {name: "d20261101-000000-" + name for name in ("a001", "a002", "a003", "a004", "a005", "a006")}
        self.write([self.start(ids["a001"], 120, 30),     # past its budget, under 24 hours: open
                    self.start(ids["a002"], 1500, 30),    # past 24 hours and twice its budget: stale
                    self.start(ids["a003"], 1500, 800),   # past 24 hours, under twice its budget: open
                    self.start(ids["a004"], 1700, 800),   # past both: stale
                    self.start(ids["a005"], 1500, None),  # no usable budget, past 24 hours: stale
                    self.start(ids["a006"], 1000, None)])  # no usable budget, under 24 hours: open
        out, digest = self.preview_digest()
        listed = {ident for ident in ids.values() if ident in out}
        self.assertEqual(listed, {ids["a002"], ids["a004"], ids["a005"]})
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        self.assertEqual(set(self.finishes()), {ids["a002"], ids["a004"], ids["a005"]})

    def test_older_than_hours_sets_the_threshold_but_never_reaches_inside_a_budget(self):
        ids = {name: "d20261101-000000-" + name for name in ("b001", "b002", "b003", "b004")}
        self.write([self.start(ids["b001"], 120, 30),     # past one hour and its budget: stale
                    self.start(ids["b002"], 50, 30),      # under one hour: open
                    self.start(ids["b003"], 90, 100),     # past one hour, inside its budget: open
                    self.start(ids["b004"], 90, None)])   # no usable budget, past one hour: stale
        code, out, err = self.stale("--older-than-hours", "1")
        self.assertEqual(code, 0, err)
        listed = {ident for ident in ids.values() if ident in out}
        self.assertEqual(listed, {ids["b001"], ids["b004"]})
        digest = [line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("Digest: ")][0]
        # The close rechecks each record against the threshold the preview used, not the default.
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        self.assertEqual(set(self.finishes()), {ids["b001"], ids["b004"]})

    def test_older_than_hours_is_bounded_and_belongs_to_the_preview(self):
        self.write([self.start("d20261101-000000-aaaa", 1500, 30)])
        for value in ("0", "-1", "8761", "x"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.ledger.build_parser().parse_args(["stale", "--older-than-hours", value])
        _, digest = self.preview_digest()
        before = self.path.read_bytes()
        code, _, _ = self.stale("--close", "--digest", digest, "--older-than-hours", "1")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_the_preview_lists_id_age_and_label_only(self):
        start = self.start("d20261101-000000-aaaa", 1500, 30)
        start.update(project="demo", task="003 T101", model="synthetic-model")
        self.write([start])
        out, _ = self.preview_digest()
        [line] = [line for line in out.splitlines() if line.startswith("d20261101-000000-aaaa")]
        self.assertIn("demo: 003 T101", line)
        self.assertNotIn("synthetic-model", out)

    def test_session_start_counts_stale_closed_records_as_closed(self):
        self.write([self.start("d20261101-000000-aaaa", 1500, 30), self.start("d20261101-000000-bbbb", 10, 30)])
        _, digest = self.preview_digest()
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        sys.path.insert(0, str(LEDGER.parents[3] / "scripts"))
        import session_start
        self.assertEqual(session_start.open_dispatches(), "1")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.ledger.cmd_open(self.ledger.build_parser().parse_args(["open"]))
        self.assertEqual([line.split()[0] for line in out.getvalue().splitlines()], ["d20261101-000000-bbbb"])

    def test_digest_mismatch_writes_nothing(self):
        self.write([self.start("d20261101-000000-aaaa", 1500, 30)])
        _, digest = self.preview_digest()
        wrong = ("0" if digest[0] != "0" else "1") + digest[1:12]
        before = self.path.read_bytes()
        code, _, _ = self.stale("--close", "--digest", wrong)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)
        code, _, _ = self.stale("--close", "--digest", digest[:6])  # too short to identify a preview
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_close_without_a_preview_writes_nothing(self):
        self.write([self.start("d20261101-000000-aaaa", 1500, 30)])
        before = self.path.read_bytes()
        code, _, _ = self.stale("--close", "--digest", "a" * 12)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_expired_preview_writes_nothing(self):
        import time as clock
        self.write([self.start("d20261101-000000-aaaa", 1500, 30)])
        _, digest = self.preview_digest()
        before = self.path.read_bytes()
        later = clock.time() + 3601
        with mock.patch.object(self.ledger.time, "time", return_value=later):
            code, _, _ = self.stale("--close", "--digest", digest)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_a_log_named_with_the_documented_slug_is_found(self):
        ident = "d20261101-000000-e002"
        self.write([self.start(ident, 1500, 45)])
        self.log(ident + "-add-parser", "output\nexit=1\n")
        out, _ = self.preview_digest()
        self.assertIn("exit=1  -> error", out)

    def test_a_held_finish_lock_ends_in_a_bounded_refusal(self):
        import fcntl, time
        self.write([self.start("d20261101-000000-e004", 1500, 45)])
        with self.ledger.dr.data_folder(self.ledger.FINISH_LOCK, create=True, private=True) as folder:
            other = os.open(".", os.O_RDONLY, dir_fd=folder)
            try:
                fcntl.flock(other, fcntl.LOCK_EX)
                started = time.monotonic()
                with mock.patch.object(self.ledger, "LOCK_WAIT", 0.3), self.assertRaises(SystemExit):
                    with self.ledger.finish_lock():
                        pass
                self.assertLess(time.monotonic() - started, 5)
            finally:
                os.close(other)
        with self.ledger.finish_lock():
            pass

    def test_close_reads_open_state_under_the_finish_lock(self):
        ident = "d20261101-000000-e003"
        self.write([self.start(ident, 1500, 45)])
        _, digest = self.preview_digest()
        held, real_lock, real_load = [], self.ledger.finish_lock, self.ledger.load

        @contextlib.contextmanager
        def lock():
            with real_lock():
                held.append(True)
                yield
                held.pop()

        def load(*args):
            self.assertTrue(held, "close read the open state outside the finish lock")
            return real_load(*args)

        with mock.patch.object(self.ledger, "finish_lock", lock), mock.patch.object(self.ledger, "load", load):
            self.ledger.stale_close(digest)
        self.assertEqual(self.finishes()[ident]["outcome"], "cancelled")

    def test_each_outcome_follows_the_log_and_none_is_accepted(self):
        ids = {name: "d20261101-000000-" + name for name in ("e001", "e000", "eeee", "ffff")}
        self.write([self.start(ident, 1500, 45) for ident in ids.values()])
        self.log(ids["e001"], "lots of output\nexit=1\n")
        self.log(ids["e000"], "x" * 500 + "\nexit=0\n")
        self.log(ids["eeee"], "still running, no exit line\n")
        out, digest = self.preview_digest()
        self.assertIn("exit=1", out)
        self.assertIn("log: none  -> cancelled", out)
        self.assertIn("exit=1  -> error", out)
        code, _, err = self.stale("--close", "--digest", digest)
        self.assertEqual(code, 0, err)
        finishes = self.finishes()
        self.assertEqual(finishes[ids["e001"]]["outcome"], "error")
        self.assertEqual(finishes[ids["e000"]]["outcome"], "stalled")
        self.assertEqual(finishes[ids["eeee"]]["outcome"], "stalled")
        self.assertEqual(finishes[ids["ffff"]]["outcome"], "cancelled")
        for finish in finishes.values():
            self.assertIn("closed late", finish["note"])
            self.assertNotEqual(finish["outcome"], "accepted")
            self.assertNotIn("verified_head", finish)
            self.assertNotIn("accept_unverified", finish)
            self.assertNotIn("still running", json.dumps(finish))  # no log content is stored
        self.assertNotIn("still running", out)

    def test_the_exit_line_is_read_only_from_the_last_64_bytes(self):
        ident = "d20261101-000000-e002"
        self.write([self.start(ident, 1500, 45)])
        self.log(ident, "exit=1\n" + "y" * 100 + "\n")
        _, digest = self.preview_digest()
        self.stale("--close", "--digest", digest)
        self.assertEqual(self.finishes()[ident]["outcome"], "stalled")

    def test_a_symlinked_log_is_refused_and_its_record_left_open(self):
        ident = "d20261101-000000-e003"
        self.write([self.start(ident, 1500, 45), self.start("d20261101-000000-aaaa", 1500, 45)])
        self.log("other", "exit=1\n")
        (self.logs / (ident + ".log")).symlink_to(self.logs / "other.log")
        out, digest = self.preview_digest()
        self.assertIn("log: refused  -> left open", out)
        self.stale("--close", "--digest", digest)
        self.assertEqual(set(self.finishes()), {"d20261101-000000-aaaa"})

    def test_a_second_close_with_the_same_digest_writes_nothing(self):
        self.write([self.start("d20261101-000000-aaaa", 1500, 30)])
        _, digest = self.preview_digest()
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        before = self.path.read_bytes()
        code, _, _ = self.stale("--close", "--digest", digest)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_a_record_finished_after_the_preview_is_not_closed_twice(self):
        self.write([self.start("d20261101-000000-aaaa", 1500, 30), self.start("d20261101-000000-bbbb", 1500, 30)])
        _, digest = self.preview_digest()
        with self.path.open("a") as stream:
            stream.write(json.dumps({"event": "finish", "id": "d20261101-000000-aaaa", "ts": "2026-11-10T00:00:00+00:00",
                                     "outcome": "rejected", "rework_rounds": 0}) + "\n")
        self.assertEqual(self.stale("--close", "--digest", digest)[0], 0)
        finishes = [r for r in self.records() if r["event"] == "finish"]
        self.assertEqual(sorted(r["id"] for r in finishes),
                         ["d20261101-000000-aaaa", "d20261101-000000-bbbb"])

    def test_load_and_pause_status_see_closed_records_as_closed(self):
        self.write([self.start("d20261101-000000-aaaa", 1500, 30), self.start("d20261101-000000-bbbb", 10, 30)])
        _, digest = self.preview_digest()
        self.stale("--close", "--digest", digest)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            starts, finishes = self.ledger.load()
        self.assertEqual(err.getvalue(), "")  # finish lines written here are well formed
        self.assertEqual(set(starts), {"d20261101-000000-aaaa", "d20261101-000000-bbbb"})
        self.assertEqual(set(finishes), {"d20261101-000000-aaaa"})
        sys.path.insert(0, str(LEDGER.parent))
        import pause
        rows = pause.open_dispatches()
        self.assertEqual([row[0] for row in rows], ["d20261101-000000-bbbb"])


class LedgerReviewFixesTest(unittest.TestCase):
    """Defects found in the 14/11/2026 ledger data review (backlog section P)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name).resolve()
        self.home = account(self, self.base / "home")
        self.path = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.path.parent.mkdir(parents=True)
        self.env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        spec = importlib.util.spec_from_file_location("review_fixes_ledger", LEDGER)
        self.ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ledger)
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)

    def run_ledger(self, *args, cwd=None, check=True):
        result = subprocess.run([sys.executable, "-I", str(LEDGER), *args], capture_output=True, text=True,
                                env=self.env, cwd=cwd)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def write(self, records):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in records))
        self.path.chmod(0o600)

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def pair(self, ident, minutes, kind="implement", **finish):
        start = {"event": "start", "id": ident, "ts": "2026-11-10T01:00:00+00:00", "project": "demo", "task": "t",
                 "kind": kind, "grade": "medium", "agent": "codex", "model": "m1", "reason": "routing",
                 "route_by": "table", "budget_min": 30}
        done = {"event": "finish", "id": ident, "ts": "2026-11-10T01:%02d:00+00:00" % minutes, "outcome": "accepted",
                "rework_rounds": 0, "tests": "passed", "note": "", "log_scan": "not_scanned", **finish}
        return [start, done]

    def git(self, *args, cwd):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=cwd,
                       check=True, capture_output=True)

    # 1. Log location, refusal reason, empty log.
    def test_finish_accepts_a_log_in_the_main_checkout_from_a_linked_worktree(self):
        main, tree = self.base / "main", self.base / "tree"
        main.mkdir()
        self.git("init", "-q", cwd=main)
        self.git("commit", "-q", "--allow-empty", "-m", "init", cwd=main)
        self.git("worktree", "add", "-q", str(tree), cwd=main)
        logs = main / ".finolabs" / "logs"
        logs.mkdir(parents=True, mode=0o700)
        (main / ".finolabs").chmod(0o700)
        log = logs / "run.log"
        log.write_text("ordinary output\n")
        log.chmod(0o600)
        for extra in ([], ["--checkout", str(tree)]):
            with self.subTest(extra=extra):
                ident = self.run_ledger(*START, cwd=tree).stdout.strip()
                self.run_ledger("finish", ident, "--outcome", "rejected", "--log-path", str(log), *extra, cwd=tree)
                self.assertEqual(self.records()[-1]["log_scan"], "no_findings")

    def test_a_refused_log_gets_one_fixed_reason_line_without_the_path(self):
        ident = self.run_ledger(*START, cwd=self.base).stdout.strip()
        outside = self.base / "outside.log"
        outside.write_text("ordinary\n")
        result = self.run_ledger("finish", ident, "--outcome", "rejected", "--log-path", str(outside), cwd=self.base,
                                 check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, self.ledger.LOG_REFUSED + "\n")
        self.assertNotIn(str(outside), result.stderr)
        self.assertIn(".finolabs/logs", self.ledger.LOG_REFUSED)

    def test_an_empty_log_is_not_scanned(self):
        logs = self.base / ".finolabs" / "logs"
        logs.mkdir(parents=True, mode=0o700)
        log = logs / "run.log"
        log.write_bytes(b"")
        log.chmod(0o600)
        ident = self.run_ledger(*START, cwd=self.base).stdout.strip()
        result = self.run_ledger("finish", ident, "--outcome", "rejected", "--log-path", str(log), cwd=self.base)
        self.assertEqual(self.records()[-1]["log_scan"], "not_scanned")
        self.assertIn("ledger: log_scan: not_scanned", result.stderr)

    # 2. Dispatch ids never repeat.
    def test_two_starts_in_the_same_second_with_the_same_token_get_different_ids(self):
        from datetime import datetime as real

        class Fixed(real):
            @classmethod
            def now(cls, tz=None):
                return real(2026, 11, 7, 17, 11, 43, tzinfo=tz)

        args = self.ledger.build_parser().parse_args(START)
        ids = []
        with mock.patch.object(self.ledger, "datetime", Fixed), \
                mock.patch.object(self.ledger.secrets, "token_hex", side_effect=["cf30", "cf30", "cf31"]):
            for _ in range(2):
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    args.func(args)
                ids.append(output.getvalue().strip())
        self.assertEqual(ids, ["d20261107-171143-cf30", "d20261107-171143-cf31"])
        self.assertEqual([r["id"] for r in self.records()], ids)

    # 3. Closed-late cancelled records and the text table.
    def test_closed_late_cancelled_records_stay_out_of_the_rates_and_medians(self):
        self.write(self.pair("d1", 10) + self.pair("d2", 50, outcome="quota") + self.pair("d3", 20, outcome="error")
                   + self.pair("d4", 30, outcome="cancelled", note="stopped by the user")
                   + self.pair("d5", 59, outcome="cancelled", note="closed late by ledger stale: no log"))
        [row] = self.ledger.summary_rows()
        self.assertEqual((row["n"], row["closed_late"], row["cancelled"]), (4, 1, 1))
        self.assertEqual(row["accepted"], 1 / 4)
        self.assertEqual(row["median_min"], 25)
        text = self.run_ledger("summary").stdout.splitlines()
        self.assertEqual(text[0].split()[-3:], ["quota", "error", "cancelled"])
        self.assertEqual(text[1].split()[-3:], ["1", "1", "1"])
        self.assertIn("closed late as cancelled, left out of the rates and medians: 1", text)

    # 4. Field validation.
    def test_rework_rounds_above_two_need_a_reason(self):
        ident = self.run_ledger(*START).stdout.strip()
        refused = self.run_ledger("finish", ident, "--outcome", "rejected", "--rework-rounds", "6", check=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("--rework-rounds above 2 needs a --reason", refused.stderr)
        negative = self.run_ledger("finish", ident, "--outcome", "rejected", "--rework-rounds", "-1", check=False)
        self.assertEqual(negative.returncode, 1)
        self.assertEqual(len(self.records()), 1)
        self.run_ledger("finish", ident, "--outcome", "rejected", "--rework-rounds", "3", "--reason", "Synthetic loop")
        self.assertEqual(self.records()[-1]["rework_rounds"], 3)

    def test_accepted_with_failed_tests_is_refused(self):
        ident = self.run_ledger(*START).stdout.strip()
        refused = self.run_ledger("finish", ident, "--outcome", "accepted", "--tests", "failed",
                                  "--accept-unverified", "--reason", "Synthetic fixture", check=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("cannot have --tests failed", refused.stderr)
        self.assertEqual(len(self.records()), 1)

    def test_a_model_the_matrix_does_not_list_warns_and_still_records(self):
        from tests.test_route_pick import host
        (self.path.parent / "host.md").write_text(host())
        warned = self.run_ledger(*START)
        self.assertIn("ledger: warning: model label is not one the assignment matrix lists", warned.stderr)
        listed = self.run_ledger(*[a if a != "m1" else "claude-opus-5-5" for a in START])
        self.assertNotIn("warning", listed.stderr)
        self.assertEqual(len(self.records()), 2)

    def test_a_project_label_other_than_the_ledger_setting_warns_and_still_records(self):
        import project_store
        args = self.ledger.build_parser().parse_args(START)
        found = ("found", mock.Mock(checkout=self.base))
        for values, warned in (({"ledger": "lab"}, True), ({"ledger": "demo"}, False), ({}, False)):
            with self.subTest(values=values), \
                    mock.patch.object(project_store, "identity", return_value=found), \
                    mock.patch.object(project_store, "settings_state", return_value=("approved", values)):
                errors = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                    args.func(args)
                self.assertEqual("ledger: warning: project label differs from this repository's ledger project (lab)"
                                 in errors.getvalue().splitlines(), warned)
        self.assertEqual(len(self.records()), 3)

    # 5. Acceptance flags.
    def test_summary_flags_accepted_findings_and_reviews_without_a_url(self):
        self.write(self.pair("d1", 10, log_scan="findings") + self.pair("d2", 10, kind="review")
                   + self.pair("d3", 10, kind="review", review_posted=True))
        rows = self.ledger.summary_rows()
        self.assertEqual(sum(r["accepted_findings"] for r in rows), 1)
        self.assertEqual(sum(r["review_unposted"] for r in rows), 1)
        text = self.run_ledger("summary").stdout
        self.assertIn("flag: 1 accepted runs had log scan findings", text)
        self.assertIn("flag: 1 review acceptances have no --review-url", text)

    # 6. Retroactive records.
    def test_retro_records_are_marked_and_left_out_of_medians(self):
        ident = self.run_ledger(*START).stdout.strip()
        self.run_ledger("finish", ident, "--outcome", "rejected", "--retro")
        self.assertIs(self.records()[-1]["retro"], True)
        self.write(self.pair("d1", 10) + self.pair("d2", 30) + self.pair("d3", 0, retro=True))
        [row] = self.ledger.summary_rows()
        self.assertEqual((row["n"], row["retro"], row["median_min"]), (3, 1, 20))
        self.write(self.pair("d3", 0, retro=True))
        [only] = self.ledger.summary_rows()
        self.assertIsNone(only["median_min"])
        self.assertIn("retroactive records, left out of the medians: 1", self.run_ledger("summary").stdout)


if __name__ == "__main__":
    unittest.main()
