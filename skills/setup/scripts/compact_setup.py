#!/usr/bin/env python3
"""Preview and apply one documented host compaction threshold; never hook-started."""
import argparse
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

try:
    import tomllib
except ImportError:
    tomllib = None

KEYS = {"claude": "autoCompactWindow", "codex": "model_auto_compact_token_limit"}
LIMIT = 4 * 1024 * 1024


class Refusal(ValueError):
    """Only fixed, content-free messages may reach the terminal."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def content_hash(raw):
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def read_target(folder, name):
    try:
        raw = dr.read_file(folder, name, LIMIT)
    except FileNotFoundError:
        return None, 0o600
    info = os.stat(name, dir_fd=folder, follow_symlinks=False)
    return raw, stat.S_IMODE(info.st_mode)


def statements(text):
    """Yield real TOML statement offsets, ignoring strings, comments and arrays."""
    quote, depth, offset = None, 0, 0
    for line in text.splitlines(keepends=True):
        if quote is None and depth == 0 and line.strip() and not line.lstrip().startswith("#"):
            yield offset, line
        i = 0
        while i < len(line):
            char = line[i]
            if quote:
                if char == "\\" and quote[0] == '"':
                    i += 2
                    continue
                if line.startswith(quote, i):
                    i += len(quote)
                    # TOML permits one or two quotes immediately before a
                    # multiline closing delimiter; consume the whole run.
                    if len(quote) == 3:
                        while i < len(line) and line[i] == quote[0]:
                            i += 1
                    quote = None
                    continue
            elif char == "#":
                break
            elif char in "\"'":
                quote = char * 3 if line.startswith(char * 3, i) else char
                i += len(quote)
                continue
            elif char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            i += 1
        offset += len(line)


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refusal("duplicate JSON key")
        result[key] = value
    return result


def json_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise Refusal("non-finite JSON number")
    return result


def json_constant(value):
    raise Refusal("invalid JSON constant")


def fallback_keys(text):
    """Without tomllib, refuse names that cannot safely be treated as absent."""
    key = r"(?:model_auto_compact_token_limit|\"model_auto_compact_token_limit\"|'model_auto_compact_token_limit')"
    in_table = False
    for _, line in statements(text):
        if re.match(r'^\s*(?:\[{1,2}\s*)?"[^"\n]*\\', line):
            raise Refusal("escaped TOML keys require tomllib")
        if line.lstrip().startswith("["):
            in_table = True
            if re.match(r"^\s*\[{1,2}\s*" + key + r"\s*[.\]]", line):
                raise Refusal("threshold must be a single integer line")
        elif not in_table and re.match(r"^\s*" + key + r"\s*\.", line):
            raise Refusal("threshold must be a single integer line")


def read_plan(state):
    raw = dr.read_file(state, "preview.json", LIMIT)
    if stat.S_IMODE(os.stat("preview.json", dir_fd=state, follow_symlinks=False).st_mode) != 0o600:
        raise Refusal("preview must be private (0600)")
    return raw


def transform(host, raw, tokens):
    key = KEYS[host]
    if host == "claude":
        try:
            data = json.loads(raw, object_pairs_hook=json_object, parse_float=json_float, parse_constant=json_constant) if raw is not None else {}
        except (ValueError, UnicodeError):
            raise Refusal("invalid JSON") from None
        if not isinstance(data, dict):
            raise Refusal("JSON must be an object")
        old = data.get(key)
        present = key in data
        if type(old) is int and old == tokens:
            return raw, "No difference."
        if tokens is None:
            if not present:
                return raw, "No difference."
            del data[key]
        else:
            data[key] = tokens
        result = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    else:
        text = raw.decode("utf-8") if raw is not None else ""
        if tomllib is not None:
            try:
                parsed = tomllib.loads(text)
            except ValueError:
                raise Refusal("invalid TOML") from None
        else:
            fallback_keys(text)
            parsed = None
        match_line, insertion = None, len(text)
        pattern = r'''^[ \t]*(?:model_auto_compact_token_limit|"model_auto_compact_token_limit"|'model_auto_compact_token_limit')[ \t]*=[ \t]*([^#\r\n]*?)([ \t]*(?:#[^\r\n]*)?)(?:\r?\n)?$'''
        for offset, line in statements(text):
            if line.lstrip().startswith("["):
                insertion = offset
                break
            match = re.fullmatch(pattern, line)
            if match:
                if match_line is not None:
                    raise Refusal("duplicate threshold key")
                literal = match[1].strip()
                if not re.fullmatch(r"(?:[+-]?(?:0|[1-9](?:_?[0-9])*)|0x[0-9A-Fa-f](?:_?[0-9A-Fa-f])*|0o[0-7](?:_?[0-7])*|0b[01](?:_?[01])*)", literal):
                    raise Refusal("threshold must be a single integer line")
                integer = int(literal.replace("_", ""), 0 if literal.startswith(("0x", "0o", "0b")) else 10)
                match_line = (offset, line, integer, match[2])
        present = match_line is not None
        if parsed is not None and (key in parsed) != present:
            raise Refusal("threshold must be a single integer line")
        old = match_line[2] if present else None
        if (tokens is None and not present) or (present and old == tokens):
            return raw, "No difference."
        newline = "\r\n" if "\r\n" in text else "\n"
        replacement = f"{key} = {tokens}{newline}" if tokens is not None else ""
        if present:
            offset, line, _, suffix = match_line
            # A replacement retains the old line's terminator, including none.
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            replacement = f"{key} = {tokens}{suffix}{ending}" if tokens is not None else ""
            result = (text[:offset] + replacement + text[offset + len(line):]).encode()
        else:
            prefix = text[:insertion]
            separator = newline if prefix and not prefix.endswith("\n") else ""
            result = (prefix + separator + replacement + text[insertion:]).encode()
        if tomllib is not None:
            try:
                tomllib.loads(result.decode())
            except ValueError:
                raise Refusal("result is invalid TOML") from None
    old_label = str(old) if type(old) is int else "present (non-integer)" if present else "absent"
    return result, f"{key}: {old_label} -> {tokens if tokens is not None else 'removed'}"


def validate_choice(host, tokens):
    if host == "antigravity":
        raise Refusal("no documented setting; /compact only")
    if host not in KEYS:
        raise Refusal("unsupported host")
    low, high = (100000, 1000000) if host == "claude" else (1000, 10000000)
    if tokens is not None and (type(tokens) is not int or not low <= tokens <= high):
        raise Refusal(f"tokens must be an integer from {low} to {high}")


def checked_path(value, host):
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts or any(ord(c) < 32 for c in str(path))
            or path.name != ("settings.json" if host == "claude" else "config.toml")):
        raise Refusal("invalid target path")
    return path


def backup_name(folder, name):
    base = name + ".bak-" + datetime.now().strftime("%Y%m%d")
    candidate, number = base, 0
    while True:
        try:
            os.stat(candidate, dir_fd=folder, follow_symlinks=False)
        except FileNotFoundError:
            return candidate
        number += 1
        candidate = base + f"-{number}"


def notices(host):
    if host == "claude":
        for name in ("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "DISABLE_AUTO_COMPACT"):
            if name in os.environ:
                print(f"Warning: {name} is set and may override or disable this setting.")
    if host == "codex" and tomllib is None:
        print("tomllib unavailable; TOML parse check skipped.")
    print("The new value applies to sessions started afterwards; a running session is unverified.")


MANAGED = {"darwin": "/Library/Application Support/ClaudeCode/managed-settings.json",
           "linux": "/etc/claude-code/managed-settings.json"}


def managed_settings():
    """The managed settings file for this platform, read only when it is readable."""
    path = MANAGED.get(sys.platform if sys.platform != "linux2" else "linux")
    return [("managed", Path(path))] if path else []


def auto_compact_conflicts(files, environ):
    """(window configured, findings) from (label, raw JSON) pairs; reads only the compaction keys.

    Findings hold fixed text, the file's label and a variable's name, never another key or any value."""
    window, findings = False, []
    for label, raw in files:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        models = data.get("modelSettings")
        if "autoCompactWindow" in data or (isinstance(models, dict) and any(
                isinstance(settings, dict) and "autoCompactWindow" in settings for settings in models.values())):
            window = True
        if data.get("autoCompactEnabled") is False:
            findings.append(f"autoCompactEnabled is false in {label} settings")
    findings += [f"{name} is set" for name in ("DISABLE_AUTO_COMPACT", "CLAUDE_CODE_AUTO_COMPACT_WINDOW")
                 if name in environ]
    return window, findings


def read_settings(path):
    """Bytes of one settings file, or None when absent, a link, too large or unreadable."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            return None
        return os.read(fd, LIMIT + 1)[:LIMIT]
    except OSError:
        return None
    finally:
        os.close(fd)


