#!/usr/bin/env python3
"""Preview and apply one documented host compaction threshold; never hook-started."""
import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
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
MODEL = re.compile(r"[a-z0-9][a-z0-9.\[\]-]{0,63}")
LIMIT = 4 * 1024 * 1024
INDEX_LIMIT = 64 * 1024 * 1024
LOCAL = ".claude/settings.local.json"


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


def model_overrides(data):
    """Names of the `modelSettings` entries that carry their own `autoCompactWindow`."""
    models = data.get("modelSettings") if isinstance(data, dict) else None
    if not isinstance(models, dict):
        return []
    return [name for name, settings in models.items() if isinstance(settings, dict) and "autoCompactWindow" in settings]


def transform_model(data, raw, key, tokens, model):
    """Set or remove `modelSettings.<model>.<key>`, creating the entry when absent and removing an entry left empty."""
    models = data.get("modelSettings")
    if "modelSettings" in data and not isinstance(models, dict):
        raise Refusal("modelSettings must be an object")
    entry = models.get(model) if models is not None else None
    if models is not None and model in models and not isinstance(entry, dict):
        raise Refusal("the model's settings must be an object")
    present = entry is not None and key in entry
    old = entry.get(key) if present else None
    if (type(old) is int and old == tokens) or (tokens is None and not present):
        return raw, "No difference."
    if tokens is None:
        del entry[key]
        if not entry:
            del models[model]
    else:
        data.setdefault("modelSettings", {}).setdefault(model, {})[key] = tokens
    result = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    old_label = str(old) if type(old) is int else "present (non-integer)" if present else "absent"
    return result, f"modelSettings.{model}.{key}: {old_label} -> {tokens if tokens is not None else 'removed'}"


def transform(host, raw, tokens, clear_models=False, model=None):
    key = KEYS[host]
    if host == "claude":
        try:
            data = json.loads(raw, object_pairs_hook=json_object, parse_float=json_float, parse_constant=json_constant) if raw is not None else {}
        except (ValueError, UnicodeError):
            raise Refusal("invalid JSON") from None
        if not isinstance(data, dict):
            raise Refusal("JSON must be an object")
        if model is not None:
            return transform_model(data, raw, key, tokens, model)
        old = data.get(key)
        present = key in data
        cleared = model_overrides(data) if clear_models else []
        same = (type(old) is int and old == tokens) or (tokens is None and not present)
        if same and not cleared:
            return raw, "No difference."
        if not same:
            if tokens is None:
                del data[key]
            else:
                data[key] = tokens
        for name in cleared:
            del data["modelSettings"][name]["autoCompactWindow"]
        result = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
        old_label = str(old) if type(old) is int else "present (non-integer)" if present else "absent"
        change = f"{key}: {old_label} -> {tokens if tokens is not None else 'removed'}" if not same else f"{key}: unchanged"
        if cleared:
            change += f"\nPer-model autoCompactWindow: removed from {len(cleared)} model setting(s)"
        return result, change
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


def validate_choice(host, tokens, clear_models=False, model=None):
    if type(clear_models) is not bool or (clear_models and host != "claude"):
        raise Refusal("--clear-model-overrides is for Claude only")
    if model is not None:
        if host != "claude":
            raise Refusal("--model is for Claude only")
        if not isinstance(model, str) or not MODEL.fullmatch(model):
            raise Refusal("--model must be a model id of lowercase letters, digits, dots, dashes and brackets")
        if clear_models:
            raise Refusal("--model and --clear-model-overrides are exclusive")
    if host == "antigravity":
        raise Refusal("no documented setting; /compact only")
    if host not in KEYS:
        raise Refusal("unsupported host")
    low, high = (100000, 1000000) if host == "claude" else (1000, 10000000)
    if tokens is not None and (type(tokens) is not int or not low <= tokens <= high):
        raise Refusal(f"tokens must be an integer from {low} to {high}")


def checked_path(value, host, scope="user"):
    path = Path(value)
    name = "settings.json" if host == "claude" else "config.toml"
    if scope == "project":
        name = "settings.local.json" if host == "claude" else None
    if (not path.is_absolute() or ".." in path.parts or any(ord(c) < 32 for c in str(path))
            or path.name != name or (scope == "project" and path.parent.name != ".claude")):
        raise Refusal("invalid target path")
    return path


