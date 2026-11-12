#!/usr/bin/env python3
"""Post a bounded review comment through a single GitHub-only path.

Usage: post_review.py PR creates a private run folder and an empty body.md and
prints its absolute filename. Fill that file, then run post_review.py PR
--body-file FILE. PR is the only positional argument and --body-file the only
option. No repository argument, browser, editing or generic gh command is allowed.
The repository comes only from the checkout's origin remote.

Content beyond the first line is not inspected. A comment in a public repository
is public. This wrapper narrows commands, not the credential's underlying powers;
it never reads, stores or searches for a token. Credential injection belongs to
the user's approved host setup. Preparing a file is not permission to post.

Exit 0: prepared or posted and observed; 1: cannot-post; 2: invalid/unsafe input.
A failed or unobserved post is never retried automatically. The coordinator calls
posting_verified before setup records posting=yes; this script writes no host
settings, event, relay count or verification receipt.
"""
import argparse
import configparser
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import git_metadata as metadata

CAP = 64 * 1024
MARKER = re.compile(r"<!-- fnl-review kind=(code|security) head=([0-9a-f]{40}) verdict=(APPROVE|REWORK)( lane=yes)? -->")
RUN = re.compile(r"post-[0-9a-f]{32}")
ROOT = Path("state/review-posting")
REASONS = {"no-cli", "no-network", "no-auth", "no-permission", "other"}


class CannotPost(Exception):
    def __init__(self, reason):
        if reason not in REASONS:
            raise ValueError("invalid cannot-post reason")
        self.reason = reason


def marker_line(body):
    # Exact first line; no trimming, leading whitespace, BOM or CR accepted.
    line = body.split("\n", 1)[0]
    if not MARKER.fullmatch(line):
        raise ValueError("invalid marker")
    return line


def posting_verified(comments, expected_identity, expected_marker):
    """A setting or a marker alone never proves the expected reviewer posted it.

The coordinator supplies the marker bound to this family's run and expected
identity from the user's posting setup. It also verifies the PR being observed.
No identity is inferred from the comment's claims or from a relay attribution.
"""
    if not isinstance(expected_identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*(?:\[bot\])?", expected_identity):
        return False
    if not isinstance(expected_marker, str) or not MARKER.fullmatch(expected_marker):
        return False
    if not isinstance(comments, list):
        return False
    return any(isinstance(comment, dict) and isinstance(comment.get("author"), dict)
               and isinstance(comment["author"].get("login"), str)
               and comment["author"]["login"].casefold() == expected_identity.casefold()
               and comment.get("includesCreatedEdit") is False
               and isinstance(comment.get("body"), str)
               and comment["body"].split("\n", 1)[0] == expected_marker
               and not re.search(r"\brelay(?:ed)?\b", (comment["body"].splitlines() + ["", ""])[1], re.I)
               for comment in comments)


def checkout_remote(checkout):
    """Read origin without invoking git, credential helpers, includes or hooks."""
    _, common = metadata.git_dirs(checkout)
    content = metadata.bounded(common / "config", 262144).decode()
    parser = configparser.RawConfigParser(strict=True)
    parser.read_string(content)
    remote = parser.get('remote "origin"', "url", fallback="")
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+?)(?:\.git)?", remote)
    if not match or match[2] in {".", ".."}:
        raise ValueError("github.com origin required")
    return "github.com/" + match[1] + "/" + match[2]


def create_run_folder():
    """Use the canonical data root and atomically create an owner-only body."""
    name = "post-" + secrets.token_hex(16)
    with dr.data_folder(ROOT, create=True, private=True) as parent:
        os.mkdir(name, 0o700, dir_fd=parent)
        with dr.descend(parent, name, private=True) as folder:
            dr.atomic_write(folder, "body.md", b"")
    root = dr.consent_root()
    if root is None:
        raise ValueError("invalid root")
    return root / ROOT / name / "body.md"


