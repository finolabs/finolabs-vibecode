#!/usr/bin/env python3
"""Local working-tree restore points on private git refs; stdlib only."""

import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr  # noqa: E402

REF_PREFIX = "refs/finolabs/restore/"
NAME_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z(-[a-z0-9-]{1,20})?$")
SUFFIX_RE = re.compile(r"^[a-z0-9-]{1,20}$")
OID_RE = re.compile(r"^[0-9a-f]{40,64}$")
DIGEST_RE = re.compile(r"^[0-9a-fA-F]{8,64}$")
OUTSIDE_GIT_MSG = (
    "Not a git repository: this cannot help here. "
    "Run `git init` yourself to start one; nothing was created."
)
AUTHOR_NAME = "finolabs-vibecode"
AUTHOR_EMAIL = "restore-point@localhost"


def validate_name(name):
    """True only when name matches the restore-point timestamp grammar."""
    return isinstance(name, str) and bool(NAME_RE.fullmatch(name))


def clean_text(value):
    """Drop non-printable characters from filenames and status lines."""
    return "".join(c for c in value if c.isprintable())


def check_no_symlinks(path, root):
    """Refuse symlinks from the repository root down, allowing aliased parents."""
    path = Path(os.path.abspath(path))
    fd = os.open(root.parent.resolve(), os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in (root.name, *path.relative_to(root).parts):
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
    except OSError as exc:
        raise ValueError("Unsafe path: symlinked or unreadable directory component refused.") from exc
    finally:
        os.close(fd)


def check_git_dir_and_refs(root, name=None):
    """Refuse a symlinked .git or any ref path component that resolves through a symlink."""
    dot_git = root / ".git"
    try:
        git_stat = os.lstat(dot_git)
    except OSError as exc:
        raise ValueError("Unsafe path: cannot stat .git directory.") from exc
    if stat.S_ISLNK(git_stat.st_mode):
        raise ValueError("Unsafe path: .git must not be a symlink.")
    if stat.S_ISREG(git_stat.st_mode):
        lines = dot_git.read_text(encoding="utf-8").splitlines()
        if len(lines) != 1 or not lines[0].startswith("gitdir: ") or not lines[0][8:]:
            raise ValueError("Unsafe path: .git must contain one gitdir path.")
        dot_git = (root / lines[0][8:]).resolve()
        if not dot_git.is_dir() or dot_git.stat().st_uid != os.getuid():
            raise ValueError("Unsafe path: gitdir must be an existing directory owned by the user.")
    elif not stat.S_ISDIR(git_stat.st_mode):
        raise ValueError("Unsafe path: .git must be a directory or a gitdir file.")

    git_dirs = [dot_git]
    common_file = dot_git / "commondir"
    if common_file.is_symlink():
        raise ValueError("Unsafe path: symlink inside .git refused.")
    if common_file.exists():
        common_dir = (dot_git / common_file.read_text(encoding="utf-8").strip()).resolve()
        if not common_dir.is_dir() or common_dir.stat().st_uid != os.getuid():
            raise ValueError("Unsafe path: common gitdir must be an existing directory owned by the user.")
        git_dirs.append(common_dir)
    for git_dir in git_dirs:
        for entry in ("HEAD", "index", "packed-refs", "objects", "refs", "logs"):
            candidate = git_dir / entry
            if os.path.lexists(candidate) and os.path.islink(candidate):
                raise ValueError("Unsafe path: symlink inside .git refused.")

        for base in (git_dir / "refs", git_dir / "logs" / "refs"):
            if not os.path.lexists(base):
                continue
            if os.path.islink(base) or not stat.S_ISDIR(os.lstat(base).st_mode):
                raise ValueError("Unsafe path: symlink in ref path refused.")
            cur = base
            for part in ("finolabs", "restore"):
                cur = cur / part
                if not os.path.lexists(cur):
                    break
                st = os.lstat(cur)
                if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
                    raise ValueError("Unsafe path: symlink in ref path refused.")
            else:
                with os.scandir(cur) as entries:
                    for entry in entries:
                        if entry.is_symlink() or entry.is_dir(follow_symlinks=False):
                            raise ValueError("Unsafe path: symlink in ref path refused.")
                if name is not None and os.path.lexists(cur / name):
                    ref_stat = os.lstat(cur / name)
                    if stat.S_ISLNK(ref_stat.st_mode) or not stat.S_ISREG(ref_stat.st_mode):
                        raise ValueError("Unsafe path: symlink in ref path refused.")
    return dot_git


def find_repo_root(cwd=None):
    """Walk up from cwd to a .git entry; return None outside git or raise ValueError on symlinks."""
    if cwd is not None:
        start = Path(os.path.abspath(cwd))
    else:
        actual = Path(os.path.abspath(os.getcwd()))
        env_pwd = os.environ.get("PWD")
        start = actual
        if env_pwd and os.path.isabs(env_pwd):
            try:
                if os.path.samestat(os.stat(env_pwd), os.stat(actual)):
                    start = Path(os.path.abspath(env_pwd))
            except OSError:
                pass

    cur = start
    found = None
    while True:
        if os.path.lexists(cur / ".git"):
            found = cur
            break
        if cur == cur.parent:
            break
        cur = cur.parent

    if found is None:
        return None

    check_no_symlinks(start, found)
    found = found.resolve()
    if not start.resolve().is_relative_to(found):
        raise ValueError("Unsafe path: working directory is outside the repository root.")
    check_git_dir_and_refs(found)
    return found


def run_git(repo_root, args, extra_env=None, check=True):
    """Run git with a fixed argv list and neutral identity; never use a shell."""
    if not isinstance(args, (list, tuple)) or not all(isinstance(a, str) for a in args):
        raise ValueError("Invalid git arguments.")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
    }
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", "-c", "core.hooksPath=/dev/null",
         "-c", "core.fsmonitor=false", *args],
        cwd=str(repo_root),
        env=env,
        shell=False,
        capture_output=True,
        check=False,
        timeout=120 if args and args[0] in ("add", "checkout-index") else 15,
    )
    if check and result.returncode != 0:
        msg = clean_text(result.stderr.decode("utf-8", errors="replace").strip())
        raise RuntimeError(msg or "git command failed")
    return result


