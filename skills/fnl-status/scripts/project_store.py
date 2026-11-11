#!/usr/bin/env python3
"""Validated repository identity and the project data folder, without running git.

User scope is the data root; project scope is the same relative path (`PROJECT_FOLDERS`) inside the main checkout.
A linked worktree shares its main checkout's identity and folder only when its metadata is reciprocal, as
`git_metadata.git_dirs` requires; anything else resolves to the checkout's own root. Makes no network call and runs
nothing.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True

PROJECT_FOLDERS = ('.finolabs', 'vibecode')
METADATA_LIMIT = 4096


@contextmanager
def open_dir(path):
    """Open every absolute component without following symlinks, including ancestors."""
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_metadata(path, name):
    """One stripped line of a small regular file this account owns, opened with no-follow descent."""
    with open_dir(path) as folder:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > METADATA_LIMIT:
                raise ValueError('invalid repository metadata')
            data = os.read(fd, METADATA_LIMIT + 1)
        finally:
            os.close(fd)
    if len(data) > METADATA_LIMIT:
        raise ValueError('invalid repository metadata')
    return data.decode('utf-8').strip()


def layout(root):
    """(main checkout root, git common folder) of a repository root.

    A `.git` file counts as a linked worktree only when it is reciprocal: its gitdir is `<common>/worktrees/<name>`
    outside this checkout, that folder's `commondir` resolves to `<common>`, and its `gitdir` points back to this
    checkout's `.git`. Anything else is the checkout's own root, so it cannot borrow another repository's identity.
    """
    root = Path(os.path.abspath(root))
    own = (root, root / '.git')
    try:
        line = read_metadata(root, '.git')
        if not line.startswith('gitdir:'):
            return own
        gitdir = Path(os.path.abspath(root / line[len('gitdir:'):].strip()))
        common = gitdir.parent.parent
        if gitdir.parent.name != 'worktrees' or not gitdir.name or gitdir.is_relative_to(root):
            return own
        relative = read_metadata(gitdir, 'commondir')
        if not relative or Path(os.path.abspath(gitdir / relative)) != common:
            return own
        back = read_metadata(gitdir, 'gitdir')
        if not back or Path(os.path.abspath(gitdir / back)) != root / '.git':
            return own
        with open_dir(common):
            pass
        return (common.parent if common.name == '.git' else common), common
    except (OSError, ValueError, UnicodeError):
        return own


def code_of(main):
    return hashlib.sha256(str(main).encode('utf-8')).hexdigest()[:8]


def repository_code(root):
    """The 8-hex identity of a checkout: its main checkout root for a reciprocal linked worktree, else its own."""
    return code_of(layout(root)[0])


@contextmanager
def project_folder(main, create=False):
    """An fd of the project data folder under <main> opened with no-follow descent from the filesystem root; each folder owned by
    this account and not writable by others. Created folders are 0700. A link anywhere on the path is refused."""
    with open_dir(main) as top:
        fd = os.dup(top)
        try:
            for part in PROJECT_FOLDERS:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                os.close(fd)
                fd = child
                info = os.fstat(fd)
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                    raise ValueError('unsafe project folder')
            yield fd
        finally:
            os.close(fd)


def read_project_file(folder, name, limit):
    """A project file's bytes; FileNotFoundError when absent, ValueError when linked, unsafe or too large."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022
                or info.st_size > limit):
            raise ValueError('unsafe project file')
        data = os.read(fd, limit + 1)
        if len(data) > limit:
            raise ValueError('project file too large')
        return data
    finally:
        os.close(fd)
