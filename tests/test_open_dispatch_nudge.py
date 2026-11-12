"""The open-dispatch reminder hook: synthetic data roots, ledgers and hook input only."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/open_dispatch_nudge.py"
SESSION = "synthetic-session-0001"
OTHER = "synthetic-session-0002"
PREFIX = "Delegated runs this session started have no ledger outcome: "


def coord(session):
    return hashlib.sha256(session.encode()).hexdigest()[:12]


def start(ident, minutes_ago, budget=30, session=SESSION):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
    record = {"event": "start", "id": ident, "ts": ts, "project": "demo", "task": "t", "kind": "implement",
              "grade": "easy", "agent": "codex", "model": "m", "reason": "routing",
              "coord_session": coord(session) if session else None}
    if budget is not None:
        record["budget_min"] = budget
    return record


def finish(ident):
    return {"event": "finish", "id": ident, "ts": "2026-11-12T00:00:00+00:00", "outcome": "rejected",
            "rework_rounds": 0}


def ended(ident, code=0):
    return {"event": "ended", "id": ident, "ts": "2026-11-12T00:00:00+00:00", "exit": code}


def ident(n):
    return f"d20261112-1000{n:02d}-abcd"


class OpenDispatchNudgeTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = account(self, Path(folder.name).resolve() / "home")
        self.data = self.home / ".finolabs/vibecode"
        self.data.mkdir(parents=True, mode=0o700)
        self.home.joinpath(".finolabs").chmod(0o700)
        self.ledger = self.data / "ledger.jsonl"
        self.marks = self.data / "state/dispatch-nudge"
        self.mark = self.marks / hashlib.sha256(SESSION.encode()).hexdigest()[:16]

    def write(self, records):
        self.ledger.write_text("".join(json.dumps(r) + "\n" for r in records))
        self.ledger.chmod(0o600)

    def run_hook(self, payload=None, raw=None, env=None):
        data = raw if raw is not None else json.dumps(
            payload if payload is not None else {"hook_event_name": "UserPromptSubmit", "session_id": SESSION,
                                                 "prompt": "synthetic"}).encode()
        result = subprocess.run([sys.executable, "-I", str(HOOK)], input=data, capture_output=True, timeout=10,
                                env={"PATH": os.defpath, **(env or {})})
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        return result.stdout.decode()

    def test_prints_this_sessions_overdue_and_ended_records_only(self):
        self.write([start(ident(1), 90),                     # past its 30-minute budget: due
                    start(ident(2), 10), ended(ident(2), 1),  # ended inside its budget: due
                    start(ident(3), 10),                     # inside its budget: not due
                    start(ident(4), 90), finish(ident(4)),   # finished: never due
                    start(ident(5), 90, session=OTHER),      # another session's run: never counted
                    start(ident(6), 90, session=None),       # no coordinator session: never counted
                    start(ident(7), 70, budget=None),        # no budget: 60 minutes
                    start(ident(8), 50, budget=None)])       # no budget, under 60 minutes
        out = self.run_hook()
        self.assertEqual(out, PREFIX + f"3 ({ident(1)}, {ident(2)}, {ident(7)}). Record each with ledger.py finish "
                              "(delegate \"Record\"); a run still working stays open.\n")
        for other in (3, 4, 5, 6, 8):
            self.assertNotIn(ident(other), out)
        self.assertEqual(self.run_hook({"session_id": OTHER}).count(ident(5)), 1)

    def test_at_most_five_ids_are_shown_beside_the_full_count(self):
        self.write([start(ident(n), 90) for n in range(1, 8)])
        out = self.run_hook()
        self.assertTrue(out.startswith(PREFIX + "7 ("))
        self.assertEqual(sum(ident(n) in out for n in range(1, 8)), 5)

    def test_nothing_prints_without_due_records_or_a_ledger(self):
        self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.marks.exists())
        self.write([start(ident(1), 10), start(ident(2), 90), finish(ident(2))])
        self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.mark.exists())  # the mark is written only when the line prints

    def test_prints_at_most_once_per_thirty_minutes_with_a_private_integer_mark(self):
        self.write([start(ident(1), 90)])
        self.assertTrue(self.run_hook().startswith(PREFIX))
        self.assertRegex(self.mark.read_text(), r"\A[0-9]{1,12}\Z")
        self.assertEqual(self.mark.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.run_hook(), "")
        self.mark.write_text(str(int(time.time()) - 31 * 60))
        self.assertTrue(self.run_hook().startswith(PREFIX))
        self.assertEqual(os.listdir(self.marks), [self.mark.name])  # one mark per session, no raw id

    def test_an_unwritable_mark_prints_nothing(self):
        self.write([start(ident(1), 90)])
        self.marks.mkdir(parents=True, mode=0o700)
        self.data.joinpath("state").chmod(0o700)
        self.marks.chmod(0o500)
        try:
            self.assertEqual(self.run_hook(), "")
        finally:
            self.marks.chmod(0o700)
        self.assertFalse(self.mark.exists())

    def test_marks_stay_at_two_hundred_files_oldest_removed(self):
        self.write([start(ident(1), 90)])
        self.marks.mkdir(parents=True, mode=0o700)
        self.data.joinpath("state").chmod(0o700)
        names = [hashlib.sha256(str(n).encode()).hexdigest()[:16] for n in range(200)]
        for age, name in enumerate(names):
            path = self.marks / name
            path.write_text("1")
            path.chmod(0o600)
            os.utime(path, (1_000_000 + age, 1_000_000 + age))
        self.assertTrue(self.run_hook().startswith(PREFIX))
        left = set(os.listdir(self.marks))
        self.assertEqual(len(left), 200)
        self.assertIn(self.mark.name, left)
        self.assertNotIn(names[0], left)  # the oldest went

    def test_the_switch_turns_it_off(self):
        self.write([start(ident(1), 90)])
        for value in ("off", "OFF", "0", "false", "no"):
            with self.subTest(value=value):
                self.assertEqual(self.run_hook(env={"FNL_DISPATCH_NUDGE": value}), "")
        self.assertFalse(self.marks.exists())

    def test_malformed_input_prints_nothing_and_exits_zero(self):
        self.write([start(ident(1), 90)])
        for raw in (b"", b"not json", b"[]", b"null", json.dumps({"session_id": 7}).encode(),
                    json.dumps({"session_id": "bad id; x"}).encode(), json.dumps({"session_id": ""}).encode(),
                    json.dumps({"session_id": "a" * 129}).encode(), b"{" + b" " * (64 * 1024)):
            with self.subTest(raw=raw[:40]):
                self.assertEqual(self.run_hook(raw=raw), "")
        self.ledger.write_text("not json\n" + json.dumps(start(ident(1), 90)) + "\n")
        self.assertTrue(self.run_hook().startswith(PREFIX))  # a malformed line is skipped, not fatal

    def test_the_hook_runs_nothing_and_sends_nothing(self):
        source = HOOK.read_text()
        for word in ("subprocess", "urllib", "socket", "http", "fnl_metrics"):
            self.assertNotIn(word, source)

    def test_the_manifest_declares_one_own_prompt_group_ending_in_exit_zero(self):
        manifest = json.loads((ROOT / ".claude-plugin/hooks.json").read_text())
        groups = [g for g in manifest["hooks"]["UserPromptSubmit"]
                  if any("open_dispatch_nudge.py" in h["command"] for h in g["hooks"])]
        self.assertEqual(len(groups), 1)
        self.assertNotIn("matcher", groups[0])
        [hook] = groups[0]["hooks"]
        self.assertEqual(hook["command"], 'python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/open_dispatch_nudge.py"; exit 0')
        self.assertTrue(hook["command"].endswith("; exit 0"))
        self.assertFalse(hook.get("async", False))
        # Never in the metrics group, and no other host declares it.
        for group in manifest["hooks"]["UserPromptSubmit"]:
            commands = [h["command"] for h in group["hooks"]]
            self.assertFalse(any("metrics_hook.py" in c for c in commands)
                             and any("open_dispatch_nudge.py" in c for c in commands))
        for name in (".codex-plugin/hooks.json", ".antigravity-plugin/hooks.json"):
            path = ROOT / name
            if path.exists():
                self.assertNotIn("open_dispatch_nudge.py", path.read_text())


if __name__ == "__main__":
    unittest.main()