@contextmanager
def temp_index_env(repo_root, seed_from_real=True):
    """Provide a GIT_INDEX_FILE in a private 0700 temp directory removed on exit."""
    # The plugin's private temporary folder under the data root, never the system one.
    with dr.data_folder("tmp", create=True, private=True):
        pass
    root, source = dr.data_root()
    if source == "invalid":
        raise ValueError("The plugin data folder is not usable; run the setup check.")
    tmpdir = str(root / "tmp" / ("fnl-restore-" + os.urandom(8).hex()))
    os.mkdir(tmpdir, 0o700)
    try:
        temp_index = os.path.join(tmpdir, "index")
        env = {"GIT_INDEX_FILE": temp_index}
        real_index = check_git_dir_and_refs(repo_root) / "index"
        if seed_from_real and os.path.lexists(real_index):
            st = os.lstat(real_index)
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                raise ValueError("Unsafe path: .git/index must be a regular file.")
            shutil.copyfile(real_index, temp_index, follow_symlinks=False)
            # Keep Git's racy-index timestamp so same-size edits are rehashed.
            os.utime(temp_index, ns=(st.st_atime_ns, st.st_mtime_ns), follow_symlinks=False)
            os.chmod(temp_index, 0o600)
        else:
            run_git(repo_root, ["read-tree", "--empty"], extra_env=env)
        yield env
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def build_working_tree(repo_root):
    """Snapshot tracked, modified and non-ignored untracked files into a tree object."""
    with temp_index_env(repo_root, seed_from_real=True) as env:
        run_git(repo_root, ["add", "-A", "--", "."], extra_env=env)
        tree_oid = run_git(repo_root, ["write-tree"], extra_env=env).stdout.decode("utf-8").strip()
        if not OID_RE.fullmatch(tree_oid):
            raise RuntimeError("Invalid tree object from git write-tree.")
        ls_out = run_git(repo_root, ["ls-files", "-z"], extra_env=env).stdout
        file_count = sum(1 for entry in ls_out.split(b"\0") if entry)
        return tree_oid, file_count


def list_points(repo_root):
    """Return restore points newest first with name, ISO timestamp and changed-file count."""
    check_git_dir_and_refs(repo_root)
    res = run_git(
        repo_root,
        [
            "for-each-ref",
            "--format=%(refname)|%(objectname)|%(committerdate:iso8601-strict)",
            "refs/finolabs/restore",
        ],
    )
    points = []
    for raw_line in res.stdout.decode("utf-8", errors="replace").splitlines():
        if not raw_line.strip():
            continue
        parts = raw_line.split("|", 2)
        if len(parts) != 3:
            continue
        refname, oid, cdate = parts
        if not refname.startswith(REF_PREFIX):
            continue
        name = refname[len(REF_PREFIX):]
        if not validate_name(name) or not OID_RE.fullmatch(oid):
            continue
        parent_res = run_git(
            repo_root, ["rev-parse", "--verify", "--quiet", f"{oid}^1^{{commit}}"], check=False
        )
        parent_oid = parent_res.stdout.decode("utf-8").strip() if parent_res.returncode == 0 else ""
        if parent_oid and OID_RE.fullmatch(parent_oid):
            diff_out = run_git(
                repo_root,
                ["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", parent_oid, oid],
            ).stdout
        else:
            diff_out = run_git(repo_root, ["ls-tree", "-r", "--name-only", "-z", oid]).stdout
        changed = sum(1 for entry in diff_out.split(b"\0") if entry)
        points.append({"name": name, "ref": refname, "oid": oid, "time": clean_text(cdate), "changed": changed})

    points.sort(key=lambda item: (item["name"][:16], item["time"], item["name"]), reverse=True)
    return points


