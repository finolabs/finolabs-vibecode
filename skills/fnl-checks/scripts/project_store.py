#!/usr/bin/env python3
"""Validated repository identity and the project-scoped settings file, without running git.

User scope is the data root; project scope is the same relative path (`PROJECT_FOLDERS`) inside the main checkout.
A linked worktree shares its main checkout's identity and folder only in the canonical, reciprocal, owner- and
mode-checked layout `<main>/.git/worktrees/<name>` that `git_metadata.git_dirs` requires; anything else resolves to
the checkout's own root. `settings.json` there counts only while its exact bytes match the SHA-256
approved in the private state folder, so a branch cannot raise `parallel` or redirect `tasks`. An invalid,
unapproved or unreadable file reads as unset and is never repaired on read. Makes no network call and runs nothing.
"""
from contextlib import contextmanager
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

PROJECT_FOLDERS = ('.finolabs', 'vibecode')
SETTINGS_FILE = 'settings.json'
SETTINGS_LIMIT = 16384
SETTINGS_APPROVED = 'state/settings-approved'
SETTING_KEYS = ('ledger', 'tasks', 'parallel', 'parallel-caps', 'label')
METADATA_LIMIT = 4096
CODE = re.compile(r'[0-9a-f]{8}')
DIGEST = re.compile(r'[0-9a-f]{64}')
LABEL = re.compile(r'[A-Za-z0-9 ._-]{1,40}')
INSTRUCTION_FILES = ('CLAUDE.MD', 'CLAUDE.LOCAL.MD', 'AGENTS.MD', 'AGENTS.OVERRIDE.MD', 'GEMINI.MD',
                     'COPILOT-INSTRUCTIONS.MD', 'CONVENTIONS.MD', '.CURSORRULES', '.WINDSURFRULES', '.CLINERULES')
EXCLUDE_LINE = b'.finolabs/\n'
EXCLUDE_FORMS = {'.finolabs/', '.finolabs', '/.finolabs/', '/.finolabs', '.finolabs/*', '/.finolabs/*'}


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


@contextmanager
def _guarded(path, *, directory=False):
    """`git_metadata.opened`: walk from / with no-follow descriptors; every folder owned by root or this account and
    not group- or world-writable (a root-owned sticky ancestor excepted), the leaf owned by this account."""
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(path.parts[1:]):
            last = index == len(path.parts) - 2
            is_dir = not last or directory
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_DIRECTORY if is_dir else 0)
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            owners = {os.getuid()} if last else {0, os.getuid()}
            sticky = not last and info.st_uid == 0 and info.st_mode & stat.S_ISVTX
            if (info.st_uid not in owners or (info.st_mode & 0o022 and not sticky)
                    or not (stat.S_ISDIR(info.st_mode) if is_dir else stat.S_ISREG(info.st_mode))):
                raise ValueError('unsafe git metadata')
        yield fd
    finally:
        os.close(fd)


def _guarded_line(path):
    """One stripped line of a small metadata file opened through `_guarded`."""
    with _guarded(path) as fd:
        if os.fstat(fd).st_size > METADATA_LIMIT:
            raise ValueError('invalid repository metadata')
        data = os.read(fd, METADATA_LIMIT + 1)
    if len(data) > METADATA_LIMIT:
        raise ValueError('invalid repository metadata')
    return data.decode('utf-8').strip()


def layout(root):
    """(main checkout root, git common folder) of a repository root, the rules of `git_metadata.git_dirs`.

    A `.git` file counts as a linked worktree only in the canonical layout `<main>/.git/worktrees/<name>`: that
    folder lies outside this checkout, its `commondir` resolves to `<main>/.git`, and its `gitdir` points back to this
    checkout's `.git`. Every file and folder on the way is owner- and mode-checked. Anything else is the checkout's own
    root, so it cannot borrow another repository's identity, settings, checks or exclude file.
    """
    root = Path(os.path.abspath(root))
    own = (root, root / '.git')
    try:
        line = _guarded_line(root / '.git')
        if not line.startswith('gitdir:'):
            return own
        gitdir = Path(os.path.abspath(root / line[len('gitdir:'):].strip()))
        common = gitdir.parent.parent
        if (gitdir.parent.name != 'worktrees' or common.name != '.git' or not gitdir.name
                or gitdir.is_relative_to(root)):
            return own
        relative = _guarded_line(gitdir / 'commondir')
        if not relative or Path(os.path.abspath(gitdir / relative)) != common:
            return own
        back = _guarded_line(gitdir / 'gitdir')
        if not back or Path(os.path.abspath(gitdir / back)) != root / '.git':
            return own
        with _guarded(gitdir, directory=True), _guarded(common, directory=True):
            pass
        return common.parent, common
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


# Settings values, validated exactly as the host.md entries were

def valid_setting(key, value):
    if not isinstance(value, str):
        return False
    if key == 'parallel':
        return bool(re.fullmatch(r'[0-9]{1,2}', value) and 1 <= int(value) <= 32)
    if key == 'parallel-caps':
        seen = set()
        for item in value.split(','):
            match = re.fullmatch(r'(claude|codex|antigravity)=([0-9]{1,2})', item.strip())
            if not match or not 1 <= int(match[2]) <= 32 or match[1] in seen:
                return False
            seen.add(match[1])
        return True
    if key in ('ledger', 'label'):
        return bool(LABEL.fullmatch(value) and value.strip())
    if key == 'tasks':
        return bool(re.fullmatch(r'[A-Za-z0-9._/-]{1,120}', value) and value.endswith('.md')
                    and all(part not in ('', '.', '..') for part in value.split('/'))
                    and value.split('/')[:2] != ['specs', 'archive']
                    and value.split('/')[-1].upper() not in INSTRUCTION_FILES)
    return False


