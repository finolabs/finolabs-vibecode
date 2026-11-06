"""Quota acceptance uses synthetic account homes and fake programs only."""
import copy
import io
import importlib.util
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import quota_probe as qp
import data_root as dr
from tests.data_root_fixture import account

FIXTURES = ROOT / "tests/fixtures/quota"
COPIES = ["scripts/quota_probe.py", *[f"skills/{name}/scripts/quota_probe.py" for name in
          ("fnl-setup", "fnl-delegate", "fnl-scan-agents", "fnl-update")]]
MEASURED = qp.timestamp("2026-11-05T09:00:00Z")


class ParsersTest(unittest.TestCase):
    def fixture(self, agent):
        return json.loads((FIXTURES / (qp.SOURCES[agent] + ".json")).read_text())

    def test_fixtures_and_exact_fields(self):
        for agent, count in (("agy", 5), ("codex", 1)):
            groups = qp.parse(agent, json.dumps(self.fixture(agent)), MEASURED)
            self.assertEqual(len(groups), count)
            for item in groups:
                self.assertEqual(set(item), {"name", "window", "remaining_fraction", "reset_time"})

    def require_claude_zone(self):
        try:
            ZoneInfo("Asia/Saigon")
        except ZoneInfoNotFoundError:
            self.skipTest("Asia/Saigon is unavailable: no system timezone data or tzdata package")

    def test_claude_fixture_and_exact_fields(self):
        self.require_claude_zone()
        claude = qp.parse("claude", json.dumps(self.fixture("claude")), MEASURED)
        self.assertEqual(len(claude), 3)
        for item in claude:
            self.assertEqual(set(item), {"name", "window", "remaining_fraction", "reset_time"})
        self.assertEqual(claude[0]["reset_time"], "2026-11-05T10:49:00Z")
        self.assertEqual(claude[2]["name"], "week-model")
        self.assertAlmostEqual(claude[0]["remaining_fraction"], .57)

    def test_strict_shapes_and_prompt(self):
        bad = self.fixture("claude")
        bad["result"] = "\n".join(x for x in bad["result"].splitlines() if not x.startswith("Current session"))
        with self.assertRaises(qp.ShapeError):
            qp.parse("claude", json.dumps(bad), MEASURED)
        for field in ("num_turns", "total_cost_usd"):
            bad = self.fixture("claude")
            bad[field] = 1
            with self.assertRaises(qp.PromptError):
                qp.parse("claude", json.dumps(bad), MEASURED)
        bad = self.fixture("codex")
        del bad["result"]["rateLimits"]["primary"]
        with self.assertRaises(qp.ShapeError):
            qp.parse("codex", json.dumps(bad), MEASURED)

    def test_fraction_and_unknown_names(self):
        for value in (True, False, float("nan"), float("inf"), -.1, 1.1, "0.2"):
            bad = self.fixture("agy")
            bad["command"]["data"]["groups"][0]["buckets"][0]["remaining_fraction"] = value
            with self.assertRaises(qp.ShapeError):
                qp.parse("agy", json.dumps(bad), MEASURED)
        bad = self.fixture("agy")
        bad["response"] = "not parsed"
        bad["command"]["data"]["groups"][0]["name"] = "arbitrary provider text"
        self.assertEqual(qp.parse_agy(bad)[0]["name"], "other")

    def test_unresolvable_zone_is_unverified(self):
        bad = self.fixture("claude")
        bad["result"] = bad["result"].replace("Asia/Saigon", "Invalid/Zone")
        with self.assertRaisesRegex(qp.ShapeError, "unverified"):
            qp.parse("claude", json.dumps(bad), MEASURED)
        with mock.patch.object(qp, "ZoneInfo", side_effect=ZoneInfoNotFoundError("no database")):
            with self.assertRaisesRegex(qp.ShapeError, "unverified"):
                qp.parse("claude", json.dumps(self.fixture("claude")), MEASURED)

    def test_zone_and_year_rollover(self):
        self.require_claude_zone()
        groups = qp.parse_claude(self.fixture("claude"), qp.timestamp("2026-12-31T00:00:00Z"))
        self.assertTrue(groups[0]["reset_time"].startswith("2027-11-05"))

    def test_codex_windows_and_discarded_account_data(self):
        data = self.fixture("codex")
        limits = data["result"]["rateLimits"]
        limits["account"] = {"id": "synthetic", "email": "not-an-address"}
        for minutes, window in ((300, "5h"), (10080, "weekly"), (90, "unknown")):
            limits["primary"]["windowDurationMins"] = minutes
            result = qp.parse_codex(data)
            self.assertEqual(result[0]["window"], window)
            self.assertNotIn("credits", json.dumps(result))
            self.assertNotIn("synthetic", json.dumps(result))


class QuotaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = account(self, self.base / "account")
        self.root = dr.default_root()
        self.config_dir = self.home / ".claude"
        self.config_dir.mkdir(mode=0o700)
        # Test-only permission seam: the system temporary ancestor is writable.
        # Preserve all checks on the synthetic tree, files, ownership and symlinks.
        ancestors = {p.stat().st_ino for p in self.base.parents if p.stat().st_mode & 0o022}
        original = os.fstat
        def fstat(fd):
            info = original(fd)
            if info.st_ino in ancestors and stat.S_ISDIR(info.st_mode):
                fields = list(info)
                fields[0] &= ~0o022
                return os.stat_result(fields)
            return info
        patch = mock.patch.object(os, "fstat", side_effect=fstat)
        patch.start()
        self.addCleanup(patch.stop)
        self.bin = self.base / "bin"
        self.bin.mkdir(mode=0o700)
        # The actual interpreter is used only for our fixed synthetic programs.
        self.interpreter = str(Path(sys.executable).resolve())
        # The test runner itself may be installed under a package manager's git
        # tree. Trust only this exact running interpreter in synthetic programs;
        # keep every production check for fake executables and config folders.
        checked_path = qp.checked_path
        def test_path(value, **kwargs):
            if str(value) == self.interpreter and not kwargs.get("directory"):
                return b""
            return checked_path(value, **kwargs)
        patch = mock.patch.object(qp, "checked_path", side_effect=test_path)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(mock.patch.stopall)

    def fake(self, agent, body=None):
        path = self.bin / agent
        if body is None:
            body = "print(" + repr((FIXTURES / (qp.SOURCES[agent] + ".json")).read_text()) + ")\n"
        path.write_text("#!" + self.interpreter + "\n" + body)
        path.chmod(0o700)
        return {"executable": str(path), "resolved": str(path), "interpreter": self.interpreter,
                "configs": {"default": str(self.config_dir) if agent == "claude" else None}}

    def configure(self, entries):
        lines = ["## Quota probe", "", "- Quota probe: on", "- Date: 2026-11-05",
                 "- Agents: " + ", ".join(entries)]
        for agent, entry in entries.items():
            lines += [f"- Executable {agent}: {entry['executable']}", f"- Interpreter {agent}: {entry['interpreter']}"]
            if "resolved" in entry:
                lines.append(f"- Resolved {agent}: {entry['resolved']}")
            if agent == "claude":
                lines += [f"- Claude config: {label}: {path}" for label, path in entry["configs"].items()]
        dr.write_data("host.md", ("\n".join(lines) + "\n").encode())
        return entries

    def ready(self):
        with qp.state_folder(create=True) as folder:
            qp.write_json(folder, "backoff.json", {})

    def test_canonical_opt_in_and_environment_off_only(self):
        decoy = self.base / "host.md"
        decoy.write_text("## Quota probe\n\n- Quota probe: on\n")
        with mock.patch.dict(os.environ, {"HOME": str(self.base), "ORCHESTRATION_HOST_CONFIG": str(decoy),
                                        "FNL_STATE_DIR": str(self.base), "XDG_STATE_HOME": str(self.base),
                                        "XDG_CONFIG_HOME": str(self.base), "FNL_QUOTA_PROBE": "on"}):
            self.assertEqual(qp.config(), {})
            entries = self.configure({"agy": self.fake("agy")})
            self.assertEqual(qp.config(), entries)
            os.environ["FNL_QUOTA_PROBE"] = "off"
            self.assertEqual(qp.config(), {})
        dr.write_data("root.json", b"broken pointer")
        self.assertEqual(qp.config(), {})

    def test_fences_duplicates_and_missing_date_do_not_opt_in(self):
        self.configure({"agy": self.fake("agy")})
        original = dr.read_data("host.md")
        for body in (b"```\n" + original + b"```\n", original + original,
                     original.replace(b"- Date: 2026-11-05\n", b"")):
            dr.write_data("host.md", body)
            self.assertEqual(qp.config(), {})

    def test_throttle_backoff_and_detached_spawn(self):
        self.configure({"agy": self.fake("agy")})
        with mock.patch.object(qp.subprocess, "Popen") as spawn:
            # The first reading starts now; reserve its retry before spawning.
            def reserved(*args, **kwargs):
                saved = json.loads((self.root / "state/quota/backoff.json").read_text())
                self.assertEqual(saved["agy"]["default"]["error"], "unfinished")
                self.assertGreater(qp.timestamp(saved["agy"]["default"]["retry_after"]), qp.now())
                return mock.Mock()
            spawn.side_effect = reserved
            self.assertTrue(qp.trigger())
            self.assertFalse(qp.trigger())
            self.assertEqual(spawn.call_count, 1)
            self.assertTrue(spawn.call_args.kwargs["start_new_session"])
            spawn.return_value.wait.assert_not_called()
        with qp.state_folder() as folder:
            qp.write_json(folder, "backoff.json", {})
            qp.write_json(folder, "quota.json", {"agy": {"default": {"measured": qp.stamp(qp.now()),
                          "source": "agy-usage", "groups": qp.parse_agy(json.loads((FIXTURES / "agy-usage.json").read_text()))}}})
        with mock.patch.object(qp.subprocess, "Popen") as spawn:
            self.assertFalse(qp.trigger())
            spawn.assert_not_called()

    def test_fresh_marker_stale_marker_and_decoys(self):
        nonce = "f" * 48
        decoy = self.base / "decoy"
        decoy.mkdir()
        (decoy / "worker.json").write_text(json.dumps({"nonce": nonce, "heartbeat": qp.stamp(qp.now())}))
        with mock.patch.dict(os.environ, {"FNL_QUOTA_WORKER": nonce, "FNL_STATE_DIR": str(decoy),
                                        "HOME": str(decoy), "XDG_STATE_HOME": str(decoy)}):
            self.assertFalse(qp.worker_guard())
            with qp.state_folder(create=True) as folder:
                real = qp.claim_marker(folder, qp.now())
                self.assertIsNone(qp.claim_marker(folder, qp.now()))
            self.assertFalse(qp.worker_guard())
            os.environ["FNL_QUOTA_WORKER"] = real
            self.assertTrue(qp.worker_guard())
            with qp.state_folder() as folder:
                qp.write_json(folder, "worker.json", {"nonce": real, "heartbeat": qp.stamp(qp.now() - qp.timedelta(minutes=5))})
            self.assertFalse(qp.worker_guard())

    def test_child_exact_environment_empty_cwd_and_planted_path(self):
        body = "import os,json,stat\nprint(json.dumps({'env':dict(os.environ),'cwd':os.getcwd(),'files':os.listdir('.'),'mode':stat.S_IMODE(os.stat('.').st_mode)}))\n"
        entry = self.fake("claude", body)
        planted = self.base / "repository"
        planted.mkdir()
        (planted / ".git").mkdir()
        sentinel = planted / "ran"
        (planted / "claude").write_text("#!/bin/sh\ntouch " + str(sentinel))
        (planted / "claude").chmod(0o700)
        decoys = {k: "decoy" for k in ("ANTHROPIC_BASE_URL", "NODE_OPTIONS", "CODEX_HOME", "CLAUDE_CONFIG_DIR", "USER", "HOME")}
        decoys["PATH"] = str(planted)
        with mock.patch.dict(os.environ, decoys), mock.patch.object(qp.subprocess, "Popen", wraps=subprocess.Popen) as spawn:
            data = json.loads(qp.command("claude", entry, "default", "a" * 48))
        # macOS Python may add its own runtime variables after exec. Pin the
        # exact environment supplied at the process boundary, and parent drops.
        self.assertNotIn("CLAUDE_CONFIG_DIR", data["env"])
        self.assertEqual(data["env"]["USER"], "quota-test-user")
        self.assertEqual(data["env"]["HOME"], str(self.home))
        expected = qp.environment(entry, "a" * 48)
        self.assertEqual(spawn.call_args.kwargs["env"], expected)
        for key, value in expected.items():
            self.assertEqual(data["env"][key], value)
        for key in ("ANTHROPIC_BASE_URL", "NODE_OPTIONS", "CODEX_HOME"):
            self.assertNotIn(key, data["env"])
        self.assertEqual(data["files"], [])
        self.assertEqual(data["mode"], 0o700)
        self.assertEqual(Path(data["cwd"]).parent, self.root / "tmp")
        self.assertFalse(Path(data["cwd"]).exists())
        self.assertFalse(sentinel.exists())

    def test_child_extra_claude_folder_and_account_environment(self):
        entry = self.fake("claude", "import os,json\nprint(json.dumps(dict(os.environ)))\n")
        extra = self.home / ".claude-work"
        extra.mkdir(mode=0o700)
        entry["configs"] = {"renamed": str(self.config_dir), "work": str(extra)}
        self.configure({"claude": entry})
        entry = qp.config()["claude"]
        self.assertEqual(entry["configs"]["renamed"], str(self.config_dir))
        with mock.patch.dict(os.environ, {"USER": "decoy", "HOME": "decoy",
                                          "CLAUDE_CONFIG_DIR": "decoy"}):
            data = json.loads(qp.command("claude", entry, "work", "a" * 48))
            self.assertEqual(data["CLAUDE_CONFIG_DIR"], str(extra))
            self.assertEqual(data["HOME"], str(self.home))
            self.assertEqual(data.get("USER"), "quota-test-user")
            default = json.loads(qp.command("claude", entry, "renamed", "a" * 48))
            self.assertNotIn("CLAUDE_CONFIG_DIR", default)
            for agent in ("agy", "codex"):
                env = qp.environment(self.fake(agent), "a" * 48)
                self.assertEqual(env["USER"], "quota-test-user")
                self.assertEqual(env["HOME"], str(self.home))
                self.assertNotIn("CLAUDE_CONFIG_DIR", env)

    def test_runtime_changed_mode_owner_and_symlink_refused(self):
        entry = self.fake("agy")
        Path(entry["executable"]).chmod(0o777)
        with self.assertRaises(ValueError):
            qp.checked_executable("agy", entry)
        Path(entry["executable"]).chmod(0o700)
        link = self.bin / "link"
        link.symlink_to(entry["executable"])
        with self.assertRaises(OSError):
            qp.checked_path(link)
        original = os.fstat
        inode = Path(entry["executable"]).stat().st_ino
        def foreign(fd):
            info = original(fd)
            if info.st_ino == inode:
                fields = list(info)
                fields[4] = os.getuid() + 123
                return os.stat_result(fields)
            return info
        with mock.patch.object(os, "fstat", side_effect=foreign):
            with self.assertRaises(ValueError):
                qp.checked_executable("agy", entry)

    def test_config_folder_rejections(self):
        qp.validate_configs({"default": str(self.config_dir)})
        for folders in ({"bad": "relative"}, {"a": str(self.config_dir), "b": str(self.config_dir)},
                        {str(i): str(self.base / str(i)) for i in range(5)}):
            with self.assertRaises((OSError, ValueError)):
                qp.validate_configs(folders)
        symlink = self.base / "linked"
        symlink.symlink_to(self.config_dir)
        with self.assertRaises(OSError):
            qp.validate_configs({"linked": str(symlink)})
        for permissions in (0o770, 0o707):
            self.config_dir.chmod(permissions)
            with self.assertRaises(ValueError):
                qp.validate_configs({"default": str(self.config_dir)})
        self.config_dir.chmod(0o700)
        (self.home / ".git").mkdir()
        with self.assertRaises(ValueError):
            qp.validate_configs({"default": str(self.config_dir)})

    def test_worker_cache_fields_labels_permissions_and_backoff(self):
        entry = self.fake("claude")
        second = self.home / "second"
        second.mkdir(mode=0o700)
        entry["configs"]["personal"] = str(second)
        self.configure({"claude": entry})
        self.ready()
        self.assertEqual(qp.dr.account_home(), self.home)
        self.assertEqual(qp.dr.consent_root(), self.root)
        # This test covers worker/cache isolation. Real IANA conversion is tested
        # separately; a fixed offset keeps the cache test independent of tzdata.
        with mock.patch.object(qp, "now", return_value=MEASURED), \
             mock.patch.object(qp, "ZoneInfo", return_value=qp.timezone(qp.timedelta(hours=7))):
            qp.worker([["claude", "default"], ["claude", "personal"]])
        with qp.state_folder() as folder:
            cache = qp.read_cache(folder)
            self.assertEqual(set(cache["claude"]), {"default", "personal"})
            self.assertEqual(set(cache["claude"]["default"]), {"measured", "source", "groups"})
            delays = qp.read_json(folder, "backoff.json")
            self.assertEqual(delays["claude"]["default"]["error"], "")
        self.assertEqual(stat.S_IMODE((self.root / "state/quota/quota.json").stat().st_mode), 0o600)
        self.assertNotIn(str(self.home), json.dumps(cache))
        self.assertFalse((self.root / "state/quota/worker.json").exists())

    def test_failure_backoffs(self):
        entry = self.fake("claude")
        self.configure({"claude": entry})
        self.ready()
        for failure, error, seconds in ((qp.ShapeError(), "unverified", 86400),
                                        (qp.PromptError(), "prompt", 7 * 86400),
                                        (TimeoutError(), "timeout", 1800), (OSError(), "execution", 1800)):
            with mock.patch.object(qp, "command", side_effect=failure), mock.patch.object(qp, "now", return_value=MEASURED):
                qp.worker([["claude", "default"]])
            with qp.state_folder() as folder:
                record = qp.read_json(folder, "backoff.json")["claude"]["default"]
            self.assertEqual(record, {"retry_after": qp.stamp(MEASURED + qp.timedelta(seconds=seconds)), "error": error})

    def test_codex_exit_without_reply_has_execution_backoff(self):
        self.configure({"codex": self.fake("codex", "import sys\nsys.stdin.readline()\n")})
        # The child exits on EOF itself. Isolate classification from platform
        # killpg behavior (covered separately) so cleanup cannot mask the error.
        with mock.patch.object(qp, "now", return_value=MEASURED), mock.patch.object(qp.os, "killpg"):
            qp.worker([["codex", "default"]])
        with qp.state_folder() as folder:
            self.assertEqual(qp.read_json(folder, "backoff.json")["codex"]["default"],
                             {"retry_after": qp.stamp(MEASURED + qp.timedelta(minutes=30)), "error": "execution"})

    def test_exited_codex_cleanup_preserves_error_and_closes_pipes(self):
        entry = self.fake("codex", "import sys\nsys.stdin.readline()\n")
        processes, popen = [], subprocess.Popen
        def spawn(*args, **kwargs):
            process = popen(*args, **kwargs)
            processes.append(process)
            return process
        def denied_group(*args):
            processes[0].wait(timeout=5)
            raise PermissionError("leader already exited")
        with mock.patch.object(qp.subprocess, "Popen", side_effect=spawn), \
             mock.patch.object(qp.os, "killpg", side_effect=denied_group):
            with self.assertRaisesRegex(OSError, "missing reply"):
                qp.command("codex", entry, "default", "a" * 48)
        self.assertEqual(processes[0].returncode, 0)
        self.assertTrue(processes[0].stdin.closed)
        self.assertTrue(processes[0].stdout.closed)

    def test_status_reads_atomic_cache_while_hook_holds_lock(self):
        self.configure({"agy": self.fake("agy")})
        with mock.patch.object(qp, "now", return_value=MEASURED):
            qp.worker([["agy", "default"]])
            with qp.state_folder() as folder:
                self.assertIn("Quota agy/default: measured", qp.status_lines()[0])

    def test_codex_protocol_ignores_requests_and_kills_group(self):
        reply = (FIXTURES / "codex-rate-limits.json").read_text()
        body = ("import sys,json,time\n"
                "a=json.loads(sys.stdin.readline()); assert a['method']=='initialize'\n"
                "print(json.dumps({'id':99,'method':'execute','params':{}}),flush=True)\n"
                "print(json.dumps({'id':1,'result':{}}),flush=True)\n"
                "assert json.loads(sys.stdin.readline())['method']=='initialized'\n"
                "assert json.loads(sys.stdin.readline())['method']=='account/rateLimits/read'\n"
                "print(" + repr(json.dumps(json.loads(reply))) + ",flush=True)\n"
                "time.sleep(60)\n")
        entry = self.fake("codex", body)
        started = time.monotonic()
        result = qp.command("codex", entry, "default", "a" * 48)
        self.assertEqual(len(qp.parse("codex", result)), 1)
        self.assertLess(time.monotonic() - started, 5)

    def test_timeout_and_output_cap(self):
        entry = self.fake("agy", "import time\ntime.sleep(60)\n")
        with mock.patch.object(qp, "TIMEOUT", .1), self.assertRaises(TimeoutError):
            qp.command("agy", entry, "default", "a" * 48)
        entry = self.fake("agy", "print('x'*70000)\n")
        with self.assertRaises(OverflowError):
            qp.command("agy", entry, "default", "a" * 48)

    def test_unsafe_state_cache_is_never_read(self):
        self.ready()
        cache = self.root / "state/quota/quota.json"
        outside = self.base / "outside"
        outside.write_text('{"not":"trusted"}')
        cache.symlink_to(outside)
        with qp.state_folder() as folder:
            with self.assertRaises((OSError, ValueError)):
                qp.read_cache(folder)
        cache.unlink()
        cache.write_text('{}')
        cache.chmod(0o666)
        with qp.state_folder() as folder:
            with self.assertRaises((OSError, ValueError)):
                qp.read_cache(folder)


    def test_manifest_hooks_nonce_guard_and_forgery(self):
        import shlex
        repo = self.base / "repository"
        repo.mkdir()
        (repo / ".git").mkdir()
        dr.write_data("host.md", b"## Delegation mode\nauto\n## Auto gate\non\n")
        with qp.state_folder(create=True) as folder:
            nonce = qp.claim_marker(folder, qp.now())
        boot = ("import runpy,sys,subprocess,unittest; "
                f"sys.path.insert(0,{str(ROOT)!r}); "
                "from tests.data_root_fixture import account; "
                f"account(unittest.TestCase(), {str(self.home)!r}); "
                f"sys.path.insert(0,{str(ROOT / 'scripts')!r}); "
                "import quota_probe,fnl_metrics; "
                "quota_probe.trigger=lambda: print('TRIGGER'); "
                "subprocess.Popen=lambda *a,**k: print('SPAWN'); "
                "subprocess.run=lambda *a,**k: print('RUN'); "
                "fnl_metrics.enabled=lambda: True; fnl_metrics.valid_id=lambda x: True; "
                "fnl_metrics.record=lambda *a,**k: print('METRIC'); "
                "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')")
        seen = set()
        invocation = 0
        for manifest in (".claude-plugin/hooks.json", ".codex-plugin/hooks.json"):
            hooks = json.loads((ROOT / manifest).read_text())["hooks"]
            for event, entries in hooks.items():
                for entry in entries:
                    for hook in entry["hooks"]:
                        command = hook["command"]
                        seen.add(command.split("/scripts/")[1].split(".py")[0])
                        command = command.replace("python3 -I ", shlex.join([sys.executable, "-I", "-c", boot]) + " ")
                        env = {"PATH": os.defpath, "CLAUDE_PLUGIN_ROOT": str(ROOT), "PLUGIN_ROOT": str(ROOT),
                               "FNL_QUOTA_WORKER": nonce, "FNL_UPDATE_CHECK": "on"}
                        invocation += 1
                        data = {"hook_event_name": event, "tool_name": "Write", "cwd": str(repo), "session_id": f"hook-{invocation}"}
                        payload = json.dumps(data)
                        with self.subTest(manifest=manifest, event=event, command=hook["command"]):
                            result = subprocess.run(["sh", "-c", command], input=payload, env=env, text=True, capture_output=True, timeout=30)
                            self.assertEqual(result.returncode, 0)
                            self.assertEqual(result.stdout, "")
                            self.assertEqual(result.stderr, "")
                            env["FNL_QUOTA_WORKER"] = "b" * 48
                            # Keep the first-write gate fresh for each independent command.
                            gate = self.root / "state/auto-gate"
                            if gate.exists():
                                for file in gate.glob("*.json"):
                                    file.unlink()
                            result = subprocess.run(["sh", "-c", command], input=payload, env=env, text=True, capture_output=True, timeout=30)
                            self.assertEqual(result.returncode, 0)
                            if "metrics_hook" not in hook["command"] or event == "SessionStart":
                                self.assertTrue(result.stdout, result.stderr)
                            expected = result.stdout
                            try:
                                with qp.state_folder() as folder:
                                    qp.write_json(folder, "worker.json", {"nonce": nonce, "heartbeat": qp.stamp(qp.now() - qp.timedelta(minutes=5))})
                                if gate.exists():
                                    for file in gate.glob("*.json"):
                                        file.unlink()
                                env["FNL_QUOTA_WORKER"] = nonce
                                # Each comparison starts before its own first edit.
                                data["session_id"] += "-stale"
                                stale = subprocess.run(["sh", "-c", command], input=json.dumps(data), env=env, text=True, capture_output=True, timeout=30)
                                self.assertEqual(stale.returncode, 0)
                                self.assertEqual(stale.stderr, "")
                                self.assertEqual(stale.stdout, expected)
                            finally:
                                with qp.state_folder() as folder:
                                    qp.write_json(folder, "worker.json", {"nonce": nonce, "heartbeat": qp.stamp(qp.now())})
        self.assertEqual(seen, {"session_start", "metrics_hook", "auto_gate_hook", "update_check", "precompact"})

    def test_metrics_consent_does_not_select_probe(self):
        import importlib.util
        import io
        spec = importlib.util.spec_from_file_location("quota_metrics_test", ROOT / "scripts/metrics_hook.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.configure({"agy": self.fake("agy")})
        for metrics in (True, False):
            payload = json.dumps({"hook_event_name": "PostToolUse", "session_id": "test", "cwd": str(self.base)}).encode()
            with mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload))), mock.patch.object(qp, "trigger") as trigger, \
                 mock.patch.object(module.fm, "enabled", return_value=metrics), mock.patch.object(module.fm, "valid_id", return_value=False):
                module.main()
                trigger.assert_called_once()


    def metrics_module(self):
        spec = importlib.util.spec_from_file_location("quota_metrics_test", ROOT / "scripts/metrics_hook.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_large_hook_payload_records_and_triggers(self):
        module = self.metrics_module()
        module.fm.write_consent(90)
        payload = json.dumps({"hook_event_name": "PostToolUse", "session_id": "large-hook",
                              "cwd": str(self.base), "tool_name": "Skill",
                              "tool_input": {"skill": "fnl-setup"}, "tool_response": "x" * 70000}).encode()
        stream = io.BytesIO(payload)
        with mock.patch.object(sys, "stdin", SimpleNamespace(buffer=stream)), \
             mock.patch.object(qp, "trigger") as trigger, mock.patch.object(module, "refresh_if_stale"):
            module.main()
        events = [json.loads(line) for path in (self.root / "state").glob("events-*.jsonl")
                  for line in path.read_text().splitlines()]
        self.assertEqual([(e["event"], e["name"]) for e in events], [("skill", "fnl-setup")])
        trigger.assert_called_once()
        self.assertLessEqual(stream.tell(), 65536)

    def test_bounded_payload_copies_only_linear_text(self):
        module = self.metrics_module()
        class CountedText(str):
            copied = 0
            def lstrip(self):
                return self
            def __getitem__(self, key):
                result = super().__getitem__(key)
                if isinstance(key, slice):
                    self.copied += len(result)
                return result
        class Raw(bytes):
            def decode(self, *args):
                return text
        expected = {str(i): i for i in range(500)}
        prefix = json.dumps(expected)[:-1] + ', "tail": "'
        raw = Raw((prefix + 'x' * 65536).encode()[:65536])
        text = CountedText(bytes(raw).decode())
        self.assertEqual(module.bounded_payload(raw), expected)
        self.assertLessEqual(text.copied, 4 * len(raw))

    def test_oversized_tool_input_keeps_edit_metadata(self):
        module = self.metrics_module()
        module.fm.write_consent(90)
        payload = {"hook_event_name": "PostToolUse", "session_id": "large-edit",
                   "cwd": str(self.base), "tool_name": "Write",
                   "tool_input": {"content": "private content " * 7000}}
        raw = json.dumps(payload).encode()[:65536]
        self.assertNotIn("tool_input", module.bounded_payload(raw))
        with mock.patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw))), \
             mock.patch.object(qp, "trigger"), mock.patch.object(module, "refresh_if_stale"):
            module.main()
        events = [json.loads(line) for path in (self.root / "state").glob("events-*.jsonl")
                  for line in path.read_text().splitlines()]
        self.assertEqual([e["event"] for e in events], ["first_edit"])
        self.assertNotIn("private content", json.dumps(events))

    def test_capped_cache_does_not_start_worker(self):
        self.configure({"agy": self.fake("agy")})
        self.ready()
        path = self.root / "state/quota/quota.json"
        path.write_bytes(b" " * (qp.LIMIT + 1))
        path.chmod(0o600)
        with mock.patch.object(qp.subprocess, "Popen") as spawn:
            self.assertFalse(qp.trigger())
            spawn.assert_not_called()

    def test_runtime_resolved_target_must_match_confirmed_path(self):
        entry = self.fake("agy")
        entry["resolved"] = self.fake("other", "print('unused')\n")["resolved"]
        with mock.patch.object(qp.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(ValueError, "target changed"):
                qp.checked_executable("agy", entry)
            spawn.assert_not_called()

    def test_setup_refuses_line_breaks_in_recorded_values(self):
        setup = self.setup_module()
        entry = self.fake("claude")
        entry.pop("configs")
        for separator in ("\n", "\r"):
            for field in ("executable", "resolved", "interpreter", "label", "folder"):
                with self.subTest(separator=repr(separator), field=field):
                    changed = dict(entry)
                    folders = {}
                    if field in changed:
                        path = self.bin / ("line" + separator + "break") / Path(entry[field]).name
                        path.parent.mkdir(exist_ok=True)
                        path.write_text("synthetic executable")
                        path.chmod(0o700)
                        changed[field] = str(path)
                        if field in {"executable", "resolved"}:
                            changed["executable"] = changed["resolved"] = str(path)
                    elif field == "label":
                        folders["line" + separator + "break"] = str(self.config_dir)
                    else:
                        path = self.home / ("line" + separator + "break")
                        path.mkdir(mode=0o700, exist_ok=True)
                        folders["work"] = str(path)
                    with mock.patch.object(setup, "resolve_executable", return_value=changed), \
                         mock.patch.object(setup, "excluded"), mock.patch.object(qp, "checked_executable"), \
                         self.assertRaisesRegex(ValueError, "newline or carriage return"):
                        setup.preview(["claude"], folders)

    def test_folder_walk_terminates_and_refuses_writable_ancestor(self):
        parent = self.home / "profiles"
        folder = parent / "work"
        folder.mkdir(parents=True, mode=0o700)
        qp.checked_path(folder, directory=True)
        for mode in (0o770, 0o707):
            parent.chmod(mode)
            with self.assertRaisesRegex(ValueError, "unsafe ancestor"):
                qp.checked_path(folder, directory=True)
        parent.chmod(0o700)
        qp.checked_path(self.bin, directory=True)

    def test_default_install_uses_filesystem_identity(self):
        setup = self.setup_module()
        entry = self.fake("claude", "import os,json\nprint(json.dumps(dict(os.environ)))\n")
        alternate = str(self.home / ".CLAUDE")
        real_samefile = os.path.samefile
        def samefile(a, b):
            return real_samefile(str(a).replace(".CLAUDE", ".claude"),
                                 str(b).replace(".CLAUDE", ".claude"))
        entry["configs"] = {"personal": alternate}
        # Model case-insensitive lookup on hosts whose temporary volume is case-sensitive.
        with mock.patch.object(os.path, "samefile", side_effect=samefile), \
             mock.patch.object(qp, "validate_configs"), mock.patch.object(setup, "excluded"), \
             mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            plan, _ = setup.preview(["claude"], entry["configs"])
            self.assertEqual(plan["configs"], entry["configs"])
            data = json.loads(qp.command("claude", entry, "personal", "a" * 48))
            self.assertNotIn("CLAUDE_CONFIG_DIR", data)

    def test_legacy_record_requires_repreview(self):
        setup = self.setup_module()
        entry = self.fake("agy")
        del entry["resolved"]
        self.configure({"agy": entry})
        with mock.patch.object(qp.subprocess, "Popen") as spawn:
            self.assertNotIn("agy", qp.config())
            self.assertFalse(qp.trigger())
            spawn.assert_not_called()
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), \
             mock.patch.object(setup, "excluded"), mock.patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
            plan, _ = setup.preview(["agy"])
        self.assertIn("agy needs re-preview: missing Resolved", errors.getvalue())
        self.assertEqual(plan["agents"]["agy"]["resolved"], entry["executable"])

    def test_no_consent_hook_never_reads_stdin_or_writes(self):
        module = self.metrics_module()
        stream = mock.Mock()
        with mock.patch.object(sys, "stdin", stream), mock.patch.object(qp, "trigger") as trigger:
            module.main()
        stream.buffer.read.assert_not_called()
        trigger.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_setup_wrong_filename_refused_by_preview_and_validation(self):
        setup = self.setup_module()
        entry = self.fake("other", "print('unused')\n")
        entry.pop("configs")
        entry["resolved"] = entry["executable"]
        with mock.patch.object(setup, "excluded"), \
             mock.patch.object(setup, "resolve_executable", return_value=entry):
            with self.assertRaises(ValueError):
                setup.preview(["agy"])
            plan = {"choice": "on", "date": "2026-11-05", "created": qp.stamp(qp.now()), "root": str(self.root),
                    "host_digest": setup.hashlib.sha256(b"").hexdigest(),
                    "agents": {"agy": entry}, "configs": {}}
            with self.assertRaisesRegex(ValueError, "wrong name"):
                setup.validate_plan(plan)

    def test_setup_apply_requires_issued_preview(self):
        setup = self.setup_module()
        entry = self.fake("agy")
        entry.pop("configs")
        plan = {"choice": "on", "date": "2026-11-05", "created": qp.stamp(qp.now()), "root": str(self.root),
                "host_digest": setup.hashlib.sha256(b"").hexdigest(),
                "agents": {"agy": entry}, "configs": {}}
        with mock.patch.object(setup, "excluded"), self.assertRaises((OSError, ValueError)):
            setup.apply(plan, setup.digest(plan), True)
        self.assertFalse(self.root.exists())

    def test_setup_edited_plan_is_not_a_preview(self):
        setup = self.setup_module()
        self.fake("agy")
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), mock.patch.object(setup, "excluded"):
            plan, value = setup.preview(["agy"])
            plan["date"] = "1999-01-01"
            with self.assertRaises(ValueError):
                setup.apply(plan, setup.digest(plan), True)
        self.assertFalse((self.root / "host.md").exists())

    def setup_module(self):
        spec = importlib.util.spec_from_file_location("quota_setup_test", ROOT / "skills/fnl-setup/scripts/quota_setup.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_setup_preview_digest_and_no_second_resolution(self):
        setup = self.setup_module()
        self.fake("agy")
        original = "# Host\n\n## Existing\nkeep these bytes\n"
        dr.write_data("host.md", original.encode())
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), mock.patch.object(setup, "excluded"):
            plan, digest = setup.preview(["agy"])
            self.assertEqual(dr.read_data("host.md").decode(), original)
            with self.assertRaises(ValueError):
                setup.apply(plan, digest, False)
            with self.assertRaises(ValueError):
                setup.apply(plan, "0" * 64, True)
            with mock.patch.object(setup.shutil, "which", side_effect=AssertionError("no second resolution")):
                setup.apply(plan, digest, True)
        self.assertTrue(dr.read_data("host.md").decode().startswith(original))
        self.assertEqual(qp.config()["agy"]["executable"], str(self.bin / "agy"))
        self.assertEqual(stat.S_IMODE((self.root / "host.md").stat().st_mode), 0o600)

    def test_setup_stored_preview_is_private_consumed_and_not_replayable(self):
        setup = self.setup_module()
        self.fake("agy")
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), mock.patch.object(setup, "excluded"):
            plan, value = setup.preview(["agy"])
            saved = self.root / "state/quota/preview.json"
            self.assertEqual(stat.S_IMODE(saved.stat().st_mode), 0o600)
            self.assertEqual(json.loads(saved.read_text()), {"plan": plan, "digest": value})
            with self.assertRaises(ValueError):
                setup.apply(None, "0" * 64, True)
            self.assertFalse((self.root / "host.md").exists())
            setup.apply(None, value, True)
            self.assertFalse(saved.exists())
            original = dr.read_data("host.md")
            with self.assertRaises(FileNotFoundError):
                setup.apply(None, value, True)
            self.assertEqual(dr.read_data("host.md"), original)

    def test_setup_edited_stored_plan_and_changed_executable_refused(self):
        setup = self.setup_module()
        self.fake("agy")
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), mock.patch.object(setup, "excluded"):
            plan, value = setup.preview(["agy"])
            edited = copy.deepcopy(plan)
            edited["date"] = "1999-01-01"
            with qp.state_folder() as folder:
                qp.write_json(folder, "preview.json", {"plan": edited, "digest": value})
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                setup.apply(None, value, True)
            plan, value = setup.preview(["agy"])
            (self.bin / "agy").chmod(0o777)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                setup.apply(None, value, True)
            self.assertFalse((self.root / "host.md").exists())

    def test_setup_wrong_filename_refused_at_apply(self):
        setup = self.setup_module()
        self.fake("agy")
        wrong = self.fake("other", "print('unused')\n")
        wrong.pop("configs")
        wrong["resolved"] = wrong["executable"]
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), mock.patch.object(setup, "excluded"):
            plan, value = setup.preview(["agy"])
            plan["agents"]["agy"] = wrong
            # Exercise re-validation independently of digest mismatch rejection.
            value = setup.digest(plan)
            with qp.state_folder() as folder:
                qp.write_json(folder, "preview.json", {"plan": plan, "digest": value})
            with self.assertRaisesRegex(ValueError, "wrong name"):
                setup.apply(None, value, True)
            self.assertFalse((self.root / "host.md").exists())

    def test_setup_versioned_target_is_recorded_and_used(self):
        setup = self.setup_module()
        entry = self.fake("2.1.318", "print('versioned')\n")
        target = entry["executable"]
        alias = self.bin / "claude"
        alias.symlink_to(target)
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), mock.patch.object(setup, "excluded"):
            plan, value = setup.preview(["claude"])
            self.assertEqual(plan["agents"]["claude"]["executable"], str(alias))
            self.assertEqual(plan["agents"]["claude"]["resolved"], target)
            self.assertIn(str(alias), setup.render(plan))
            self.assertIn(target, setup.render(plan))
            setup.apply(None, value, True)
        recorded = qp.config()["claude"]
        self.assertEqual(recorded["resolved"], target)
        self.assertEqual(qp.checked_executable("claude", recorded), [self.interpreter, target])
        self.assertEqual(qp.command("claude", recorded, "default", "a" * 48).strip(), b"versioned")

    def test_setup_versioned_target_safety_checks(self):
        setup = self.setup_module()
        entry = self.fake("2.1.318", "print('unused')\n")
        target = Path(entry["executable"])
        alias = self.bin / "claude"
        alias.symlink_to(target)
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            for unsafe in ("repository", "group-writable", "temporary"):
                with self.subTest(unsafe=unsafe):
                    if unsafe == "repository":
                        (self.bin / ".git").mkdir()
                    elif unsafe == "group-writable":
                        target.chmod(0o720)
                    # Allow only the fixture's temporary alias/interpreter;
                    # exercise real exclusion on the target for the temp case.
                    excluded = setup.excluded
                    def check(path):
                        if unsafe == "temporary" and path == target:
                            excluded(path)
                    with mock.patch.object(setup, "excluded", side_effect=check):
                        with self.assertRaises(ValueError):
                            setup.preview(["claude"])
                    if unsafe == "repository":
                        (self.bin / ".git").rmdir()
                    target.chmod(0o700)

    def test_runtime_wrong_recorded_name_is_refused(self):
        entry = self.fake("sh", "print('unused')\n")
        self.configure({"codex": entry})
        with mock.patch.object(qp.subprocess, "Popen", side_effect=AssertionError("must not spawn")) as spawn:
            with self.assertRaisesRegex(ValueError, "wrong name"):
                qp.command("codex", qp.config()["codex"], "default", "a" * 48)
            spawn.assert_not_called()

    def test_setup_preview_expires_after_sixty_minutes(self):
        setup = self.setup_module()
        for seconds, accepted in ((3600, True), (3601, False)):
            with self.subTest(seconds=seconds):
                with mock.patch.object(qp, "now", return_value=MEASURED):
                    plan, value = setup.preview([], off=True)
                before = setup.read_host()
                with mock.patch.object(qp, "now", return_value=MEASURED + qp.timedelta(seconds=seconds)):
                    if accepted:
                        setup.apply(None, value, True)
                    else:
                        with self.assertRaisesRegex(ValueError, "expired"):
                            setup.apply(None, value, True)
                        self.assertEqual(setup.read_host(), before)

    def test_setup_unsafe_preview_is_refused(self):
        setup = self.setup_module()
        plan, value = setup.preview([], off=True)
        saved = self.root / "state/quota/preview.json"
        outside = self.base / "outside-preview"
        outside.write_bytes(saved.read_bytes())
        outside.chmod(0o600)
        saved.unlink()
        saved.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)):
            setup.apply(None, value, True)
        saved.unlink()
        saved.write_bytes(outside.read_bytes())
        saved.chmod(0o644)
        with self.assertRaises(ValueError):
            setup.apply(None, value, True)
        self.assertFalse((self.root / "host.md").exists())

    def test_setup_host_change_and_off(self):
        setup = self.setup_module()
        self.configure({"agy": self.fake("agy")})
        plan, digest = setup.preview([], off=True)
        dr.write_data("host.md", dr.read_data("host.md") + b"\n# changed\n")
        with self.assertRaises(ValueError):
            setup.apply(plan, digest, True)
        plan, digest = setup.preview([], off=True)
        setup.apply(plan, digest, True)
        self.assertEqual(qp.config(), {})
        self.assertIn("- Quota probe: off", dr.read_data("host.md").decode())

    def test_setup_refuses_temporary_downloads_repository_wrong_name(self):
        setup = self.setup_module()
        entry = self.fake("agy")
        with self.assertRaises(ValueError):
            setup.excluded(Path(entry["executable"]))
        for path in (self.home / "Downloads/agy", self.home / "tmp/agy"):
            with self.assertRaises(ValueError):
                setup.excluded(path)
        with mock.patch.object(setup.shutil, "which", return_value=str(self.bin / "other")):
            with self.assertRaises(ValueError):
                setup.resolve_executable("agy")
        (self.bin / ".git").mkdir()
        with self.assertRaises(ValueError):
            qp.checked_path(entry["executable"])

    def test_setup_default_counts_toward_four(self):
        setup = self.setup_module()
        self.fake("claude")
        folders = {}
        for i in range(4):
            path = self.home / ("install" + str(i))
            path.mkdir(mode=0o700)
            folders["install" + str(i)] = str(path)
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}), mock.patch.object(setup, "excluded"):
            with self.assertRaises(ValueError):
                setup.preview(["claude"], folders)
            folders.pop("install3")
            plan, digest = setup.preview(["claude"], folders)
            self.assertEqual(len(plan["configs"]), 4)
            setup.apply(plan, digest, True)
        self.assertEqual(len(qp.config()["claude"]["configs"]), 4)

    def test_setup_fenced_example_is_preserved(self):
        setup = self.setup_module()
        original = "# Host\n\n```markdown\n## Quota probe\nexample\n```\n\n## Other\nkeep\n"
        result = setup.replace_section(original, "## Quota probe\n\n- Quota probe: off\n\n")
        self.assertTrue(result.startswith(original))
        self.assertEqual(qp.section(result).strip(), "- Quota probe: off")


    def test_account_fixture_blocks_real_quota_anchor(self):
        from tests.data_root_fixture import REAL_HOME
        # The assertion must fire before the OS is asked to open either path.
        for path in (REAL_HOME, REAL_HOME / ".finolabs/vibecode/state/quota"):
            with self.subTest(path_kind=path.name), self.assertRaisesRegex(AssertionError, "real account state"):
                os.open(path, os.O_RDONLY)
        self.assertEqual(dr.account_home(), self.home)
        self.ready()
        self.assertEqual(qp.status_lines(), ["Quota: unverified (no reading)."])

    def test_account_fixture_reaches_dashboard_and_nested_subprocess(self):
        import shlex
        from tests.data_root_fixture import REAL_HOME
        leaf = self.base / "dashboard.py"
        leaf.write_text(
            "import os,pwd\n"
            f"assert pwd.getpwuid(os.getuid()).pw_dir == {str(self.home)!r}\n"
            "print('synthetic-home')\n"
            "try:\n"
            f" os.open({str(REAL_HOME / '.finolabs/vibecode/state/quota')!r}, os.O_RDONLY)\n"
            "except AssertionError:\n print('guarded')\n"
            "else:\n raise AssertionError('guard missing')\n")
        parent = self.base / "refresh.py"
        parent.write_text(
            "import subprocess,sys\n"
            f"subprocess.run([sys.executable, '-I', {str(leaf)!r}], check=True)\n")
        commands = ([sys.executable, "-I", str(parent)],
                    ["sh", "-c", "python3 -I " + shlex.quote(str(parent))])
        for command in commands:
            with self.subTest(command=command[0]):
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "synthetic-home\nguarded\n")

    def test_env_shebang_uses_recorded_interpreter(self):
        entry = self.fake("agy", "print('ok')\n")
        Path(entry["executable"]).write_text("#!/usr/bin/env " + Path(self.interpreter).name + "\nprint('ok')\n")
        self.assertEqual(qp.checked_executable("agy", entry), [entry["interpreter"], entry["executable"]])
        with mock.patch.dict(os.environ, {"PATH": str(self.base / "decoy")}):
            self.assertEqual(qp.command("agy", entry, "default", "a" * 48).strip(), b"ok")
        Path(entry["executable"]).write_text("#!/usr/bin/env -S python3\n")
        with self.assertRaises(ValueError):
            qp.checked_executable("agy", entry)

    def test_timeout_kills_descendants(self):
        sentinel = self.base / "descendant-survived"
        body = ("import os,time\n"
                "if os.fork() == 0:\n"
                " time.sleep(.6)\n"
                f" open({str(sentinel)!r},'w').write('survived')\n"
                " os._exit(0)\n"
                "time.sleep(60)\n")
        entry = self.fake("agy", body)
        with mock.patch.object(qp, "TIMEOUT", .2), self.assertRaises(TimeoutError):
            qp.command("agy", entry, "default", "a" * 48)
        time.sleep(.7)
        self.assertFalse(sentinel.exists())

    def test_cache_display_safe_and_age(self):
        self.configure({"agy": self.fake("agy")})
        self.ready()
        with mock.patch.object(qp, "now", return_value=MEASURED):
            qp.worker([["agy", "default"]])
        with mock.patch.object(qp, "now", return_value=MEASURED + qp.timedelta(hours=9)):
            lines = qp.status_lines()
        self.assertIn("measured 2026-11-05T09:00:00Z", lines[0])
        self.assertIn("gemini weekly", lines[0])
        self.assertIn("unverified: older than 8 hours", lines[0])
        self.assertNotIn(str(self.home), lines[0])

    def test_scan_and_check_print_cached_measurement_without_probing(self):
        self.configure({"agy": self.fake("agy")})
        self.ready()
        with mock.patch.object(qp, "now", return_value=MEASURED):
            qp.worker([["agy", "default"]])
        # Empty PATH ensures the scan can never find a real agent executable.
        env = {"HOME": str(self.home), "PATH": ""}
        for script, args in (("fnl-scan-agents/scripts/agent_scan.py", ["--host", "codex"]),
                             ("fnl-setup/scripts/checkup.py", ["--json"])):
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, "-I", str(ROOT / "skills" / script), *args],
                                        cwd=self.base, env=env, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("measured 2026-11-05T09:00:00Z", result.stdout)
                self.assertIn("gemini weekly", result.stdout)
        self.assertFalse((self.root / "state/quota/worker.json").exists())

    def test_foreign_config_folder_refused(self):
        original = os.fstat
        inode = self.config_dir.stat().st_ino
        def foreign(fd):
            info = original(fd)
            if info.st_ino == inode:
                fields = list(info)
                fields[4] = os.getuid() + 123
                return os.stat_result(fields)
            return info
        with mock.patch.object(os, "fstat", side_effect=foreign), self.assertRaises(ValueError):
            qp.validate_configs({"default": str(self.config_dir)})

    def test_bad_pointer_and_decoy_cache_never_display(self):
        decoy = self.base / "decoy"
        decoy.mkdir()
        (decoy / "quota.json").write_text('{"identity":"forged"}')
        with mock.patch.dict(os.environ, {"HOME": str(decoy), "FNL_STATE_DIR": str(decoy), "XDG_STATE_HOME": str(decoy)}):
            self.assertEqual(qp.status_lines(), ["Quota: unverified (no reading)."])
        dr.write_data("root.json", b"truncated")
        self.assertEqual(qp.status_lines(), ["Quota: unverified (no reading)."])


    def test_worker_lock_contention_is_bounded_but_hook_never_waits(self):
        self.ready()
        with mock.patch.object(qp.fcntl, "flock", side_effect=[BlockingIOError(), None]), mock.patch.object(qp.time, "sleep") as sleep:
            with qp.state_folder(writer=True):
                pass
            sleep.assert_called_once_with(.05)
        with mock.patch.object(qp.fcntl, "flock", side_effect=BlockingIOError()), mock.patch.object(qp.time, "sleep") as sleep:
            with self.assertRaises(BlockingIOError):
                with qp.state_folder():
                    pass
            sleep.assert_not_called()
        with mock.patch.object(qp.fcntl, "flock", side_effect=BlockingIOError()) as flock, mock.patch.object(qp.time, "sleep") as sleep:
            with self.assertRaises(BlockingIOError):
                with qp.state_folder(writer=True):
                    pass
            self.assertEqual(flock.call_count, 3)
            self.assertEqual(sleep.call_args_list, [mock.call(.05), mock.call(.05)])

    def test_codex_malformed_reply_is_shape_error(self):
        entry = self.fake("codex", "import sys,time\nsys.stdin.readline()\nprint('not-json',flush=True)\ntime.sleep(60)\n")
        with self.assertRaises(qp.ShapeError):
            qp.command("codex", entry, "default", "a" * 48)

    def test_direct_shebang_symlink_keeps_recorded_real_interpreter(self):
        entry = self.fake("agy")
        alias = self.bin / "python-alias"
        alias.symlink_to(entry["interpreter"])
        Path(entry["executable"]).write_text("#!" + str(alias) + "\nprint('ok')\n")
        self.assertEqual(qp.checked_executable("agy", entry), [entry["interpreter"], entry["executable"]])


