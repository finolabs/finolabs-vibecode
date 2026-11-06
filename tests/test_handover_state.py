"""Private handover storage acceptance, using only synthetic account state."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("handover_state", ROOT / "scripts/handover_state.py")
hs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hs)


def setup_store(test):
    temp = tempfile.TemporaryDirectory()
    test.addCleanup(temp.cleanup)
    base = Path(temp.name).resolve()
    home = account(test, base / "home")
    # Same fstat seam as test_compact_setup: only writable system ancestors
    # are masked; checks on every synthetic folder and file stay in force.
    ancestors = {p.stat().st_ino for p in base.parents if p.stat().st_mode & 0o022}
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
    test.addCleanup(patch.stop)
    return home / ".finolabs/vibecode"


class HandoverStateTest(unittest.TestCase):
    def setUp(self):
        self.root = setup_store(self)
        self.folder = self.root / "state/handover"
        self.path = self.folder / (hashlib.sha256(b"synthetic").hexdigest()[:16] + ".md")

    def cli(self, *args, raw=b""):
        out, err = io.StringIO(), io.StringIO()
        original_write = os.write

        def output(fd, data):
            if fd == 1:
                out.write(data.decode("utf-8"))
                return len(data)
            return original_write(fd, data)

        with mock.patch.object(sys, "argv", ["handover_state.py", *args]), \
                mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")), \
                mock.patch.object(os, "write", side_effect=output), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hs.main()
        return code, out.getvalue(), err.getvalue()

    def seed(self):
        self.assertEqual(self.cli("write", "--session", "synthetic", "--repo", "sample", raw=b"Private next action\n"), (0, "", ""))
        self.assertTrue(self.path.exists())

    def assert_silent_read(self):
        self.assertEqual(self.cli("read", "--session", "synthetic"), (0, "", ""))

    def test_round_trip_utf8_exact_limit_private_modes_and_hashed_identity(self):
        text = "\u03bb" * 4096
        self.assertEqual(self.cli("write", "--session", "synthetic", "--repo", "sample", raw=text.encode()), (0, "", ""))
        self.assertEqual(self.cli("read", "--session", "synthetic"), (0, text, ""))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.folder.stat().st_mode), 0o700)
        self.assertEqual(list(self.folder.iterdir()), [self.path])
        self.assertNotIn("sample", self.path.read_text())
        hs.write("../../another/session", "another")
        self.assertEqual(hs.read("../../another/session"), "another")
        self.assertEqual(len(list(self.folder.glob("*.md"))), 2)

    def test_oversized_and_invalid_utf8_writes_refused_without_truncation(self):
        self.seed()
        before = self.path.read_bytes()
        for raw in (b"x" * 8193, b"\xffprivate-text"):
            with self.subTest(size=len(raw)):
                self.assertEqual(self.cli("write", "--session", "synthetic", raw=raw),
                                 (2, "", "Handover refused: invalid input.\n"))
                self.assertEqual(self.path.read_bytes(), before)

    def test_missing_expired_future_oversized_invalid_utf8_and_nonregular_read(self):
        self.assert_silent_read()
        self.seed()
        now = time.time()
        with mock.patch.object(hs.time, "time", return_value=now):
            for age, expected in ((86399, "Private next action\n"), (86400, ""), (86401, ""), (-1, "")):
                os.utime(self.path, (now - age, now - age))
                self.assertEqual(hs.read("synthetic"), expected)
        os.utime(self.path, None)
        for raw in (b"x" * 8193, b"\xffprivate-text"):
            self.path.write_bytes(raw)
            self.assert_silent_read()
        self.path.unlink()
        self.path.mkdir()
        self.assert_silent_read()
        self.path.rmdir()
        os.mkfifo(self.path)
        self.assert_silent_read()

    def test_symlink_file_and_component_refuse_read_and_write(self):
        self.seed()
        original = self.folder / "original"
        self.path.rename(original)
        self.path.symlink_to(original)
        self.assert_silent_read()
        self.assertEqual(self.cli("write", "--session", "synthetic", raw=b"replacement"), (0, "", ""))
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(original.read_bytes(), b"Private next action\n")
        self.path.unlink()
        original.rename(self.path)
        real = self.folder.with_name("real")
        self.folder.rename(real)
        self.folder.symlink_to(real, target_is_directory=True)
        self.assert_silent_read()
        self.assertEqual(self.cli("write", "--session", "synthetic", raw=b"replacement"), (0, "", ""))
        self.assertEqual((real / self.path.name).read_bytes(), b"Private next action\n")

    def test_writable_folder_or_file_refuses_read_and_write(self):
        self.seed()
        for target, modes in ((self.path, (0o620, 0o602)), (self.folder, (0o770, 0o707)),
                              (self.folder.parent, (0o770, 0o707)), (self.root, (0o770, 0o707))):
            original = stat.S_IMODE(target.stat().st_mode)
            for mode in modes:
                with self.subTest(target=target.name, mode=oct(mode)):
                    target.chmod(mode)
                    self.assert_silent_read()
                    self.assertEqual(self.cli("write", "--session", "synthetic", raw=b"replacement"), (0, "", ""))
                    self.assertEqual(self.path.read_bytes(), b"Private next action\n")
            target.chmod(original)

    def test_wrong_owner_refuses_read_and_write(self):
        self.seed()
        original_fstat, original_stat = os.fstat, os.stat
        inode = self.path.stat().st_ino

        def foreign(info):
            if info.st_ino == inode:
                fields = list(info)
                fields[4] = os.getuid() + 1
                return os.stat_result(fields)
            return info

        with mock.patch.object(os, "fstat", side_effect=lambda fd: foreign(original_fstat(fd))), \
                mock.patch.object(os, "stat", side_effect=lambda *a, **kw: foreign(original_stat(*a, **kw))):
            self.assert_silent_read()
            self.assertEqual(self.cli("write", "--session", "synthetic", raw=b"replacement"), (0, "", ""))
        self.assertEqual(self.path.read_bytes(), b"Private next action\n")

    def test_keeps_twenty_removing_oldest_mtime_and_overwrites_atomically(self):
        for i in range(21):
            hs.write(str(i), str(i))
            path = self.folder / hs.filename(str(i))
            os.utime(path, (1000 + i, 1000 + i))
        self.assertEqual(len(list(self.folder.iterdir())), 20)
        self.assertFalse((self.folder / hs.filename("0")).exists())
        self.seed()
        with self.path.open("rb") as old:
            hs.write("synthetic", "replacement")
            self.assertEqual(old.read(), b"Private next action\n")
        self.assertEqual(hs.read("synthetic"), "replacement")
        self.assertEqual(len(list(self.folder.iterdir())), 20)
        with mock.patch.object(os, "replace", side_effect=OSError("private text")):
            self.assertEqual(self.cli("write", "--session", "synthetic", raw=b"discard"), (0, "", ""))
        self.assertEqual(hs.read("synthetic"), "replacement")
        self.assertFalse(list(self.folder.glob(".write-*")))

    def test_invalid_root_disables_and_relocated_root_uses_ancestor_checks(self):
        self.seed()
        (self.root / "root.json").write_text('{"invalid":"private text"}')
        self.assert_silent_read()
        self.assertEqual(self.cli("write", "--session", "synthetic", raw=b"replacement"), (0, "", ""))
        self.assertEqual(self.path.read_bytes(), b"Private next action\n")
        (self.root / "root.json").unlink()
        relocated = self.root.parents[1] / "relocated"
        relocated.mkdir(mode=0o700)
        (relocated / ".root-id").write_text("synthetic-id")
        hs.dr.write_pointer(relocated, "synthetic-id")
        self.assert_silent_read()
        hs.write("synthetic", "relocated")
        self.assertEqual(hs.read("synthetic"), "relocated")
        relocated.chmod(0o777)
        self.assert_silent_read()

    def test_any_read_failure_is_silent_including_bad_arguments_and_output(self):
        self.assertEqual(self.cli("read", "--session"), (0, "", ""))
        self.assertEqual(self.cli("read", "--unknown", "private text"), (0, "", ""))
        with mock.patch.object(hs.dr, "data_folder", side_effect=RuntimeError("private text")):
            self.assert_silent_read()
        with mock.patch.object(sys, "argv", ["handover_state.py", "read", "--session", "synthetic"]), \
                mock.patch.object(hs, "read", return_value="private text"), \
                mock.patch.object(os, "write", side_effect=BrokenPipeError("private text")):
            self.assertEqual(hs.main(), 0)

    def test_parallel_writers_serialize_eviction_to_keep_twenty(self):
        for i in range(19):
            hs.write(str(i), str(i))
        first_writing, release, second_started, second_writing = (threading.Event() for _ in range(4))
        original = hs.dr.atomic_write

        def atomic_write(folder, name, raw):
            if raw == b"first":
                first_writing.set()
                if not release.wait(2):
                    raise RuntimeError("test timeout")
            elif raw == b"second":
                second_writing.set()
            return original(folder, name, raw)

        def second():
            second_started.set()
            hs.write("second", "second")

        with mock.patch.object(hs.dr, "atomic_write", side_effect=atomic_write):
            first = threading.Thread(target=hs.write, args=("first", "first"))
            other = threading.Thread(target=second)
            first.start()
            try:
                self.assertTrue(first_writing.wait(2))
                other.start()
                self.assertTrue(second_started.wait(2))
                self.assertFalse(second_writing.wait(0.1), "second writer entered before first completed")
            finally:
                release.set()
                first.join(2)
                if other.ident is not None:
                    other.join(2)
        self.assertFalse(first.is_alive() or other.is_alive())
        self.assertTrue(second_writing.is_set())
        self.assertEqual(len(list(self.folder.iterdir())), 20)

    def test_read_broken_pipe_exits_zero_without_shutdown_error(self):
        # No account data: the child substitutes the read result before main.
        code = ("import sys; "
                f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
                "import handover_state as h; h.read = lambda session: 'x' * 8192; "
                "sys.argv = ['handover_state.py', 'read', '--session', 'synthetic']; "
                "raise SystemExit(h.main())")
        reader, writer = os.pipe()
        os.close(reader)
        try:
            result = subprocess.run([sys.executable, "-I", "-c", code], stdout=writer,
                                    stderr=subprocess.PIPE, timeout=5)
        finally:
            os.close(writer)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