def repository_root(value):
    """The checkout root `value` names exactly, and its own Git folder; no Git process runs."""
    import git_metadata
    root = Path(value)
    if not root.is_absolute() or ".." in root.parts or any(ord(c) < 32 for c in str(root)):
        raise Refusal("--project needs an absolute repository root")
    try:
        found, git, _ = git_metadata.checkout_dirs(root)
    except git_metadata.NoCheckout:
        raise Refusal("--project must be a git repository root") from None
    if Path(found) != root:
        raise Refusal("--project must be a git repository root")
    return root, Path(git)


def local_tracked(git):
    """True when the checkout's own index lists the local settings file; no index means False."""
    import afk_overlay
    import git_metadata
    index = git / "index"
    try:
        os.stat(index, follow_symlinks=False)
    except FileNotFoundError:
        return False
    try:
        paths = afk_overlay.index_paths(git_metadata.bounded(index, INDEX_LIMIT))
    except (ValueError, IndexError, struct.error):
        raise Refusal("the Git index cannot be read, so the local file cannot be shown to be untracked") from None
    # Any letter case: a case-insensitive file system maps it to the same file.
    return LOCAL.casefold() in {path.decode("utf-8", "replace").casefold() for path in paths}


@contextmanager
def project_folder(root, *, create=False):
    """The `.claude` folder of a checked repository root, no-follow and owner-checked; None when it is absent.

    Only an apply that writes creates it (mode 0700)."""
    import git_metadata
    root, git = repository_root(root)
    if local_tracked(git):
        raise Refusal("the local settings file is tracked by Git; it would not stay on this machine")
    with git_metadata.opened(root, directory=True) as repo:
        if create:
            try:
                os.mkdir(".claude", 0o700, dir_fd=repo)
            except FileExistsError:
                pass
        try:
            fd = os.open(".claude", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=repo)
        except FileNotFoundError:
            yield None
            return
        try:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise Refusal("unsafe .claude folder")
            yield fd
        finally:
            os.close(fd)


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


def other_settings(project=None, skip_local=False):
    """Project, local and managed Claude Code settings that can turn the window off: those of `project` when given,
    else of the repository holding the working folder."""
    cwd = Path(os.getcwd())
    root = Path(project) if project else next((p for p in (cwd, *cwd.parents) if os.path.lexists(p / ".git")), None)
    files = [("project", root / ".claude/settings.json")] + ([] if skip_local else [("local", root / LOCAL)]) \
        if root else []
    return [(label, raw) for label, path in [*files, *managed_settings()]
            for raw in [read_settings(path)] if raw is not None]


def disabled_notice(raws, project=None):
    """Warn when the window being set would do nothing; environment variables are named by notices()."""
    others = other_settings(project, skip_local=project is not None)
    _, findings = auto_compact_conflicts([*raws, *others], {})
    for finding in dict.fromkeys(findings):
        print(f"Warning: {finding}, so the window shown here does nothing until auto-compaction is on.")


def target_notice(host, raw, clear_models=False, model=None):
    # Called only after transform has validated the target JSON. Names and values stay unprinted:
    # a non-integer value may hold any text.
    if host == "claude" and raw is not None and not clear_models:
        overrides = model_overrides(json.loads(raw))
        if model is not None:
            others = len([name for name in overrides if name != model])
            if others:
                print(f"Per-model autoCompactWindow: {others} other model setting(s) keep their own value.")
            return
        count = len(overrides)
        if count:
            print("Warning: modelSettings contains a per-model autoCompactWindow that overrides the top-level setting.")
            print(f"Per-model autoCompactWindow: {count} model setting(s); preview again with "
                  "--clear-model-overrides to remove them in this same write.")


def preview(host, folders, tokens, project=None, clear_models=False, model=None):
    validate_choice(host, tokens, clear_models, model)
    if project is not None:
        if host != "claude":
            raise Refusal("--project is for Claude only")
        if folders:
            raise Refusal("--project and --folder are exclusive")
        return preview_project(project, tokens, clear_models, model)
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
            result, change = transform(host, raw, tokens, clear_models, model)
            target_notice(host, raw, clear_models, model)
            if raw is not None:
                raws.append(("user", raw))
            backup = backup_name(folder, path.name)
            targets.append({"path": str(path), "sha256": content_hash(raw), "mode": mode, "backup": backup})
            displays.append((path, raw is not None, change, backup, result != raw))
    value = store_plan(host, tokens, root, targets, "user", clear_models, model)
    for path, exists, change, backup, changed in displays:
        print(f"Target: {path}\nExists: {'yes' if exists else 'no'}\n{change}")
        print(f"Backup: {path.parent / backup}" + (" (not needed)" if not exists or not changed else ""))
    if host == "claude":
        disabled_notice(raws)
    notices(host)
    print("Digest: " + value)


