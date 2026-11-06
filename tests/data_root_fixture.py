"""Inject a synthetic passwd home into existing CLI tests, never via product env flags."""

import os
import pwd
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


# Capture only the account path, never read its contents. Opening this anchor
# would let a missed bootstrap walk into the real quota state with dir_fd.
REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)


def account(test, home):
    home = Path(home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    patch = mock.patch.object(pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(home), pw_name="quota-test-user"))
    patch.start()
    test.addCleanup(patch.stop)
    # Only writable system ancestors of the synthetic home get this test seam.
    # Checks on the fixture tree itself remain real, including unsafe fixtures.
    ancestors = {(p.stat().st_dev, p.stat().st_ino) for p in home.parent.parents
                 if p.stat().st_mode & 0o022}
    original_fstat = os.fstat

    def fstat(fd):
        info = original_fstat(fd)
        if (info.st_dev, info.st_ino) in ancestors and stat.S_ISDIR(info.st_mode):
            fields = list(info)
            fields[0] &= ~0o022
            return os.stat_result(fields)
        return info

    patch = mock.patch.object(os, "fstat", side_effect=fstat)
    patch.start()
    test.addCleanup(patch.stop)
    original_open = os.open

    def guarded_open(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            candidate = Path(os.fsdecode(path))
            quota = REAL_HOME / ".finolabs/vibecode/state/quota"
            assert candidate != REAL_HOME and not candidate.is_relative_to(quota), "test touched real account state"
        return original_open(path, *args, **kwargs)

    patch = mock.patch.object(os, "open", side_effect=guarded_open)
    patch.start()
    test.addCleanup(patch.stop)
    original = subprocess.run
    boot = ("import runpy,sys,unittest; "
            f"sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r}); "
            "from tests.data_root_fixture import account; "
            f"account(unittest.TestCase(), {str(home)!r}); "
            "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')")

    def run(command, *args, **kwargs):
        command = list(command)
        if len(command) > 2 and command[0] == sys.executable and command[1] == "-I" and command[2] != "-c":
            command[2:2] = ["-c", boot]
        elif len(command) == 3 and command[:2] == ["sh", "-c"]:
            # Match a bare command only, never the suffix of an absolute
            # interpreter path already bootstrapped by the caller.
            command[2] = re.sub(r"(?<![\w/.'\"-])python3 -I ",
                                lambda _: shlex.join([sys.executable, "-I", "-c", boot]) + " ", command[2])
        return original(command, *args, **kwargs)

    original_popen = subprocess.Popen

    def popen(command, *args, **kwargs):
        command = list(command)
        if len(command) > 2 and command[:2] == [sys.executable, "-I"] and command[2] != "-c":
            command[2:2] = ["-c", boot]
        return original_popen(command, *args, **kwargs)

    patch = mock.patch.object(subprocess, "Popen", side_effect=popen)
    patch.start()
    test.addCleanup(patch.stop)
    patch = mock.patch.object(subprocess, "run", side_effect=run)
    patch.start()
    test.addCleanup(patch.stop)
    return home
