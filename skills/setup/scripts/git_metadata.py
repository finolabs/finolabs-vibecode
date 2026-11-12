"""Owner-checked, no-follow local Git metadata reads; no Git processes or hooks."""
import os
from pathlib import Path
import stat
from contextlib import contextmanager


@contextmanager
def opened(path, *, directory=False, search=False):
    """Walk from / using descriptors, refusing links and special files.

    `search` opens a folder only to look for a `.git` entry in it, so the folder itself may also be owned by root,
    like every ancestor; anything read from inside it is checked again on its own.
    """
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(path.parts[1:]):
            last = index == len(path.parts) - 2
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if not last or directory:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            is_dir = not last or directory
            owners = {0, os.getuid()} if not last or search else {os.getuid()}
            # Root-owned sticky temporary ancestors are safe to traverse: every
            # following component is checked again. Never allow a writable leaf.
            sticky = (not last or search) and info.st_uid == 0 and info.st_mode & stat.S_ISVTX
            if (info.st_uid not in owners or (info.st_mode & 0o022 and not sticky)
                    or not (stat.S_ISDIR(info.st_mode) if is_dir else stat.S_ISREG(info.st_mode))):
                raise ValueError("unsafe git metadata")
        yield fd
    finally:
        os.close(fd)


def bounded(path, cap):
    with opened(path) as fd:
        if os.fstat(fd).st_size > cap:
            raise ValueError("oversized git data")
        chunks, size = [], 0
        while size <= cap:
            chunk = os.read(fd, min(65536, cap + 1 - size))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
    raise ValueError("oversized git data")


class NoCheckout(ValueError):
    """Every parent folder was checked and none holds a .git entry: positively no repository."""


def git_dirs(checkout):
    """Only reciprocal main-repo/.git/worktrees/name links are accepted."""
    return checkout_dirs(checkout)[1:]


def checkout_dirs(checkout):
    """(checkout root, git folder, common folder) under the rules of `git_dirs`; NoCheckout when there is none.

    Any other exception (an unreadable or unsafe folder, a .git link, a non-reciprocal linked layout) means the
    identity is unknown, never that there is no repository.
    """
    checkout = Path(os.path.abspath(checkout))
    for folder in (checkout, *checkout.parents):
        with opened(folder, directory=True, search=True) as fd:
            try:
                info = os.stat(".git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
        dot = folder / ".git"
        if stat.S_ISDIR(info.st_mode):
            with opened(dot, directory=True) as fd:
                try:
                    os.stat("commondir", dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    return folder, dot, dot
            raise ValueError("commondir outside linked worktree")
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("unsafe .git entry")
        line = bounded(dot, 4096).decode().strip()
        if not line.startswith("gitdir: ") or not line[8:]:
            raise ValueError("invalid gitdir")
        git = Path(os.path.abspath(folder / line[8:]))
        if (git.is_relative_to(folder) or git.parent.name != "worktrees"
                or git.parent.parent.name != ".git"):
            raise ValueError("invalid linked gitdir")
        common = git.parent.parent
        relative = bounded(git / "commondir", 4096).decode().strip()
        if not relative or Path(os.path.abspath(git / relative)) != common:
            raise ValueError("invalid commondir")
        back = bounded(git / "gitdir", 4096).decode().strip()
        if not back or Path(os.path.abspath(git / back)) != dot:
            raise ValueError("invalid worktree back-pointer")
        with opened(common, directory=True):
            return folder, git, common
    raise NoCheckout("no checkout")