def read_body(path):
    """Resolve-check and then descriptor-walk with no-follow on every component."""
    root = dr.consent_root()
    if root is None:
        raise ValueError("invalid root")
    path = Path(os.path.abspath(path))
    base = root / ROOT
    relative = path.relative_to(base)
    if len(relative.parts) != 2 or not RUN.fullmatch(relative.parts[0]) or relative.name != "body.md":
        raise ValueError("not a run body")
    if path.resolve(strict=True) != path or not path.is_relative_to(base.resolve(strict=True)):
        raise ValueError("redirected body")
    with dr.data_folder(ROOT, private=True) as parent:
        with dr.descend(parent, relative.parts[0], private=True) as folder:
            fd = os.open("body.md", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
            try:
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > CAP):
                    raise ValueError("private bounded body required")
                chunks, size = [], 0
                while size <= CAP:
                    chunk = os.read(fd, min(4096, CAP + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                if size > CAP:
                    raise ValueError("body too large")
                body = b"".join(chunks)
            finally:
                os.close(fd)
    text = body.decode("utf-8")
    marker_line(text)
    return text


def gh_environment():
    # Only approved github.com token injection and canonical account auth survive.
    # No ambient host/repo, proxy, socket, config, browser or loader overrides.
    env = {key: os.environ[key] for key in ("GH_TOKEN", "GITHUB_TOKEN", "LANG", "LC_ALL") if key in os.environ}
    env.update(HOME=str(dr.account_home()), PATH="/usr/bin:/bin", GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1")
    return env


def homebrew_gh(candidate, prefix, uid, stat_path=Path.stat):
    """Check a Homebrew path; injectable root/stat keep fixtures outside real installs.

    Walk symlink destinations as well as the final path: even an intermediate
    link leaving the prefix and returning through another link is refused.
    """
    if not prefix.is_absolute() or prefix.resolve(strict=True) != prefix:
        raise ValueError("unsafe gh installation")
    for parent in prefix.parents:
        marker = parent / ".git"
        if marker.exists() or marker.is_symlink():
            raise ValueError("unsafe gh installation")
    pending = list(candidate.relative_to(prefix).parts)
    current, links = prefix, 0
    while True:
        info = stat_path(current)
        if (info.st_uid not in {0, uid} or info.st_mode & 0o002
                or (info.st_mode & 0o020 and info.st_gid != 80)):
            raise ValueError("unsafe gh installation")
        marker = current / ".git"
        if current != prefix and (marker.exists() or marker.is_symlink()):
            raise ValueError("unsafe gh installation")
        if not pending:
            return current
        part = pending.pop(0)
        path = current / part
        if part == "..":
            if current == prefix:
                raise ValueError("unsafe gh installation")
            current = current.parent
        elif path.is_symlink():
            links += 1
            if links > 40:
                raise ValueError("unsafe gh installation")
            target = path.readlink()
            if target.is_absolute():
                # relative_to refuses targets outside this exact prefix.
                target = target.relative_to(prefix)
                current = prefix
            pending = list(target.parts) + pending
        else:
            current = path


def trusted_gh():
    # Search fixed installation locations, never workspace/relative PATH entries.
    for folder in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        candidate = Path(folder) / "gh"
        try:
            if folder == "/opt/homebrew/bin":
                resolved = homebrew_gh(candidate, Path("/opt/homebrew"), os.getuid())
                if stat.S_ISREG(resolved.stat().st_mode) and os.access(resolved, os.X_OK):
                    return str(resolved)
                continue
            resolved = candidate.resolve(strict=True)
            # Other fixed locations retain the strict ancestor checks.
            if not any(resolved.is_relative_to(root) for root in (Path("/opt/homebrew"), Path("/usr/local"), Path("/usr/bin"))):
                continue
            for path in (candidate.parent, resolved, *resolved.parents):
                info = path.stat()
                if info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022 or (path / ".git").exists():
                    raise ValueError("unsafe gh installation")
            if not stat.S_ISREG(resolved.stat().st_mode) or not os.access(resolved, os.X_OK):
                continue
            return str(resolved)
        except FileNotFoundError:
            continue
    raise CannotPost("no-cli")


def gh_call(executable, args, body=None):
    """Only the two fixed call sites below supply argv; never a shell."""
    try:
        result = subprocess.run([executable, *args], input=body, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30, shell=False, env=gh_environment(),
                                **({"stdin": subprocess.DEVNULL} if body is None else {}))
    except FileNotFoundError:
        raise CannotPost("no-cli") from None
    except subprocess.TimeoutExpired:
        raise CannotPost("no-network") from None
    except OSError:
        raise CannotPost("other") from None
    if result.returncode:
        error = result.stderr.lower()
        if any(word in error for word in ("authentication", "not logged", "http 401", "gh auth login")):
            reason = "no-auth"
        elif any(word in error for word in ("http 403", "permission", "not accessible")):
            reason = "no-permission"
        elif any(word in error for word in ("connect", "network", "timed out", "resolve host")):
            reason = "no-network"
        else:
            reason = "other"
        raise CannotPost(reason)
    return result.stdout


def view(executable, pr, repo):
    try:
        result = gh_call(executable, ["pr", "view", str(pr), "--repo", repo, "--json", "headRefOid,comments"])
        if len(result.encode()) > 4 * 1024 * 1024:
            raise ValueError("oversized view")
        data = json.loads(result)
        if (not isinstance(data, dict) or not isinstance(data.get("headRefOid"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", data["headRefOid"])
                or not isinstance(data.get("comments"), list)):
            raise ValueError("invalid view")
        return data
    except (ValueError, TypeError):
        raise CannotPost("other") from None


def post(pr, path, checkout):
    repo = checkout_remote(checkout)
    body = read_body(path)
    marker = marker_line(body)
    executable = trusted_gh()
    before = view(executable, pr, repo)
    if MARKER.fullmatch(marker)[2] != before["headRefOid"]:
        raise ValueError("reviewed head changed")
    # Supply the already verified bytes on stdin, so gh never reopens a swapped
    # body pathname. Everything after the marker is intentionally opaque.
    gh_call(executable, ["pr", "comment", str(pr), "--repo", repo, "--body-file", "-"], body)
    after = view(executable, pr, repo)
    if after["headRefOid"] != before["headRefOid"]:
        raise CannotPost("other")
    if not any(isinstance(c, dict) and c.get("body") == body for c in after["comments"]):
        raise CannotPost("other")
    # Delete only this validated run's draft, after observing the exact post.
    root = dr.consent_root()
    relative = Path(os.path.abspath(path)).relative_to(root / ROOT)
    with dr.data_folder(ROOT, private=True) as parent:
        with dr.descend(parent, relative.parts[0], private=True) as folder:
            os.unlink("body.md", dir_fd=folder)
        os.rmdir(relative.parts[0], dir_fd=parent)


def positive_pr(value):
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value):
        raise argparse.ArgumentTypeError("positive PR number required")
    return int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False, add_help=False)
    parser.add_argument("pr", type=positive_pr)
    parser.add_argument("--body-file")
    args = parser.parse_args(argv)
    try:
        if args.body_file is None:
            checkout_remote(Path.cwd())
            print(create_run_folder())
        else:
            post(args.pr, args.body_file, Path.cwd())
            print("posted")
        return 0
    except CannotPost as error:
        print("cannot-post: " + error.reason)
        return 1
    except (OSError, ValueError, UnicodeError, configparser.Error):
        print("invalid or unsafe review input", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
