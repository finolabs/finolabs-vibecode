"""Inject a synthetic passwd home into existing CLI tests, never via product env flags."""

import os
import pwd
import shlex
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
    patch = mock.patch.object(pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(home)))
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
            command[2] = command[2].replace("python3 -I ", shlex.join([sys.executable, "-I", "-c", boot]) + " ")
        return original(command, *args, **kwargs)

    patch = mock.patch.object(subprocess, "run", side_effect=run)
    patch.start()
    test.addCleanup(patch.stop)
    return home
