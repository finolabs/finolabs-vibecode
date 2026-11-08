"""Tests for skills/fnl-delegate/scripts/ledger.py, run through its CLI."""

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

LEDGER = Path(__file__).resolve().parent.parent / "skills/fnl-delegate/scripts/ledger.py"
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

    def test_start_hashes_session_flag_and_overrides_environment(self):
        self.env["CLAUDE_CODE_SESSION_ID"] = "synthetic-other-session"
        result = self.run_ledger(*START, "--session", "abc-123")
        [rec] = self.records()
        self.assertEqual(rec["coord_session"], hashlib.sha256(b"abc-123").hexdigest()[:12])
        self.assertRegex(rec["coord_session"], r"^[0-9a-f]{12}$")
        for raw in ("abc-123", "synthetic-other-session"):
            self.assertNotIn(raw, self.path.read_text() + result.stdout + result.stderr)

    def test_start_hashes_session_environment(self):
        self.env["CLAUDE_CODE_SESSION_ID"] = "abc-123"
        result = self.run_ledger(*START)
        self.assertEqual(self.records()[0]["coord_session"],
                         hashlib.sha256(b"abc-123").hexdigest()[:12])
        self.assertNotIn("abc-123", self.path.read_text() + result.stdout + result.stderr)

    def test_start_records_null_when_session_unknown(self):
        for value in (None, ""):
            if value is not None:
                self.env["CLAUDE_CODE_SESSION_ID"] = value
            self.run_ledger(*START)
            self.assertIsNone(self.records()[-1]["coord_session"])

    def test_start_refuses_invalid_session_flag_without_writing(self):
        self.env["CLAUDE_CODE_SESSION_ID"] = "synthetic-valid-session"
        for value in ("", "a" * 129, "bad session", "bad/session", "bad\n", "é", "bad.session"):
            with self.subTest(case_length=len(value)):
                result = self.run_ledger(*START, "--session", value, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr,
                                 "ledger: --session must contain 1 to 128 ASCII letters, digits, dash or underscore\n")
                self.assertFalse(self.path.exists())

    def test_start_accepts_session_flag_boundaries(self):
        for value in ("A", "Z9_-" * 32):
            self.run_ledger(*START, "--session", value)
            self.assertEqual(self.records()[-1]["coord_session"],
                             hashlib.sha256(value.encode()).hexdigest()[:12])

    def test_open_and_summary_read_mixed_session_records(self):
        old = self.run_ledger(*START).stdout.strip()
        [legacy] = self.records()
        legacy.pop("coord_session", None)
        self.path.write_text(json.dumps(legacy) + "\n")
        new = self.run_ledger(*START, "--session", "abc-123").stdout.strip()
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
        result = self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--head", "a" * 40,
                                 "--accept-unverified", "--reason", "Head binding fixture", check=False)
        self.assertIn("only implementation dispatches", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.records()), 1)

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


if __name__ == "__main__":
    unittest.main()
