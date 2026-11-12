"""Context readings use synthetic account state, never transcripts or host settings."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import time
import unittest
from unittest import mock

from tests.test_handover_state import setup_store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("context_snapshot", ROOT / "scripts" / "context_snapshot.py")
ctx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctx)


def fixture(session="synthetic"):
    return {"session_id": session, "version": "2.1.0", "transcript_path": "/" + "discard" + "/" + "never-read",
            "context_window": {"used_percentage": 99, "context_window_size": 200000,
                               "current_usage": {"input_tokens": 100000, "cache_creation_input_tokens": 20000,
                                                 "cache_read_input_tokens": 4000, "output_tokens": 9999}}}


def agy_fixture(session="synthetic"):
    event = fixture(session)
    event["conversation_id"] = event.pop("session_id")
    event["context_window"].update(total_input_tokens=999999, total_output_tokens=888888,
                                   remaining_percentage=1)
    event["exceeds_200k_tokens"] = True
    return event


class ContextSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.root = setup_store(self)
        self.folder = self.root / "state" / "context"
        self.path = self.folder / ctx.filename("synthetic")
        patch = mock.patch.dict(os.environ, {}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def cli(self, *args, raw=None):
        raw = json.dumps(fixture()).encode() if raw is None else raw
        out, err = io.StringIO(), io.StringIO()
        original_write = os.write
        def output(fd, data):
            if fd == 1:
                out.write(data.decode("utf-8"))
                return len(data)
            return original_write(fd, data)
        with mock.patch.object(os, "write", side_effect=output), \
                mock.patch.object(sys, "argv", ["context_snapshot.py", *args]), \
                mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ctx.main()
        return code, out.getvalue(), err.getvalue()

    def seed(self):
        self.assertEqual(self.cli("record"), (0, "", ""))
        self.assertTrue(self.path.exists())

    def refused(self, *args):
        self.assertEqual(self.cli(*args), (3, "", ctx.NO_READING + "\n"))

    def test_stores_only_allowed_fields_uses_inputs_not_output_or_reported_percent(self):
        self.seed()
        data = json.loads(self.path.read_bytes())
        self.assertEqual(set(data), {"used", "window", "percent", "measured", "version", "host"})
        self.assertEqual((data["used"], data["window"], data["percent"], data["version"], data["host"]),
                         (124000, 200000, 62, "2.1.0", "claude"))
        self.assertTrue(data["measured"].endswith("Z"))
        self.assertEqual(stat.S_IMODE(self.folder.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(self.cli("record", "--line"), (0, "ctx 62%\n", ""))
        code, out, err = self.cli("read", "--session", "synthetic")
        self.assertEqual((code, err), (0, ""))
        data = json.loads(out)
        self.assertEqual(set(data), {"used", "window", "percent", "age_seconds", "stale"})
        self.assertEqual((data["used"], data["window"], data["percent"], data["stale"]), (124000, 200000, 62, False))

    def test_antigravity_records_conversation_id_and_namespaces_filename(self):
        self.seed()
        event = agy_fixture()
        event["session_id"] = "compatibility-id-is-ignored"
        self.assertEqual(self.cli("record", "--host", "antigravity", "--line", raw=json.dumps(event).encode()),
                         (0, "ctx 62%\n", ""))
        name = hashlib.sha256(b"antigravity:" + b"synthetic").hexdigest()[:16] + ".json"
        self.assertEqual(ctx.filename("synthetic", "antigravity"), name)
        self.assertEqual(ctx.filename("synthetic"), hashlib.sha256(b"synthetic").hexdigest()[:16] + ".json")
        other = self.folder / name
        self.assertNotEqual(other, self.path)
        data = json.loads(other.read_bytes())
        self.assertEqual(set(data), ctx.FIELDS)
        self.assertEqual((data["host"], data["used"], data["percent"]), ("antigravity", 124000, 62))
        self.assertEqual(json.loads(self.path.read_bytes())["host"], "claude")
        self.assertEqual(self.cli("read", "--session", "synthetic", "--host", "antigravity")[0], 0)
        self.assertFalse((self.folder / ctx.filename(event["session_id"], "antigravity")).exists())

    def test_antigravity_unknown_window_missing_id_and_null_usage(self):
        event = agy_fixture()
        event["context_window"]["context_window_size"] = 0
        self.assertEqual(self.cli("record", "--host", "antigravity", raw=json.dumps(event).encode()), (0, "", ""))
        self.assertFalse(self.folder.exists())
        event["context_window"]["context_window_size"] = 200000
        self.cli("record", "--host", "antigravity", raw=json.dumps(event).encode())
        path = self.folder / ctx.filename("synthetic", "antigravity")
        before = path.read_bytes()
        for window in (0, -1, True, 1.5, None, 10000001):
            event["context_window"]["context_window_size"] = window
            self.assertEqual(self.cli("record", "--host", "antigravity", "--line", raw=json.dumps(event).encode()), (0, "", ""))
            self.assertEqual(path.read_bytes(), before)
        event = fixture()  # session_id cannot substitute for conversation_id
        self.assertEqual(self.cli("record", "--host", "antigravity", raw=json.dumps(event).encode()), (0, "", ""))
        self.assertEqual(path.read_bytes(), before)
        self.seed()
        event = agy_fixture()
        event["context_window"].update(current_usage=None, context_window_size=0)
        self.assertEqual(self.cli("record", "--host", "antigravity", raw=json.dumps(event).encode()), (0, "", ""))
        self.assertFalse(path.exists())
        self.assertTrue(self.path.exists())

    def test_latest_host_filter_and_unfiltered_latest_keep_output_contract(self):
        for newest in ("claude", "antigravity"):
            for host, used in (("claude", 100000), ("antigravity", 120000)):
                event = fixture() if host == "claude" else agy_fixture()
                event["context_window"]["current_usage"]["input_tokens"] = used
                self.cli("record", "--host", host, raw=json.dumps(event).encode())
                path = self.folder / ctx.filename("synthetic", host)
                os.utime(path, (2000 if host == newest else 1000,) * 2)
            for host, used in (("claude", 124000), ("antigravity", 144000), (None, 124000 if newest == "claude" else 144000)):
                args = ("--host", host) if host else ()
                code, out, err = self.cli("read", "--latest", *args)
                self.assertEqual((code, err), (0, ""))
                data = json.loads(out)
                self.assertEqual(set(data), {"used", "window", "percent", "age_seconds", "stale"})
                self.assertEqual(data["used"], used)
                code, out, err = self.cli("check", "--latest", "--threshold", "150000", *args)
                self.assertEqual((code, err), (0, ""))
                self.assertEqual(set(json.loads(out)), {"action", "reason"})

    def test_host_filter_refuses_missing_stale_or_invalid_matching_latest(self):
        self.seed()
        self.refused("read", "--latest", "--host", "antigravity")
        self.cli("record", "--host", "antigravity", raw=json.dumps(agy_fixture()).encode())
        path = self.folder / ctx.filename("synthetic", "antigravity")
        valid = path.read_bytes()
        for data in ({**json.loads(valid), "measured": "2000-01-01T00:00:00Z"},
                     {**json.loads(valid), "percent": -1}):
            path.write_text(json.dumps(data))
            self.refused("read", "--latest", "--host", "antigravity")
        path.write_bytes(valid)
        path.chmod(0o644)
        self.refused("read", "--latest", "--host", "antigravity")

    def test_session_host_must_match_snapshot_and_unknown_host_is_refused(self):
        self.seed()
        data = json.loads(self.path.read_bytes())
        data["host"] = "antigravity"
        self.path.write_text(json.dumps(data))
        self.refused("read", "--session", "synthetic")
        self.refused("read", "--latest", "--host", "codex")
        self.assertEqual(self.cli("record", "--host", "codex"), (0, "", ""))

    def test_null_or_noninteger_usage_removes_stale_snapshot_without_a_line(self):
        for usage in (None, {}, {"input_tokens": True}, {"input_tokens": 1.2}, "invalid"):
            self.seed()
            event = fixture()
            event["context_window"]["current_usage"] = usage
            self.assertEqual(self.cli("record", "--line", raw=json.dumps(event).encode()), (0, "", ""))
            self.assertFalse(self.path.exists())

    def test_invalid_or_oversized_payload_leaves_existing_bytes_unchanged(self):
        self.seed()
        before = self.path.read_bytes()
        for raw in (b"{bad", b"\xff", b"null", b"[]", b"x" * 65537, b'{"session_id":"synthetic","session_id":"other"}'):
            self.assertEqual(self.cli("record", "--line", raw=raw), (0, "", ""))
            self.assertEqual(self.path.read_bytes(), before)
        raw = json.dumps(fixture()).encode()
        self.assertEqual(self.cli("record", raw=raw + b" " * (65536 - len(raw))), (0, "", ""))

    def test_invalid_counts_and_host_version_never_leak_input(self):
        for field in ("context_window_size", "current_usage"):
            for value in (-1, True, 1.5, "private" + "-value", None):
                event = fixture()
                event["context_window"][field] = value
                self.assertEqual(self.cli("record", "--line", raw=json.dumps(event).encode()), (0, "", ""))
                self.assertFalse(self.path.exists())
        event = fixture()
        event["version"] = "2.1.0\x1b[31m" + "/" + "private"
        self.cli("record", raw=json.dumps(event).encode())
        self.assertEqual(json.loads(self.path.read_bytes())["version"], "unknown")
        for value in (-1, True, 1.5, None, 10**20):
            event = fixture()
            event["context_window"]["current_usage"]["cache_read_input_tokens"] = value
            self.cli("record", raw=json.dumps(event).encode())
            self.assertFalse(self.path.exists())

    def test_missing_stale_future_invalid_snapshot_read_and_check_refuse(self):
        self.refused("read", "--session", "synthetic")
        self.refused("check", "--session", "synthetic", "--threshold", "150000")
        self.seed()
        measured = ctx.timestamp(json.loads(self.path.read_bytes())["measured"])
        for age in (-1, 3601):
            with mock.patch.object(ctx.time, "time", return_value=measured + age):
                self.refused("read", "--session", "synthetic")
                self.refused("check", "--session", "synthetic", "--threshold", "150000")
        with mock.patch.object(ctx.time, "time", return_value=measured + 20):
            self.refused("read", "--session", "synthetic", "--max-age-seconds", "10")
        for raw in (b"{}", b"{bad", b"[]", b"x" * 4097):
            self.path.write_bytes(raw)
            self.refused("read", "--session", "synthetic")

    def test_check_uses_real_counts_and_steward_actions(self):
        self.seed()
        for threshold, boundary, action in ((180000, "yes", "ok"), (150000, "unknown", "prepare"),
                                             (120000, "no", "wait"), (120000, "yes", "compact")):
            code, out, err = self.cli("check", "--session", "synthetic", "--threshold", str(threshold), "--boundary", boundary)
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(json.loads(out)["action"], action)
        self.refused("check", "--session", "synthetic", "--threshold", "0")

    def test_latest_is_explicit_and_never_falls_back_from_bad_newest(self):
        self.seed()
        os.utime(self.path, (1000, 1000))
        event = fixture("other")
        event["context_window"]["current_usage"]["input_tokens"] = 120000
        self.cli("record", raw=json.dumps(event).encode())
        self.assertEqual(json.loads(self.cli("read", "--latest")[1])["used"], 144000)
        other = self.folder / ctx.filename("other")
        other.write_bytes(b"invalid")
        self.refused("read", "--latest")
        self.refused("read", "--latest", "--session", "synthetic")
        self.refused("read")

    def test_unsafe_file_and_folder_disable_read_write_and_clear(self):
        self.seed()
        before = self.path.read_bytes()
        for target, modes in ((self.path, (0o644, 0o620)), (self.folder, (0o755, 0o770)), (self.root, (0o777,))):
            original = stat.S_IMODE(target.stat().st_mode)
            for mode in modes:
                target.chmod(mode)
                self.refused("read", "--session", "synthetic")
                self.assertEqual(self.cli("record", "--line"), (0, "", ""))
                self.assertEqual(self.path.read_bytes(), before)
            target.chmod(original)
        original = self.folder / "original"
        self.path.rename(original)
        self.path.symlink_to(original)
        self.refused("read", "--session", "synthetic")
        self.assertEqual(self.cli("record", "--line"), (0, "", ""))
        event = fixture()
        event["context_window"]["current_usage"] = None
        self.cli("record", raw=json.dumps(event).encode())
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(original.read_bytes(), before)
        self.path.unlink()
        original.rename(self.path)
        real = self.folder.with_name("real")
        self.folder.rename(real)
        self.folder.symlink_to(real, target_is_directory=True)
        self.refused("read", "--session", "synthetic")
        self.assertEqual(self.cli("record", "--line"), (0, "", ""))
        self.assertEqual((real / self.path.name).read_bytes(), before)

    def test_hard_linked_snapshot_is_refused_for_read_latest_and_record(self):
        self.seed()
        before = self.path.read_bytes()
        link = self.folder / "alias"
        os.link(self.path, link)
        self.refused("read", "--session", "synthetic")
        self.refused("read", "--latest")
        self.assertEqual(self.cli("record", "--line"), (0, "", ""))
        self.assertEqual(self.path.read_bytes(), before)
        link.unlink()
        self.assertEqual(self.cli("read", "--session", "synthetic")[0], 0)

    def test_wrong_owner_folder_target_and_other_user_snapshot(self):
        self.seed()
        before = self.path.read_bytes()
        other = self.folder / ctx.filename("foreign")
        other.write_bytes(before)
        other.chmod(0o600)
        for target in (self.folder, self.path, other):
            inode = target.stat().st_ino
            real_stat, real_fstat = os.stat, os.fstat
            def foreign(info):
                if info.st_ino == inode:
                    values = list(info)
                    values[4] = os.getuid() + 1
                    return os.stat_result(values)
                return info
            with mock.patch.object(os, "stat", side_effect=lambda *a, **kw: foreign(real_stat(*a, **kw))), \
                    mock.patch.object(os, "fstat", side_effect=lambda fd: foreign(real_fstat(fd))):
                self.refused("read", "--session", "foreign" if target == other else "synthetic")
                self.assertEqual(self.cli("record", "--line"), (0, "", ""))
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(other.read_bytes(), before)

    def test_twenty_file_cap_oldest_evicted_and_atomic_failure_preserves_bytes(self):
        for number in range(21):
            self.cli("record", raw=json.dumps(fixture(str(number))).encode())
            path = self.folder / ctx.filename(str(number))
            os.utime(path, (1000 + number, 1000 + number))
        self.assertEqual(len(list(self.folder.iterdir())), 20)
        self.assertFalse((self.folder / ctx.filename("0")).exists())
        self.seed()
        before = self.path.read_bytes()
        event = fixture()
        event["context_window"]["current_usage"]["input_tokens"] = 110000
        with self.path.open("rb") as old:
            self.cli("record", raw=json.dumps(event).encode())
            self.assertEqual(old.read(), before)
        replacement = self.path.read_bytes()
        self.assertNotEqual(before, replacement)
        with mock.patch.object(os, "replace", side_effect=OSError("private" + "-text")):
            self.assertEqual(self.cli("record", "--line"), (0, "", ""))
        self.assertEqual(self.path.read_bytes(), replacement)
        self.assertEqual(len(list(self.folder.iterdir())), 20)

    def test_invalid_root_and_nonregular_files_refuse(self):
        self.seed()
        (self.root / "root.json").write_bytes(b"invalid")
        self.refused("read", "--session", "synthetic")
        self.assertEqual(self.cli("record", "--line"), (0, "", ""))
        (self.root / "root.json").unlink()
        self.path.unlink()
        for kind in ("directory", "fifo"):
            if kind == "directory":
                self.path.mkdir()
            else:
                os.mkfifo(self.path)
            self.refused("read", "--session", "synthetic")
            self.assertEqual(self.cli("record", "--line"), (0, "", ""))
            self.path.rmdir() if kind == "directory" else self.path.unlink()

    def test_record_output_failure_and_invalid_arguments_still_exit_zero(self):
        buffered = io.StringIO()
        with contextlib.redirect_stdout(buffered), mock.patch.object(sys, "argv", ["context_snapshot.py", "record", "--line"]), \
                mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(fixture()).encode()))), \
                mock.patch.object(os, "write", side_effect=BrokenPipeError("closed")):
            self.assertEqual(ctx.main(), 0)
        self.assertEqual(buffered.getvalue(), "")
        self.assertEqual(self.cli("record", "--unknown"), (0, "", ""))

    def test_new_shared_script_copies_match(self):
        self.assertEqual((ROOT / "scripts" / "context_snapshot.py").read_bytes(),
                         (ROOT / "skills" / "tidy" / "scripts" / "context_snapshot.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
