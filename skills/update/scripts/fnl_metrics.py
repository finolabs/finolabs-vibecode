"""Shared core of the usage metrics: where events live, what an event may hold, how one is written.

Metadata only. An event carries a time, a session id, a short repository code and a few
enum or name fields; no prompt, code, command text, file path or review text. Nothing is
written until the user has consented (consent.json) and FNL_METRICS is not "off".

This file is copied byte for byte into the skills that import it (fnl-coding-router,
fnl-status, fnl-update); a test keeps the copies equal.
"""

import hashlib
import json
import os
import re
import stat
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

HOSTS = ("claude", "codex", "antigravity", "other")
SOURCES = ("startup", "resume", "clear", "compact")
DEPTHS = ("MIN", "NORMAL", "DEEP")
TRIGGERS = ("none", "contract", "security", "privacy", "permission", "migration", "dependency",
            "uncertainty", "consumers", "irreversible", "calculation", "prediction", "input")
KINDS = ("code", "security")
VERDICTS = ("APPROVE", "REWORK")
KEPT_REASONS = ("needs-context", "brief-costs-more", "hard-grade", "no-delegate", "never-delegated", "user-choice")
ROUTE_BY = ("table", "judge", "user")
JUDGE_SITES = ("route", "depth", "activity", "instruction")
JUDGE_GRADERS = ("judge", "agent")
JUDGE_RESULTS = ("validated", "unverified")
JUDGE_FOLLOWED = ("yes", "no", "na")
RETENTIONS = (30, 90, 365)
MARKER_DAYS = 7
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

ID = re.compile(r"^[A-Za-z0-9_-]{1,64}\Z")
TASK_ID = re.compile(r"^T[0-9]{1,4}\Z")
NAME = re.compile(r"^fnl-[a-z][a-z-]{0,39}\Z")
REPO = re.compile(r"^[0-9a-f]{8}\Z")
TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00\Z")
EVENT_FILE = re.compile(r"^events-(\d{4})-(\d{2})\.jsonl\Z")


def valid_id(v):
    return isinstance(v, str) and ID.match(v) is not None


def _name(v):
    return isinstance(v, str) and NAME.match(v) is not None


def _tasks(v):
    return isinstance(v, int) and not isinstance(v, bool) and 0 < v < 1000


def _pr(v):
    return isinstance(v, int) and not isinstance(v, bool) and 0 < v < 10**8


# Field name -> check, per event. An event holds exactly these fields beside the common ones.
SCHEMA = {
    "session_start": {"host": lambda v: v in HOSTS, "dispatch": lambda v: v is None or valid_id(v),
                      "source": lambda v: v in SOURCES},
    "skill": {"name": _name},
    "agent": {"name": _name},
    "first_edit": {},
    "commit": {},
    "review": {"kind": lambda v: v in KINDS, "verdict": lambda v: v in VERDICTS, "pr": _pr},
    "task": {"id": lambda v: isinstance(v, str) and TASK_ID.fullmatch(v) is not None},
    "router": {"depth": lambda v: v in DEPTHS, "trigger": lambda v: v in TRIGGERS},
    "judge": {"site": lambda v: v in JUDGE_SITES, "grader": lambda v: v in JUDGE_GRADERS,
              "result": lambda v: v in JUDGE_RESULTS, "followed": lambda v: v in JUDGE_FOLLOWED},
    "kept": {"tasks": _tasks, "reason": lambda v: v in KEPT_REASONS, "route_by": lambda v: v in ROUTE_BY},
}


def valid_judge_pairs(fields):
    """Cross-field constraints, in addition to the closed enumerations."""
    return ((fields["grader"] != "agent" or fields["result"] == "validated")
            and (fields["followed"] == "na" or
                 fields["grader"] == "judge" and fields["result"] == "validated"))


def state_dir():
    """FNL_STATE_DIR when it is an absolute path, else the resolved data root state folder.

    A relative override is ignored, as is a relative XDG_STATE_HOME. A machine that already
    keeps its state in the older folder (${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode)
    and has none in the new one keeps using the older folder; nothing is moved.
    """
    override = os.environ.get("FNL_STATE_DIR")
    if override and os.path.isabs(override):
        return Path(override)
    root, source = dr.data_root()
    new = root / "state"
    xdg = os.environ.get("XDG_STATE_HOME")
    old = Path(xdg if xdg and os.path.isabs(xdg) else dr.account_home() / ".local/state") / "finolabs-vibecode"
    return old if source != "relocated" and old.is_dir() and not new.exists() else new


