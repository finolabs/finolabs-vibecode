#!/usr/bin/env python3
"""Opt-in, bounded usage reads. Provider output is never persisted verbatim."""

import argparse
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import hashlib
import json
import math
import os
try:
    import pwd
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
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
MIN_AGE = 15 * 60
MAX_INSTALLS = 4
# Four sequential provider limits plus a bounded parsing/publication allowance.
MARKER_AGE = MAX_INSTALLS * TIMEOUT + 30
SOURCES = {"agy": "agy-usage", "claude": "claude-usage", "codex": "codex-rate-limits"}
NAMES = {"agy": {"gemini", "argon", "claude-gpt", "other"},
         "claude": {"session", "week-all", "week-model", "other"}, "codex": {"codex"}}
LABEL = re.compile(r"[a-z0-9-]{1,20}")
HOMEBREW_PREFIX = Path("/opt/homebrew")
ADMIN_GID = 80
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
    r"([A-Z][a-z]{2}) ([0-9]{1,2}) at ([0-9]{1,2})(?::([0-9]{2}))?(am|pm) "
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
                candidate = datetime(year, MONTHS.index(month) + 1, int(day), hour, int(minute or 0), tzinfo=zone)
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
    return canonical_config()


def canonical_config():
    """Read recorded installs for display; this alone never authorizes execution."""
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


def in_homebrew(path):
    path = Path(path)
    return path == HOMEBREW_PREFIX or HOMEBREW_PREFIX in path.parents


def brew_links(path):
    """Validate the lexical Homebrew path as well as its resolved target."""
    path = Path(path)
    if not in_homebrew(path):
        raise ValueError("outside Homebrew")
    for component in [*reversed(path.parents), path]:
        if not in_homebrew(component):
            continue
        info = component.lstat()
        if info.st_uid != os.getuid():
            raise ValueError("Homebrew owner")
        if stat.S_ISLNK(info.st_mode):
            if not in_homebrew(component.resolve(strict=True)):
                raise ValueError("Homebrew symlink leaves prefix")
        elif info.st_mode & 0o002 or (info.st_mode & 0o020 and info.st_gid != ADMIN_GID):
            raise ValueError("Homebrew mode")
        if component != path and os.path.lexists(component / ".git") and component != HOMEBREW_PREFIX:
            raise ValueError("nested repository")


def path_permissions(info, path, *, directory=False):
    if in_homebrew(path) and not directory:
        return (info.st_uid == os.getuid() and not info.st_mode & 0o002
                and (not info.st_mode & 0o020 or info.st_gid == ADMIN_GID))
    return info.st_uid in ({os.getuid()} if directory else {0, os.getuid()}) and not info.st_mode & 0o022


def checked_path(value, *, directory=False):
    """No-follow component walk, with the single numeric-gid Homebrew exception."""
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute path required")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        walked = Path(path.anchor)
        for index, part in enumerate(path.parts[1:]):
            info = os.fstat(fd)
            if not path_permissions(info, walked, directory=directory and in_homebrew(walked)):
                raise ValueError("unsafe ancestor")
            try:
                os.stat(".git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                if directory or walked != HOMEBREW_PREFIX:
                    raise ValueError("repository")
            last = index == len(path.parts) - 2
            child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                            (os.O_DIRECTORY if directory or not last else 0), dir_fd=fd)
            os.close(fd)
            fd = child
            walked /= part
        info = os.fstat(fd)
        if not path_permissions(info, path, directory=directory):
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
    excluded(Path(entry["executable"]))
    if str(Path(entry["executable"]).resolve(strict=True)) != executable:
        raise ValueError("executable target changed; preview again")
    if in_homebrew(Path(entry["executable"])):
        brew_links(entry["executable"])
        if not in_homebrew(Path(executable)):
            raise ValueError("Homebrew target leaves prefix")
    excluded(Path(executable))
    first = checked_path(executable)
    interpreter = entry.get("interpreter")
    if first.startswith(b"#!"):
        words = first[2:].decode().strip().split()
        if not words or not Path(words[0]).is_absolute() or not interpreter:
            raise ValueError("recorded interpreter required")
        if in_homebrew(Path(executable)):
            brew_links(interpreter)
            if words[0] != "/usr/bin/env":
                brew_links(words[0])
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
        # Hooks never wait; synchronous readers retry brief publication contention.
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
    # Check privacy on the descriptor actually read, never on a separate stat.
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > LIMIT):
            raise ValueError("private regular file required")
        data = bytearray()
        while len(data) <= LIMIT:
            chunk = os.read(fd, min(4096, LIMIT + 1 - len(data)))
            if not chunk:
                return json.loads(data)
            data.extend(chunk)
        raise ValueError("file too large")
    finally:
        os.close(fd)


