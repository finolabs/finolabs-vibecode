"""Exercise actual hook stdout and exits, using only a synthetic account home."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/auto_gate_hook.py"
# Run the shipped script under -I, replacing only the account lookup. No production
# state-path override exists; settings are resolved by the shipped mode.py.
BOOT = '''import pwd, runpy, sys
from types import SimpleNamespace
account_home = sys.argv.pop(1)
pwd.getpwuid = lambda uid: SimpleNamespace(pw_dir=account_home)
sys.dont_write_bytecode = True
script = sys.argv.pop(1)
{setup}
sys.argv[0] = script
runpy.run_path(script, run_name="__main__")
'''


class AutoGateHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.repo = self.home / "repo"
        self.repo.mkdir()
        (self.repo / ".git").touch()
        self.config = self.home / ".finolabs/vibecode/host.md"
        self.config.parent.mkdir(parents=True)
        self.config.write_text("## Delegation mode\nauto\n## Auto gate\non\n")
        self.folder = self.home / ".finolabs/vibecode/state/auto-gate"
        import hashlib
        self.key = hashlib.sha256(os.fsencode(self.repo)).hexdigest()[:12]
        self.state = self.folder / (self.key + ".json")
        self.env = {"HOME": str(self.home / "decoy"), "ORCHESTRATION_HOST_CONFIG": str(self.config),
                    "FNL_STATE_DIR": str(self.home / "decoy"), "XDG_STATE_HOME": str(self.home / "decoy")}
        self.payload = json.dumps({"tool_name": "Write", "cwd": str(self.repo)})
        self.setup = 'sys.path.insert(0, ' + repr(str(ROOT / 'scripts')) + ')'

    def run_hook(self, payload=None, setup=None):
        result = subprocess.run([sys.executable, "-I", "-c", BOOT.format(setup=self.setup if setup is None else setup),
                                 str(self.home), str(HOOK)],
                                input=self.payload if payload is None else payload, env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def seed(self, data):
        self.folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.state.write_text(data)

    def assert_deny(self, output):
        self.assertEqual(len(output.splitlines()), 1)
        self.assertEqual(json.loads(output), {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Run the keep-or-hand-off step of fnl-delegate, then retry."}})

    def test_first_write_denies_once_for_each_write_tool(self):
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                self.state.unlink(missing_ok=True)
                payload = json.dumps({"tool_name": tool, "cwd": str(self.repo), "tool_input": {"ignored": True}})
                self.assert_deny(self.run_hook(payload))
                self.assertEqual(self.run_hook(payload), "")
        self.assertFalse((self.home / "decoy").exists())

    def decoy_config(self, source):
        self.config.unlink()
        decoy = self.repo / "decoy"
        config = decoy / ".finolabs/vibecode/host.md"
        config.parent.mkdir(parents=True)
        config.write_text("## Delegation mode\nauto\n## Auto gate\non\n")
        self.env["HOME"] = str(decoy)
        if source == "override":
            self.env["ORCHESTRATION_HOST_CONFIG"] = str(config)
        else:
            self.env.pop("ORCHESTRATION_HOST_CONFIG", None)
        if source == "xdg":
            config.rename(decoy / "host.md")
            self.env["XDG_CONFIG_HOME"] = str(self.repo)
            legacy = self.repo / "finolabs-vibecode"
            legacy.mkdir()
            (decoy / "host.md").rename(legacy / "host.md")

    def test_decoy_override_cannot_opt_in_hook(self):
        self.decoy_config("override")
        self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.folder.exists())

    def test_decoy_home_cannot_opt_in_hook(self):
        self.decoy_config("home")
        self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.folder.exists())

    def test_decoy_xdg_cannot_opt_in_hook(self):
        self.decoy_config("xdg")
        self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.folder.exists())

    def test_decoy_override_cannot_opt_in_writers(self):
        self.decoy_config("override")
        for kind in ("keep", "implement"):
            with self.subTest(kind=kind):
                self.run_writer(kind)
                self.assertFalse(self.folder.exists())

    def test_decoy_home_cannot_opt_in_writers(self):
        self.decoy_config("home")
        for kind in ("keep", "implement"):
            with self.subTest(kind=kind):
                self.run_writer(kind)
                self.assertFalse(self.folder.exists())

    def test_decoy_xdg_cannot_opt_in_writers(self):
        self.decoy_config("xdg")
        for kind in ("keep", "implement"):
            with self.subTest(kind=kind):
                self.run_writer(kind)
                self.assertFalse(self.folder.exists())

    def test_off_values_allow_before_file_access(self):
        for value in ("off", "0", "false", "no", "OFF", "False", "NO"):
            with self.subTest(value=value):
                self.env["FNL_AUTO_GATE"] = value
                self.assertEqual(self.run_hook(setup='import os\nos.open = lambda *a, **k: os._exit(99)'), "")
        self.assertFalse(self.folder.exists())

    def test_non_write_tools_and_bad_input_allow_without_state(self):
        payloads = ["", "{", "[]", "null", "{}", "x" * 65537,
                    '{"tool_name":"Write"}', '{"tool_name":"Write","cwd":7}']
        payloads += [json.dumps({"tool_name": t, "cwd": str(self.repo)}) for t in ("Read", "Bash", "Glob")]
        for payload in payloads:
            with self.subTest(payload=payload[:60]):
                self.assertEqual(self.run_hook(payload), "")
        self.assertFalse(self.folder.exists())

    def test_config_opt_in_and_effective_auto_both_required(self):
        for text, env in (
            ("## Delegation mode\nauto\n", {}),
            ("## Delegation mode\nauto\n## Auto gate\noff\n", {}),
            ("## Delegation mode\nmanual\n## Auto gate\non\n", {}),
            ("## Delegation mode\nsuggest\n## Auto gate\non\n", {}),
            ("## Delegation mode\nauto\n", {"FNL_AUTO_GATE": "on"}),
            ("## Delegation mode\nauto\n## Auto gate\non\n", {"FNL_DELEGATION_MODE": "manual"}),
        ):
            with self.subTest(text=text, env=env):
                self.config.write_text(text)
                self.env.pop("FNL_AUTO_GATE", None)
                self.env.pop("FNL_DELEGATION_MODE", None)
                self.env.update(env)
                self.assertEqual(self.run_hook(), "")
                self.assertFalse(self.folder.exists())

    def test_unsafe_canonical_config_allows_without_state(self):
        for data in (b"x" * 262145, b"\xff", b"## Auto gate\non\n## Auto gate\non\n"):
            with self.subTest(data=data[:20]):
                self.config.write_bytes(data)
                self.assertEqual(self.run_hook(), "")
                self.run_writer("keep")
                self.run_writer("implement")
                self.assertFalse(self.folder.exists())
        self.config.unlink()
        target = self.home / "target.md"
        target.write_text("## Delegation mode\nauto\n## Auto gate\non\n")
        self.config.symlink_to(target)
        self.assertEqual(self.run_hook(), "")
        self.config.unlink()
        os.mkfifo(self.config)
        self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.folder.exists())

    def test_symlinked_canonical_config_folder_allows(self):
        target = self.home / "config"
        self.config.parent.rename(target)
        self.config.parent.symlink_to(target, target_is_directory=True)
        self.assertEqual(self.run_hook(), "")
        self.run_writer("keep")
        self.run_writer("implement", rejected=True)
        self.assertFalse(self.folder.exists())

    def test_foreign_canonical_component_allows(self):
        components = (self.home, self.home / ".finolabs", self.config.parent, self.config)
        for component in components:
            setup = self.setup + "\n" + f'''import os
from types import SimpleNamespace
original = os.fstat
inode = os.stat({str(component)!r}).st_ino
def foreign(fd):
 info = original(fd)
 if info.st_ino == inode:
  return SimpleNamespace(st_uid=os.getuid() + 1, st_mode=info.st_mode, st_size=info.st_size)
 return info
os.fstat = foreign
'''
            with self.subTest(component=component):
                self.assertEqual(self.run_hook(setup=setup), "")
                self.assertFalse(self.folder.exists())

    def test_large_first_event_does_not_consume_deny(self):
        self.assertEqual(self.run_hook(" " * 65536 + self.payload), "")
        self.assertFalse(self.folder.exists())
        self.assert_deny(self.run_hook())

    def test_writer_lock_contention_retries(self):
        setup = '''import auto_gate
original = auto_gate.fcntl.flock
calls = 0
def contend(*args):
 global calls
 calls += 1
 if calls < 3: raise BlockingIOError()
 return original(*args)
auto_gate.fcntl.flock = contend
'''
        for kind in ("keep", "implement"):
            with self.subTest(kind=kind):
                self.state.unlink(missing_ok=True)
                self.run_writer(kind, setup)
                self.assertTrue(self.state.exists())
                self.assertEqual(self.run_hook(), "")

    def test_alarm_api_failure_allows(self):
        self.assertEqual(self.run_hook(setup="import signal\ndef fail(*a): raise OSError()\nsignal.alarm = fail"), "")

    def test_only_gate_environment_is_resolved(self):
        setup = self.setup + '\nimport os\noriginal = os.environ\nclass GateEnvironment(dict):\n def __contains__(self, key):\n  if key == "FNL_ROUTING": os._exit(99)\n  return super().__contains__(key)\n def get(self, key, default=None):\n  if key == "FNL_ROUTING": os._exit(99)\n  return super().get(key, default)\nos.environ = GateEnvironment(original)'
        self.assert_deny(self.run_hook(setup=setup))

    def test_no_repository_allows(self):
        self.assertEqual(self.run_hook(json.dumps({"tool_name": "Write", "cwd": str(self.home)})), "")
        self.assertFalse(self.folder.exists())

    def test_stale_decision_and_denial_deny_again(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        self.seed(json.dumps({"decision": "keep", "decided": old, "denied": recent}))
        self.assertEqual(self.run_hook(), "")
        self.seed(json.dumps({"decision": "keep", "decided": old, "denied": old}))
        self.assert_deny(self.run_hook())
        self.assertEqual(self.run_hook(), "")

    def test_malformed_and_oversized_state_allow(self):
        for data in ("{", "{}", "null", "x" * 4097, '{"denied":"bad"}'):
            with self.subTest(data=data[:40]):
                self.seed(data)
                self.assertEqual(self.run_hook(), "")
                self.assertEqual(self.state.read_text(), data)

    def test_symlinked_folder_allows(self):
        self.folder.parent.mkdir(parents=True, exist_ok=True)
        self.folder.symlink_to(self.repo, target_is_directory=True)
        self.assertEqual(self.run_hook(), "")
        self.assertFalse((self.repo / self.state.name).exists())

    def test_symlinked_file_and_fifo_allow(self):
        self.folder.mkdir(parents=True, mode=0o700)
        self.state.symlink_to(self.config)
        self.assertEqual(self.run_hook(), "")
        self.state.unlink()
        os.mkfifo(self.state)
        self.assertEqual(self.run_hook(), "")

    def test_foreign_owned_file_allows(self):
        self.seed('{"denied":"2000-01-01T00:00:00+00:00"}')
        try:
            os.chown(self.state, os.getuid() + 1, -1)
        except PermissionError:
            self.skipTest("current user cannot create a foreign-owned file (chown denied)")
        self.assertEqual(self.run_hook(), "")

    def test_unreadable_state_allows(self):
        if os.getuid() == 0:
            self.skipTest("root bypasses mode-bit read restrictions")
        self.seed('{"denied":"2000-01-01T00:00:00+00:00"}')
        self.state.chmod(0)
        self.addCleanup(self.state.chmod, 0o600)
        self.assertEqual(self.run_hook(), "")

    def test_unwritable_folder_allows(self):
        self.folder.mkdir(parents=True, mode=0o700)
        self.folder.chmod(0o500)
        self.addCleanup(self.folder.chmod, 0o700)
        self.assertEqual(self.run_hook(), "")
        self.assertFalse(self.state.exists())

    def test_failed_publish_or_readback_allows(self):
        for function in ("write_state", "read_state"):
            setup = self.setup + '\nimport auto_gate\n'
            if function == "read_state":
                setup += 'original = auto_gate.read_state\ncalls = 0\ndef fail(*a):\n global calls\n calls += 1\n if calls > 1: raise PermissionError()\n return original(*a)\nauto_gate.read_state = fail'
            else:
                setup += 'def fail(*a, **k): raise PermissionError()\nauto_gate.write_state = fail'
            self.assertEqual(self.run_hook(setup=setup), "")

    def test_parallel_first_writes_at_most_one_deny(self):
        for stale in (False, True):
            if stale:
                self.seed('{"denied":"2000-01-01T00:00:00+00:00"}')
            with ThreadPoolExecutor(max_workers=8) as pool:
                outputs = list(pool.map(lambda _: self.run_hook(), range(8)))
            self.assertLessEqual(sum(bool(output) for output in outputs), 1)
            for output in outputs:
                if output:
                    self.assert_deny(output)
            self.assertEqual(self.run_hook(), "")

    def test_alarm_allows_a_hung_input(self):
        proc = subprocess.Popen([sys.executable, "-I", "-c", BOOT.format(setup=self.setup),
                                 str(self.home), str(HOOK)], env=self.env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(proc.wait(timeout=4), 0)
            self.assertEqual(proc.stdout.read(), b"")
            self.assertEqual(proc.stderr.read(), b"")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdin.close()
            proc.stdout.close()
            proc.stderr.close()

    def run_writer(self, kind="keep", setup="", rejected=False):
        folder = ROOT / "skills/fnl-delegate/scripts"
        if kind == "keep":
            script = folder / "record.py"
            args = ["keep", "--tasks", "1", "--reason", "needs-context"]
        else:
            script = folder / "ledger.py"
            args = ["start", "--project", "fixture", "--task", "fixture", "--kind", kind,
                    "--grade", "easy", "--agent", "subagent", "--budget", "5"]
        setup = 'sys.path.insert(0, ' + repr(str(folder)) + ')\n' + setup
        result = subprocess.run([sys.executable, "-I", "-c", BOOT.format(setup=setup),
                                 str(self.home), str(script), *args], cwd=self.repo,
                                env={**self.env, "ORCHESTRATION_LEDGER": str(self.home / "ledger.jsonl")},
                                capture_output=True, text=True, timeout=5)
        if rejected:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid data root", result.stderr)
            return
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stderr, r"\A(label: [^\n]+\n)?\Z")
        if kind == "keep":
            self.assertEqual(result.stdout, "keep receipt: tasks=1 reason=needs-context route_by=table\n")
        else:
            self.assertRegex(result.stdout, r"^d\d{8}-\d{6}-[0-9a-f]{4}\n$")
        return result.stdout

    def test_writers_record_decisions_and_allow_hook(self):
        for kind, decision in (("implement", "handoff"), ("keep", "keep")):
            with self.subTest(kind=kind):
                self.state.unlink(missing_ok=True)
                self.run_writer(kind)
                self.assertTrue(self.state.exists(), "writer must record the enabled decision")
                state = json.loads(self.state.read_text())
                self.assertEqual(state["decision"], decision)
                self.assertIn("decided", state)
                self.assertEqual(self.run_hook(), "")

    def test_review_dispatch_writes_no_decision(self):
        self.run_writer("review")
        self.assertFalse(self.state.exists())
        self.assert_deny(self.run_hook())

    def test_writer_failures_preserve_output_and_exit(self):
        setup = 'import auto_gate\ndef fail(*a): raise PermissionError()\nauto_gate.write_decision = fail'
        self.run_writer("keep", setup)
        self.run_writer("implement", setup)
        self.assertFalse(self.state.exists())

    def test_writers_only_write_when_gate_enabled(self):
        for config, env in (("## Delegation mode\nauto\n", {}),
                            ("## Delegation mode\nmanual\n## Auto gate\non\n", {}),
                            ("## Delegation mode\nauto\n## Auto gate\non\n", {"FNL_AUTO_GATE": "off"})):
            self.config.write_text(config)
            self.env.update(env)
            self.run_writer("keep")
            self.run_writer("implement")
            self.assertFalse(self.state.exists())
