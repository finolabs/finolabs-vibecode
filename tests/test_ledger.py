"""Tests for skills/fnl-delegate/scripts/ledger.py, run through its CLI."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "skills/fnl-delegate/scripts/ledger.py"
START = ["start", "--project", "demo", "--task", "add parser", "--kind", "implement",
         "--grade", "medium", "--agent", "codex", "--model", "m1", "--budget", "40"]


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "ledger.jsonl"
        self.env = {**os.environ, "ORCHESTRATION_LEDGER": str(self.path)}

    def tearDown(self):
        self.dir.cleanup()

    def run_ledger(self, *args, check=True):
        result = subprocess.run([sys.executable, "-I", str(LEDGER), *args],
                                capture_output=True, text=True, env=self.env)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_the_five_grades_are_accepted_and_an_ultra_hard_run_is_summarised(self):
        for grade in ("easy", "medium", "hard", "very-hard", "ultra-hard"):
            args = [a if a != "medium" else grade for a in START]
            self.assertEqual(self.run_ledger(*args).returncode, 0, grade)
        self.assertNotEqual(self.run_ledger(*[a if a != "medium" else "extreme" for a in START], check=False).returncode, 0)
        self.assertEqual(sorted(r["grade"] for r in json.loads(self.run_ledger("summary", "--json").stdout)), [])

    def test_start_writes_a_start_line_and_prints_its_id(self):
        dispatch_id = self.run_ledger(*START).stdout.strip()
        [rec] = self.records()
        self.assertEqual(rec["event"], "start")
        self.assertEqual(rec["id"], dispatch_id)
        self.assertEqual(rec["budget_min"], 40)
        self.assertEqual(rec["reason"], "routing")
        self.assertEqual(rec["route_by"], "table")

    def test_open_lists_unfinished_runs_with_age_against_budget(self):
        dispatch_id = self.run_ledger(*START).stdout.strip()
        out = self.run_ledger("open").stdout
        self.assertIn(dispatch_id, out)
        self.assertIn("/40 min", out)
        self.run_ledger("finish", dispatch_id, "--outcome", "accepted")
        self.assertEqual(self.run_ledger("open").stdout, "")

    def test_finish_needs_a_start_and_happens_once(self):
        missing = self.run_ledger("finish", "d-missing", "--outcome", "accepted", check=False)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("no start line", missing.stderr)
        dispatch_id = self.run_ledger(*START).stdout.strip()
        self.run_ledger("finish", dispatch_id, "--outcome", "accepted", "--rework-rounds", "1")
        again = self.run_ledger("finish", dispatch_id, "--outcome", "rejected", check=False)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already has a finish line", again.stderr)

    def test_start_rejects_unknown_choices(self):
        bad = self.run_ledger(*[a if a != "codex" else "nobody" for a in START], check=False)
        self.assertNotEqual(bad.returncode, 0)

    def test_summary_counts_first_pass_and_fallbacks(self):
        first = self.run_ledger(*START).stdout.strip()
        second = self.run_ledger(*START, "--reason", "fallback-quota").stdout.strip()
        self.run_ledger("finish", first, "--outcome", "accepted")
        self.run_ledger("finish", second, "--outcome", "accepted", "--rework-rounds", "2")
        row = self.run_ledger("summary").stdout.splitlines()[1].split()
        self.assertEqual(row[:5], ["codex", "m1", "implement", "medium", "2"])
        self.assertEqual(row[5:9], ["50%", "100%", "0", "1"])

    def test_summary_json_reports_the_same_counts_with_quota_and_error(self):
        ids = [self.run_ledger(*START).stdout.strip() for _ in range(3)]
        self.run_ledger("finish", ids[0], "--outcome", "accepted")
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


class LedgerLocationTest(unittest.TestCase):
    """The default file: the finolabs home, or the older XDG file while only that one exists."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = Path(self.dir.name) / "home"
        self.xdg = Path(self.dir.name) / "xdg"
        self.home.mkdir()
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

    def test_an_existing_older_ledger_keeps_being_used_until_a_new_one_exists(self):
        old = self.xdg / "finolabs-vibecode/ledger.jsonl"
        old.parent.mkdir(parents=True)
        old.write_text("")
        self.start()
        self.assertEqual(len(old.read_text().splitlines()), 1)
        self.assertFalse((self.home / ".finolabs").exists())
        new = self.home / ".finolabs/vibecode/ledger.jsonl"
        new.parent.mkdir(parents=True)
        new.write_text("")
        self.start()
        self.assertEqual(len(new.read_text().splitlines()), 1)
        self.assertEqual(len(old.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
