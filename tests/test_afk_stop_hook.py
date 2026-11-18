"""The afk stop hook: actual hook stdout and exits, using only a synthetic account home and environment."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/afk_stop_hook.py"
AFK = ROOT / "skills/delegate/scripts/afk.py"
BOOT = '''import pwd, runpy, sys
from types import SimpleNamespace
account_home = sys.argv.pop(1)
pwd.getpwuid = lambda uid: SimpleNamespace(pw_dir=account_home, pw_name="afk-test-user")
sys.dont_write_bytecode = True
script = sys.argv.pop(1)
sys.argv[0] = script
runpy.run_path(script, run_name="__main__")
'''
SESSION = "0b6f3c1e-1111-4222-8333-944455556666"


class StopHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.root = self.home / ".finolabs/vibecode"
        self.state = self.root / "state/autopilot"
        self.state.mkdir(parents=True, mode=0o700)
        (self.root / "state").chmod(0o700)
        self.env = {"PATH": os.defpath}

    def lease(self, start=None, expiry=None):
        current = time.time()
        value = {"id": "a" * 32, "start": current - 600 if start is None else start,
                 "expiry": current + 3600 if expiry is None else expiry, "settings_hash": "b" * 64, "counters": {}}
        path = self.state / "lease.json"
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return value

    def record(self, kind, session=SESSION, age=0):
        entry = {"time": time.time() - age, "tier": 2, "kind": kind, "note": ""}
        if session is not None:
            entry["session"] = hashlib.sha256(session.encode()).hexdigest()[:16]
        path = self.state / "log.jsonl"
        with path.open("a") as stream:
            stream.write(json.dumps(entry) + "\n")
        path.chmod(0o600)

    def run_hook(self, active=False, env=None, raw=None, session=SESSION):
        payload = raw if raw is not None else json.dumps(
            {"session_id": session, "hook_event_name": "Stop", "stop_hook_active": active, "cwd": str(self.home),
             "transcript_path": str(self.home / "t.jsonl")})
        result = subprocess.run([sys.executable, "-I", "-c", BOOT, str(self.home), str(HOOK)], input=payload,
                                env=env or self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout) if result.stdout else None

    def assert_blocks(self, answer):
        self.assertEqual(set(answer), {"decision", "reason"})
        self.assertEqual(answer["decision"], "block")
        self.assertIn('afk "Decide"', answer["reason"])
        self.assertIn("--kind idle", answer["reason"])

    def test_a_pending_turn_is_sent_back_once_then_the_next_stop_passes(self):
        self.lease()
        self.assert_blocks(self.run_hook())
        self.assertIsNone(self.run_hook(active=True))  # the host marks the continued turn
        # A later turn with nothing recorded is sent back again, once.
        self.assert_blocks(self.run_hook())
        mark = next((self.root / "state/afk-stop").iterdir())
        self.assertEqual(mark.name, hashlib.sha256(SESSION.encode()).hexdigest()[:16])
        self.assertNotIn(SESSION, mark.read_text())

    def test_an_idle_or_parked_record_of_this_session_since_its_last_stop_lets_it_through(self):
        self.lease()
        for kind in ("idle", "parked"):
            with self.subTest(kind=kind):
                self.assert_blocks(self.run_hook())
                time.sleep(0.01)
                self.record(kind)
                self.assertIsNone(self.run_hook())
                # The record served its turn: the next turn needs one of its own.
                self.assert_blocks(self.run_hook())
                self.assertIsNone(self.run_hook(active=True))

    def test_another_sessions_record_or_one_before_the_last_stop_does_not_count(self):
        self.lease()
        self.record("idle", session="another-session")
        self.record("parked", session=None)
        self.assert_blocks(self.run_hook())
        self.record("idle", age=3600)  # older than this session's last stop
        self.assert_blocks(self.run_hook())
        self.record("action")
        self.assert_blocks(self.run_hook())

    def test_a_reached_limit_lets_the_stop_through(self):
        self.lease()
        self.assert_blocks(self.run_hook())
        time.sleep(0.01)
        self.record("limit", session=None)
        self.assertIsNone(self.run_hook())

    def test_no_lease_off_switch_and_errors_let_the_stop_through(self):
        self.assertIsNone(self.run_hook())
        current = time.time()
        self.lease(start=current - 7200, expiry=current - 1)
        self.assertIsNone(self.run_hook())
        self.lease()
        for value in ("off", "OFF", "0", "false", "no"):
            self.assertIsNone(self.run_hook(env=dict(self.env, FNL_AFK_STOP=value)))
        for raw in ("", "not json", "[]", json.dumps({"hook_event_name": "Stop"}), "x" * (64 * 1024 + 2),
                    json.dumps({"session_id": SESSION, "hook_event_name": "SubagentStop"}),
                    json.dumps({"session_id": "x" * 129, "hook_event_name": "Stop"})):
            self.assertIsNone(self.run_hook(raw=raw))
        (self.state / "log.jsonl").write_text("not json\n")
        (self.state / "log.jsonl").chmod(0o600)
        self.assertIsNone(self.run_hook())  # an unreadable log
        (self.state / "log.jsonl").chmod(0o644)
        self.assertIsNone(self.run_hook())  # an unsafe log
        (self.state / "stop").write_text("")
        (self.state / "stop").chmod(0o600)
        self.assertIsNone(self.run_hook())  # a stopped lease

    def test_the_hook_holds_no_content_and_reads_no_transcript(self):
        self.lease()
        transcript = self.home / "t.jsonl"
        transcript.write_text("SECRET-LOOKING-TEXT\n")
        transcript.chmod(0o000)  # it would fail to open if read
        self.addCleanup(transcript.chmod, 0o600)
        self.assert_blocks(self.run_hook())
        for path in (self.root / "state").rglob("*"):
            if path.is_file() and path.stat().st_mode & 0o400:
                self.assertNotIn("SECRET", path.read_text(errors="replace"))

    def afk(self, *argv):
        return subprocess.run([sys.executable, "-I", "-c", BOOT, str(self.home), str(AFK), *argv],
                              env=self.env, capture_output=True, text=True, timeout=30, cwd=self.home)

    def test_afk_log_records_idle_with_this_sessions_hash_and_the_stop_passes(self):
        (self.root / "host.md").write_text("## afk\n- Hosts: Claude Code\n- Mode: open\n")
        (self.root / "host.md").chmod(0o600)
        self.assertEqual(self.afk("log", "--kind", "idle", "--session", SESSION).returncode, 3)  # no lease yet
        self.assertEqual(self.afk("start").returncode, 0)
        self.assert_blocks(self.run_hook())
        time.sleep(0.01)
        logged = self.afk("log", "--kind", "idle", "--session", SESSION)
        self.assertEqual(logged.returncode, 0, logged.stdout)
        self.assertIsNone(self.run_hook())
        text = (self.state / "log.jsonl").read_text()
        self.assertNotIn(SESSION, text)
        for bad in (("--kind", "action", "--session", SESSION), ("--kind", "idle", "--session", "a b"),
                    ("--kind", "idle", "--session", "x" * 129)):
            with self.subTest(bad=bad):
                self.assertEqual(self.afk("log", *bad).returncode, 3)


if __name__ == "__main__":
    unittest.main()
