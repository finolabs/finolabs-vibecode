#!/usr/bin/env python3
"""List the linked worktrees of the current repository, and remove the ones that are safe to remove.

  worktree_sweep.py [list]                      one line per linked worktree; always exits 0
  worktree_sweep.py --remove [--path <dir>]...  remove the safe ones; non-zero only on its own error

For each linked worktree (never the main checkout) `list` prints its path relative to the main checkout,
its branch, its size on disk (a bounded walk that follows no symlink), clean or dirty (`git status
--porcelain`, untracked files included), unpushed commits and merged:

- unpushed: commits ahead of the branch's upstream; with no upstream, or one deleted on the forge,
  commits that no remote-tracking branch holds, marked "(no upstream)".
- merged: yes when the branch head is an ancestor of `origin/<default>` as known locally, or when
  `gh pr list --head <branch> --state merged` (a read) finds a merged pull request; no when gh finds none;
  unknown when neither can tell, for example without gh.

`--remove` takes a worktree only when every check holds: it is named with `--path`, or, with no `--path`,
it is the checkout of a finished dispatch in the delegation ledger; no open ledger dispatch names it; it
is neither locked nor detached, nor the current working directory or a parent of it; it is clean, holds
no unpushed commit and is merged. It runs `git worktree remove <path>` (never forced), then
`git branch -d <branch>` (never -D), then `git worktree prune`, and prints what it removed and what it
kept with the reason. Anything it cannot tell is kept. Files git ignores go with a removed worktree.
It stores nothing and makes no network call of its own; gh, when present, reads the forge.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path

MAX_ENTRIES = 200000  # the size walk stops here and reports a lower bound
LEDGER_LIMIT = 16 * 1024 * 1024
GH_TIMEOUT = 20


class OwnError(Exception):
    """An error of this script itself, as opposed to a worktree it keeps."""


def child_environment():
    """Keep credentials and home or config overrides out of git."""
    env = {k: os.environ[k] for k in ("PATH", "LANG", "TMPDIR") if k in os.environ}
    env.setdefault("PATH", os.defpath)
    return env


def git(checkout, *args):
    return subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                           "-c", "core.untrackedCache=false", "-C", str(checkout), *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=60,
                          env=child_environment())


def git_out(checkout, *args):
    """stdout of a git command that succeeded, else None."""
    try:
        done = git(checkout, *args)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def run_gh(args, cwd):
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=GH_TIMEOUT, cwd=cwd)


def worktrees(checkout):
    """[(path, info)] from `git worktree list --porcelain`; the first entry is the main checkout."""
    try:
        done = git(checkout, "worktree", "list", "--porcelain")
    except (OSError, subprocess.SubprocessError) as error:
        raise OwnError("git could not run: " + type(error).__name__)
    if done.returncode != 0:
        raise OwnError("not inside a git repository")
    entries, current = [], None
    for line in done.stdout.splitlines():
        if line.startswith("worktree "):
            current = {"path": Path(line[len("worktree "):])}
            entries.append(current)
        elif current is not None and line:
            key, _, value = line.partition(" ")
            current[key] = value
    if not entries:
        raise OwnError("git listed no worktree")
    return entries


def size_on_disk(root):
    """(bytes, complete) for a folder, counting allocated blocks, never following a symlink."""
    total, seen, stack = 0, 0, [str(root)]
    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_ENTRIES:
                        return total, False
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
                    total += getattr(info, "st_blocks", 0) * 512 or info.st_size
        except OSError:
            continue
    return total, True


def human(size):
    amount, complete = size
    for unit in ("B", "KiB", "MiB", "GiB"):
        if amount < 1024 or unit == "GiB":
            text = f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
            return text if complete else "over " + text
        amount /= 1024
    return str(amount)


def state(path):
    out = git_out(path, "status", "--porcelain", "--untracked-files=normal")
    return "unknown" if out is None else ("clean" if out == "" else "dirty")


def unpushed(path):
    """(count or None, has upstream)."""
    if git_out(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"):
        count = git_out(path, "rev-list", "--count", "@{upstream}..HEAD")
        return (int(count) if count and count.isdigit() else None), True
    count = git_out(path, "rev-list", "--count", "HEAD", "--not", "--remotes")
    return (int(count) if count and count.isdigit() else None), False


def default_ref(main):
    ref = git_out(main, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    return ref if ref and ref.startswith("refs/remotes/origin/") else None


def merged(path, head, branch, default):
    """"yes", "no" or "unknown"."""
    if default and head:
        try:
            done = git(path, "merge-base", "--is-ancestor", head, default)
            if done.returncode == 0:
                return "yes"
        except (OSError, subprocess.SubprocessError):
            pass
    if not branch:
        return "unknown"
    try:
        done = run_gh(["pr", "list", "--head", branch, "--state", "merged", "--json", "number"], str(path))
        found = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        found = None
    if not isinstance(found, list):
        return "unknown"
    return "yes" if found else "no"


def describe(main, entry, default):
    path = entry["path"]
    branch = entry.get("branch", "")
    branch = branch[len("refs/heads/"):] if branch.startswith("refs/heads/") else ""
    info = {"path": path, "rel": os.path.relpath(path, main), "branch": branch, "head": entry.get("HEAD"),
            "locked": "locked" in entry, "prunable": "prunable" in entry or not path.is_dir()}
    if info["prunable"]:
        info.update(size=(0, True), state="unknown", unpushed=(None, False), merged="unknown")
        return info
    info["size"] = size_on_disk(path)
    info["state"] = state(path)
    info["unpushed"] = unpushed(path)
    info["merged"] = merged(path, info["head"], branch, default)
    return info


def line(info):
    count, upstream = info["unpushed"]
    pushed = ("unknown" if count is None else str(count)) + ("" if upstream else " (no upstream)")
    return (f"{info['rel']}  branch={info['branch'] or '(detached)'}  size={human(info['size'])}  "
            f"{info['state']}  unpushed={pushed}  merged={info['merged']}")


def ledger_checkouts():
    """(finished, open) sets of checkout ids from the delegation ledger, or None when it cannot be read."""
    try:
        import data_root as dr
        raw = dr.read_data("ledger.jsonl", LEDGER_LIMIT).decode("utf-8")
    except FileNotFoundError:
        return set(), set()
    except Exception:
        return None
    starts, finished = {}, set()
    for text in raw.splitlines():
        try:
            record = json.loads(text)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("event") == "start" and isinstance(record.get("checkout_id"), str):
            starts[record.get("id")] = record["checkout_id"]
        elif record.get("event") == "finish":
            finished.add(record.get("id"))
    done = {c for i, c in starts.items() if i in finished}
    running = {c for i, c in starts.items() if i not in finished}
    return done, running


def checkout_id(path):
    return hashlib.sha256(os.fsencode(Path(path).resolve())).hexdigest()


def reason_to_keep(info, named, ledger, cwd):
    path = info["path"].resolve()
    ident = checkout_id(path)
    if info["prunable"]:
        return "its folder is missing; git worktree prune clears the record"
    if info["locked"]:
        return "locked"
    if not info["branch"]:
        return "detached HEAD"
    if cwd == path or path in cwd.parents:
        return "it is the working directory or a parent of it"
    if ledger is None:
        return "the delegation ledger cannot be read"
    done, running = ledger
    if ident in running:
        return "an open dispatch uses it"
    if named is not None:
        if path not in named:
            return "not named with --path"
    elif ident not in done:
        return "not named with --path and not the checkout of a finished dispatch"
    if info["state"] != "clean":
        return "dirty" if info["state"] == "dirty" else "status unknown"
    count, _ = info["unpushed"]
    if count is None:
        return "unpushed commits unknown"
    if count:
        return f"{count} unpushed commit(s)"
    if info["merged"] != "yes":
        return "not merged" if info["merged"] == "no" else "merge state unknown (no gh or no answer)"
    return None


def remove(main, entries, default, paths):
    cwd = Path.cwd().resolve()
    named = None if not paths else {Path(p).resolve() for p in paths}
    ledger = ledger_checkouts()
    main_path = entries[0]["path"].resolve()
    linked = {entry["path"].resolve() for entry in entries[1:]}
    for path in sorted(named or ()):
        if path == main_path:
            print(f"kept {os.path.relpath(path, main)}: the main checkout is never removed")
        elif path not in linked:
            print(f"kept {os.path.relpath(path, main)}: not a linked worktree of this repository")
    removed = 0
    for entry in entries[1:]:
        if named is not None and entry["path"].resolve() not in named:
            continue
        info = describe(main, entry, default)
        reason = reason_to_keep(info, named, ledger, cwd)
        if reason:
            print(f"kept {info['rel']} ({human(info['size'])}): {reason}")
            continue
        done = git(main, "worktree", "remove", str(info["path"]))
        if done.returncode != 0:
            print(f"kept {info['rel']} ({human(info['size'])}): git worktree remove refused it")
            continue
        removed += 1
        gone = git(main, "branch", "-d", info["branch"])
        note = f"branch {info['branch']} deleted" if gone.returncode == 0 else \
            f"branch {info['branch']} kept: git branch -d refused it"
        print(f"removed {info['rel']} ({human(info['size'])}); {note}")
    git(main, "worktree", "prune")
    if removed == 0:
        print("worktree_sweep: nothing removed")


def main(argv=None):
    parser = argparse.ArgumentParser(description="List linked worktrees; remove the safe ones.")
    parser.add_argument("command", nargs="?", choices=["list"], default="list")
    parser.add_argument("--remove", action="store_true", help="remove the worktrees that pass every check")
    parser.add_argument("--path", action="append", default=[], help="a worktree to remove (repeatable)")
    args = parser.parse_args(argv)
    if args.path and not args.remove:
        parser.error("--path needs --remove")
    try:
        entries = worktrees(".")
        main_checkout = entries[0]["path"]
        default = default_ref(main_checkout)
        if args.remove:
            remove(main_checkout, entries, default, args.path)
            return 0
        linked = entries[1:]
        print(f"worktree_sweep: {len(linked)} linked worktree(s)")
        for entry in linked:
            print(line(describe(main_checkout, entry, default)))
        return 0
    except OwnError as error:
        print("worktree_sweep: " + str(error), file=sys.stderr)
        return 1 if args.remove else 0
    except Exception as error:
        print("worktree_sweep: failed: " + type(error).__name__, file=sys.stderr)
        return 1 if args.remove else 0


if __name__ == "__main__":
    sys.exit(main())