def _object(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate key')
    return dict(pairs)


def _constant(value):
    raise ValueError('constant')


def parse_settings(raw):
    """The settings of the closed schema `{"version": 1, <key>: "<value>", ...}`; anything else raises."""
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
    if (not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1
            or not set(data) - {'version'} <= set(SETTING_KEYS)):
        raise ValueError('invalid settings file')
    values = {key: value for key, value in data.items() if key != 'version'}
    for key, value in values.items():
        if not valid_setting(key, value):
            raise ValueError('invalid settings file')
    return values


def render_settings(values):
    """The exact bytes a writer stores: the version, then every set key in fixed order."""
    data = {'version': 1}
    for key in SETTING_KEYS:
        if key in values:
            data[key] = values[key]
    raw = (json.dumps(data, indent=2, ensure_ascii=True) + '\n').encode()
    parse_settings(raw)
    return raw


def read_approved(code):
    """The approved SHA-256 of this repository's settings file; FileNotFoundError when none, ValueError when invalid."""
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise ValueError('invalid code')
    with dr.data_folder(SETTINGS_APPROVED, private=True) as folder:
        record = json.loads(dr.read_file(folder, code + '.json', 4096), object_pairs_hook=_object)
    if (not isinstance(record, dict) or set(record) != {'sha256', 'approved'} or not isinstance(record['sha256'], str)
            or not DIGEST.fullmatch(record['sha256']) or type(record['approved']) is not int
            or record['approved'] < 0):
        raise ValueError('invalid approval')
    return record['sha256']


def read_settings(root):
    """This repository's approved settings as a dict of set keys; every doubt is unset (an empty dict).

    `root` is the repository root of the caller's checkout; None means no repository, which is unset too.
    """
    if root is None:
        return {}
    try:
        main, _ = layout(root)
        with project_folder(main) as folder:
            raw = read_project_file(folder, SETTINGS_FILE, SETTINGS_LIMIT)
        if read_approved(code_of(main)) != hashlib.sha256(raw).hexdigest():
            return {}
        return parse_settings(raw)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return {}


def _write_approval(folder, code, raw):
    record = {'sha256': hashlib.sha256(raw).hexdigest(), 'approved': int(time.time())}
    dr.atomic_write(folder, code + '.json', json.dumps(record, sort_keys=True).encode())


def write_setting(root, key, value):
    """Set (or clear, with None) one key in this repository's settings file and approve the new bytes.

    Starts from what readers see: an unapproved or invalid file counts as unset, so its values are never carried
    forward. Returns False when nothing changed. Never opens host.md.
    """
    if key not in SETTING_KEYS or value is not None and not valid_setting(key, value):
        raise ValueError('invalid project setting')
    main, _ = layout(root)
    code = code_of(main)
    with dr.data_folder(SETTINGS_APPROVED, create=True, private=True) as approvals:
        fcntl.flock(approvals, fcntl.LOCK_EX | fcntl.LOCK_NB)
        values = read_settings(root)
        if values.get(key) == value:
            return False
        if value is None:
            values.pop(key)
        else:
            values[key] = value
        raw = render_settings(values)
        with project_folder(main, create=True) as folder:
            if values:
                dr.atomic_write(folder, SETTINGS_FILE, raw)
                _write_approval(approvals, code, raw)
            else:
                try:
                    os.unlink(SETTINGS_FILE, dir_fd=folder)
                    os.fsync(folder)
                except FileNotFoundError:
                    pass
                try:
                    os.unlink(code + '.json', dir_fd=approvals)
                    os.fsync(approvals)
                except FileNotFoundError:
                    pass
    return True


def ensure_excluded(root):
    """Add `.finolabs/` to `<main>/.git/info/exclude` of the validated layout when missing, never to a tracked
    .gitignore and never under any other folder.

    True when the line is present afterwards; False when it could not be added (a link, an unsafe file, no folder).
    """
    try:
        main, common = layout(root)
        if common != main / '.git':
            return False
        with _guarded(common, directory=True) as git:
            try:
                os.mkdir('info', 0o755, dir_fd=git)
            except FileExistsError:
                pass
            info = os.open('info', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=git)
            try:
                if os.fstat(info).st_uid != os.getuid() or os.fstat(info).st_mode & 0o022:
                    return False
                try:
                    raw = dr.read_file(info, 'exclude', 262144)
                    mode = stat.S_IMODE(os.stat('exclude', dir_fd=info, follow_symlinks=False).st_mode)
                except FileNotFoundError:
                    raw, mode = b'', 0o644
                lines = {line.strip() for line in raw.decode('utf-8', 'replace').splitlines()}
                if lines & EXCLUDE_FORMS:
                    return True
                if raw and not raw.endswith(b'\n'):
                    raw += b'\n'
                temporary = '.write-' + os.urandom(12).hex()
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=info)
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        os.fchmod(stream.fileno(), mode)
                        stream.write(raw + EXCLUDE_LINE)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, 'exclude', src_dir_fd=info, dst_dir_fd=info)
                    os.fsync(info)
                finally:
                    try:
                        os.unlink(temporary, dir_fd=info)
                    except FileNotFoundError:
                        pass
                return True
            finally:
                os.close(info)
    except (OSError, ValueError, UnicodeError):
        return False
