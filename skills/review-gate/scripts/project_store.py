#!/usr/bin/env python3
"""Validated repository identity and the project-scoped settings file, without running git.

User scope is the data root; project scope is the same relative path (`PROJECT_FOLDERS`) inside the main checkout.
A linked worktree shares its main checkout's identity and folder only in the canonical, reciprocal, owner- and
mode-checked layout `<main>/.git/worktrees/<name>` that `git_metadata.git_dirs` requires. Two readers apply that
rule: `identity` (authorization: away permissions, their setup writer, branch and remote reads) reports a rejected
layout as unknown, and `layout` (display, capacity, labels and checks) resolves it to the checkout's own root.
`settings.json` there counts only while its exact bytes match the SHA-256
approved in the private state folder, so a branch cannot raise `parallel` or redirect `tasks`. A file with no
approval record reads as unset; an approved file that is now missing, invalid, unsafe or changed is broken, which
capacity and ledger readers report as unknown (`settings_state`) and writers refuse to change. The approval of an
`autopilot` object also records the GitHub repository origin named when it was approved (`target`); a reader treats
a different origin as broken. Nothing is repaired on read; `reset_settings` discards every setting to recover. Makes
no network call and runs nothing.
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
from typing import NamedTuple

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import git_metadata

PROJECT_FOLDERS = ('.finolabs', 'vibecode')
SETTINGS_FILE = 'settings.json'
SETTINGS_LIMIT = 16384
SETTINGS_APPROVED = 'state/settings-approved'
SETTING_KEYS = ('ledger', 'tasks', 'parallel', 'parallel-caps', 'label', 'autopilot')
# The project-scoped away keys (docs/specs/autopilot.md "Project scope"), in stored order; every other autopilot
# key is user scope only, so a project file cannot carry it.
AUTOPILOT_KEYS = {'task-choice': ('choose', 'listed'), 'push-and-pull-requests': ('yes', 'no'),
                  'merge': ('yes', 'no'), 'trusted-authors': ('own',), 'roots': None}
ROOT_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
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


class Identity(NamedTuple):
    """A validated repository: its checkout root, main checkout root, own Git folder and common Git folder."""
    checkout: Path
    main: Path
    git: Path
    common: Path


def identity(cwd):
    """('found', Identity), ('absent', None) or ('unknown', None): the one repository identity authorization uses.

    `git_metadata.checkout_dirs` checks the working directory and every parent with no depth bound and accepts a
    linked worktree only in the canonical, reciprocal, owner- and mode-checked layout. Absent means every parent was
    checked and none holds `.git`. A rejected layout, an unreadable or unsafe folder, a `.git` link or a common folder
    not named `.git` is unknown, never the checkout's own identity.
    """
    try:
        checkout, git, common = git_metadata.checkout_dirs(cwd)
    except git_metadata.NoCheckout:
        return 'absent', None
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return 'unknown', None
    if common.name != '.git':
        return 'unknown', None
    return 'found', Identity(checkout, common.parent, git, common)


# The repository a GitHub mutation may name, read from the identity's own Git config as local metadata.
GITHUB = 'github.com'
OWNER_OR_NAME = re.compile(r'[A-Za-z0-9_.-]{1,100}')
TARGET = re.compile(r'github\.com/[a-z0-9_.-]{1,100}/[a-z0-9_.-]{1,100}')
SECTION = re.compile(r'\s*\[\s*([A-Za-z0-9-]+)(?:\s+"((?:[^"\\\n]|\\.)*)")?\s*\]\s*(?:[#;].*)?')
ENTRY = re.compile(r'\s*([A-Za-z][A-Za-z0-9-]*)\s*(?:=\s*(.*?))?\s*')
# Remote keys this reader understands; any other (mirror, receivepack, vcs, proxy...) is doubt.
REMOTE_KEYS = {'url', 'pushurl', 'fetch', 'gh-resolved', 'tagopt', 'prune', 'prunetags', 'push', 'skipdefaultupdate',
               'skipfetchall', 'followremotehead'}


def repository_target(host, owner, name):
    """`github.com/<owner>/<name>` casefolded for a GitHub repository, or None for anything else."""
    name = name.removesuffix('.git')
    if host.casefold() != GITHUB or not all(OWNER_OR_NAME.fullmatch(p) and p not in {'.', '..'} for p in (owner, name)):
        return None
    return '/'.join((GITHUB, owner.casefold(), name.casefold()))


def url_target(url):
    """The repository of a plain GitHub remote URL (https, ssh:// or scp form); None for any other form."""
    for pattern in (r'https://([A-Za-z0-9.-]+)/([^/]+)/([^/]+)', r'ssh://git@([A-Za-z0-9.-]+)/([^/]+)/([^/]+)',
                    r'git@([A-Za-z0-9.-]+):([^/]+)/([^/]+)'):
        match = re.fullmatch(pattern, url)
        if match:
            return repository_target(*match.groups())
    return None


def remote_config(ident):
    """{remote: {key: [value, ...]}} from the identity's own Git config; None on any doubt.

    Doubt: no config, a per-worktree config, an include, a URL rewrite (insteadOf, pushInsteadOf), a continuation
    line, a remote key outside `REMOTE_KEYS` or any line this small reader does not recognize. Global and system
    config are not read (an advisory limit in the spec). Raises on unsafe or unreadable metadata.
    """
    for folder in {ident.git, ident.common}:
        with git_metadata.opened(folder, directory=True) as fd:
            try:
                os.stat('config.worktree', dir_fd=fd, follow_symlinks=False)
                return None
            except FileNotFoundError:
                pass
    text = git_metadata.bounded(ident.common / 'config', 65536).decode('utf-8')
    found, section, subsection = {}, None, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(('#', ';')):
            continue
        if line.rstrip().endswith('\\'):
            return None
        header = SECTION.fullmatch(line)
        if header:
            section, subsection = header[1].casefold(), header[2]
            if section in {'include', 'includeif', 'url'}:
                return None
            if section == 'remote':
                if subsection is None:
                    return None
                found.setdefault(subsection, {})
            continue
        entry = ENTRY.fullmatch(line)
        if not entry or section is None:
            return None
        key = entry[1].casefold()
        if key in {'insteadof', 'pushinsteadof'}:
            return None
        if section == 'remote':
            if key not in REMOTE_KEYS:
                return None
            if key in {'url', 'pushurl'} and (not entry[2] or not re.fullmatch(r'[^\s"\\#;]+', entry[2])):
                return None
            found[subsection].setdefault(key, []).append(entry[2] or '')
    return found


def _origin(ident):
    try:
        config = remote_config(ident) if ident is not None else None
    except (OSError, ValueError, UnicodeError):
        return None
    return None if config is None else config.get('origin', {})


def origin_target(ident):
    """The GitHub repository of origin's single fetch URL, or None."""
    origin = _origin(ident)
    urls = (origin or {}).get('url', [])
    return url_target(urls[0]) if len(urls) == 1 else None


def push_target(ident):
    """The GitHub repository `git push origin` would update (its single pushurl, else its single url), or None."""
    origin = _origin(ident) or {}
    urls, destinations = origin.get('url', []), origin.get('pushurl', []) or origin.get('url', [])
    return url_target(destinations[0]) if len(urls) == 1 and len(destinations) == 1 else None


def layout(root):
    """(main checkout root, git common folder) of a repository root, the rules of `git_metadata.git_dirs`.

    A `.git` file counts as a linked worktree only in the canonical layout `<main>/.git/worktrees/<name>`: that
    folder lies outside this checkout, its `commondir` resolves to `<main>/.git`, and its `gitdir` points back to this
    checkout's `.git`. Every file and folder on the way is owner- and mode-checked. Anything else is the checkout's own
    root, so it cannot borrow another repository's identity, settings, checks or exclude file. Display, capacity and
    checks readers only: authorization uses `identity`, where a rejected layout is unknown.
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

def valid_autopilot(value):
    """The closed `autopilot` object: at least one project-scoped key, each with a fixed value or a roots list."""
    if not isinstance(value, dict) or not value or not set(value) <= set(AUTOPILOT_KEYS):
        return False
    for key, item in value.items():
        if key == 'roots':
            if (not isinstance(item, list) or not 1 <= len(item) <= 16 or len(set(map(str, item))) != len(item)
                    or not all(isinstance(name, str) and ROOT_NAME.fullmatch(name)
                               and name.upper() not in INSTRUCTION_FILES for name in item)):
                return False
        elif not isinstance(item, str) or item not in AUTOPILOT_KEYS[key]:
            return False
    return True


def autopilot_value(text):
    """The canonical `autopilot` object of a JSON string (fixed key order); ValueError when it is not valid."""
    if not isinstance(text, str) or len(text) > 4096:
        raise ValueError('invalid project setting')
    value = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    if not valid_autopilot(value):
        raise ValueError('invalid project setting')
    return {key: value[key] for key in AUTOPILOT_KEYS if key in value}


def valid_setting(key, value):
    if key == 'autopilot':
        return valid_autopilot(value)
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
    """The settings of the closed schema `{"version": 1, <key>: "<value>", ..., "autopilot": {...}}`; anything else
    raises."""
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
        if key == 'autopilot' and key in values and isinstance(values[key], dict):
            data[key] = {name: values[key][name] for name in AUTOPILOT_KEYS if name in values[key]}
        elif key in values:
            data[key] = values[key]
    raw = (json.dumps(data, indent=2, ensure_ascii=True) + '\n').encode()
    parse_settings(raw)
    return raw


def read_record(code):
    """This repository's approval record `{sha256, approved[, target]}`; FileNotFoundError when none, ValueError when
    invalid. `target` is the GitHub repository (`github.com/<owner>/<name>`, or null) its `autopilot` object is bound
    to."""
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise ValueError('invalid code')
    with dr.data_folder(SETTINGS_APPROVED, private=True) as folder:
        record = json.loads(dr.read_file(folder, code + '.json', 4096), object_pairs_hook=_object)
    if (not isinstance(record, dict) or set(record) - {'target'} != {'sha256', 'approved'}
            or not isinstance(record['sha256'], str) or not DIGEST.fullmatch(record['sha256'])
            or type(record['approved']) is not int or record['approved'] < 0
            or record.get('target') is not None and not (isinstance(record['target'], str)
                                                         and TARGET.fullmatch(record['target']))):
        raise ValueError('invalid approval')
    return record


def read_approved(code):
    """The approved SHA-256 of this repository's settings file; FileNotFoundError when none, ValueError when invalid."""
    return read_record(code)['sha256']


class SettingsNeedSetup(ValueError):
    """An approved settings file is now missing, unreadable, unsafe, malformed or changed: limits are unknown."""


def _read_state(main):
    """(state, values, approved digest or None, approval record or None) of the settings under one main root."""
    try:
        record = read_record(code_of(main))
    except FileNotFoundError:
        return 'unset', {}, None, None
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return 'broken', {}, None, None
    try:
        with project_folder(main) as folder:
            raw = read_project_file(folder, SETTINGS_FILE, SETTINGS_LIMIT)
        digest = hashlib.sha256(raw).hexdigest()
        if record['sha256'] != digest:
            return 'broken', {}, None, None
        return 'approved', parse_settings(raw), digest, record
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return 'broken', {}, None, None


def settings_state(root):
    """('unset', {}), ('approved', values) or ('broken', {}) for this repository's settings file.

    Unset means no approval record: never configured, or a file nobody approved here (a branch-supplied file sets
    nothing). Broken means an approval record exists but the file is missing, unreadable, unsafe, malformed or its
    digest differs, or the record itself cannot be read; callers then report unknown instead of the defaults.
    `root` None means no repository, which is unset. Resolved through `layout`, so never used for authorization.
    """
    if root is None:
        return 'unset', {}
    try:
        main, _ = layout(root)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return 'broken', {}
    return _read_state(main)[:2]


def autopilot_binding(ident):
    """(state, values, approved digest, approval record) of a validated identity's settings, for authorization."""
    return _read_state(ident.main)


def preview_token(ident, state, prior, target, value):
    """The SHA-256 a setup preview shows and its apply must repeat: identity, prior state and digest, the origin the
    approval would bind and the desired `autopilot` object (None to remove it)."""
    payload = [str(ident.checkout), str(ident.main), state, prior, target, value]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_settings(root):
    """This repository's approved settings as a dict of set keys; unset and broken are both empty here, so task-file
    and label readers fall back to off and none. Capacity and ledger readers use `settings_state` to tell them apart."""
    return settings_state(root)[1]


def _write_approval(folder, code, raw, binding):
    record = {'sha256': hashlib.sha256(raw).hexdigest(), 'approved': int(time.time()), **binding}
    dr.atomic_write(folder, code + '.json', json.dumps(record, sort_keys=True).encode())


def _remove(name, folder):
    try:
        os.unlink(name, dir_fd=folder)
        os.fsync(folder)
    except FileNotFoundError:
        pass


def write_setting(root, key, value, ident=None, expect=None):
    """Set (or clear, with None) one key in this repository's settings file and approve the new bytes.

    Starts from the full settings state: unset starts empty (an unapproved file's values are never carried forward),
    approved starts from the approved values, and broken raises `SettingsNeedSetup` with nothing written, so a
    partial update never drops the keys the broken file held; `reset_settings` is the recovery. Returns False when
    nothing changed. Never opens host.md.

    The `autopilot` object is written only for a validated `ident` (never the `layout` fallback); its approval binds
    the origin read now, and `expect`, when given, must equal the `preview_token` of the state found under the lock,
    so a concurrent change or a new origin refuses the write. Other keys carry the recorded binding forward unchanged.
    The settings file is written before its approval, so an interrupted pair reads as broken.
    """
    if key not in SETTING_KEYS or value is not None and not valid_setting(key, value):
        raise ValueError('invalid project setting')
    if key == 'autopilot' and not isinstance(ident, Identity):
        raise ValueError('away settings need a validated repository identity')
    main = ident.main if isinstance(ident, Identity) else layout(root)[0]
    code = code_of(main)
    with dr.data_folder(SETTINGS_APPROVED, create=True, private=True) as approvals:
        fcntl.flock(approvals, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state, values, prior, record = _read_state(main)
        if state not in ('unset', 'approved'):
            raise SettingsNeedSetup('project settings need setup again')
        if key == 'autopilot':
            target = origin_target(ident)
            if expect is not None and expect != preview_token(ident, state, prior, target, value):
                raise ValueError('the shown preview is stale')
            binding = {'target': target}
            same = (record or {}).get('target', ...) == target or 'autopilot' not in values
        else:
            binding = {'target': record['target']} if record and 'target' in record else {}
            same = True
        values = dict(values)
        if values.get(key) == value and same:
            return False
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
        raw = render_settings(values)
        with project_folder(main, create=True) as folder:
            if values:
                dr.atomic_write(folder, SETTINGS_FILE, raw)
                _write_approval(approvals, code, raw, binding)
            else:
                _remove(SETTINGS_FILE, folder)
                _remove(code + '.json', approvals)
    return True


def reset_settings(root):
    """Discard every project setting of this repository: remove its settings file, then its approval record, under
    the setters' lock, so the repository reads as never configured. The one recovery from broken settings.

    A project folder that is a link or unsafe refuses with the record kept, so the state stays broken, never unset.
    """
    main, _ = layout(root)
    code = code_of(main)
    with dr.data_folder(SETTINGS_APPROVED, create=True, private=True) as approvals:
        fcntl.flock(approvals, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with project_folder(main) as folder:
                _remove(SETTINGS_FILE, folder)
        except FileNotFoundError:
            pass
        _remove(code + '.json', approvals)


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
