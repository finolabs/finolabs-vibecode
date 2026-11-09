#!/usr/bin/env python3
"""Private local handovers; unsafe storage disables the feature silently."""
import argparse
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

LIMIT = 8 * 1024
LIFETIME = 24 * 60 * 60
MAX_FILES = 20


def filename(session):
    if not isinstance(session, str) or not session:
        raise ValueError("invalid session")
    return hashlib.sha256(session.encode("utf-8")).hexdigest()[:16] + ".md"


def safe_file(info):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077 and info.st_size <= LIMIT)


def read(session):
    """Return fresh UTF-8 text, or nothing on any failure, including unsafe files."""
    try:
        name = filename(session)
        with dr.data_folder("state/handover", private=True) as folder:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
            try:
                info = os.fstat(fd)
                if not safe_file(info) or not 0 <= time.time() - info.st_mtime < LIFETIME:
                    return ""
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    raw = stream.read(LIMIT + 1)
                if len(raw) > LIMIT:
                    return ""
                return raw.decode("utf-8")
            finally:
                os.close(fd)
    except Exception:
        return ""


def write(session, text):
    """Atomically store a bounded handover; storage failures are silent."""
    raw = text.encode("utf-8")
    if len(raw) > LIMIT:
        raise ValueError("invalid handover")
    try:
        name = filename(session)
        with dr.data_folder("state/handover", create=True, private=True) as folder:
            # Serialize writers across sessions so scan/write/evict keeps the cap.
            # The folder descriptor releases the lock on exit; readers never wait.
            fcntl.flock(folder, fcntl.LOCK_EX)
            files = []
            for entry in os.listdir(folder):
                if not re.fullmatch(r"[0-9a-f]{16}\.md", entry):
                    continue
                info = os.stat(entry, dir_fd=folder, follow_symlinks=False)
                if not safe_file(info):
                    return
                if entry != name:
                    files.append((info.st_mtime, entry))
            dr.atomic_write(folder, name, raw)
            files.append((os.stat(name, dir_fd=folder, follow_symlinks=False).st_mtime, name))
            for _, entry in sorted(files)[:max(0, len(files) - MAX_FILES)]:
                os.unlink(entry, dir_fd=folder)
    except Exception:
        return


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid arguments")


def main():
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="action", required=True)
        writer = commands.add_parser("write")
        writer.add_argument("--session", required=True)
        writer.add_argument("--repo")  # Accepted context only; never persisted or sent.
        reader = commands.add_parser("read")
        reader.add_argument("--session", required=True)
        args = parser.parse_args()
        if args.action == "read":
            try:
                # No buffered stdout: a closed pipe must not fail again at shutdown.
                raw = read(args.session).encode("utf-8")
                while raw:
                    written = os.write(1, raw)
                    if written <= 0:
                        break
                    raw = raw[written:]
            except Exception:
                pass
            return 0
        filename(args.session)
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("invalid handover")
        write(args.session, raw.decode("utf-8"))
        return 0
    except Exception:
        if sys.argv[1:2] == ["read"]:
            return 0
        print("Handover refused: invalid input.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