def other_settings():
    """Project, local and managed Claude Code settings that can turn the user's window off."""
    cwd = Path(os.getcwd())
    root = next((p for p in (cwd, *cwd.parents) if os.path.lexists(p / ".git")), None)
    files = [("project", root / ".claude/settings.json"), ("local", root / ".claude/settings.local.json")] \
        if root else []
    return [(label, raw) for label, path in [*files, *managed_settings()]
            for raw in [read_settings(path)] if raw is not None]


def disabled_notice(raws):
    """Warn when the window being set would do nothing; environment variables are named by notices()."""
    _, findings = auto_compact_conflicts([*raws, *other_settings()], {})
    for finding in findings:
        print(f"Warning: {finding}, so the window shown here does nothing until auto-compaction is on.")


def target_notice(host, raw):
    # Called only after transform has validated the target JSON.
    if host == "claude" and raw is not None:
        models = json.loads(raw).get("modelSettings")
        if isinstance(models, dict) and any(isinstance(settings, dict) and "autoCompactWindow" in settings
                                            for settings in models.values()):
            print("Warning: modelSettings contains a per-model autoCompactWindow that overrides the top-level setting.")


def preview(host, folders, tokens):
    validate_choice(host, tokens)
    if host == "codex":
        if folders:
            raise Refusal("--folder is for Claude only")
        configured = Path(os.environ.get("CODEX_HOME", ""))
        folders = [configured if configured.is_absolute() else dr.account_home() / ".codex"]
    else:
        folders = folders or [dr.account_home() / ".claude"]
    if not 1 <= len(folders) <= 4:
        raise Refusal("one to four config folders required")
    root = dr.consent_root()
    if root is None:
        raise Refusal("invalid data root")
    targets, identities, displays, raws = [], set(), [], []
    for folder_path in folders:
        path = checked_path(Path(folder_path) / ("settings.json" if host == "claude" else "config.toml"), host)
        with dr.relocated_folder(path.parent) as folder:
            info = os.fstat(folder)
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise Refusal("duplicate config folder")
            identities.add(identity)
            raw, mode = read_target(folder, path.name)
            result, change = transform(host, raw, tokens)
            target_notice(host, raw)
            if raw is not None:
                raws.append(("user", raw))
            backup = backup_name(folder, path.name)
            targets.append({"path": str(path), "sha256": content_hash(raw), "mode": mode, "backup": backup})
            displays.append((path, raw is not None, change, backup, result != raw))
    plan = {"host": host, "tokens": tokens, "created": time.time(), "root": str(root), "targets": targets}
    value = digest(plan)
    with dr.data_folder("state/compact", create=True, private=True) as state:
        # An existing unsafe preview is never silently replaced.
        try:
            read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, "preview.json", json.dumps({"plan": plan, "digest": value}).encode())
    for path, exists, change, backup, changed in displays:
        print(f"Target: {path}\nExists: {'yes' if exists else 'no'}\n{change}")
        print(f"Backup: {path.parent / backup}" + (" (not needed)" if not exists or not changed else ""))
    if host == "claude":
        disabled_notice(raws)
    notices(host)
    print("Digest: " + value)


