#!/usr/bin/env python3
"""Local repository-window state for the opt-in auto gate (stdlib only).

Invalid state raises: callers must allow silently, not replace unsafe state.
Only a missing file is an empty state. No environment variable selects storage.
"""

try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import hashlib
import json
import os
try:
    import pwd
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import re
import stat
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

OFF_VALUES = {"off", "0", "false", "no"}
WINDOW = timedelta(hours=8)
MAX_BYTES = 4096


def repository_key(cwd):
    root = Path(os.path.realpath(cwd))
    while True:
        if os.path.lexists(root / ".git"):
            return hashlib.sha256(os.fsencode(root)).hexdigest()[:12]
        if root == root.parent:
            return None
        root = root.parent


def enabled(effective):
    """Environment can disable, but only host config can opt in."""
    if os.environ.get("FNL_AUTO_GATE", "").lower() in OFF_VALUES:
        return False
    if effective(keys=("auto_gate",), gate_opt_in=True).get("auto_gate") != "on":
        return False
    return effective(keys=("delegation_mode",)).get("delegation_mode") == "auto"


@contextmanager
def state_folder(*, writer=False):
    with dr.data_folder("state/auto-gate", create=True, private=True) as fd:
        # Serialize merges and stale-file retirement without another state file.
        # Only writers retry contention; the hook always allows immediately.
        for attempt in range(3 if writer else 1):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not writer or attempt == 2:
                    raise
                time.sleep(0.05)
        yield fd


def filename(key):
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{12}", key):
        raise ValueError("invalid repository key")
    return key + ".json"


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp needs timezone")
    return parsed


def read_state(folder, key):
    try:
        fd = os.open(filename(key), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    except FileNotFoundError:
        return {}
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > MAX_BYTES:
            raise ValueError("unsafe state file")
        data = os.read(fd, MAX_BYTES)
        state = json.loads(data)
        if not isinstance(state, dict) or not state or state.keys() - {"decision", "decided", "denied"}:
            raise ValueError("invalid state")
        if "decision" in state or "decided" in state:
            if state.get("decision") not in ("keep", "handoff") or "decided" not in state:
                raise ValueError("invalid decision")
            timestamp(state["decided"])
        if "denied" in state:
            timestamp(state["denied"])
        return state
    finally:
        os.close(fd)


def in_window(state, now=None):
    now = now or datetime.now(timezone.utc)
    return any(timedelta(0) <= now - timestamp(state[field]) < WINDOW
               for field in ("decided", "denied") if field in state)


def write_state(folder, key, state, exclusive=False):
    """Publish a complete merged state, with an exclusive link for a denial."""
    temporary = ".auto-gate-" + os.urandom(12).hex()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=folder)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(json.dumps(state).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            try:
                os.link(temporary, filename(key), src_dir_fd=folder, dst_dir_fd=folder,
                        follow_symlinks=False)
            except FileExistsError:
                return False
        else:
            os.replace(temporary, filename(key), src_dir_fd=folder, dst_dir_fd=folder)
        os.fsync(folder)
        return True
    finally:
        try:
            os.unlink(temporary, dir_fd=folder)
        except FileNotFoundError:
            pass


def write_decision(key, decision):
    if decision not in ("handoff", "keep"):
        raise ValueError("invalid decision")
    with state_folder(writer=True) as folder:
        state = read_state(folder, key)
        state.update(decision=decision, decided=datetime.now(timezone.utc).isoformat())
        write_state(folder, key, state)


def claim_denial(key):
    """True only for a durable, exclusively claimed and read-back first denial."""
    with state_folder() as folder:
        state = read_state(folder, key)
        if in_window(state):
            return False
        if state:
            # Only validated, expired state is retired, under the merge lock.
            os.unlink(filename(key), dir_fd=folder)
        state["denied"] = datetime.now(timezone.utc).isoformat()
        return write_state(folder, key, state, exclusive=True) and read_state(folder, key) == state