def write_json(folder, name, value):
    dr.atomic_write(folder, name, json.dumps(value, allow_nan=False, separators=(",", ":")).encode())


def read_cache(folder, repair=False):
    # Status reads raise on an unsafe, capped or unparsable file. On-demand readings
    # pass repair=True: nothing here trusts the content, cadence comes from backoff.json,
    # and the reading's atomic write replaces the file.
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
        return {}  # content that fails validation counts as no reading; the next reading replaces it


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
        saved = read_json(folder, "inflight.json")
        if (not isinstance(saved, dict) or set(saved) != {"token", "started"}
                or not isinstance(saved["token"], str)
                or not re.fullmatch(r"[0-9a-f]{48}", saved["token"])):
            return None
        age = (current - timestamp(saved["started"])).total_seconds()
        return saved if age < MARKER_AGE else None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def claim_marker(folder, current):
    # Caller holds the directory flock across check and atomic replacement.
    if marker(folder, current):
        return None
    value = {"token": os.urandom(24).hex(), "started": stamp(current)}
    write_json(folder, "inflight.json", value)
    return value["token"]


def due(configs, cache, delays, current, max_age=MIN_AGE):
    result = []
    for agent, entry in configs.items():
        for label in entry["configs"]:
            saved = cache.get(agent, {}).get(label)
            retry = delays.get(agent, {}).get(label)
            if retry and timestamp(retry["retry_after"]) > current:
                continue
            if saved and 0 <= (current - timestamp(saved["measured"])).total_seconds() < max(MIN_AGE, max_age):
                continue
            result.append((agent, label))
    return result


def environment(entry, config_path=None):
    folders = [str(Path(entry["interpreter"]).parent)] if entry.get("interpreter") else []
    folders.append(str(Path(entry.get("resolved", entry["executable"])).parent))
    env = {"HOME": str(dr.account_home()), "PATH": ":".join(dict.fromkeys([*folders, *SYSTEM_PATH.split(":")])),
           "USER": pwd.getpwuid(os.getuid()).pw_name,
           "LANG": "C.UTF-8", "FNL_METRICS": "off", "FNL_UPDATE_CHECK": "off"}
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


def command(agent, entry, label):
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
                                   env=environment(entry, folder), start_new_session=True, close_fds=True)
        try:
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            start, output, pending, initialized = time.monotonic(), bytearray(), bytearray(), False
            def send(value):
                process.stdin.write((json.dumps(value) + "\n").encode())
                process.stdin.flush()
            if agent == "codex":
                send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "fnl-quota", "version": "1"}}})
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= TIMEOUT:
                    raise TimeoutError("timeout")
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


