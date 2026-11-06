#!/usr/bin/env python3
"""Opt-in, bounded usage reads. Provider output is never persisted verbatim."""

import fcntl
import hashlib
import json
import math
import os
import pwd
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

LIMIT = 65536
TIMEOUT = 30
FRESH = 4 * 3600
MARKER_AGE = 300
SOURCES = {"agy": "agy-usage", "claude": "claude-usage", "codex": "codex-rate-limits"}
NAMES = {"agy": {"gemini", "argon", "claude-gpt", "other"},
         "claude": {"session", "week-all", "week-model", "other"}, "codex": {"codex"}}
LABEL = re.compile(r"[a-z0-9-]{1,20}")
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


class ShapeError(ValueError):
    pass


class PromptError(ShapeError):
    pass


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str):
        raise ShapeError("timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ShapeError("UTC required")
    return parsed


def number(value, maximum=1):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ShapeError("fraction")
    return value


def group(name, window, fraction, reset):
    if window not in {"5h", "weekly", "unknown"}:
        raise ShapeError("window")
    return {"name": name, "window": window, "remaining_fraction": number(fraction),
            "reset_time": stamp(timestamp(reset))}


def parse_agy(data, measured=None):
    groups = data["command"]["data"]["groups"]
    if data.get("status") != "SUCCESS" or not isinstance(groups, list) or not groups:
        raise ShapeError("groups")
    result = []
    names = {"Gemini Models": "gemini", "Gemini 4 Argon": "argon", "Claude and GPT models": "claude-gpt"}
    for pool in groups:
        if not isinstance(pool["name"], str) or not isinstance(pool["buckets"], list) or not pool["buckets"]:
            raise ShapeError("pool")
        for bucket in pool["buckets"]:
            if bucket["window"] not in {"5h", "weekly"}:
                raise ShapeError("window")
            result.append(group(names.get(pool["name"], "other"), bucket["window"],
                                bucket["remaining_fraction"], bucket["reset_time"]))
    return result


CLAUDE_LINE = re.compile(
    r"Current (session|week \(([^()\r\n]+)\)): ([0-9]+(?:\.[0-9]+)?)% used · resets "
    r"([A-Z][a-z]{2}) ([0-9]{1,2}) at ([0-9]{1,2}):([0-9]{2})(am|pm) "
    r"\(([A-Za-z_]+(?:/[A-Za-z0-9_+-]+)*)\)")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def parse_claude(data, measured=None):
    measured = measured or now()
    for field in ("num_turns", "total_cost_usd"):
        value = data[field]
        number(value, float("inf"))
        if value:
            raise PromptError("prompt")
    if data.get("is_error") is not False or data.get("subtype") != "success" or data.get("type") != "result":
        raise ShapeError("result")
    result = []
    for line in data["result"].splitlines():
        if not line.startswith("Current "):
            continue
        match = CLAUDE_LINE.fullmatch(line)
        if not match:
            raise ShapeError("line")
        period, family, used, month, day, hour, minute, half, zone = match.groups()
        zone = ZoneInfo(zone)
        hour = int(hour)
        if not 1 <= hour <= 12:
            raise ShapeError("hour")
        hour = hour % 12 + (12 if half == "pm" else 0)
        local = measured.astimezone(zone)
        dates = []
        for year in range(local.year, local.year + 5):
            try:
                candidate = datetime(year, MONTHS.index(month) + 1, int(day), hour, int(minute), tzinfo=zone)
                if candidate.astimezone(timezone.utc) >= measured:
                    dates.append(candidate)
            except ValueError:
                continue
        if not dates:
            raise ShapeError("date")
        name = "session" if period == "session" else "week-all" if family == "all models" else "week-model"
        result.append(group(name, "5h" if name == "session" else "weekly",
                            1 - number(float(used), 100) / 100, stamp(min(dates))))
    names = [item["name"] for item in result]
    if names.count("session") != 1 or names.count("week-all") != 1 or names.count("week-model") < 1:
        raise ShapeError("missing line")
    return result


def parse_codex(data, measured=None):
    limits = data["result"]["rateLimits"]
    if not isinstance(limits["primary"], dict):
        raise ShapeError("primary")
    result = []
    for bucket in (limits["primary"], limits.get("secondary")):
        if bucket is None:
            continue
        minutes = bucket["windowDurationMins"]
        if type(minutes) is not int or minutes <= 0:
            raise ShapeError("window")
        epoch = number(bucket["resetsAt"], 253402300799)
        result.append(group("codex", {300: "5h", 10080: "weekly"}.get(minutes, "unknown"),
                            1 - number(bucket["usedPercent"], 100) / 100,
                            stamp(datetime.fromtimestamp(epoch, timezone.utc))))
    return result


def parse(agent, raw, measured=None):
    try:
        data = json.loads(raw)
        result = {"agy": parse_agy, "claude": parse_claude, "codex": parse_codex}[agent](data, measured)
        if len(result) > 64:
            raise ShapeError("groups")
        return result
    except PromptError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        raise ShapeError("unverified") from error


def section(text):
    """Unique real heading only; examples in fenced blocks cannot opt in."""
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    parts = re.split(r"^## (.+?)\s*$", "\n".join(lines), flags=re.M)
    found = [parts[i + 1] for i in range(1, len(parts), 2) if parts[i] == "Quota probe"]
    if len(found) != 1:
        return ""
    return found[0]


def config():
    if os.environ.get("FNL_QUOTA_PROBE", "").lower() == "off":
        return {}
    try:
        text = dr.read_data("host.md").decode()
        # Preserve non-CR/LF separators while locating the section so they
        # cannot disappear before configuration values are validated.
        guarded = text.translate(str.maketrans({char: "\0" for char in "\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"}))
        if "\0" in section(guarded):
            raise ValueError("line break in quota config")
        body = section(text)
        values, folders = {}, {}
        for line in body.splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r"- ([A-Za-z ]+): (.+)", line)
            if not match:
                raise ValueError("config")
            key, value = match.groups()
            if key == "Claude config":
                label, path = value.split(": ", 1)
                if not LABEL.fullmatch(label) or label in folders:
                    raise ValueError("label")
                folders[label] = path
            elif key in values:
                raise ValueError("duplicate")
            else:
                values[key] = value
        if values.get("Quota probe") != "on":
            return {}
        datetime.strptime(values["Date"], "%Y-%m-%d")
        agents = values["Agents"].split(", ")
        if not agents or len(set(agents)) != len(agents) or set(agents) - SOURCES.keys():
            raise ValueError("agents")
        allowed = {"Quota probe", "Date", "Agents"} | {f"{kind} {a}" for a in agents for kind in ("Executable", "Resolved", "Resolved digest", "Interpreter")}
        if set(values) - allowed or ("claude" in agents and not 1 <= len(folders) <= 4) or (folders and "claude" not in agents):
            raise ValueError("config")
        if len(set(folders.values())) != len(folders):
            raise ValueError("duplicate folder")
        result = {}
        for agent in agents:
            if "Resolved " + agent not in values:
                continue  # Legacy records need a new preview and confirmation.
            resolved = values["Resolved " + agent]
            confirmed = values.get("Resolved digest " + agent, "")
            if confirmed != hashlib.sha256(resolved.encode()).hexdigest():
                continue  # Missing or changed confirmation requires a new preview.
            executable = values["Executable " + agent]
            interpreter = values.get("Interpreter " + agent)
            for path in [executable, *([interpreter] if interpreter else [])]:
                if not Path(path).is_absolute():
                    raise ValueError("absolute executable")
            result[agent] = {"executable": executable, "interpreter": interpreter,
                             "configs": folders if agent == "claude" else {"default": None}}
            result[agent]["resolved"] = values["Resolved " + agent]
        return result
    except (OSError, ValueError, KeyError, UnicodeError):
        return {}


