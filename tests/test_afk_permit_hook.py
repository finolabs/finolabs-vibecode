"""The afk permission hook: actual hook stdout and exits, using only a synthetic account home and environment."""

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
HOOK = ROOT / "scripts/afk_permit_hook.py"
AFK = ROOT / "skills/delegate/scripts/afk.py"
# Run the shipped script under -I, replacing only the account lookup.
BOOT = '''import pwd, runpy, sys
from types import SimpleNamespace
account_home = sys.argv.pop(1)
pwd.getpwuid = lambda uid: SimpleNamespace(pw_dir=account_home, pw_name="afk-test-user")
# As tests/data_root_fixture.py: only writable system ancestors of the synthetic home (a shared /tmp on Linux)
# read as not group- or world-writable; checks on the fixture tree itself stay real.
import os, stat
from pathlib import Path
_ancestors = {(q.stat().st_dev, q.stat().st_ino) for q in Path(account_home).parents if q.stat().st_mode & 0o022}
_fstat = os.fstat
def _seam(fd):
    info = _fstat(fd)
    if (info.st_dev, info.st_ino) in _ancestors and stat.S_ISDIR(info.st_mode):
        fields = list(info)
        fields[0] &= ~0o022
        return os.stat_result(fields)
    return info
os.fstat = _seam
sys.dont_write_bytecode = True
script = sys.argv.pop(1)
sys.argv[0] = script
runpy.run_path(script, run_name="__main__")
'''
SETUP = "## afk\n- Hosts: Claude Code\n"
DENY_START = 'The user is away under an afk lease: settle this request through afk "Decide"'
PARK_START = "The user is away under an afk lease and this request was denied before"
HOST_YES = ["--rung", "host", "--settled", "yes", "--by", "claude", "--option", "1", "--of", "2",
            "--model", "claude-opus-5-5"]


class PermitHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.root = self.home / ".finolabs/vibecode"
        self.state = self.root / "state/autopilot"
        self.state.mkdir(parents=True, mode=0o700)
        (self.root / "state").chmod(0o700)
        self.work = self.home / "work"
        self.work.mkdir()
        # A synthetic environment: only the switch under test is ever set, and nothing is printed from it.
        # Its PATH resolves a bare python3 to the interpreter the hook runs under.
        self.bin = self.home / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        self.env = {"PATH": str(self.bin) + os.pathsep + os.defpath}

    def lease(self, start=None, expiry=None):
        current = time.time()
        value = {"id": "a" * 32, "start": current - 60 if start is None else start,
                 "expiry": current + 3600 if expiry is None else expiry, "settings_hash": "b" * 64}
        path = self.state / "lease.json"
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return value

    def event(self, command="make deploy", tool="Bash", cwd=None, **extra):
        tool_input = {"command": command} if tool == "Bash" else {"file_path": command}
        tool_input.update(extra)
        return {"session_id": "s1", "hook_event_name": "PermissionRequest", "tool_name": tool,
                "tool_input": tool_input, "cwd": str(cwd or self.work)}

    def run_hook(self, event=None, env=None, raw=None):
        payload = raw if raw is not None else json.dumps(event or self.event())
        result = subprocess.run([sys.executable, "-I", "-c", BOOT, str(self.home), str(HOOK)], input=payload,
                                env=env or self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)["hookSpecificOutput"]["decision"] if result.stdout else None

    def digest_of(self, decision):
        message = decision["message"]
        value = message.rsplit("Request digest: ", 1)[1]
        self.assertRegex(value, r"\A[0-9a-f]{64}\Z")
        return value

    def approve(self, value, current=None):
        current = time.time() if current is None else current
        path = self.state / "permits.json"
        kept = json.loads(path.read_text()) if path.exists() else []
        kept.append({"kind": "approval", "digest": value, "time": current, "lease": self.lease_start})
        path.write_text(json.dumps(kept))
        path.chmod(0o600)

    def test_a_request_without_approval_is_denied_with_the_fixed_message_and_its_digest_only(self):
        self.lease_start = self.lease()["start"]
        decision = self.run_hook(self.event("cat notes.txt | wc -l"))
        self.assertEqual(decision["behavior"], "deny")
        self.assertTrue(decision["message"].startswith(DENY_START))
        value = self.digest_of(decision)
        self.assertNotIn("notes.txt", decision["message"])
        expected = hashlib.sha256(json.dumps(
            {"cwd": os.path.realpath(self.work), "input": {"command": "cat notes.txt | wc -l"}, "tool": "Bash"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(value, expected)
        # Only digests are kept: no command text reaches the private state.
        self.assertNotIn("notes", (self.state / "permits.json").read_text())

    def test_an_exact_recorded_approval_allows_once_and_nothing_else(self):
        self.lease_start = self.lease()["start"]
        value = self.digest_of(self.run_hook())
        self.approve(value)
        self.assertEqual(self.run_hook(), {"behavior": "allow"})
        # Used once: the same request is denied again, as a first denial since an approval came in between.
        again = self.run_hook()
        self.assertTrue(again["message"].startswith(DENY_START))
        self.approve(value)
        for other in (self.event("make deploy "), self.event("make deploy", tool="Write"),
                      self.event("make deploy", cwd=self.home), self.event("make deploy", description="x")):
            with self.subTest(other=other):
                self.assertEqual(self.run_hook(other)["behavior"], "deny")
        self.assertEqual(self.run_hook(), {"behavior": "allow"})

    def test_an_expired_approval_or_one_of_another_lease_is_not_used(self):
        self.lease_start = self.lease()["start"]
        value = self.digest_of(self.run_hook())
        self.approve(value, current=time.time() - 1801)
        self.assertEqual(self.run_hook()["behavior"], "deny")
        self.lease_start = self.lease_start - 10
        self.approve(value)
        self.assertEqual(self.run_hook()["behavior"], "deny")

    def test_a_second_denial_without_an_approval_tells_the_agent_to_park(self):
        self.lease_start = self.lease()["start"]
        first = self.run_hook()
        second = self.run_hook()
        self.assertTrue(second["message"].startswith(PARK_START))
        self.assertIn("log --kind parked", second["message"])
        self.assertEqual(self.digest_of(first), self.digest_of(second))

    def test_the_installs_own_lease_commands_with_plain_arguments_are_allowed(self):
        self.lease()
        for command in (f"python3 -I {AFK} log --kind parked --note waiting",
                        f"python3 {AFK} effective", f"{sys.executable} -I {AFK} check --paths src/a.py",
                        f"python3 -I {AFK} log --kind decision --approve-request {'a' * 64} --topic run-it"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(self.event(command)), {"behavior": "allow"})
        for command in (f"python3 -I {AFK} start", f"python3 -I {AFK} log --note 'x'", f"python3 -I {AFK} log; ls",
                        f"python3 -I {AFK} log --note $HOME", f"python3 -I {AFK} log\nls", f"bash {AFK} log",
                        f"python3 -c {AFK} log", f"X=1 python3 -I {AFK} log", f"python3 -I /tmp/afk.py log",
                        f"python3 -I {AFK} log --note a*"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(self.event(command))["behavior"], "deny")
        sandbox = self.event(f"python3 -I {AFK} effective", dangerouslyDisableSandbox=True)
        self.assertEqual(self.run_hook(sandbox)["behavior"], "deny")

    def test_a_bare_interpreter_counts_only_when_the_path_resolves_it_to_the_hooks_own(self):
        self.lease()
        command = f"python3 -I {AFK} effective"
        wrapper = self.home / "wrapper"
        wrapper.mkdir()
        (wrapper / "python3").write_text("#!/bin/sh\nexit 0\n")
        (wrapper / "python3").chmod(0o755)
        for path in (str(wrapper) + os.pathsep + str(self.bin), "relative" + os.pathsep + str(self.bin),
                     os.pathsep + str(self.bin)):
            decision = self.run_hook(self.event(command), env={"PATH": path})
            self.assertEqual(decision["behavior"], "deny", path)
        self.assertEqual(self.run_hook(self.event(command))["behavior"], "allow")

    def test_an_answer_rereads_the_lease_and_the_time_once_it_holds_the_lock(self):
        # A request judged with a time from before the lease ended gets no answer and consumes nothing.
        current = time.time()
        self.lease_start = self.lease(start=current - 600, expiry=current - 1)["start"]
        self.approve("c" * 64, current=current - 60)
        probe = self.home / "probe.py"
        probe.write_text("import sys, time\nsys.path.insert(0, %r)\nimport away_lease\n"
                         "print(away_lease.answer_permit('c' * 64, time.time() - 30))\n" % str(HOOK.parent))
        result = subprocess.run([sys.executable, "-I", "-c", BOOT, str(self.home), str(probe)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual((result.returncode, result.stdout.strip(), result.stderr), (0, "None", ""))
        self.assertIn("c" * 64, (self.state / "permits.json").read_text())

    def test_no_lease_off_switch_and_errors_fall_back_to_the_host_prompt(self):
        self.assertIsNone(self.run_hook())  # no lease
        current = time.time()
        self.lease(start=current - 7200, expiry=current - 1)
        self.assertIsNone(self.run_hook())  # expired
        self.lease()
        for value in ("off", "OFF", "0", "false", "no"):
            self.assertIsNone(self.run_hook(env=dict(self.env, FNL_AFK_PERMIT=value)))
        for raw in ("", "not json", "[]", json.dumps({"tool_name": "Bash"}), "x" * (1024 * 1024 + 2),
                    json.dumps(dict(self.event(), hook_event_name="PreToolUse")),
                    json.dumps(dict(self.event(), cwd="relative"))):
            self.assertIsNone(self.run_hook(raw=raw))
        (self.state / "permits.json").write_text("[]")
        (self.state / "permits.json").chmod(0o644)  # unsafe store: the host's prompt stays
        self.assertIsNone(self.run_hook())
        (self.state / "stop").write_text("")
        (self.state / "stop").chmod(0o600)
        (self.state / "permits.json").chmod(0o600)
        self.assertIsNone(self.run_hook())  # stopped lease

    def afk(self, *argv, cwd=None):
        return subprocess.run([sys.executable, "-I", "-c", BOOT, str(self.home), str(AFK), *argv],
                              env=self.env, capture_output=True, text=True, timeout=30, cwd=cwd or self.work)

    def test_recording_the_digest_through_the_exempt_log_command_lets_the_request_through_once(self):
        (self.root / "host.md").write_text(SETUP)
        (self.root / "host.md").chmod(0o600)
        started = self.afk("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        value = self.digest_of(self.run_hook())
        record = ["log", "--kind", "decision", "--project", "demo", "--topic", "run it", "--precedents", "0",
                  *HOST_YES, "--approve-request", value]
        # The agent's own log command passes the permission hook without an approval of its own.
        self.assertEqual(self.run_hook(self.event("python3 -I " + str(AFK) + " " + " ".join(
            w for w in record if " " not in w))), {"behavior": "allow"})
        logged = self.afk(*record)
        self.assertEqual(logged.returncode, 0, logged.stdout)
        # `check` never consumes a permission approval.
        checked = self.afk("check", "--argv-json", '["make","deploy"]')
        self.assertEqual(json.loads(checked.stdout)["tier"], 1)
        self.assertEqual(self.run_hook(), {"behavior": "allow"})
        self.assertEqual(self.run_hook()["behavior"], "deny")
        # A second denial with no approval in between ends in a parked record.
        self.assertTrue(self.run_hook()["message"].startswith(PARK_START))
        parked = self.afk("log", "--kind", "parked", "--session", "s1", "--note", "waiting for the user")
        self.assertEqual(parked.returncode, 0, parked.stdout)
        lines = [json.loads(line) for line in (self.state / "log.jsonl").read_text().splitlines()]
        self.assertEqual([e["kind"] for e in lines if e["kind"] in {"permit", "parked"}], ["permit", "parked"])
        self.assertNotIn("make deploy", (self.state / "log.jsonl").read_text())

    def test_an_approval_needs_option_one_a_valid_digest_and_one_approval_flag(self):
        (self.root / "host.md").write_text(SETUP)
        (self.root / "host.md").chmod(0o600)
        self.assertEqual(self.afk("start").returncode, 0)
        base = ["log", "--kind", "decision", "--project", "demo", "--topic", "run it", "--precedents", "0"]
        for extra in (["--rung", "host", "--settled", "yes", "--by", "claude", "--option", "2", "--of", "2",
                       "--model", "claude-opus-5-5", "--approve-request", "a" * 64],
                      [*HOST_YES, "--approve-request", "A" * 64], [*HOST_YES, "--approve-request", "a" * 63]):
            with self.subTest(extra=extra):
                self.assertEqual(self.afk(*base, *extra).returncode, 3)
        # `--approve-paths` and `--approve-argv-json` went with `strict` (docs/specs/afk-one-mode.md): a usage error.
        self.assertEqual(self.afk(*base, *HOST_YES, "--approve-request", "a" * 64, "--approve-paths", "src/a.py").returncode, 2)
        self.assertFalse((self.state / "permits.json").exists())
        self.assertEqual(self.afk("log", "--kind", "action", "--approve-request", "a" * 64).returncode, 3)


if __name__ == "__main__":
    unittest.main()
