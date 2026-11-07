#!/usr/bin/env python3
"""Preview and write one agent instruction file (or one block of it) after a shown digest.

preview --target <path> --content-file <path> [--block "Agent skills"|"Work tracking"]
    Stores a private plan, prints the diff and a full SHA-256 digest. Writes nothing else.
apply --digest <64 hex> --yes
    Re-checks the plan and writes atomically, keeping a backup that never overwrites an earlier one.

Allowed targets are a closed list: the user-level files `hosts.md` lists under the account home, and
AGENTS.md, CLAUDE.md and CLAUDE.local.md at the git top level of the working folder. Symlinks are refused
at the target and at every folder below the allowed base. Metadata only: nothing is sent anywhere.
"""
import argparse
import difflib
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

LIMIT = 262144
EXPIRY = 3600
USER_TARGETS = {
    (".claude", "CLAUDE.md"), (".codex", "AGENTS.override.md"), (".codex", "AGENTS.md"),
    (".gemini", "GEMINI.md"), (".gemini", "AGENTS.md"), (".agents", "instructions.md"),
}
PROJECT_TARGETS = ("AGENTS.md", "CLAUDE.md", "CLAUDE.local.md")
BLOCKS = ("Agent skills", "Work tracking")
FULL = re.compile(r"[0-9a-f]{64}")
STATE = "state/instructions"


