#!/usr/bin/env python3
"""List the linked worktrees of the current repository and the git commands that remove the safe ones.

  worktree_sweep.py [list]    read-only; always exits 0

It deletes nothing: git does the removal, with its own checks, when the agent runs the printed commands.

For each linked worktree (never the main checkout), in the order `git worktree list --porcelain` gives,
it prints the path exactly as git lists it, its branch, its size on disk (a bounded walk that follows
no symlink), clean or dirty (`git status --porcelain`, untracked files included), unpushed commits,
merged and whether it is a candidate:

- unpushed: commits ahead of the branch's upstream; with no upstream, or one deleted on the forge,
  commits that no remote-tracking branch holds, marked "(no upstream)". When the forge merged a pull
  request at exactly the branch's current head, that head was pushed, so the count is 0.
- merged: yes when the branch head is an ancestor of `origin/<default>` as known locally, or when
  `gh pr list --head <branch> --state merged --json number,headRefOid` (a read) finds a merged pull
  request whose head commit is the branch's current head; no when gh finds no merged pull request;
  unknown when neither can tell, for example without gh, or when the merged pull requests had another head.
- candidate: yes only when it is merged, clean, has nothing unpushed, is not locked, not detached, not
  the working folder or a parent of it, and neither holds nor lies inside another registered worktree
  (linked worktrees inside the main checkout are the usual layout and stay eligible). Paths are compared
  as written, resolved and case-folded, so another spelling of a path counts as the same path. Otherwise
  it prints "candidate=no" with the first reason.

Under each candidate it prints the two commands to run, the path quoted for a POSIX shell:
`git worktree remove <path as git lists it>` (never forced; git refuses a dirty worktree) and
`git branch -d <branch>` (git refuses an unmerged branch). `git worktree remove` also deletes the files
git ignores inside that worktree. A change made after the listing is for git's own checks to catch.
It stores nothing and makes no network call of its own; gh, when present, reads the forge.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

MAX_ENTRIES = 200000  # the size walk stops here and reports a lower bound
GH_TIMEOUT = 20


class OwnError(Exception):
    """An error of this script itself, as opposed to a worktree it reports."""


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
    """[info] from `git worktree list --porcelain -z`; the first entry is the main checkout.

    NUL-separated, so a path or branch holding a newline cannot forge another entry."""
    try:
        done = git(checkout, "worktree", "list", "--porcelain", "-z")
    except (OSError, subprocess.SubprocessError) as error:
        raise OwnError("git could not run: " + type(error).__name__)
    if done.returncode != 0:
        raise OwnError("not inside a git repository")
    entries, current = [], None
    for line in done.stdout.split("\0"):
        if line.startswith("worktree "):
            current = {"path": line[len("worktree "):]}
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


def spellings(path):
    """The path as written, resolved, and both case-folded, each absolute and normalized."""
    written = os.path.normpath(os.path.abspath(path))
    try:
        resolved = os.path.realpath(path)
    except (OSError, ValueError):
        resolved = written
    return {Path(p) for p in (written, resolved, written.casefold(), resolved.casefold())}


def within(inner, outer):
    """True when some spelling of `inner` is `outer` itself or lies below some spelling of `outer`."""
    return any(i == o or o in i.parents for i in inner for o in outer)


def nesting(path, main_path, linked):
    """Why a worktree is not a candidate because of where it lies among the registered worktrees, or None."""
    mine = spellings(path)
    for other in (main_path, *linked):
        theirs = spellings(other)
        if theirs != mine and within(theirs, mine) and not within(mine, theirs):
            return "it holds another worktree"
    for other in linked:
        theirs = spellings(other)
        if theirs != mine and within(mine, theirs) and not within(theirs, mine):
            return "it lies inside another worktree"
    return None


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
    """("yes", "no" or "unknown", "ancestor", "forge" or None for what proved a yes).

    The forge counts only for a merged pull request whose head commit is the branch's current head: a
    branch name reused, or pushed to after its pull request merged, proves nothing.
    """
    if default and head:
        try:
            done = git(path, "merge-base", "--is-ancestor", head, default)
            if done.returncode == 0:
                return "yes", "ancestor"
        except (OSError, subprocess.SubprocessError):
            pass
    if not branch or not head:
        return "unknown", None
    try:
        done = run_gh(["pr", "list", "--head", branch, "--state", "merged", "--json", "number,headRefOid"],
                      str(path))
        found = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        found = None
    if not isinstance(found, list):
        return "unknown", None
    if not found:
        return "no", None
    for pull in found:
        if isinstance(pull, dict) and isinstance(pull.get("headRefOid"), str) \
                and pull["headRefOid"].lower() == head.lower():
            return "yes", "forge"
    return "unknown", None


def describe(entry, default):
    path = entry["path"]
    branch = entry.get("branch", "")
    branch = branch[len("refs/heads/"):] if branch.startswith("refs/heads/") else ""
    info = {"path": path, "branch": branch, "head": entry.get("HEAD"), "locked": "locked" in entry,
            "forge_head": False, "missing": "prunable" in entry or not os.path.isdir(path)}
    if info["missing"]:
        info.update(size=(0, True), state="unknown", unpushed=(None, False), merged="unknown")
        return info
    info["size"] = size_on_disk(path)
    info["state"] = state(path)
    info["unpushed"] = unpushed(path)
    info["merged"], proof = merged(path, info["head"], branch, default)
    count, upstream = info["unpushed"]
    if proof == "forge" and not upstream and count:
        # The forge merged a pull request at exactly this head, so every commit of it was pushed; the
        # remote-tracking refs no longer hold them only because the branch was deleted after a squash.
        info["unpushed"] = (0, False)
        info["forge_head"] = True
    return info


def reason_not_candidate(info, place, cwd):
    if any(ord(c) < 32 or ord(c) == 127 for c in info["path"] + (info["branch"] or "")):
        return "control character in the path or branch"
    if info["missing"]:
        return "its folder is missing"
    if info["locked"]:
        return "locked"
    if not info["branch"]:
        return "detached HEAD"
    if within(cwd, spellings(info["path"])):
        return "it is the working folder or a parent of it"
    if place:
        return place
    if info["state"] != "clean":
        return "dirty" if info["state"] == "dirty" else "status unknown"
    count, _ = info["unpushed"]
    if count is None:
        return "unpushed=unknown"
    if count:
        return f"unpushed={count}"
    if info["merged"] != "yes":
        return f"merged={info['merged']}"
    return None


def report(info, reason):
    count, upstream = info["unpushed"]
    pushed = ("unknown" if count is None else str(count)) + ("" if upstream else " (no upstream)")
    if info["forge_head"]:
        pushed = "0 (no upstream; the forge merged this head)"
    text = (f"{info['path'].encode('unicode_escape').decode('ascii')}  branch={info['branch'] or '(detached)'}  size={human(info['size'])}  "
            f"{info['state']}  unpushed={pushed}  merged={info['merged']}  ")
    if reason:
        return [text + f"candidate=no ({reason})"]
    return [text + "candidate=yes",
            "  git worktree remove -- " + shlex.quote(info["path"]),
            "  git branch -d -- " + shlex.quote(info["branch"])]


def main(argv=None):
    parser = argparse.ArgumentParser(description="List linked worktrees and the git commands that remove the safe ones.")
    parser.add_argument("command", nargs="?", choices=["list"], default="list")
    parser.parse_args(argv)
    try:
        entries = worktrees(".")
        main_checkout = entries[0]["path"]
        default = default_ref(main_checkout)
        linked = [entry["path"] for entry in entries[1:]]
        cwd = spellings(os.getcwd())
        print(f"worktree_sweep: {len(linked)} linked worktree(s)")
        for entry in entries[1:]:
            info = describe(entry, default)
            reason = reason_not_candidate(info, nesting(info["path"], main_checkout, linked), cwd)
            for text in report(info, reason):
                print(text)
    except OwnError as error:
        print("worktree_sweep: " + str(error), file=sys.stderr)
    except Exception as error:
        print("worktree_sweep: failed: " + type(error).__name__, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