def checked_path(value, *, directory=False):
    """No symlink or git work tree at any component; root/user-owned ancestors."""
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute path required")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(path.parts[1:]):
            info = os.fstat(fd)
            if info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022:
                raise ValueError("unsafe ancestor")
            try:
                os.stat(".git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError("repository")
            last = index == len(path.parts) - 2
            child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                            (os.O_DIRECTORY if directory or not last else 0), dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid not in ({os.getuid()} if directory else {0, os.getuid()}) or info.st_mode & 0o022:
            raise ValueError("unsafe owner or mode")
        if directory:
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("folder")
            try:
                os.stat(".git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError("repository")
            return None
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
            raise ValueError("executable")
        return os.read(fd, 512).split(b"\n", 1)[0]
    finally:
        os.close(fd)


def excluded(path):
    path = Path(path)
    roots = [Path(p).resolve() for p in ("/tmp", "/var/tmp", "/var/folders")]
    roots += [dr.account_home() / "Downloads", dr.account_home() / "tmp"]
    root = dr.consent_root()
    if root is not None:
        roots.append(root / "tmp")
    if any(path == base or base in path.parents for base in roots) or any(p.lower() == "downloads" for p in path.parts):
        raise ValueError("temporary or downloads path")


def has_line_break(value):
    return any(char in "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029" for char in value)


def checked_executable(agent, entry):
    if agent not in SOURCES or Path(entry["executable"]).name != agent:
        raise ValueError("executable missing or wrong name")
    executable = entry.get("resolved")
    if not executable:
        raise ValueError("missing resolved target; preview again")
    if str(Path(entry["executable"]).resolve(strict=True)) != executable:
        raise ValueError("executable target changed; preview again")
    excluded(Path(executable))
    first = checked_path(executable)
    interpreter = entry.get("interpreter")
    if first.startswith(b"#!"):
        words = first[2:].decode().strip().split()
        if not words or not Path(words[0]).is_absolute() or not interpreter:
            raise ValueError("recorded interpreter required")
        excluded(Path(interpreter))
        checked_path(interpreter)
        if words[0] == "/usr/bin/env":
            # No env options, assignments, or extra interpreter arguments.
            if len(words) != 2 or not re.fullmatch(r"[A-Za-z0-9._+-]+", words[1]) or Path(interpreter).name != words[1]:
                raise ValueError("env interpreter")
        elif len(words) != 1 or str(Path(words[0]).resolve(strict=True)) != interpreter:
            raise ValueError("interpreter changed")
        return [interpreter, executable]
    if interpreter:
        raise ValueError("unexpected interpreter")
    return [executable]


def validate_configs(folders):
    if not 1 <= len(folders) <= 4 or len(set(folders.values())) != len(folders):
        raise ValueError("config folders")
    for label, path in folders.items():
        if has_line_break(label) or has_line_break(path):
            raise ValueError("newline or carriage return in quota label or path")
        if not LABEL.fullmatch(label):
            raise ValueError("label")
        checked_path(path, directory=True)


@contextmanager
def state_folder(*, create=False, writer=False, read_only=False):
    with dr.data_folder("state/quota", create=create, private=True) as folder:
        # Cache files are atomically replaced; status can read a complete old or
        # new snapshot without contending with a hook's exclusive writer lock.
        if read_only:
            yield folder
            return
        # Hooks never wait. A just-spawned worker can briefly contend with its
        # parent publishing the reservation, as in the auto-gate writer.
        for attempt in range(3 if writer else 1):
            try:
                fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not writer or attempt == 2:
                    raise
                time.sleep(0.05)
        yield folder


def read_json(folder, name):
    # Trust-bearing quota files must be private, not merely non-writable.
    info = os.stat(name, dir_fd=folder, follow_symlinks=False)
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("private file required")
    return json.loads(dr.read_file(folder, name, LIMIT))


def write_json(folder, name, value):
    dr.atomic_write(folder, name, json.dumps(value, allow_nan=False, separators=(",", ":")).encode())


def read_cache(folder, repair=False):
    # Status reads raise on an unsafe, capped or unparsable file. Spawning and the worker
    # pass repair=True: nothing here trusts the content, cadence comes from backoff.json,
    # and the worker's atomic write replaces the file.
    try:
        data = read_json(folder, "quota.json")
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, OverflowError):
        if repair:
            return {}
        raise
    try:
        if not isinstance(data, dict) or data.keys() - SOURCES.keys():
            raise ValueError("cache")
        for agent, labels in data.items():
            if not isinstance(labels, dict) or not 1 <= len(labels) <= (4 if agent == "claude" else 1):
                raise ValueError("labels")
            for label, entry in labels.items():
                if not LABEL.fullmatch(label) or (agent != "claude" and label != "default"):
                    raise ValueError("label")
                if set(entry) != {"measured", "source", "groups"} or entry["source"] != SOURCES[agent]:
                    raise ValueError("entry")
                timestamp(entry["measured"])
                if not isinstance(entry["groups"], list) or not 1 <= len(entry["groups"]) <= 64:
                    raise ValueError("groups")
                for item in entry["groups"]:
                    if set(item) != {"name", "window", "remaining_fraction", "reset_time"} or item["name"] not in NAMES[agent]:
                        raise ValueError("group")
                    group(item["name"], item["window"], item["remaining_fraction"], item["reset_time"])
        return data
    except (ValueError, TypeError, KeyError, AttributeError):
        return {}  # content that fails validation counts as no reading; the worker replaces it


def backoff(folder, configs, current):
    try:
        data = read_json(folder, "backoff.json")
        if not isinstance(data, dict) or data.keys() - SOURCES.keys():
            raise ValueError("backoff")
        for agent, labels in data.items():
            if not isinstance(labels, dict) or len(labels) > 4:
                raise ValueError("labels")
            for label, entry in labels.items():
                if not LABEL.fullmatch(label) or set(entry) != {"retry_after", "error"}:
                    raise ValueError("entry")
                timestamp(entry["retry_after"])
                if entry["error"] not in {"", "unfinished", "unverified", "prompt", "timeout", "output-limit", "execution"}:
                    raise ValueError("error")
        return data
    except (OSError, ValueError, TypeError, KeyError):
        # A brand-new probe has no failed attempt to back off from. Missing
        # backoff beside an existing cache, or corrupt backoff, still waits.
        # Persist that wait, so repeated hooks never move the deadline forward.
        try:
            modified = os.stat("backoff.json", dir_fd=folder, follow_symlinks=False).st_mtime
        except FileNotFoundError:
            try:
                os.stat("quota.json", dir_fd=folder, follow_symlinks=False)
            except FileNotFoundError:
                return {}
            modified = os.fstat(folder).st_mtime
        deadline = stamp(datetime.fromtimestamp(modified, timezone.utc) + timedelta(minutes=30))
        data = {a: {label: {"retry_after": deadline, "error": "unfinished"} for label in e["configs"]}
                for a, e in configs.items()}
        write_json(folder, "backoff.json", data)
        return data


def marker(folder, current):
    try:
        saved = read_json(folder, "worker.json")
        if (set(saved) != {"nonce", "heartbeat"} or not isinstance(saved["nonce"], str)
                or not re.fullmatch(r"[0-9a-f]{48}", saved["nonce"])):
            return None
        age = (current - timestamp(saved["heartbeat"])).total_seconds()
        return saved if 0 <= age < MARKER_AGE else None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def worker_guard():
    nonce = os.environ.get("FNL_QUOTA_WORKER", "")
    if not re.fullmatch(r"[0-9a-f]{48}", nonce):
        return False
    try:
        # A reader must not contend with a heartbeat writer and miss its guard.
        with dr.data_folder("state/quota", private=True) as folder:
            saved = marker(folder, now())
            return bool(saved and saved["nonce"] == nonce)
    except (OSError, ValueError):
        return False


def claim_marker(folder, current):
    if marker(folder, current):
        return None
    value = {"nonce": os.urandom(24).hex(), "heartbeat": stamp(current)}
    try:
        fd = os.open("worker.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
    except FileExistsError:
        # Caller holds flock; re-read before the atomic stale replacement.
        if marker(folder, current):
            return None
        write_json(folder, "worker.json", value)
    else:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
    return value["nonce"]


def heartbeat(nonce):
    with state_folder(writer=True) as folder:
        saved = marker(folder, now())
        if not saved or saved["nonce"] != nonce:
            raise ValueError("worker retired")
        write_json(folder, "worker.json", {"nonce": nonce, "heartbeat": stamp(now())})


def due(configs, cache, delays, current):
    result = []
    for agent, entry in configs.items():
        for label in entry["configs"]:
            saved = cache.get(agent, {}).get(label)
            retry = delays.get(agent, {}).get(label)
            if retry and timestamp(retry["retry_after"]) > current:
                continue
            if saved and 0 <= (current - timestamp(saved["measured"])).total_seconds() < FRESH:
                continue
            result.append((agent, label))
    return result


def environment(entry, nonce, config_path=None):
    folders = [str(Path(entry["interpreter"]).parent)] if entry.get("interpreter") else []
    folders.append(str(Path(entry.get("resolved", entry["executable"])).parent))
    env = {"HOME": str(dr.account_home()), "PATH": ":".join(dict.fromkeys([*folders, *SYSTEM_PATH.split(":")])),
           "USER": pwd.getpwuid(os.getuid()).pw_name,
           "LANG": "C.UTF-8", "FNL_QUOTA_WORKER": nonce, "FNL_METRICS": "off"}
    if config_path is not None:
        env["CLAUDE_CONFIG_DIR"] = config_path
    return env


@contextmanager
def working_folder():
    name = "quota-" + os.urandom(16).hex()
    with dr.data_folder("tmp", create=True, private=True) as parent:
        os.mkdir(name, 0o700, dir_fd=parent)
        path = dr.consent_root() / "tmp" / name
        try:
            yield path
        finally:
            shutil.rmtree(name, dir_fd=parent)


def command(agent, entry, label, nonce):
    argv = checked_executable(agent, entry)
    folder = None
    if agent == "claude":
        validate_configs(entry["configs"])
        folder = entry["configs"][label]
        if os.path.samefile(folder, dr.account_home() / ".claude"):
            folder = None
    argv += ["app-server"] if agent == "codex" else ["-p", "/usage", "--output-format", "json"]
    with working_folder() as cwd:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE if agent == "codex" else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd,
                                   env=environment(entry, nonce, folder), start_new_session=True, close_fds=True)
        try:
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            start, beat, output, pending, initialized = time.monotonic(), time.monotonic(), bytearray(), bytearray(), False
            def send(value):
                process.stdin.write((json.dumps(value) + "\n").encode())
                process.stdin.flush()
            if agent == "codex":
                send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "fnl-quota", "version": "1"}}})
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= TIMEOUT:
                    raise TimeoutError("timeout")
                if time.monotonic() - beat >= 30:
                    heartbeat(nonce)
                    beat = time.monotonic()
                for key, _ in selector.select(min(0.1, TIMEOUT - elapsed)):
                    chunk = os.read(key.fd, min(4096, LIMIT + 1 - len(output)))
                    if not chunk:
                        if agent == "codex":
                            raise OSError("missing reply")
                        if process.wait(timeout=max(0.001, TIMEOUT - (time.monotonic() - start))) != 0:
                            raise OSError("execution")
                        return bytes(output)
                    output.extend(chunk)
                    if len(output) > LIMIT:
                        raise OverflowError("output-limit")
                    if agent != "codex":
                        continue
                    pending.extend(chunk)
                    while b"\n" in pending:
                        line, _, pending = pending.partition(b"\n")
                        try:
                            reply = json.loads(line)
                        except (ValueError, UnicodeError) as error:
                            raise ShapeError("reply") from error
                        if not isinstance(reply, dict) or "method" in reply:
                            continue  # never answer a server request
                        if type(reply.get("id")) is not int:
                            continue
                        if reply["id"] == 1 and not initialized:
                            if "result" not in reply or "error" in reply:
                                raise ShapeError("initialize")
                            send({"method": "initialized", "params": {}})
                            send({"id": 2, "method": "account/rateLimits/read", "params": {}})
                            initialized = True
                        elif reply["id"] == 2 and initialized:
                            return bytes(line)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            process.wait()
            process.stdout.close()
            if process.stdin:
                process.stdin.close()
            if "selector" in locals():
                selector.close()