def read_family(family, max_age_minutes=15):
    """Synchronous, opt-in reading; all reservations are local and locked."""
    configs = config()
    entry = configs.get(family)
    if entry is None:
        recorded = canonical_config().get(family, {})
        labels = recorded.get("configs", {"default": None})
        try:
            with state_folder(read_only=True) as folder:
                cache = read_cache(folder)
        except (OSError, ValueError, TypeError, KeyError):
            cache = {}
        return read_lines(family, labels, {label: "off" for label in labels}, cache)
    configs = {family: entry}
    cache, states, token = {}, {}, None
    labels = entry["configs"]
    try:
        with state_folder(create=True) as folder:
            current = now()
            cache = read_cache(folder, repair=True)
            if marker(folder, current):
                states = {label: "busy" for label in labels}
            else:
                delays = backoff(folder, configs, current)
                jobs = due(configs, cache, delays, current, max(15, max_age_minutes) * 60)
                for label in labels:
                    saved = cache.get(family, {}).get(label)
                    retry = delays.get(family, {}).get(label)
                    states[label] = ("backoff" if retry and timestamp(retry["retry_after"]) > current
                                     and retry["error"] else "fresh" if saved else "unverified")
                if jobs:
                    token = claim_marker(folder, current)
                    for agent, label in jobs:
                        delays.setdefault(agent, {})[label] = {
                            "retry_after": stamp(current + timedelta(minutes=30)), "error": "unfinished"}
                    write_json(folder, "backoff.json", delays)
        if token:
            for agent, label in jobs:
                # Recheck consent and the reservation before every invocation.
                if config().get(agent) != entry:
                    states[label] = "off"
                    continue
                with state_folder(writer=True) as folder:
                    saved = marker(folder, now())
                    if not saved or saved["token"] != token:
                        states[label] = "busy"
                        continue
                measured = now()
                groups, error, seconds = None, "", MIN_AGE
                try:
                    groups = parse(agent, command(agent, entry, label), measured)
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
                    saved = marker(folder, now())
                    if not saved or saved["token"] != token:
                        states[label] = "busy"
                        continue
                    delays = backoff(folder, configs, now())
                    if groups is not None:
                        try:
                            cache = read_cache(folder, repair=True)
                            cache.setdefault(agent, {})[label] = {
                                "measured": stamp(measured), "source": SOURCES[agent], "groups": groups}
                            write_json(folder, "quota.json", cache)
                        except (OSError, ValueError):
                            error, seconds = "execution", 1800
                    delays.setdefault(agent, {})[label] = {
                        "retry_after": stamp(now() + timedelta(seconds=seconds)), "error": error}
                    write_json(folder, "backoff.json", delays)
                    states[label] = "unverified" if error else "read"
    except BlockingIOError:
        states = {label: "busy" for label in labels}
    except (OSError, ValueError, TypeError, KeyError):
        states = {label: "unverified" for label in labels}
    finally:
        if token:
            try:
                with state_folder(writer=True) as folder:
                    saved = read_json(folder, "inflight.json")
                    if saved.get("token") == token:
                        os.unlink("inflight.json", dir_fd=folder)
            except (OSError, ValueError, TypeError, AttributeError):
                pass
    return read_lines(family, labels, states, cache)


def read_lines(family, labels, states, cache):
    lines = []
    for label in labels:
        saved = cache.get(family, {}).get(label)
        age = int((now() - timestamp(saved["measured"])).total_seconds()) if saved else None
        state = states.get(label, "unverified")
        if state == "fresh" and (age is None or age < 0 or age > 8 * 3600):
            state = "unverified"
        lines.append(f"Quota {family}/{label}: {state}; age " +
                     (f"{age}s" if age is not None else "unknown"))
    return lines


def limit_markers(folder):
    try:
        values = read_json(folder, "limits.json")
    except FileNotFoundError:
        return {}
    if not isinstance(values, dict) or values.keys() - {"claude"}:
        raise ValueError("limits")
    for value in values.values():
        timestamp(value)
    return values


def limited_until(agent, marked, cache, current):
    started = timestamp(marked)
    if started > current:
        return None
    entries = list(cache.get(agent, {}).values())
    if any(timestamp(e["measured"]) > started for e in entries):
        return None
    # Only depleted pools supply a reset; unrelated weekly pools cannot extend it.
    # Ignore percent-to-fraction round-off at exactly 10% without changing parsers.
    resets = [timestamp(g["reset_time"]) for e in entries for g in e["groups"]
              if g["remaining_fraction"] < .1
              and not math.isclose(g["remaining_fraction"], .1, rel_tol=0, abs_tol=1e-15)]
    reset = min(resets) if resets else None
    end = reset if reset and current < reset <= started + timedelta(hours=5) else started + timedelta(hours=1)
    return end if current < end <= started + timedelta(hours=5) else None


def status_lines():
    try:
        with state_folder(read_only=True) as folder:
            cache = read_cache(folder)
            limits = limit_markers(folder)
        lines = []
        for agent, marked in limits.items():
            end = limited_until(agent, marked, cache, now())
            if end:
                lines.append(f"Quota {agent}: rate-limit marker {marked}; out of quota until {stamp(end)} (advisory)")
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
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    read = sub.add_parser("read")
    read.add_argument("--family", choices=tuple(SOURCES), required=True)
    read.add_argument("--max-age-minutes", type=int, default=15)
    args = parser.parse_args()
    try:
        lines = status_lines() if args.action == "status" else read_family(args.family, args.max_age_minutes)
        print("\n".join(lines))
    except Exception:
        if args.action == "read":
            print(f"Quota {args.family}/default: unverified; age unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
