"""The away question gate: actual hook stdout and exits, using only a synthetic account home."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/away_gate_hook.py"
# Run the shipped script under -I, replacing only the account lookup.
BOOT = '''import pwd, runpy, sys
from types import SimpleNamespace
account_home = sys.argv.pop(1)
pwd.getpwuid = lambda uid: SimpleNamespace(pw_dir=account_home)
sys.dont_write_bytecode = True
script = sys.argv.pop(1)
sys.argv[0] = script
runpy.run_path(script, run_name="__main__")
'''
DENY = {"hookSpecificOutput": {
    "hookEventName": "PreToolUse", "permissionDecision": "deny",
    "permissionDecisionReason": 'The user is away under an active away mandate: do not ask the user; follow fnl-autopilot "Decide".'}}


class AwayGateHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.root = self.home / ".finolabs/vibecode"
        self.state = self.root / "state/autopilot"
        self.state.mkdir(parents=True, mode=0o700)
        (self.root / "state").chmod(0o700)
        self.ledger = self.root / "ledger.jsonl"
        # A synthetic environment: only the switch under test is ever set, and nothing is printed from it.
        self.env = {"PATH": os.defpath}
        self.payload = json.dumps({"tool_name": "AskUserQuestion", "tool_input": {"questions": [{"question": "Q?"}]}})

    def lease(self, start=None, expiry=None, **change):
        current = time.time()
        value = {"id": "a" * 32, "start": current - 60 if start is None else start,
                 "expiry": current + 3600 if expiry is None else expiry, "settings_hash": "b" * 64,
                 "counters": {"runs": 0, "runtime_minutes": 0, "actions": 0, "hour_actions": []}}
        value.update(change)
        path = self.state / "lease.json"
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return value

    def run_hook(self, payload=None, env=None):
        result = subprocess.run([sys.executable, "-I", "-c", BOOT, str(self.home), str(HOOK)],
                                input=self.payload if payload is None else payload, env=env or self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def lines(self):
        return [json.loads(line) for line in self.ledger.read_text().splitlines()] if self.ledger.exists() else []

    def test_a_live_lease_denies_the_question_tool_once_per_call_and_records_only_time_and_lease(self):
        lease = self.lease()
        for n in (1, 2):
            output = self.run_hook()
            self.assertEqual(len(output.splitlines()), 1)
            self.assertEqual(json.loads(output), DENY)
            self.assertEqual(len(self.lines()), n)
        line = self.lines()[-1]
        self.assertEqual(set(line), {"event", "ts", "lease_start"})
        self.assertEqual((line["event"], line["lease_start"]), ("question_denied", lease["start"]))
        self.assertNotIn("Q?", self.ledger.read_text())

    def test_no_lease_expired_stopped_and_unreadable_leases_allow(self):
        self.assertEqual(self.run_hook(), "")
        current = time.time()
        self.lease(start=current - 7200, expiry=current - 1)
        self.assertEqual(self.run_hook(), "")  # expired
        self.lease(start=current + 600, expiry=current + 3600)
        self.assertEqual(self.run_hook(), "")  # not yet started
        self.lease()
        (self.state / "stop").write_text("")
        (self.state / "stop").chmod(0o600)
        self.assertEqual(self.run_hook(), "")  # stopped
        (self.state / "stop").unlink()
        for broken in ("{broken", json.dumps({"id": "x"}), json.dumps([])):
            (self.state / "lease.json").write_text(broken)
            self.assertEqual(self.run_hook(), "")
        self.lease()
        (self.state / "lease.json").chmod(0o644)
        self.assertEqual(self.run_hook(), "")  # an unsafe mode is unreadable
        (self.state / "lease.json").unlink()
        target = self.home / "elsewhere.json"
        target.write_text(json.dumps(self.lease()))
        target.chmod(0o600)
        (self.state / "lease.json").unlink()
        (self.state / "lease.json").symlink_to(target)
        self.assertEqual(self.run_hook(), "")  # a link is never followed
        self.assertEqual(self.lines(), [])

    def test_other_tools_bad_input_the_switch_and_errors_allow(self):
        self.lease()
        for payload in (json.dumps({"tool_name": "Write"}), json.dumps({"tool_name": "Bash"}), "", "{broken", "[]",
                        json.dumps({"tool_name": "askuserquestion"}), "x" * (64 * 1024)):
            self.assertEqual(self.run_hook(payload), "")
        for value in ("off", "OFF", "0", "false", "no"):
            self.assertEqual(self.run_hook(env={**self.env, "FNL_AWAY_GATE": value}), "")
        self.assertEqual(self.lines(), [])
        # A ledger that cannot be appended to is an error: the call is allowed.
        self.ledger.mkdir()
        self.assertEqual(self.run_hook(), "")
        self.ledger.rmdir()
        # An invalid data root pointer resolves no lease.
        (self.root / "root.json").write_text('{"root":"relative","id":"x"}')
        self.assertEqual(self.run_hook(), "")
        (self.root / "root.json").unlink()
        # A group- or world-writable state folder is unsafe.
        self.state.chmod(0o777)
        self.assertEqual(self.run_hook(), "")
        self.state.chmod(0o700)
        self.assertEqual(json.loads(self.run_hook()), DENY)

    def test_the_manifest_declares_one_own_group_for_the_question_tool_only(self):
        manifest = json.loads((ROOT / ".claude-plugin/hooks.json").read_text())
        groups = [g for g in manifest["hooks"]["PreToolUse"] if any("away_gate_hook.py" in h["command"] for h in g["hooks"])]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["matcher"], "AskUserQuestion")
        self.assertEqual(len(groups[0]["hooks"]), 1)
        hook = groups[0]["hooks"][0]
        self.assertEqual(hook["command"], 'python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/away_gate_hook.py" 2>/dev/null; exit 0')
        self.assertFalse(hook.get("async", False))
        for name in (".codex-plugin/hooks.json",):
            self.assertNotIn("away_gate_hook.py", (ROOT / name).read_text())
        # The gate runs nothing and makes no network call: its only imports are the standard library and the lease reader.
        source = HOOK.read_text()
        for word in ("subprocess", "urllib", "socket", "http"):
            self.assertNotIn(word, source)


if __name__ == "__main__":
    unittest.main()