def trigger():
    """Reserve backoff before spawn; return immediately, even on contention."""
    try:
        configs = config()
        if not configs or worker_guard():
            return False
        current = now()
        with state_folder(create=True) as folder:
            delays = backoff(folder, configs, current)
            jobs = due(configs, read_cache(folder, repair=True), delays, current)
            if not jobs or marker(folder, current):
                return False
            for agent, label in jobs:
                delays.setdefault(agent, {})[label] = {"retry_after": stamp(current + timedelta(minutes=30)), "error": "unfinished"}
            write_json(folder, "backoff.json", delays)
            # The worker claims its marker under this same lock. Backoff reserves
            # the handoff while it starts, including when it dies before claiming.
            subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--worker",
                              json.dumps(jobs, separators=(",", ":"))], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                             start_new_session=True, cwd=str(Path(__file__).resolve().parent),
                             env={"HOME": str(dr.account_home()), "PATH": SYSTEM_PATH, "LANG": "C.UTF-8"})
        return True
    except Exception:
        return False


def worker(jobs):
    configs = config()
    if not configs or not isinstance(jobs, list) or len(jobs) > 6:
        return
    valid = {(a, label) for a, entry in configs.items() for label in entry["configs"]}
    if any(not isinstance(job, list) or len(job) != 2 or tuple(job) not in valid for job in jobs):
        return
    with state_folder(create=True, writer=True) as folder:
        nonce = claim_marker(folder, now())
    if not nonce:
        return
    try:
        for agent, label in jobs:
            # Re-read consent before each provider invocation.
            current_configs = config()
            if current_configs.get(agent) != configs[agent]:
                continue
            heartbeat(nonce)
            measured = now()
            with state_folder(writer=True) as folder:
                delays = backoff(folder, configs, measured)
                delays.setdefault(agent, {})[label] = {"retry_after": stamp(measured + timedelta(minutes=30)), "error": "unfinished"}
                write_json(folder, "backoff.json", delays)
            groups, error, seconds = None, "", FRESH
            try:
                groups = parse(agent, command(agent, configs[agent], label, nonce), measured)
            except PromptError:
                error, seconds = "prompt", 7 * 86400
            except ShapeError:
                error, seconds = "unverified", 86400
            except (TimeoutError, subprocess.TimeoutExpired):
                error, seconds = "timeout", 1800
            except OverflowError:
                error, seconds = "output-limit", 1800
            except (OSError, ValueError, UnicodeError):
                error, seconds = "execution", 1800
            with state_folder(writer=True) as folder:
                delays = backoff(folder, configs, now())
                if groups is not None:
                    try:
                        cache = read_cache(folder, repair=True)
                        cache.setdefault(agent, {})[label] = {"measured": stamp(measured), "source": SOURCES[agent], "groups": groups}
                        write_json(folder, "quota.json", cache)
                    except (OSError, ValueError):
                        error, seconds = "execution", 1800
                delays.setdefault(agent, {})[label] = {"retry_after": stamp(now() + timedelta(seconds=seconds)), "error": error}
                write_json(folder, "backoff.json", delays)
    finally:
        with state_folder(writer=True) as folder:
            saved = marker(folder, now())
            if saved and saved["nonce"] == nonce:
                os.unlink("worker.json", dir_fd=folder)


def status_lines():
    try:
        with state_folder(read_only=True) as folder:
            cache = read_cache(folder)
        lines = []
        for agent, labels in cache.items():
            for label, entry in labels.items():
                age = (now() - timestamp(entry["measured"])).total_seconds()
                pools = "; ".join(f"{g['name']} {g['window']}: {g['remaining_fraction']:.0%} remaining, resets {g['reset_time']}"
                                  for g in entry["groups"])
                lines.append(f"Quota {agent}/{label}: measured {entry['measured']}; {pools}" +
                             (" (unverified: older than 8 hours)" if age > 8 * 3600 or age < 0 else ""))
        return lines or ["Quota: unverified (no reading)."]
    except (OSError, ValueError, TypeError, KeyError):
        return ["Quota: unverified (no reading)."]


def main():
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--worker":
            worker(json.loads(sys.argv[2]))
        elif sys.argv[1:] == ["status"]:
            print("\n".join(status_lines()))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