def now():
    return datetime.now(timezone.utc)


def atomic_write(path, data):
    """Write str or bytes to path through a temporary file in the same folder, mode 0600."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data.encode("utf-8") if isinstance(data, str) else data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ensure_dir(path, follow=False):
    """Create path with mode 0700 and return it. Only a folder created here has its mode set.

    Refuses something that is not a folder, and a symlink unless follow is True (the state
    folder may be a link the user made; the folders inside it must be real).
    """
    if path.is_symlink():
        if not follow or not path.is_dir():
            raise ValueError("refusing a symlink or a non-folder: " + path.name)
    elif path.exists():
        if not path.is_dir():
            raise ValueError("not a folder: " + path.name)
    else:
        missing, folder = [], path
        while not folder.exists() and folder != folder.parent:
            missing.append(folder)
            folder = folder.parent
        for new in reversed(missing):  # every folder made here, ~/.finolabs included, is private
            try:
                new.mkdir(mode=0o700)
                os.chmod(new, 0o700)
            except FileExistsError:  # another hook made it first
                if not new.is_dir() or new.is_symlink():
                    raise ValueError("not a folder: " + new.name)
    return path


def read_consent():
    """The consent record, or None when missing or not valid."""
    try:
        if dr.consent_root() is None:
            return None
        data = json.loads(dr.read_data("state/consent.json", 4096))
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and data.get("retention_days") in RETENTIONS and isinstance(data.get("date"), str):
        return data
    return None


def write_consent(retention_days):
    if retention_days not in RETENTIONS:
        raise ValueError("retention must be one of %s days" % (RETENTIONS,))
    dr.write_data("state/consent.json",
                  (json.dumps({"date": now().date().isoformat(), "retention_days": retention_days}) + "\n").encode())


def enabled():
    return os.environ.get("FNL_METRICS", "").lower() != "off" and read_consent() is not None


def read_small(path):
    """The first 4 KB of a regular file as text; never blocks on a pipe and never follows a symlink."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        return os.read(fd, 4096).decode("utf-8", "replace")
    finally:
        os.close(fd)


def repo_root(cwd):
    """The main repository root: the folder holding .git, or for a linked worktree the root of the repository it belongs to."""
    start = Path(cwd).resolve()
    for folder in (start, *start.parents):
        git = folder / ".git"
        if git.is_dir():
            return folder
        if git.is_file():
            try:
                with open(git, "rb") as handle:
                    text = handle.read(4096).decode("utf-8", "replace").strip()
                if text.startswith("gitdir:"):
                    gitdir = (folder / text[len("gitdir:"):].strip()).resolve()
                    common = (gitdir / read_small(gitdir / "commondir").strip()).resolve()
                    return common.parent if common.name == ".git" else common
            except (OSError, ValueError):
                pass
            return folder
    return start


def repo_code(cwd):
    """First 8 hex characters of SHA-256 of the repository root path."""
    return hashlib.sha256(str(repo_root(cwd)).encode("utf-8")).hexdigest()[:8]


def build_event(event, sid, repo, fields):
    """A checked event dict. Raises ValueError for an unknown event, field or value."""
    schema = SCHEMA.get(event)
    if schema is None:
        raise ValueError("unknown event")
    if set(fields) != set(schema):
        raise ValueError("fields do not match the event")
    if not valid_id(sid) or not isinstance(repo, str) or not REPO.match(repo):
        raise ValueError("bad session id or repository code")
    for key, check in schema.items():
        if not check(fields[key]):
            raise ValueError("bad value for " + key)
    if event == "judge" and not valid_judge_pairs(fields):
        raise ValueError("invalid judge field pair")
    return {"ts": now().isoformat(timespec="milliseconds"), "sid": sid, "repo": repo, "event": event, **fields}


def valid_event(item):
    """True for a stored line that has exactly the fields its event allows, each with an allowed value."""
    schema = SCHEMA.get(item.get("event")) if isinstance(item, dict) else None
    if schema is None or set(item) != {"ts", "sid", "repo", "event", *schema}:
        return False
    if not (isinstance(item["ts"], str) and TS.match(item["ts"]) and valid_id(item["sid"])
            and isinstance(item["repo"], str) and REPO.match(item["repo"])):
        return False
    try:
        datetime.fromisoformat(item["ts"])  # the pattern allows 2026-13-45; a real date is needed
    except ValueError:
        return False
    return (all(check(item[key]) for key, check in schema.items())
            and (item["event"] != "judge" or valid_judge_pairs(item)))


