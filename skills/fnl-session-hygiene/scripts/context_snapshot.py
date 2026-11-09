#!/usr/bin/env python3
"""Store status-line context counts only; never read a transcript or run a command."""
import argparse
from datetime import datetime, timezone
try:
    import fcntl
except ImportError:  # native Windows has no fcntl
    raise ImportError("finolabs-vibecode scripts need macOS, Linux or WSL; "
                      "native Windows is not supported (no fcntl module)") from None
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
from context_steward import check as steward_check

LIMIT = 64 * 1024
MAX_SNAPSHOT = 4096
MAX_FILES = 20
LIFETIME = 3600
NO_READING = "Context snapshot unavailable: missing, unsafe, invalid or stale reading."
FIELDS = {"used", "window", "percent", "measured", "version", "host"}
VERSION = r"[0-9]{1,3}(?:\.[0-9]{1,3}){1,3}(?:-[A-Za-z0-9]{1,12})?"
HOSTS = ("claude", "antigravity")


def filename(session, host="claude"):
    if host not in HOSTS or not isinstance(session, str) or not session or len(session) > 4096:
        raise ValueError("invalid session")
    if host == "antigravity":
        session = "antigravity:" + session
    return hashlib.sha256(session.encode("utf-8")).hexdigest()[:16] + ".json"


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("invalid number")


def load(raw):
    return json.loads(raw, object_pairs_hook=json_object, parse_constant=invalid_constant)


def safe_file(info):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
            and info.st_size <= MAX_SNAPSHOT)


def snapshots(folder):
    files = []
    for name in os.listdir(folder):
        if re.fullmatch(r"[0-9a-f]{16}\.json", name):
            info = os.stat(name, dir_fd=folder, follow_symlinks=False)
            if not safe_file(info):
                raise ValueError("unsafe snapshot")
            files.append((info.st_mtime_ns, name))
    return files


def counts(used, window):
    return (type(used) is int and type(window) is int
            and 0 < window <= 10000000 and 0 <= used <= 10 * window)


def record(raw, host="claude"):
    """Return a percent only after a successful write; invalid usage clears this session."""
    if len(raw) > LIMIT:
        return None
    event = load(raw)
    if not isinstance(event, dict):
        return None
    name = filename(event.get("conversation_id" if host == "antigravity" else "session_id"), host)
    context = event.get("context_window")
    if not isinstance(context, dict):
        return None
    usage = context.get("current_usage")
    values = [usage.get(key) for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")] if isinstance(usage, dict) else []
    valid_usage = len(values) == 3 and all(type(value) is int and 0 <= value <= 100000000 for value in values)
    if not valid_usage:
        # Do not create storage just to invalidate a reading after /compact.
        try:
            with dr.data_folder("state/context", private=True) as folder:
                fcntl.flock(folder, fcntl.LOCK_EX)
                if name in {entry for _, entry in snapshots(folder)}:
                    os.unlink(name, dir_fd=folder)
                    os.fsync(folder)
        except FileNotFoundError:
            pass
        return None
    used, window = sum(values), context.get("context_window_size")
    if not counts(used, window):
        return None
    version = event.get("version")
    version = version if isinstance(version, str) and len(version) <= 32 and re.fullmatch(VERSION, version) else "unknown"
    percent = used * 100 // window
    data = {"used": used, "window": window, "percent": percent,
            "measured": datetime.fromtimestamp(time.time(), timezone.utc).isoformat().replace("+00:00", "Z"),
            "version": version, "host": host}
    with dr.data_folder("state/context", create=True, private=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX)
        files = [(mtime, entry) for mtime, entry in snapshots(folder) if entry != name]
        # Evict before writing so even a failed write never exceeds the cap.
        for _, entry in sorted(files)[:max(0, len(files) - MAX_FILES + 1)]:
            os.unlink(entry, dir_fd=folder)
        dr.atomic_write(folder, name, json.dumps(data, separators=(",", ":")).encode())
    return percent


def timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z") or len(value) > 32:
        raise ValueError("invalid timestamp")
    return datetime.fromisoformat(value[:-1] + "+00:00").timestamp()


def read_data(folder, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        if not safe_file(os.fstat(fd)):
            raise ValueError("unsafe snapshot")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_SNAPSHOT + 1)
        if len(raw) > MAX_SNAPSHOT:
            raise ValueError("oversized snapshot")
        return load(raw)
    finally:
        os.close(fd)


def read(session=None, *, latest=False, max_age_seconds=LIFETIME, host=None):
    """Return validated fresh counts or None; latest is explicit and may name another session."""
    try:
        if (type(max_age_seconds) is not int or not 0 <= max_age_seconds <= 86400
                or (latest and session is not None) or (not latest and session is None)
                or (host is not None and host not in HOSTS)):
            return None
        with dr.data_folder("state/context", private=True) as folder:
            if latest:
                files = snapshots(folder)
                if host is not None:
                    files = [(mtime, name) for mtime, name in files if read_data(folder, name).get("host") == host]
                if not files:
                    return None
                name = max(files)[1]
            else:
                name = filename(session, host or "claude")
            data = read_data(folder, name)
        if (not isinstance(data, dict) or set(data) != FIELDS
                or not counts(data["used"], data["window"])
                or type(data["percent"]) is not int or data["percent"] != data["used"] * 100 // data["window"]
                or data["host"] not in HOSTS
                or (not latest and data["host"] != (host or "claude"))
                or (host is not None and data["host"] != host) or not isinstance(data["version"], str)
                or not (data["version"] == "unknown" or (len(data["version"]) <= 32 and re.fullmatch(VERSION, data["version"])))):
            return None
        age = time.time() - timestamp(data["measured"])
        if not 0 <= age <= max_age_seconds:
            return None
        return {"used": data["used"], "window": data["window"], "percent": data["percent"],
                "age_seconds": int(age), "stale": False}
    except Exception:
        return None


def emit(text):
    # Avoid buffered stdout retrying a closed status-line pipe at interpreter exit.
    raw = text.encode("ascii")
    while raw:
        written = os.write(1, raw)
        if written <= 0:
            raise OSError("closed output")
        raw = raw[written:]


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid arguments")


def main():
    recording = sys.argv[1:2] == ["record"]
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="action", required=True)
        writer = commands.add_parser("record")
        writer.add_argument("--line", action="store_true")
        writer.add_argument("--host", choices=HOSTS, default="claude")
        for command in ("read", "check"):
            reader = commands.add_parser(command)
            reader.add_argument("--host", choices=HOSTS)
            choice = reader.add_mutually_exclusive_group(required=True)
            choice.add_argument("--session")
            choice.add_argument("--latest", action="store_true")
            reader.add_argument("--max-age-seconds", type=int, default=LIFETIME)
            if command == "check":
                reader.add_argument("--threshold", type=int, required=True)
                reader.add_argument("--boundary", choices=("yes", "no", "unknown"), default="unknown")
        args = parser.parse_args()
        if args.action == "record":
            value = record(sys.stdin.buffer.read(LIMIT + 1), args.host)
            if args.line and value is not None:
                emit(f"ctx {value}%\n")
            return 0
        result = read(args.session, latest=args.latest, max_age_seconds=args.max_age_seconds, host=args.host)
        if result is None:
            raise ValueError("unavailable")
        if args.action == "check":
            result = steward_check(result["used"], result["window"], args.threshold, args.boundary)
        emit(json.dumps(result) + "\n")
        return 0
    except Exception:
        if recording:
            return 0
        print(NO_READING, file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