class AccountCommandTest(unittest.TestCase):
    def test_bootstrap_never_prefixes_an_absolute_interpreter(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(subprocess, "run") as runner:
            case = unittest.TestCase()
            try:
                account(case, Path(temporary) / "account")
                command = ["sh", "-c", "/synthetic/bin/python3 -I -c 'pass'"]
                subprocess.run(command)
                runner.assert_called_once_with(command)
            finally:
                case.doCleanups()


class CopiesTest(unittest.TestCase):
    def test_all_copies_identical_and_listed(self):
        actual = {str(p.relative_to(ROOT)) for base in (ROOT / "scripts", ROOT / "skills") for p in base.rglob("quota_probe.py")}
        self.assertEqual(actual, set(COPIES))
        ci = (ROOT / ".github/workflows/validate.yml").read_text()
        for name in COPIES:
            self.assertEqual((ROOT / name).read_bytes(), (ROOT / COPIES[0]).read_bytes())
            self.assertIn('"' + name + '"', ci)

    def test_fixtures_have_no_identity_or_path(self):
        for path in FIXTURES.glob("*.json"):
            text = path.read_text()
            self.assertNotIn("@", text)
            self.assertNotIn("/" + "Users/", text)
            self.assertNotIn("/" + "home/", text)
            self.assertNotIn('"accountId"', text)


class DocumentationTest(unittest.TestCase):
    def test_routing_thresholds_and_advisory(self):
        text = (ROOT / "skills/fnl-delegate/SKILL.md").read_text()
        step = text.split("4. **Reachability and quota**", 1)[1].split("5. **Effort**", 1)[0]
        for phrase in ("advisory, agent judgment", "Below 10%", "reset time still ahead", "older than 8 hours",
                       "excludes nothing", "week-all", "user's own statement", "wins", "state/quota/quota.json"):
            self.assertIn(phrase, step)

    def test_privacy_sentences(self):
        text = (ROOT / "PRIVACY.md").read_text()
        for phrase in ("For the quota probe, the plugin itself makes no network call.",
                       "The user's own `agy`, `claude` and `codex` programs contact their providers with the user's own accounts; the plugin sends nothing about the user.",
                       "<data root>/state/quota/quota.json", "dated opt-in", "canonical `<data root>/host.md`"):
            self.assertIn(phrase, text)

    def test_setup_consent_and_displays(self):
        text = (ROOT / "skills/fnl-setup/SKILL.md").read_text()
        self.assertIn("Every 4 hours a background step runs each agent's own read-only usage command", text)
        self.assertIn("its hooks, plugins and servers run", text)
        self.assertIn("neutral Yes and No", text)
        for file in ("skills/fnl-setup/scripts/checkup.py", "skills/fnl-scan-agents/scripts/agent_scan.py"):
            self.assertIn("status_lines()", (ROOT / file).read_text())
