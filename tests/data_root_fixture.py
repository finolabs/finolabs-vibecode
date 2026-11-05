"""Inject a synthetic passwd home into existing CLI tests, never via product env flags."""

import os
import pwd
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def account(test, home):
    home = Path(home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    patch = mock.patch.object(pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(home)))
    patch.start()
    test.addCleanup(patch.stop)
    original = subprocess.run
    boot = ("import pwd,runpy,sys; from types import SimpleNamespace; "
            f"pwd.getpwuid=lambda uid: SimpleNamespace(pw_dir={str(home)!r}); "
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
