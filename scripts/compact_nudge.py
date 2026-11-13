#!/usr/bin/env python3
"""Compaction nudge (Claude Code UserPromptSubmit): one fixed line at 80% and 90% of the threshold.

Reads only the integer `usage` counts of the latest assistant entry in the session's
transcript tail and the two compaction settings; never blocks, always exits 0, sends nothing.
See docs/specs/compaction-nudge.md and the eighth scoped exception in CLAUDE.md.
"""
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_LIMIT = 64 * 1024
TAIL = 256 * 1024
MAX_MARKS = 200
MARK_LIMIT = 32
TOKENS = (1000, 10000000)
USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
FOLDER = "state/compaction-nudge"
MESSAGE = ("Context is at {}% of this session's compaction threshold. Before the host compacts, run "
           "tidy now: save the handover, write back decisions and lessons, note background runs "
           "and open pull requests, then offer to compact or start a fresh session.\n")


def config_dir(environ):
    selected = environ.get("CLAUDE_CONFIG_DIR", "")
    if os.path.isabs(selected):
        return Path(selected)
    import data_root as dr
    return dr.account_home() / ".claude"


def transcript_tail(value, projects):
    """Bytes of the last 256 KiB of a regular, non-symlink file inside `projects`, else None."""
    if not isinstance(value, str) or not os.path.isabs(value) or "\0" in value:
        return None
    path = Path(value)
    real = Path(os.path.realpath(path))
    root = Path(os.path.realpath(projects))
    if root not in real.parents:
        return None
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        return None
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            return None
        start = max(0, opened.st_size - TAIL)
        os.lseek(fd, start, os.SEEK_SET)
        data, size = bytearray(), 0
        while size < TAIL:
            chunk = os.read(fd, TAIL - size)
            if not chunk:
                break
            data.extend(chunk)
            size += len(chunk)
        if start:
            data = data[data.find(b"\n") + 1:] if b"\n" in data else bytearray()
        return bytes(data)
    finally:
        os.close(fd)


def used_tokens(tail):
    """Sum of the four usage counts of the latest assistant entry; no other field is kept."""
    lines = tail.split(b"\n")
    if not tail.endswith(b"\n"):
        lines = lines[:-1]  # only complete lines
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
        if not isinstance(usage, dict):
            continue
        values = [usage.get(key) for key in USAGE]
        if all(type(v) is int and 0 <= v <= 100000000 for v in values) and sum(values) > 0:
            return sum(values)
    return None


def integer(value):
    if type(value) is int:
        return value if TOKENS[0] <= value <= TOKENS[1] else None
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,9}", value.strip()):
        number = int(value.strip())
        return number if TOKENS[0] <= number <= TOKENS[1] else None
    return None


def truthy(value):
    return isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on"}


def settings_files(environ, cwd):
    """(label, path) most precedent first: managed, local, project, user."""
    from compact_setup import managed_settings
    files = list(managed_settings())
    if isinstance(cwd, str) and os.path.isabs(cwd):
        here = Path(cwd)
        root = next((p for p in (here, *here.parents) if os.path.lexists(p / ".git")), here)
        files += [("local", root / ".claude/settings.local.json"), ("project", root / ".claude/settings.json")]
    files.append(("user", config_dir(environ) / "settings.json"))
    return files


def settings_values(files):
    """Only `autoCompactEnabled` and `autoCompactWindow` from each readable file, in the given order."""
    from compact_setup import read_settings
    values = []
    for _, path in files:
        raw = read_settings(path)
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            continue
        if isinstance(data, dict):
            values.append((data.get("autoCompactEnabled"), data.get("autoCompactWindow")))
    return values


def threshold(environ, values):
    """Effective compaction threshold in tokens, or None when off or unresolved."""
    if truthy(environ.get("DISABLE_AUTO_COMPACT")):
        return None
    enabled = next((e for e, _ in values if type(e) is bool), None)
    if enabled is False:
        return None
    window = integer(environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW"))
    if window is None:
        window = next((w for _, w in values if type(w) is int and integer(w) is not None), None)
    if window is None:
        return None  # the host default is not recorded yet
    override = environ.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE")
    if isinstance(override, str) and re.fullmatch(r"[0-9]{1,3}", override.strip()):
        percent = int(override.strip())
        if 1 <= percent <= 100:
            window = window * percent // 100
    return window if window > 0 else None


def band(used, limit):
    percent = used * 100 // limit
    return 90 if percent >= 90 else 80 if percent >= 80 else 0


def safe_mark(info):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1 and info.st_size <= MARK_LIMIT)


def decide(session, used, limit):
    """Return the percent to print after the mark (the last band) is written, else None."""
    import data_root as dr
    name = hashlib.sha256(session.encode()).hexdigest()[:16]
    current = band(used, limit)
    try:
        with dr.data_folder(FOLDER, private=True) as folder:
            fcntl.flock(folder, fcntl.LOCK_SH)
            info = os.stat(name, dir_fd=folder, follow_symlinks=False)
            if not safe_mark(info):
                return None
            raw = dr.read_file(folder, name, MARK_LIMIT).decode("ascii")
            if raw not in {"0", "80", "90"}:
                return None
            last = int(raw)
    except FileNotFoundError:
        last = None
    # A lower band than the stored one means the count dropped (a compaction): reset to 0.
    stored = 0 if last is None or current < last else last
    if current <= stored and (last is None or last == stored):
        return None
    with dr.data_folder(FOLDER, create=True, private=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX)
        if last is None:
            marks = []
            for entry in os.listdir(folder):
                if re.fullmatch(r"[0-9a-f]{16}", entry) and entry != name:
                    marks.append((os.stat(entry, dir_fd=folder, follow_symlinks=False).st_mtime_ns, entry))
            # Evict before writing so the folder never holds more than MAX_MARKS.
            for _, entry in sorted(marks)[:max(0, len(marks) - MAX_MARKS + 1)]:
                os.unlink(entry, dir_fd=folder)
        dr.atomic_write(folder, name, str(current if current > stored else stored).encode("ascii"))
    return used * 100 // limit if current > stored else None


def main():
    try:
        environ = os.environ
        if environ.get("FNL_COMPACT_NUDGE", "").strip().lower() == "off":
            return 0
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict):
            return 0
        session = event.get("session_id")
        if (not isinstance(session, str) or not 0 < len(session) <= 128
                or not isinstance(event.get("transcript_path"), str)):
            return 0
        limit = threshold(environ, settings_values(settings_files(environ, event.get("cwd"))))
        if limit is None:
            return 0
        tail = transcript_tail(event.get("transcript_path"), config_dir(environ) / "projects")
        used = used_tokens(tail) if tail is not None else None
        if used is None:
            return 0
        percent = decide(session, used, limit)
        if percent is not None:
            os.write(1, MESSAGE.format(percent).encode("ascii"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    raise SystemExit(0)