class Refusal(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal("usage: " + message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_top():
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL") if key in os.environ}
    env["HOME"] = str(dr.account_home())
    try:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=os.getcwd(), env=env, shell=False,
                              capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    text = done.stdout.decode("utf-8", "replace").strip()
    return os.path.realpath(text) if text.startswith("/") else None


def allowed(target):
    """Return (base folder, relative parts) when the target is on the closed list, else refuse."""
    path = os.path.abspath(target)
    home = str(dr.account_home())
    rel = Path(path).relative_to(home).parts if path.startswith(home.rstrip("/") + "/") else None
    if rel is not None and rel in USER_TARGETS:
        return home, rel
    top = git_top()
    if top is not None and Path(path).name in PROJECT_TARGETS and os.path.realpath(os.path.dirname(path)) == top:
        path = os.path.join(top, Path(path).name)
        return top, (Path(path).name,)
    raise Refusal("target is not on the allowed list (user-level instruction files, or AGENTS.md, CLAUDE.md, "
                  "CLAUDE.local.md at the repository top level)")


def open_dir(base, rel, create):
    """Open the folder holding the target, refusing a symlink at every step below the base."""
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in rel[:-1]:
            try:
                nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(name, 0o700, dir_fd=fd)
                nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except OSError as error:
        os.close(fd)
        if getattr(error, "errno", None) in (errno.ELOOP, errno.ENOTDIR):
            raise Refusal("a symlink or non-folder lies on the path to the target")
        raise


def read_existing(folder, name):
    """Return the current bytes, or None when the file is absent. A symlink or non-regular file is refused."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=folder)
    except FileNotFoundError:
        return None
    except OSError:
        raise Refusal("target is a symlink or cannot be opened safely")
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise Refusal("target is not a regular file")
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise Refusal("existing target is over the size cap")
    return raw


def read_content(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        raise Refusal("content file is missing or a symlink")
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise Refusal("content file is not a regular file")
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise Refusal("content is over the size cap")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal("content is not UTF-8 text")
    if "\x00" in text:
        raise Refusal("content holds a NUL byte")
    return text


def section_bounds(lines, heading):
    marker = "## " + heading
    found, fence = [], False
    for index, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence and line.rstrip() == marker:
            found.append(index)
    if len(found) > 1:
        raise Refusal("the file has more than one '" + marker + "' section; resolve that first")
    if not found:
        return None
    start, fence = found[0], False
    for index in range(start + 1, len(lines)):
        if lines[index].lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence and lines[index].startswith("## "):
            return start, index
    return start, len(lines)


def merge_block(current, block, heading):
    if heading not in BLOCKS:
        raise Refusal("block must be one of: " + ", ".join(BLOCKS))
    lines = block.rstrip("\n").split("\n")
    if lines[0].rstrip() != "## " + heading or any(line.startswith("## ") for line in lines[1:]):
        raise Refusal("block text must start with '## " + heading + "' and hold no other level-two heading")
    old = current.split("\n") if current else []
    if old and old[-1] == "":
        old.pop()
    bounds = section_bounds(old, heading)
    if bounds is None:
        merged = old + ([""] if old else []) + lines
    else:
        start, end = bounds
        tail = old[end:]
        merged = old[:start] + lines + ([""] if tail else []) + tail
    return "\n".join(merged) + "\n"


def plan_digest(plan):
    body = {key: plan[key] for key in ("target", "content_sha256", "existing_sha256")}
    return sha(json.dumps(body, sort_keys=True).encode())


def preview(target, content_file, block):
    base, rel = allowed(target)
    path = os.path.join(base, *rel)
    content = read_content(content_file)
    folder = None
    try:
        try:
            folder = open_dir(base, rel, create=False)
            existing = read_existing(folder, rel[-1])
        except FileNotFoundError:
            existing = None
    finally:
        if folder is not None:
            os.close(folder)
    old_text = existing.decode("utf-8", "replace") if existing is not None else ""
    new_text = merge_block(old_text, content, block) if block else content
    if len(new_text.encode("utf-8")) > LIMIT:
        raise Refusal("resulting file is over the size cap")
    if existing is not None and new_text.encode("utf-8") == existing:
        print("No difference.")
        return
    data = new_text.encode("utf-8")
    plan = {"target": path, "base": base, "rel": list(rel), "content": new_text, "content_sha256": sha(data),
            "existing_sha256": sha(existing) if existing is not None else "absent", "created": time.time()}
    value = plan_digest(plan)
    with dr.data_folder(STATE, create=True, private=True) as state:
        for name in os.listdir(state):
            if name.endswith(".json"):
                try:
                    if time.time() - os.stat(name, dir_fd=state, follow_symlinks=False).st_mtime > EXPIRY:
                        os.unlink(name, dir_fd=state)
                except OSError:
                    pass
        dr.atomic_write(state, value + ".json", json.dumps(plan).encode())
    diff = difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), "current" if existing is not None else "(new file)",
                                "proposed", lineterm="")
    print("Target: " + path)
    print("Exists: " + ("yes" if existing is not None else "no"))
    print("Lines: %d, bytes: %d" % (len(new_text.splitlines()), len(data)))
    print("Backup: " + ("<file>.bak-YYYYMMDD (next free suffix)" if existing is not None else "not needed"))
    for line in diff:
        print(line)
    print("Digest: " + value)


def backup(folder, name, raw):
    day = time.strftime("%Y%m%d")
    for number in range(1, 100):
        candidate = "%s.bak-%s%s" % (name, day, "" if number == 1 else "-%d" % number)
        try:
            fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
        except FileExistsError:
            continue
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return candidate
    raise Refusal("no free backup name")


def apply(value, yes):
    if not yes:
        raise Refusal("--yes is required after the user's clear yes to this file")
    if not FULL.fullmatch(value):
        raise Refusal("the full 64-character digest is required")
    with dr.data_folder(STATE, private=True) as state:
        try:
            raw = dr.read_file(state, value + ".json", LIMIT * 2)
        except FileNotFoundError:
            raise Refusal("no stored preview for this digest; run preview again")
        if stat.S_IMODE(os.stat(value + ".json", dir_fd=state, follow_symlinks=False).st_mode) != 0o600:
            raise Refusal("preview must be private (0600)")
        plan = json.loads(raw)
        age = time.time() - float(plan["created"])
        if age < 0 or age > EXPIRY:
            raise Refusal("the preview is older than 60 minutes; run preview again")
        data = plan["content"].encode("utf-8")
        if sha(data) != plan["content_sha256"] or plan_digest(plan) != value:
            raise Refusal("the content digest differs from the one shown")
        base, rel = allowed(plan["target"])
        if os.path.join(base, *rel) != plan["target"]:
            raise Refusal("the target is no longer on the allowed list")
        folder = open_dir(base, rel, create=True)
        try:
            existing = read_existing(folder, rel[-1])
            if (sha(existing) if existing is not None else "absent") != plan["existing_sha256"]:
                raise Refusal("the file changed after the preview; run preview again")
            made = backup(folder, rel[-1], existing) if existing is not None else None
            mode = stat.S_IMODE(os.stat(rel[-1], dir_fd=folder, follow_symlinks=False).st_mode) if existing is not None else 0o600
            temporary = ".write-" + os.urandom(12).hex()
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fchmod(stream.fileno(), mode)
                    os.fsync(stream.fileno())
                os.replace(temporary, rel[-1], src_dir_fd=folder, dst_dir_fd=folder)
                os.fsync(folder)
            finally:
                try:
                    os.unlink(temporary, dir_fd=folder)
                except FileNotFoundError:
                    pass
        finally:
            os.close(folder)
        os.unlink(value + ".json", dir_fd=state)
    print("Wrote: " + plan["target"])
    print("Backup: " + (made if made else "not needed"))


def main():
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="action", required=True)
        pre = commands.add_parser("preview")
        pre.add_argument("--target", required=True)
        pre.add_argument("--content-file", required=True)
        pre.add_argument("--block")
        app = commands.add_parser("apply")
        app.add_argument("--digest", required=True)
        app.add_argument("--yes", action="store_true")
        args = parser.parse_args()
        if args.action == "preview":
            preview(args.target, args.content_file, args.block)
        else:
            apply(args.digest, args.yes)
        return 0
    except Refusal as error:
        print("Instructions write refused: " + str(error), file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print("Instructions write refused: unsafe, unreadable or invalid file or plan", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