def store_plan(host, tokens, root, targets, scope, clear_models=False, model=None):
    plan = {"host": host, "tokens": tokens, "created": time.time(), "root": str(root), "targets": targets,
            "scope": scope, "clear_models": clear_models, "model": model}
    value = digest(plan)
    with dr.data_folder("state/compact", create=True, private=True) as state:
        # An existing unsafe preview is never silently replaced.
        try:
            read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, "preview.json", json.dumps({"plan": plan, "digest": value}).encode())
    return value


def preview_project(project, tokens, clear_models=False, model=None):
    """One repository's untracked `.claude/settings.local.json`: this checkout on this machine only."""
    root = dr.consent_root()
    if root is None:
        raise Refusal("invalid data root")
    path = checked_path(Path(project) / LOCAL, "claude", "project")
    with project_folder(project) as folder:
        raw, mode = read_target(folder, path.name) if folder is not None else (None, 0o600)
        result, change = transform("claude", raw, tokens, clear_models, model)
        target_notice("claude", raw, clear_models, model)
        backup = backup_name(folder, path.name) if folder is not None else path.name + ".bak-" + datetime.now().strftime("%Y%m%d")
    targets = [{"path": str(path), "sha256": content_hash(raw), "mode": mode, "backup": backup}]
    value = store_plan("claude", tokens, root, targets, "project", clear_models, model)
    print(f"Target: {path}\nScope: this repository on this machine (untracked local settings)")
    print(f"Exists: {'yes' if raw is not None else 'no'}" + ("" if folder is not None else " (.claude folder will be created)"))
    print(change)
    print(f"Backup: {path.parent / backup}" + (" (not needed)" if raw is None or result == raw else ""))
    print("Local settings override the user-scope window in this repository; managed settings still win.")
    print("If git status lists the file, add it to .git/info/exclude; setup does not change Git files.")
    disabled_notice([("local", raw)] if raw is not None else [], project)
    notices("claude")
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
        if not isinstance(plan, dict) or set(plan) != {"host", "tokens", "created", "root", "targets", "scope",
                                                       "clear_models", "model"}:
            raise Refusal("invalid plan")
        validate_choice(plan["host"], plan["tokens"], plan["clear_models"], plan["model"])
        scope = plan["scope"]
        if scope not in ("user", "project") or (scope == "project" and plan["host"] != "claude"):
            raise Refusal("invalid plan")
        if plan["root"] != str(dr.consent_root()):
            raise Refusal("data root changed; preview again")
        if type(plan["created"]) not in (int, float) or not 0 <= time.time() - plan["created"] <= 3600:
            raise Refusal("preview expired; preview again")
        targets = plan["targets"]
        if not isinstance(targets, list) or not 1 <= len(targets) <= (4 if plan["host"] == "claude" and scope == "user" else 1):
            raise Refusal("invalid targets")
        ready, identities = [], set()
        for target in targets:
            if not isinstance(target, dict) or set(target) != {"path", "sha256", "mode", "backup"}:
                raise Refusal("invalid target")
            path = checked_path(target["path"], plan["host"], scope)
            if scope == "project":
                # The folder is created only when this apply writes; an absent one held no file at preview.
                folder = stack.enter_context(project_folder(path.parent.parent))
                if folder is None:
                    if target["sha256"] is not None:
                        raise Refusal("target changed; preview again")
                    if plan["tokens"] is None:
                        print("No difference.")
                        continue
                    folder = stack.enter_context(project_folder(path.parent.parent, create=True))
            else:
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
            result, _ = transform(plan["host"], raw, plan["tokens"], plan["clear_models"], plan["model"])
            if result != raw and raw is not None:
                try:
                    os.stat(target["backup"], dir_fd=folder, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise Refusal("previewed backup exists; preview again")
            ready.append((folder, path, target, raw, mode, result))
        for folder, path, target, raw, mode, result in ready:
            target_notice(plan["host"], raw, plan["clear_models"], plan["model"])
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
        pre.add_argument("--project")
        pre.add_argument("--clear-model-overrides", action="store_true")
        pre.add_argument("--model")
        choice = pre.add_mutually_exclusive_group(required=True)
        choice.add_argument("--tokens", type=int)
        choice.add_argument("--off", action="store_true")
        app = commands.add_parser("apply")
        app.add_argument("--digest", required=True)
        app.add_argument("--yes", action="store_true")
        args = parser.parse_args()
        if args.action == "preview":
            preview(args.host, args.folder, args.tokens, args.project, args.clear_model_overrides, args.model)
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
