#!/usr/bin/env python3
"""Store context counts only; never read a transcript.

`record` stores status-line counts and runs no command. `probe`, run only by the
coordinator or the user, runs the user's own `claude` or `codex` once, as the
context probe exception in the repository rules allows.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
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
HOSTS = ("claude", "antigravity", "codex")
RECORD_HOSTS = ("claude", "antigravity")
PROBE_HOSTS = ("claude", "codex")
PROBE_TIMEOUT = 30
PROBE_LIMIT = 64 * 1024
NO_PROBE = "Context probe unavailable: off, unconfirmed program, refused thread state or no reading."
# Claude Code session ids and Codex thread ids are UUIDs; nothing else is passed to a program.
SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
AMOUNT = r"([0-9]{1,9}(?:\.[0-9]{1,3})?)([kKmM]?)"
TOKENS = re.compile(r"Tokens: " + AMOUNT + " / " + AMOUNT + r"(?![0-9A-Za-z.])")
INITIALIZE = {"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "fnl-context", "version": "1"}}}


def filename(session, host="claude"):
    if host not in HOSTS or not isinstance(session, str) or not session or len(session) > 4096:
        raise ValueError("invalid session")
    if host != "claude":
        session = host + ":" + session
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
    return store(name, used, window, version, host)


def store(name, used, window, version, host):
    """The one snapshot writer: fixed fields, a private atomic file and bounded retention."""
    if not counts(used, window) or host not in HOSTS:
        raise ValueError("invalid counts")
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


class Refused(ValueError):
    pass


def amount(number, unit):
    return int(Decimal(number) * {"": 1, "k": 1000, "m": 1000000}[unit.lower()])


def claude_counts(raw):
    """Only the `Tokens: <used> / <window>` line of a turnless, successful `/context` result."""
    data = load(raw)
    if (not isinstance(data, dict) or data.get("type") != "result" or data.get("subtype") != "success"
            or data.get("is_error") is not False or type(data.get("num_turns")) is not int or data["num_turns"] != 0
            or data.get("total_cost_usd", 0) not in (0, 0.0) or type(data.get("total_cost_usd", 0)) not in (int, float)
            or not isinstance(data.get("result"), str)):
        raise Refused("result")
    found = [match for line in data["result"].splitlines() for match in [TOKENS.search(line)] if match]
    if len(found) != 1:
        raise Refused("tokens")
    used, used_unit, window, window_unit = found[0].groups()
    return amount(used, used_unit), amount(window, window_unit)


def codex_step(message, session, state, send):
    """Advance the fixed app-server exchange; return counts once, never answer a server request."""
    if not isinstance(message, dict):
        raise Refused("message")
    if "method" in message:
        params = message.get("params")
        if ("id" not in message and message["method"] == "thread/tokenUsage/updated" and state["resumed"]
                and isinstance(params, dict) and params.get("threadId") == session):
            usage = params.get("tokenUsage")
            last = usage.get("last") if isinstance(usage, dict) else None
            if not isinstance(last, dict):
                raise Refused("usage")
            return last.get("totalTokens"), usage.get("modelContextWindow")
        return None  # other notifications and every server request are ignored
    ident = message.get("id")
    if type(ident) is not int or ident not in (1, 2, 3, 4) or "error" in message or "result" not in message:
        raise Refused("reply")
    result = message["result"]
    if ident == 1 and not state["initialized"]:
        state["initialized"] = True
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "thread/read", "params": {"threadId": session}})
        send({"id": 3, "method": "thread/goal/get", "params": {"threadId": session}})
    elif ident == 2 and state["initialized"] and "thread" not in state:
        thread = result.get("thread") if isinstance(result, dict) else None
        status = thread.get("status") if isinstance(thread, dict) else None
        if (not isinstance(status, dict) or thread.get("id") != session or thread.get("archived", False) is not False
                or status.get("type") not in ("idle", "notLoaded")):
            raise Refused("thread state")
        state["thread"] = True
    elif ident == 3 and state["initialized"] and "goal" not in state:
        if not isinstance(result, dict) or "goal" not in result or result["goal"] is not None:
            raise Refused("goal")
        state["goal"] = True
    elif ident == 4 and state["resumed"]:
        pass
    else:
        raise Refused("order")
    if state.get("thread") and state.get("goal") and not state["resumed"]:
        state["resumed"] = True
        send({"id": 4, "method": "thread/resume", "params": {"threadId": session}})
    return None


def run_program(qp, argv, entry, folder, cwd, session=None):
    """Fixed argv, the quota probe's allowlisted environment, no shell, a group-killing time limit and an output cap."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if session else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd,
                               env=qp.environment(entry, folder),
                               start_new_session=True, close_fds=True)
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        start, output, pending = time.monotonic(), bytearray(), bytearray()
        state = {"initialized": False, "resumed": False}

        def send(value):
            process.stdin.write((json.dumps(value) + "\n").encode())
            process.stdin.flush()
        if session:
            send(INITIALIZE)
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= PROBE_TIMEOUT:
                raise TimeoutError("timeout")
            for key, _ in selector.select(min(0.1, PROBE_TIMEOUT - elapsed)):
                chunk = os.read(key.fd, min(4096, PROBE_LIMIT + 1 - len(output)))
                if not chunk:
                    if session:
                        raise OSError("missing reply")
                    if process.wait(timeout=max(0.001, PROBE_TIMEOUT - (time.monotonic() - start))) != 0:
                        raise OSError("execution")
                    return claude_counts(bytes(output))
                output.extend(chunk)
                if len(output) > PROBE_LIMIT:
                    raise OverflowError("output limit")
                if not session:
                    continue
                pending.extend(chunk)
                while b"\n" in pending:
                    line, _, pending = pending.partition(b"\n")
                    reading = codex_step(load(line), session, state, send)
                    if reading is not None:
                        return reading
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        process.wait()
        selector.close()
        process.stdout.close()
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass


def probe(host, session, label=None):
    """Run the confirmed program once and store its counts; None on any refusal or failure."""
    try:
        if (os.environ.get("FNL_CONTEXT_PROBE", "").lower() == "off" or host not in PROBE_HOSTS
                or not isinstance(session, str) or not SESSION.fullmatch(session)
                or (label is not None and host != "claude")):
            return None
        import quota_probe as qp  # the quota probe's confirmed executables and execution rules
        entry = qp.canonical_config().get(host)
        if not entry:
            return None
        argv = qp.checked_executable(host, entry)
        folder = None
        if host == "claude":
            qp.validate_configs(entry["configs"])
            if label is None and len(entry["configs"]) == 1:
                label = next(iter(entry["configs"]))
            if label not in entry["configs"]:
                return None
            folder = entry["configs"][label]
            if os.path.samefile(folder, dr.account_home() / ".claude"):
                folder = None
            argv += ["-p", "/context", "--resume", session, "--fork-session", "--no-session-persistence",
                     "--output-format", "json"]
        else:
            argv += ["app-server"]
        with qp.working_folder() as cwd:
            used, window = run_program(qp, argv, entry, folder, cwd, session if host == "codex" else None)
        store(filename(session, host), used, window, "unknown", host)
        return read(session, host=host)
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
    probing = sys.argv[1:2] == ["probe"]
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="action", required=True)
        writer = commands.add_parser("record")
        writer.add_argument("--line", action="store_true")
        writer.add_argument("--host", choices=RECORD_HOSTS, default="claude")
        prober = commands.add_parser("probe")
        prober.add_argument("--host", choices=PROBE_HOSTS, required=True)
        prober.add_argument("--session", required=True)
        prober.add_argument("--config")
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
        if args.action == "probe":
            result = probe(args.host, args.session, args.config)
            if result is None:
                raise ValueError("unavailable")
            emit(json.dumps(result) + "\n")
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
        print(NO_PROBE if probing else NO_READING, file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