def bump_errors(error=None):
    """Count one writer failure as one appended byte in errors.count, and keep the class name of the latest one in errors.last.

    Only when metrics are enabled; never raises. Only the exception's class name is kept, never its message.
    """
    try:
        if not enabled():
            return
        folder = ensure_dir(state_dir(), follow=True)
        fd = os.open(folder / "errors.count", os.O_WRONLY | os.O_APPEND | os.O_CREAT | NOFOLLOW, 0o600)
        try:
            os.write(fd, b"x")
        finally:
            os.close(fd)
        if error is not None and re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,60}\Z", type(error).__name__):
            atomic_write(folder / "errors.last", "%s %s\n" % (now().isoformat(timespec="seconds"), type(error).__name__))
    except Exception:
        pass


def errors_last():
    """The time and exception class of the latest writer failure, or None."""
    try:
        text = (state_dir() / "errors.last").read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text if re.match(r"^\d{4}-\d{2}-\d{2}T[\d:+]+ [A-Za-z_][A-Za-z0-9_]{0,60}\Z", text) else None


def errors_count():
    try:
        return (state_dir() / "errors.count").stat().st_size
    except OSError:
        return 0


def append(event_dict):
    folder = ensure_dir(state_dir(), follow=True)
    path = folder / ("events-%s.jsonl" % event_dict["ts"][:7])
    data = (json.dumps(event_dict, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | NOFOLLOW, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def record(event, sid, cwd, **fields):
    """Write one event. True when written. Never raises: a failure is counted and swallowed."""
    try:
        if not enabled():
            return False
        append(build_event(event, sid, repo_code(cwd), fields))
        return True
    except Exception as error:
        bump_errors(error)
        return False


def first_edit(sid):
    """True the first time it is called for a session (a marker file per session), else False."""
    if not valid_id(sid):
        raise ValueError("bad session id")
    folder = ensure_dir(ensure_dir(state_dir(), follow=True) / "markers")
    try:
        os.close(os.open(folder / sid, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600))
        return True
    except FileExistsError:
        return False


def _line_ts(line):
    try:
        item = json.loads(line)
    except ValueError:
        return None
    return item.get("ts") if isinstance(item, dict) and isinstance(item.get("ts"), str) else None


def _regular_files(folder):
    """The regular files directly in folder, never following a symlink (the folder itself must be a real folder)."""
    if folder.is_symlink() or not folder.is_dir():
        return []
    with os.scandir(folder) as entries:
        return [Path(e.path) for e in entries if e.is_file(follow_symlinks=False)]


def prune(retention_days, at=None):
    """Drop events older than the retention: whole files past it, and old lines in the file it cuts through. Drop old marker files."""
    at = at or now()
    cutoff = at - timedelta(days=retention_days)
    keep_from = cutoff.isoformat(timespec="milliseconds")
    folder = state_dir()
    for path in _regular_files(folder):
        found = EVENT_FILE.match(path.name)
        if not found:
            continue
        try:  # one damaged or oddly named file must not stop the rest
            year, month = int(found.group(1)), int(found.group(2))
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=timezone.utc)
            if end <= cutoff:
                path.unlink(missing_ok=True)
            elif start < cutoff:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                kept = [line for line in lines if (_line_ts(line) or keep_from) >= keep_from]
                if len(kept) != len(lines):
                    atomic_write(path, "".join(line + "\n" for line in kept))
        except (ValueError, OSError):
            continue
    stale = at.timestamp() - MARKER_DAYS * 86400
    for path in _regular_files(folder / "markers"):
        if path.lstat().st_mtime < stale:
            path.unlink(missing_ok=True)


def read_events():
    """(events, skipped): every well-formed event line, oldest first, and the count of lines ignored."""
    events, skipped = [], 0
    for path in sorted(state_dir().glob("events-*.jsonl")):
        if not EVENT_FILE.match(path.name):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if valid_event(item):
                events.append(item)
            else:
                skipped += 1
    return events, skipped


def purge_store():
    """Delete the recorded events, the marker files and the error record. Keeps consent.json. Returns files removed."""
    folder, removed = state_dir(), 0
    for path in [p for p in _regular_files(folder) if EVENT_FILE.match(p.name) or p.name in ("errors.count", "errors.last")] + _regular_files(folder / "markers"):
        path.unlink()
        removed += 1
    return removed
