#!/usr/bin/env python3
"""Preview, apply or remove an opt-in host status-line context recorder."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import compact_setup as common
import data_root as dr

Refusal = common.Refusal
HOSTS = ("claude", "antigravity")


def check_antigravity_plugin(root):
    # Same installed-copy exception as compact_stop_setup.check_plugin_root.
    try:
        with dr.relocated_folder(root):
            return
    except ValueError as error:
        if str(error) != "root is a git work tree":
            raise
    if root != dr.account_home() / ".gemini/config/plugins/finolabs-vibecode":
        raise Refusal("plugin folder is inside a git work tree; use the installed copy of the plugin")
    with dr.relocated_folder(root.parent):
        pass
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise Refusal("plugin folder is not private enough")
        if not stat.S_ISDIR(os.stat(".git", dir_fd=fd, follow_symlinks=False).st_mode):
            raise Refusal("plugin folder .git is not a directory")
    finally:
        os.close(fd)


def recorder_path(host="claude"):
    scripts = Path(os.path.abspath(__file__)).parent
    candidate = scripts / "context_snapshot.py"
    if not candidate.is_file() and scripts.parent.name == "setup":
        candidate = scripts.parents[2] / "scripts" / "context_snapshot.py"
    if not candidate.is_file() or candidate.is_symlink():
        raise Refusal("whole plugin required; use the manual procedure for standalone installs")
    if host == "antigravity":
        check_antigravity_plugin(candidate.parent.parent)
        fd = os.open(candidate.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for info in (os.fstat(fd), os.stat(candidate.name, dir_fd=fd, follow_symlinks=False)):
                if info.st_uid != os.getuid() or info.st_mode & 0o022:
                    raise Refusal("unsafe plugin script or folder")
        finally:
            os.close(fd)
    return candidate


def statusline(path=None, host="claude"):
    path = recorder_path(host) if path is None else path
    return {"type": "command", "command": "python3 -I " + shlex.quote(str(path)) + " record --host " + host + " --line"}


def settings(raw):
    data = json.loads(raw, object_pairs_hook=common.json_object,
                      parse_float=common.json_float, parse_constant=common.json_constant) if raw is not None else {}
    if not isinstance(data, dict):
        raise Refusal("settings must be a JSON object")
    return data


def transform(raw, remove, command):
    data = settings(raw)
    if remove:
        if "statusLine" not in data:
            return raw
        if data["statusLine"] != command:
            raise Refusal("existing statusLine is not this recorder; remove it by hand")
        del data["statusLine"]
    else:
        if "statusLine" in data:
            raise Refusal("existing statusLine; use the manual recipe")
        data["statusLine"] = command
    return (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def recipe(host):
    command = "python3 -I " + shlex.quote(str(recorder_path(host))) + " record --host " + host
    print("Existing statusLine: unchanged. No plan saved.\nRecipe: wrap your existing command in a local shell script:")
    print('input=$(mktemp) || exit 0\ntrap \'rm -f "$input"\' EXIT\ncat > "$input"')
    print(command + ' < "$input"')
    print('YOUR_EXISTING_COMMAND < "$input"')
    print("Replace YOUR_EXISTING_COMMAND by hand. The recorder receives the same stdin JSON; it prints nothing.")


def target_path(value, host):
    path = common.checked_path(value, "claude")
    if host == "antigravity" and path != dr.account_home() / ".gemini/antigravity-cli/settings.json":
        raise Refusal("Antigravity target is fixed at the account home's settings file")
    return path


def preview(folders, remove=False, host="claude"):
    if host not in HOSTS or (host == "antigravity" and folders):
        raise Refusal("unsupported host or config folders")
    folders = folders or [dr.account_home() / (".gemini/antigravity-cli" if host == "antigravity" else ".claude")]
    if not 1 <= len(folders) <= 4:
        raise Refusal("one to four config folders required")
    root = dr.consent_root()
    if root is None:
        raise Refusal("invalid data root")
    command = statusline(host=host)
    targets, displays, identities = [], [], set()
    existing = False
    for folder_path in folders:
        path = target_path(Path(folder_path) / "settings.json", host)
        with dr.relocated_folder(path.parent) as folder:
            info = os.fstat(folder)
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise Refusal("duplicate config folder")
            identities.add(identity)
            raw, mode = common.read_target(folder, path.name)
            data = settings(raw)
            if not remove and "statusLine" in data:
                existing = True
            elif remove:
                transform(raw, remove, command)  # refuse removal of a user-owned command
            backup = common.backup_name(folder, path.name)
            targets.append({"path": str(path), "sha256": common.content_hash(raw), "mode": mode, "backup": backup})
            displays.append((path, raw, backup))
    if existing:
        recipe(host)
        return
    plan = {"host": host, "created": time.time(), "root": str(root), "remove": remove,
            "statusLine": command, "targets": targets}
    value = common.digest(plan)
    with dr.data_folder("state/statusline", create=True, private=True) as state:
        try:
            common.read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, "preview.json", json.dumps({"plan": plan, "digest": value}).encode())
    for path, raw, backup in displays:
        print(f"Target: {path}\nExists: {'yes' if raw is not None else 'no'}")
        print("statusLine: " + ("remove this recorder only" if remove else json.dumps(command)))
        print(f"Backup: {path.parent / backup}" + (" (not needed)" if raw is None else ""))
    print("Local context counts only; no transcript reads. Live status-line delivery remains unverified.")
    print("Digest: " + value)


def apply(value, yes, host="claude"):
    if not yes or not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise Refusal("clear yes and full 64-hex preview digest required")
    value = value.lower()
    with ExitStack() as stack:
        state = stack.enter_context(dr.data_folder("state/statusline", private=True))
        saved = json.loads(common.read_plan(state), object_pairs_hook=common.json_object,
                           parse_float=common.json_float, parse_constant=common.json_constant)
        if (not isinstance(saved, dict) or set(saved) != {"plan", "digest"}
                or saved["digest"] != value or common.digest(saved["plan"]) != value):
            raise Refusal("digest mismatch; preview again")
        plan = saved["plan"]
        if (not isinstance(plan, dict) or set(plan) != {"host", "created", "root", "remove", "statusLine", "targets"}
                or host not in HOSTS or plan["host"] != host
                or type(plan["remove"]) is not bool or plan["statusLine"] != statusline(host=host)):
            raise Refusal("invalid or moved install; preview again")
        if plan["root"] != str(dr.consent_root()):
            raise Refusal("data root changed; preview again")
        if type(plan["created"]) not in (int, float) or not 0 <= time.time() - plan["created"] <= 3600:
            raise Refusal("preview expired; preview again")
        targets = plan["targets"]
        if not isinstance(targets, list) or not 1 <= len(targets) <= (1 if host == "antigravity" else 4):
            raise Refusal("invalid targets")
        ready, identities = [], set()
        for target in targets:
            if not isinstance(target, dict) or set(target) != {"path", "sha256", "mode", "backup"}:
                raise Refusal("invalid target")
            path = target_path(target["path"], host)
            folder = stack.enter_context(dr.relocated_folder(path.parent))
            info = os.fstat(folder)
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise Refusal("duplicate config folder")
            identities.add(identity)
            raw, mode = common.read_target(folder, path.name)
            if common.content_hash(raw) != target["sha256"] or mode != target["mode"]:
                raise Refusal("target changed; preview again")
            if not isinstance(target["backup"], str) or not re.fullmatch(r"settings\.json\.bak-\d{8}(?:-[1-9][0-9]*)?", target["backup"]):
                raise Refusal("invalid backup name")
            result = transform(raw, plan["remove"], plan["statusLine"])
            if result != raw and raw is not None:
                try:
                    os.stat(target["backup"], dir_fd=folder, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise Refusal("previewed backup exists; preview again")
            ready.append((folder, path, target, raw, mode, result))
        for folder, path, target, raw, mode, result in ready:
            if result == raw:
                print("No difference.")
                continue
            current, current_mode = common.read_target(folder, path.name)
            if current != raw or current_mode != mode:
                raise Refusal("target changed; preview again")
            if raw is not None:
                fd = os.open(target["backup"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            common.write_target(folder, path.name, result, 0o600)
            print(f"Updated: {path}")
        os.unlink("preview.json", dir_fd=state)
        os.fsync(state)


def main():
    try:
        parser = common.Parser(description=__doc__)
        commands = parser.add_subparsers(dest="action", required=True)
        pre = commands.add_parser("preview")
        pre.add_argument("--host", choices=HOSTS, default="claude")
        pre.add_argument("--folder", action="append", default=[])
        pre.add_argument("--remove", action="store_true")
        app = commands.add_parser("apply")
        app.add_argument("--host", choices=HOSTS, default="claude")
        app.add_argument("--digest", required=True)
        app.add_argument("--yes", action="store_true")
        args = parser.parse_args()
        if args.action == "preview":
            preview(args.folder, args.remove, args.host)
        else:
            apply(args.digest, args.yes, args.host)
        return 0
    except Refusal as error:
        print("Status-line setup refused: " + str(error), file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print("Status-line setup refused: unsafe, unreadable or invalid file or plan", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
