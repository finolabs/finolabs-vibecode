"""Synthetic on-demand and StopFailure acceptance.

The StopFailure payload fixture is NOT verified against a live Claude Code event.
Capture and compare a real event before release; these tests pin the assumed shape.
"""
import io
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import signal
import stat
import sys
import time
import unittest
from unittest import mock

from tests import test_quota_probe as tq

qp, dr = tq.qp, tq.dr
ROOT, MEASURED = tq.ROOT, tq.MEASURED


class OnDemandTest(unittest.TestCase):
    setUp = tq.QuotaTest.setUp
    fake = tq.QuotaTest.fake
    configure = tq.QuotaTest.configure
    ready = tq.QuotaTest.ready

    def test_concurrent_reads_run_once(self):
        sentinel = self.base / "started"
        entry = self.fake("agy", f"import time\nfrom pathlib import Path\nPath({str(sentinel)!r}).write_text('started')\ntime.sleep(.5)\nprint({(tq.FIXTURES / 'agy-usage.json').read_text()!r})\n")
        self.configure({"agy": entry, "codex": self.fake("codex")})
        ctx = multiprocessing.get_context("fork")
        child = ctx.Process(target=qp.read_family, args=("agy",))
        child.start()
        self.addCleanup(lambda: child.kill() if child.is_alive() else None)
        deadline = time.monotonic() + 5
        while not sentinel.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(sentinel.exists())
        with mock.patch.object(qp, "command") as command:
            self.assertIn(": busy;", qp.read_family("agy")[0])
            self.assertIn(": busy;", qp.read_family("codex")[0])
            command.assert_not_called()
        child.join(5)
        self.assertEqual(child.exitcode, 0)
        self.assertIn(": fresh;", qp.read_family("agy")[0])

    def test_killed_reader_marker_expires_without_retry_early(self):
        self.configure({"agy": self.fake("agy")})
        ctx = multiprocessing.get_context("fork")
        started = ctx.Event()
        def blocked(*args):
            started.set()
            signal.pause()
        def run():
            with mock.patch.object(qp, "command", side_effect=blocked):
                qp.read_family("agy")
        child = ctx.Process(target=run)
        child.start()
        self.addCleanup(lambda: child.kill() if child.is_alive() else None)
        self.assertTrue(started.wait(5))
        child.kill()
        child.join(5)
        with qp.state_folder() as folder:
            old = qp.marker(folder, qp.now())
            self.assertIsNotNone(old)
        self.assertIn(": busy;", qp.read_family("agy")[0])
        after = qp.timestamp(old["started"]) + qp.timedelta(seconds=150)
        with mock.patch.object(qp, "now", return_value=after), mock.patch.object(qp, "command") as command:
            self.assertIn(": backoff;", qp.read_family("agy")[0])
            command.assert_not_called()
        with mock.patch.object(qp, "now", return_value=after + qp.timedelta(minutes=30)):
            self.assertIn(": read;", qp.read_family("agy")[0])
        self.assertFalse((self.root / "state/quota/inflight.json").exists())

    def test_four_installs_sequential_and_only_requested_family(self):
        entry = self.fake("claude")
        for index in range(3):
            folder = self.home / str(index)
            folder.mkdir(mode=0o700)
            entry["configs"][f"extra-{index}"] = str(folder)
        self.configure({"claude": entry, "agy": self.fake("agy")})
        raw = (tq.FIXTURES / "claude-usage.json").read_bytes()
        with mock.patch.object(qp, "command", return_value=raw) as command, \
             mock.patch.object(qp, "now", return_value=MEASURED), \
             mock.patch.object(qp, "ZoneInfo", return_value=qp.timezone(qp.timedelta(hours=7))):
            lines = qp.read_family("claude")
            self.assertEqual(len(lines), 4)
            self.assertTrue(all(": read; age 0s" in line for line in lines))
            self.assertEqual([c.args[2] for c in command.call_args_list], list(entry["configs"]))
            self.assertEqual({c.args[0] for c in command.call_args_list}, {"claude"})
            self.assertNotIn("Current session", "\n".join(lines))
            qp.read_family("claude")
            self.assertEqual(command.call_count, 4)

    def test_off_and_custom_max_age(self):
        with mock.patch.object(qp, "command") as command:
            self.assertIn(": off;", qp.read_family("agy")[0])
            self.configure({"agy": self.fake("agy")})
            with mock.patch.dict(os.environ, {"FNL_QUOTA_PROBE": "off"}):
                self.assertIn(": off;", qp.read_family("agy")[0])
            command.assert_not_called()
        with mock.patch.object(qp, "now", return_value=MEASURED):
            qp.read_family("agy")
        with mock.patch.object(qp, "now", return_value=MEASURED + qp.timedelta(minutes=16)), \
             mock.patch.object(qp, "command") as command:
            self.assertIn(": fresh;", qp.read_family("agy", 60)[0])
            command.assert_not_called()

    def test_child_update_check_makes_no_request(self):
        # Execute the actual update-check hook in the fake Claude child. Any
        # request or detached launch emits a sentinel, making its output invalid.
        body = (f"import sys\nsys.path.insert(0,{str(ROOT / 'scripts')!r})\n"
                "import update_check, urllib.request, subprocess\n"
                "def forbidden(*a,**k):\n print('UNEXPECTED REQUEST OR PROCESS')\n raise RuntimeError()\n"
                "urllib.request.urlopen=forbidden\nurllib.request.build_opener=forbidden\nsubprocess.Popen=forbidden\n"
                "update_check.main([])\n"
                f"print({(tq.FIXTURES / 'claude-usage.json').read_text()!r})\n")
        entry = self.fake("claude", body)
        result = qp.command("claude", entry, "default")
        self.assertNotIn(b"UNEXPECTED", result)
        self.assertEqual(json.loads(result)["type"], "result")
        self.assertEqual(qp.environment(entry)["FNL_UPDATE_CHECK"], "off")
        self.assertEqual(qp.environment(entry)["FNL_METRICS"], "off")

    def hook(self, raw=None):
        spec = importlib.util.spec_from_file_location("quota_limit_test", ROOT / "scripts/quota_limit_hook.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if raw is None:
            raw = (tq.FIXTURES / "stop-failure.json").read_bytes()
        with mock.patch.object(sys, "stdin", type("Input", (), {"buffer": io.BytesIO(raw)})()), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as out, \
             mock.patch.object(qp, "now", return_value=MEASURED):
            self.assertEqual(module.main(), 0)
            self.assertEqual(out.getvalue(), "")

    def test_hook_exact_error_consent_and_private_atomic_marker(self):
        self.configure({"claude": self.fake("claude")})
        self.ready()
        target = self.root / "state/quota/limits.json"
        for raw in (b"{}", b"null", b"[]", b"{", b" " * (qp.LIMIT + 1),
                    b'{"error":"rate_limit_extra"}', b'{"error":true}', b'{"error":"RATE_LIMIT"}'):
            self.hook(raw)
            self.assertFalse(target.exists())
        with mock.patch.dict(os.environ, {"FNL_QUOTA_PROBE": "off"}):
            self.hook()
            self.assertFalse(target.exists())
        with mock.patch.dict(os.environ, {"HOME": str(self.base), "FNL_STATE_DIR": str(self.base), "XDG_STATE_HOME": str(self.base)}):
            self.hook()
        self.assertEqual(json.loads(target.read_text()), {"claude": qp.stamp(MEASURED)})
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(target.parent.stat().st_mode), 0o700)
        self.assertFalse((self.base / "limits.json").exists())

    def test_hook_no_consent_missing_folder_symlinks_and_failed_write(self):
        self.hook()
        self.assertFalse(self.root.exists())
        self.configure({"claude": self.fake("claude")})
        self.hook()
        self.assertFalse((self.root / "state").exists())
        self.ready()
        target = self.root / "state/quota/limits.json"
        with mock.patch.object(qp, "write_json", side_effect=OSError("failed")):
            self.hook()
        self.assertFalse(target.exists())
        outside = self.base / "outside"
        outside.write_text("untouched")
        target.symlink_to(outside)
        self.hook()
        self.assertTrue(target.is_symlink())
        self.assertEqual(outside.read_text(), "untouched")
        target.unlink()
        host = self.root / "host.md"
        original = host.read_bytes()
        host.unlink()
        host.symlink_to(outside)
        self.hook()
        self.assertFalse(target.exists())
        host.unlink()
        dr.write_data("host.md", original)
        folder = target.parent
        moved = folder.with_name("saved")
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
        self.hook()
        self.assertFalse((moved / "limits.json").exists())

    def test_hook_unsafe_file_owner_mode_and_lock_write_nothing(self):
        self.configure({"claude": self.fake("claude")})
        self.ready()
        target = self.root / "state/quota/limits.json"
        target.write_text("{}")
        target.chmod(0o644)
        self.hook()
        self.assertEqual(target.read_text(), "{}")
        target.chmod(0o600)
        with mock.patch.object(qp.fcntl, "flock", side_effect=BlockingIOError):
            self.hook()
        self.assertEqual(target.read_text(), "{}")
        original = dr.read_file
        def refuse(folder, name, limit):
            if name == "host.md":
                raise ValueError("foreign owner")
            return original(folder, name, limit)
        with mock.patch.object(dr, "read_file", side_effect=refuse):
            self.hook()
        self.assertEqual(target.read_text(), "{}")

    def cache(self, reset, remaining=.05, measured=None):
        return {"claude": {"default": {"measured": qp.stamp(measured or MEASURED - qp.timedelta(minutes=1)),
                                     "source": qp.SOURCES["claude"], "groups": [
                                         qp.group("session", "5h", remaining, qp.stamp(reset))]}}}

    def test_marker_reset_fallback_cap_earliest_pool_and_override(self):
        marked = qp.stamp(MEASURED)
        current = MEASURED + qp.timedelta(minutes=5)
        reset = MEASURED + qp.timedelta(hours=2)
        cache = self.cache(reset)
        self.assertEqual(qp.limited_until("claude", marked, cache, current), reset)
        cache["claude"]["default"]["groups"].append(qp.group("week-all", "weekly", .02, qp.stamp(reset + qp.timedelta(hours=1))))
        self.assertEqual(qp.limited_until("claude", marked, cache, current), reset)
        for hours, remaining in ((6, .05), (2, .5), (-1, .05), (2, .1), (2, 1 - .9)):
            self.assertEqual(qp.limited_until("claude", marked, self.cache(MEASURED + qp.timedelta(hours=hours), remaining), current), MEASURED + qp.timedelta(hours=1))
        self.assertEqual(qp.limited_until("claude", marked, self.cache(MEASURED + qp.timedelta(hours=5)), current), MEASURED + qp.timedelta(hours=5))
        self.assertIsNone(qp.limited_until("claude", marked, cache, MEASURED + qp.timedelta(hours=5, seconds=1)))
        self.assertEqual(qp.limited_until("claude", marked, self.cache(reset, measured=MEASURED), current), reset)
        self.assertIsNone(qp.limited_until("claude", marked, self.cache(reset, measured=current), current))
        self.ready()
        with qp.state_folder() as folder:
            qp.write_json(folder, "quota.json", cache)
            qp.write_json(folder, "limits.json", {"claude": marked})
        with mock.patch.object(qp, "now", return_value=current):
            self.assertIn("out of quota until", "\n".join(qp.status_lines()))
        with qp.state_folder() as folder:
            qp.write_json(folder, "quota.json", self.cache(reset, measured=current))
        with mock.patch.object(qp, "now", return_value=current):
            self.assertNotIn("rate-limit marker", "\n".join(qp.status_lines()))

    def test_homebrew_numeric_admin_permissions_and_boundaries(self):
        prefix = self.base / "brew"
        prefix.mkdir(mode=0o775)
        (prefix / ".git").mkdir()
        bin_dir = prefix / "bin"
        bin_dir.mkdir(mode=0o775)
        program = bin_dir / "codex"
        program.write_bytes(b"binary fixture")
        program.chmod(0o775)
        # No chown of real files: emulate the stock numeric gid using fstat and
        # lstat on just the fake prefix, retaining the actual component modes.
        fstat, lstat = os.fstat, os.lstat
        gid = [80]
        def result(info):
            fields = list(info)
            fields[5] = gid[0]
            return os.stat_result(fields)
        def fake_fstat(fd):
            info = fstat(fd)
            if info.st_ino in {p.lstat().st_ino for p in (prefix, bin_dir, program)}:
                return result(info)
            return info
        def fake_lstat(path, *args, **kwargs):
            info = lstat(path, *args, **kwargs)
            return result(info) if qp.in_homebrew(Path(path)) else info
        with mock.patch.object(qp, "HOMEBREW_PREFIX", prefix), \
             mock.patch.object(os, "fstat", side_effect=fake_fstat), \
             mock.patch.object(os, "lstat", side_effect=fake_lstat):
            self.assertEqual(qp.checked_path(program), b"binary fixture")
            qp.brew_links(program)
            # Inject every individual component's other-group mode, including file.
            for component in (prefix, bin_dir, program):
                for p in (prefix, bin_dir, program):
                    p.chmod(0o755)
                component.chmod(0o775)
                gid[0] = 81
                with self.assertRaises(ValueError):
                    qp.checked_path(program)
                gid[0] = 80
                component.chmod(0o777)
                with self.assertRaises(ValueError):
                    qp.checked_path(program)
                component.chmod(0o755)
            nested = bin_dir / ".git"
            nested.mkdir()
            with self.assertRaises(ValueError):
                qp.checked_path(program)
            nested.rmdir()
            tap = prefix / "Library/Taps/example"
            tap.mkdir(parents=True)
            (tap / ".git").write_text("gitdir: elsewhere")
            tool = tap / "codex"
            tool.write_bytes(b"binary")
            tool.chmod(0o755)
            with self.assertRaises(ValueError):
                qp.checked_path(tool)
            outside = self.base / "outside-tool"
            outside.write_bytes(b"binary")
            outside.chmod(0o755)
            program.unlink()
            program.symlink_to(outside)
            with self.assertRaises(ValueError):
                qp.brew_links(program)
            with self.assertRaises((ValueError, OSError)):
                qp.checked_executable("codex", {"executable": str(program), "resolved": str(outside), "interpreter": None})
            program.unlink()
            program.write_text("#!" + self.interpreter + "\n")
            program.chmod(0o755)
            with self.assertRaises(ValueError):
                qp.checked_executable("codex", {"executable": str(program), "resolved": str(program), "interpreter": self.interpreter})
            other = self.base / "clone"
            other.mkdir()
            (other / ".git").mkdir()
            executable = other / "codex"
            executable.write_text("binary")
            executable.chmod(0o755)
            with self.assertRaises(ValueError):
                qp.checked_path(executable)

    def test_setup_homebrew_exception_and_preview_path(self):
        setup = tq.QuotaTest.setup_module(self)
        prefix = self.base / "brew"
        prefix.mkdir()
        (prefix / ".git").mkdir()
        bin_dir = prefix / "bin"
        bin_dir.mkdir()
        program = bin_dir / "codex"
        program.write_bytes(b"binary fixture")
        program.chmod(0o755)
        # Temporary exclusion remains production behavior; only its list is
        # replaced for this synthetic prefix, not the .git exception check.
        resolve = Path.resolve
        def paths(path, *args, **kwargs):
            if str(path) in ("/tmp", "/var/tmp", "/var/folders"):
                return self.base / "forbidden-temp"
            return resolve(path, *args, **kwargs)
        with mock.patch.object(qp, "HOMEBREW_PREFIX", prefix), \
             mock.patch.object(Path, "resolve", paths), \
             mock.patch.dict(os.environ, {"PATH": str(bin_dir)}):
            setup.excluded(program)
            plan, _ = setup.preview(["codex"])
            self.assertIn(str(program), setup.render(plan))
            (bin_dir / ".git").mkdir()
            with self.assertRaises(ValueError):
                setup.excluded(program)

    def test_off_displays_each_recorded_install_and_cached_age(self):
        entry = self.fake("claude")
        second = self.home / "second"
        second.mkdir(mode=0o700)
        entry["configs"]["work"] = str(second)
        self.configure({"claude": entry})
        self.ready()
        with qp.state_folder() as folder:
            qp.write_json(folder, "quota.json", self.cache(MEASURED + qp.timedelta(hours=1), measured=MEASURED))
        with mock.patch.dict(os.environ, {"FNL_QUOTA_PROBE": "off"}), \
             mock.patch.object(qp, "now", return_value=MEASURED), \
             mock.patch.object(qp, "command") as command:
            self.assertEqual(qp.read_family("claude"), ["Quota claude/default: off; age 0s", "Quota claude/work: off; age unknown"])
            command.assert_not_called()

    def test_cli_reads_only_selected_family_without_provider_text(self):
        self.configure({"agy": self.fake("agy"), "codex": self.fake("codex")})
        with mock.patch.object(sys, "argv", ["quota_probe.py", "read", "--family", "agy", "--max-age-minutes", "0"]), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as out, \
             mock.patch.object(qp, "command", wraps=qp.command) as command:
            self.assertEqual(qp.main(), 0)
            self.assertEqual(len(out.getvalue().splitlines()), 1)
            self.assertRegex(out.getvalue(), r"^Quota agy/default: read; age [0-9]+s\n$")
            self.assertEqual(command.call_count, 1)
        with mock.patch.object(sys, "argv", ["quota_probe.py", "read", "--family", "agy"]), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as out, \
             mock.patch.object(qp, "command") as command:
            self.assertEqual(qp.main(), 0)
            self.assertIn(": fresh;", out.getvalue())
            command.assert_not_called()

    def test_setup_preview_discloses_on_demand_cadence(self):
        setup = tq.QuotaTest.setup_module(self)
        entry = self.fake("agy")
        with mock.patch.object(setup, "resolve_executable", return_value={k: entry[k] for k in ("executable", "resolved", "interpreter")}), \
             mock.patch.object(setup, "excluded"), \
             mock.patch.object(sys, "argv", ["quota_setup.py", "preview", "--agents", "agy"]), \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as out:
            self.assertEqual(setup.main(), 0)
        self.assertIn(setup.ON_DEMAND_CONSENT, out.getvalue())
        self.assertIn(str(self.bin / "agy"), out.getvalue())
        self.assertNotIn("4 hours", out.getvalue())
        self.assertFalse((self.root / "host.md").exists())

    def test_hook_cap_boundary_and_limits_foreign_owner(self):
        self.configure({"claude": self.fake("claude")})
        self.ready()
        raw = (tq.FIXTURES / "stop-failure.json").read_bytes()
        self.hook(raw + b" " * (qp.LIMIT - len(raw)))
        target = self.root / "state/quota/limits.json"
        self.assertEqual(json.loads(target.read_text()), {"claude": qp.stamp(MEASURED)})
        with mock.patch.object(qp, "write_json") as write:
            self.hook(raw + b" " * (qp.LIMIT + 1 - len(raw)))
            write.assert_not_called()
        inode = target.stat().st_ino
        original = os.fstat
        def foreign(fd):
            info = original(fd)
            if info.st_ino == inode:
                fields = list(info)
                fields[4] = os.getuid() + 1
                return os.stat_result(fields)
            return info
        with mock.patch.object(os, "fstat", side_effect=foreign), mock.patch.object(qp, "write_json") as write:
            self.hook()
            write.assert_not_called()
        target.parent.chmod(0o755)
        with mock.patch.object(qp, "write_json") as write:
            self.hook()
            write.assert_not_called()

    def test_old_snapshot_stays_unverified_when_caller_sets_long_age(self):
        self.configure({"agy": self.fake("agy")})
        with mock.patch.object(qp, "now", return_value=MEASURED):
            qp.read_family("agy")
        with mock.patch.object(qp, "now", return_value=MEASURED + qp.timedelta(hours=9)), \
             mock.patch.object(qp, "command") as command:
            self.assertIn(": unverified; age 32400s", qp.read_family("agy", 600)[0])
            command.assert_not_called()