def next_timestamp(existing_points):
    """Choose a UTC timestamp that is strictly newer than any existing restore point."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for item in existing_points:
        try:
            existing_dt = datetime.strptime(item["name"][:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if existing_dt >= now:
            now = existing_dt + timedelta(seconds=1)
    return now


def create_point(repo_root, suffix=None):
    """Create a commit object on refs/finolabs/restore/<timestamp> without touching index or HEAD."""
    if suffix is not None and not SUFFIX_RE.fullmatch(suffix):
        raise ValueError("Invalid restore point suffix.")
    existing = list_points(repo_root)
    dt = next_timestamp(existing)
    stamp = dt.strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{suffix}" if suffix else stamp
    if not validate_name(name):
        raise ValueError("Invalid restore point name.")
    check_git_dir_and_refs(repo_root, name)

    tree_oid, file_count = build_working_tree(repo_root)
    head_res = run_git(repo_root, ["rev-parse", "--verify", "--quiet", "HEAD^{commit}"], check=False)
    head_oid = head_res.stdout.decode("utf-8").strip() if head_res.returncode == 0 else ""

    commit_args = ["commit-tree", tree_oid]
    if head_oid and OID_RE.fullmatch(head_oid):
        commit_args.extend(["-p", head_oid])
    commit_args.extend(["-m", f"restore point {name}"])

    iso_date = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    commit_oid = (
        run_git(
            repo_root,
            commit_args,
            extra_env={"GIT_AUTHOR_DATE": iso_date, "GIT_COMMITTER_DATE": iso_date},
        )
        .stdout.decode("utf-8")
        .strip()
    )
    if not OID_RE.fullmatch(commit_oid):
        raise RuntimeError("Invalid commit object from git commit-tree.")

    ref = REF_PREFIX + name
    run_git(repo_root, ["update-ref", ref, commit_oid])
    return name, ref, commit_oid, file_count


def check_target_paths_no_symlinks(repo_root, ref):
    """Refuse restoring through any symlinked path in the working tree."""
    out = run_git(repo_root, ["ls-tree", "-r", "--name-only", "-z", ref]).stdout
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = Path(raw.decode("utf-8", errors="surrogateescape"))
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe path in restore point tree.")
        cur = repo_root
        for part in rel.parts:
            cur = cur / part
            if os.path.lexists(cur) and os.path.islink(cur):
                raise ValueError("Unsafe path: symlink in working tree refused.")


def format_list(items, limit=12):
    if not items:
        return "none"
    shown = ", ".join(items[:limit])
    if len(items) > limit:
        shown += f" (+{len(items) - limit} more)"
    return shown


def cmd_create(repo_root):
    _, ref, _, file_count = create_point(repo_root)
    noun = "file" if file_count == 1 else "files"
    print(f"Created {ref} ({file_count} {noun}).")
    return 0


def cmd_list(repo_root):
    points = list_points(repo_root)
    if not points:
        print("No restore points.")
        return 0
    for item in points[:35]:
        noun = "file" if item["changed"] == 1 else "files"
        print(f'{item["name"]}  {item["time"]}  {item["changed"]} {noun} changed')
    if len(points) > 35:
        print(f"... ({len(points) - 35} older restore points omitted)")
    return 0


def cmd_restore(repo_root, name, yes=False, digest_arg=None):
    if not validate_name(name):
        raise ValueError("Invalid restore point name; nothing written.")
    check_git_dir_and_refs(repo_root, name)
    ref = REF_PREFIX + name
    verify = run_git(repo_root, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], check=False)
    if verify.returncode != 0:
        print(f"Restore point {clean_text(name)} not found; nothing written.")
        return 0

    point_oid = verify.stdout.decode("utf-8").strip()
    if not OID_RE.fullmatch(point_oid):
        raise RuntimeError("Invalid restore point commit object.")
    current_tree, _ = build_working_tree(repo_root)
    stat_raw = run_git(
        repo_root, ["diff", "--no-renames", "--stat", "--stat-width=120", "--stat-name-width=80", current_tree, point_oid]
    ).stdout.decode("utf-8", errors="replace")
    stat_lines = [clean_text(line) for line in stat_raw.splitlines() if line.strip()]

    ns_raw = run_git(
        repo_root, ["diff", "--no-renames", "--name-status", "-z", current_tree, point_oid]
    ).stdout
    tokens = [tok.decode("utf-8", errors="replace") for tok in ns_raw.split(b"\0") if tok]
    changes = []
    overwritten = []
    kept = []
    for i in range(0, len(tokens) - 1, 2):
        status = clean_text(tokens[i])
        filepath = clean_text(tokens[i + 1])
        if len(filepath) > 80:
            filepath = filepath[:77] + "..."
        changes.append((status, filepath))
        if status.startswith(("M", "T")):
            overwritten.append(filepath)
        elif status.startswith("D"):
            kept.append(filepath)

    preview_lines = [f"Restore preview for {name} ({ref}):"]
    if stat_lines:
        if len(stat_lines) <= 10:
            preview_lines.extend(stat_lines)
        else:
            preview_lines.extend(stat_lines[:8])
            preview_lines.append(f" ... ({len(stat_lines) - 9} more stat lines)")
            preview_lines.append(stat_lines[-1])
    else:
        preview_lines.append("No file differences between working tree and restore point.")

    if changes:
        preview_lines.append("Changed files (name-status):")
        for status, filepath in changes[:10]:
            preview_lines.append(f"  {status}\t{filepath}")
        if len(changes) > 10:
            preview_lines.append(f"  ... ({len(changes) - 10} more files)")
    else:
        preview_lines.append("Changed files (name-status): none")

    preview_lines.append("Would overwrite: " + format_list(overwritten))
    preview_lines.append(
        "Exist now but not in restore point (kept, NOT deleted): " + format_list(kept)
    )

    preview_text = "\n".join(preview_lines)
    digest = hashlib.sha256(f"{point_oid}\n{current_tree}\n{preview_text}".encode("utf-8")).hexdigest()
    print(preview_text)
    print(f"Digest: {digest}")

    if not yes:
        print("Preview only; confirm with --yes --digest <prefix> to write.")
        return 0

    if not digest_arg or not DIGEST_RE.fullmatch(digest_arg) or not digest.startswith(digest_arg.lower()):
        print("Digest missing or mismatched; nothing written.")
        return 0

    check_target_paths_no_symlinks(repo_root, point_oid)
    _, pre_ref, _, _ = create_point(repo_root, suffix="pre-restore")
    try:
        with temp_index_env(repo_root, seed_from_real=False) as env:
            run_git(repo_root, ["read-tree", point_oid], extra_env=env)
            run_git(repo_root, ["checkout-index", "-a", "-f", "--prefix="], extra_env=env)
    except (subprocess.SubprocessError, OSError, RuntimeError, UnicodeError, ValueError) as exc:
        raise RuntimeError(
            f"Restore failed: {clean_text(str(exc))}; saved pre-restore point {pre_ref}; "
            "the tree may be partly restored; restoring that point undoes changes to captured files. "
            "Extra files are kept; symlinked paths require manual review."
        ) from exc
    print(f"Saved pre-restore point {pre_ref} and restored {ref}.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("create", help="create a restore point from the working tree")
    subparsers.add_parser("list", help="list restore points newest first")
    restore_parser = subparsers.add_parser("restore", help="preview or restore a named point")
    restore_parser.add_argument("name", help="restore point name (YYYYMMDDTHHMMSSZ)")
    restore_parser.add_argument("--yes", action="store_true", help="write after user confirmation")
    restore_parser.add_argument("--digest", help="SHA-256 prefix (at least 8 hex characters) from preview")
    return parser


def main(argv=None, cwd=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "restore" and not validate_name(args.name):
            print("Invalid restore point name; nothing written.")
            return 0
        repo_root = find_repo_root(cwd)
        if repo_root is None:
            print(OUTSIDE_GIT_MSG)
            return 0
        if args.action == "create":
            return cmd_create(repo_root)
        if args.action == "list":
            return cmd_list(repo_root)
        if args.action == "restore":
            return cmd_restore(repo_root, args.name, yes=args.yes, digest_arg=args.digest)
    except (subprocess.SubprocessError, OSError, RuntimeError, UnicodeError, ValueError) as exc:
        line = clean_text(str(exc)).splitlines()[0] if str(exc) else "Restore point unavailable; nothing written."
        print(line)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
