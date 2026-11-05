"""Quota acceptance uses synthetic account homes and fake programs only."""
import copy
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
        for agent, count in (("agy", 5), ("claude", 3), ("codex", 1)):
            groups = qp.parse(agent, json.dumps(self.fixture(agent)), MEASURED)
            self.assertEqual(len(groups), count)
            for item in groups:
                self.assertEqual(set(item), {"name", "window", "remaining_fraction", "reset_time"})
        claude = qp.parse_claude(self.fixture("claude"), MEASURED)
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

    def test_zone_and_year_rollover(self):
        bad = self.fixture("claude")
        bad["result"] = bad["result"].replace("Asia/Saigon", "Invalid/Zone")
        with self.assertRaises(qp.ShapeError):
            qp.parse("claude", json.dumps(bad), MEASURED)
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
        self.interpreter = str(Path("/usr/bin/python3").resolve())
        self.addCleanup(mock.patch.stopall)

    def fake(self, agent, body=None):
        path = self.bin / agent
        if body is None:
            body = "print(" + repr((FIXTURES / (qp.SOURCES[agent] + ".json")).read_text()) + ")\n"
        path.write_text("#!" + self.interpreter + "\n" + body)
        path.chmod(0o700)
        return {"executable": str(path), "interpreter": self.interpreter,
                "configs": {"default": str(self.config_dir) if agent == "claude" else None}}

    def configure(self, entries):
        lines = ["## Quota probe", "", "- Quota probe: on", "- Date: 2026-11-05",
                 "- Agents: " + ", ".join(entries)]
        for agent, entry in entries.items():
            lines += [f"- Executable {agent}: {entry['executable']}", f"- Interpreter {agent}: {entry['interpreter']}"]
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
            # Missing backoff first waits 30 minutes, anchored to file/folder time.
            self.assertFalse(qp.trigger())
            self.ready()
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
        decoys = {k: "decoy" for k in ("ANTHROPIC_BASE_URL", "NODE_OPTIONS", "CODEX_HOME", "CLAUDE_CONFIG_DIR")}
        decoys["PATH"] = str(planted)
        with mock.patch.dict(os.environ, decoys), mock.patch.object(qp.subprocess, "Popen", wraps=subprocess.Popen) as spawn:
            data = json.loads(qp.command("claude", entry, "default", "a" * 48))
        # macOS Python may add its own runtime variables after exec. Pin the
        # exact environment supplied at the process boundary, and parent drops.
        expected = qp.environment(entry, "a" * 48, str(self.config_dir))
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

    def test_runtime_changed_mode_owner_and_symlink_refused(self):
        entry = self.fake("agy")
        Path(entry["executable"]).chmod(0o777)
        with self.assertRaises(ValueError):
            qp.checked_executable(entry)
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
                qp.checked_executable(entry)

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
        with mock.patch.object(qp, "now", return_value=MEASURED):
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
            self.assertEqual(qp.read_cache(folder), {})
        cache.unlink()
        cache.write_text('{}')
        cache.chmod(0o666)
        with qp.state_folder() as folder:
            self.assertEqual(qp.read_cache(folder), {})


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