def write_target(folder, name, raw, mode):
    temporary = ".compact-" + os.urandom(12).hex()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=folder, dst_dir_fd=folder)
        os.fsync(folder)
    finally:
        try:
            os.unlink(temporary, dir_fd=folder)
        except FileNotFoundError:
            pass


def apply(value, yes):
    if not yes or not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise Refusal("clear yes and full 64-hex preview digest required")
    value = value.lower()
    with ExitStack() as stack:
        state = stack.enter_context(dr.data_folder("state/compact", private=True))
        saved = json.loads(read_plan(state))
        if (not isinstance(saved, dict) or set(saved) != {"plan", "digest"}
                or saved["digest"] != value or digest(saved["plan"]) != value):
            raise Refusal("digest mismatch; preview again")
        plan = saved["plan"]
        if not isinstance(plan, dict) or set(plan) != {"host", "tokens", "created", "root", "targets"}:
            raise Refusal("invalid plan")
        validate_choice(plan["host"], plan["tokens"])
        if plan["root"] != str(dr.consent_root()):
            raise Refusal("data root changed; preview again")
        if type(plan["created"]) not in (int, float) or not 0 <= time.time() - plan["created"] <= 3600:
            raise Refusal("preview expired; preview again")
        targets = plan["targets"]
        if not isinstance(targets, list) or not 1 <= len(targets) <= (4 if plan["host"] == "claude" else 1):
            raise Refusal("invalid targets")
        ready, identities = [], set()
        for target in targets:
            if not isinstance(target, dict) or set(target) != {"path", "sha256", "mode", "backup"}:
                raise Refusal("invalid target")
            path = checked_path(target["path"], plan["host"])
            folder = stack.enter_context(dr.relocated_folder(path.parent))
            info = os.fstat(folder)
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise Refusal("duplicate config folder")
            identities.add(identity)
            raw, mode = read_target(folder, path.name)
            if content_hash(raw) != target["sha256"] or mode != target["mode"]:
                raise Refusal("target changed; preview again")
            if not re.fullmatch(re.escape(path.name) + r"\.bak-\d{8}(?:-[1-9][0-9]*)?", target["backup"]):
                raise Refusal("invalid backup name")
            result, _ = transform(plan["host"], raw, plan["tokens"])
            if result != raw and raw is not None:
                try:
                    os.stat(target["backup"], dir_fd=folder, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise Refusal("previewed backup exists; preview again")
            ready.append((folder, path, target, raw, mode, result))
        for folder, path, target, raw, mode, result in ready:
            target_notice(plan["host"], raw)
            if result == raw:
                print("No difference.")
                continue
            current, current_mode = read_target(folder, path.name)
            if current != raw or current_mode != mode:
                raise Refusal("target changed; preview again")
            if raw is not None:
                fd = os.open(target["backup"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
                with os.fdopen(fd, "wb") as stream:
                    os.fchmod(stream.fileno(), mode)
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            write_target(folder, path.name, result, mode)
            print(f"Updated: {path}")
        os.unlink("preview.json", dir_fd=state)
        os.fsync(state)
        notices(plan["host"])


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal("invalid arguments")


def main():
    try:
        # Give the documented refusal for any Antigravity invocation.
        if any(arg == "--host=antigravity" or (arg == "--host" and i + 1 < len(sys.argv) and sys.argv[i + 1] == "antigravity") for i, arg in enumerate(sys.argv)):
            raise Refusal("no documented setting; /compact only")
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="action", required=True)
        pre = commands.add_parser("preview")
        pre.add_argument("--host", required=True, choices=("claude", "codex", "antigravity"))
        pre.add_argument("--folder", action="append", default=[])
        choice = pre.add_mutually_exclusive_group(required=True)
        choice.add_argument("--tokens", type=int)
        choice.add_argument("--off", action="store_true")
        app = commands.add_parser("apply")
        app.add_argument("--digest", required=True)
        app.add_argument("--yes", action="store_true")
        args = parser.parse_args()
        if args.action == "preview":
            preview(args.host, args.folder, args.tokens)
        else:
            apply(args.digest, args.yes)
        return 0
    except Refusal as error:
        print("Compaction setup refused: " + str(error), file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print("Compaction setup refused: unsafe, unreadable or invalid file or plan", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
