#!/usr/bin/env python3
"""Read a repository's check list, its local-receipt mode and the local checks receipts.

The list lives in the main checkout's project data folder (`PROJECT_FOLDERS`), in `checks.json`, and counts only while its exact bytes match
the digest approved in the private state folder; without that file the legacy `## Checks` section of the canonical
host config is read (through 0.2.x). Shared, read-mostly: `checks_setup.py` writes the file and its approval,
`checks.py` writes a receipt, `merge_check.py` reads both. A check is a short name and a JSON argument array, never a
shell string. An invalid file or section counts as unset and is never repaired here. Runs no command and makes no
network call.
"""
from contextlib import contextmanager
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
import project_progress as pp

CAP = 262144
HEADING = '## Checks'
NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
CODE = re.compile(r'[0-9a-f]{8}')
HEAD = re.compile(r'[0-9a-f]{40}|[0-9a-f]{64}')
DIGEST = re.compile(r'[0-9a-f]{64}')
LINE = re.compile(r'- ([0-9a-f]{8}): ([a-z0-9][a-z0-9-]{0,31}) = (.+)')
RECEIPT_MODE = 'local-receipt'  # reserved: never a check name
MAX_CHECKS = 20
MAX_ARGV = 1024
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'mksh', 'fish', 'csh', 'tcsh', 'ash', 'cmd', 'powershell', 'pwsh'}
LAUNCHERS = {'env', 'xargs', 'nohup', 'nice', 'timeout', 'time', 'sudo', 'doas', 'exec', 'eval', 'command',
             'busybox', 'script', 'watch'}
INTERPRETER = re.compile(r'python[0-9.]*|node|nodejs|deno|bun|perl[0-9.]*|ruby[0-9.]*|php[0-9.]*')
INLINE = re.compile(r'-[cerEp].*|--(?:eval|print)(?:=.*)?|-[bBdEiIOPqsSuvx]+c.*|eval')
SHELL_FLAG = re.compile(r'-c.*|--call(?:=.*)?|--shell-mode')
RECEIPTS = 'state/checks-receipts'
RECEIPT_KEYS = {'kind', 'code', 'head', 'digest', 'created'}
RECEIPT_LIMIT = 4096
PROJECT_FOLDERS = ('.finolabs', 'vibecode')
PROJECT_FILE = 'checks.json'
PROJECT_LIMIT = 65536
PROJECT_KEYS = {'version', 'checks', 'local_receipt'}
APPROVED = 'state/checks-approved'
APPROVED_KEYS = {'sha256', 'approved'}
CHANGED = 'changed since it was approved'
AGAIN = 'run /fnl-setup add checks again'


# The stored argument form

def program_name(path):
    """Lowercase base name without a Windows suffix, splitting on both kinds of slash."""
    name = re.split(r'[\\/]', path)[-1].lower()
    return re.sub(r'\.(?:exe|cmd|bat|com|ps1)$', '', name)


def refused_program(argv):
    """True when the argument array hands control to a shell, a launcher or inline code (deny on doubt)."""
    name = program_name(argv[0])
    if name in SHELLS or name in LAUNCHERS:
        return True
    rest = argv[1:]
    if name == 'yarn' and 'exec' in rest:
        return True
    runs_package = name == 'npx' or (name in ('npm', 'pnpm') and any(arg in ('exec', 'x', 'dlx') for arg in rest))
    if runs_package and any(SHELL_FLAG.fullmatch(arg) for arg in rest):
        return True
    return bool(INTERPRETER.fullmatch(name)) and any(INLINE.fullmatch(arg) for arg in argv[1:])


def check_argv(argv):
    """Refuse anything that is not a bounded argument list, or that hands a string to a shell, a launcher or inline code."""
    if not isinstance(argv, list) or not argv or len(argv) > 64:
        raise ValueError('argument array')
    for item in argv:
        if not isinstance(item, str) or re.search(r'[\x00-\x1f\x7f]', item):
            raise ValueError('argument')
    if not argv[0]:
        raise ValueError('program')
    encoded = json.dumps(argv, separators=(',', ':'), ensure_ascii=True)
    if len(encoded.encode()) > MAX_ARGV:
        raise ValueError('argument array too long')
    if refused_program(argv):
        raise ValueError('shell, launcher or inline code')
    return encoded


def check_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name == RECEIPT_MODE:
        raise ValueError('check name')
    return name


def check_list(checks):
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        raise ValueError('checks')
    names = set()
    for item in checks:
        if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str):
            raise ValueError('check')
        if check_name(item[0]) in names:
            raise ValueError('check name')
        check_argv(item[1])
        names.add(item[0])


def list_digest(checks):
    """SHA-256 of the ordered list in its canonical JSON form; any change of name, order or argument changes it."""
    canonical = [[name, json.loads(check_argv(list(argv)))] for name, argv in checks]
    return hashlib.sha256(json.dumps(canonical, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


# Document-only changes: the paths-ignore rule of the cheaper workflow, shared by its writer and `checks.py usage`

DOCUMENT_PATTERNS = ('**/*.md', 'docs/**', 'LICENSE')


def document_path(path):
    """True when one changed path matches a DOCUMENT_PATTERNS entry as GitHub filters read it (case-sensitive)."""
    return isinstance(path, str) and (path.endswith('.md') or path.startswith('docs/') or path == 'LICENSE')


def document_only(paths):
    """True when there is at least one changed path and every one is a document; no paths is never document-only."""
    return bool(paths) and all(document_path(path) for path in paths)


# The section

def split(text):
    """Return (headings as (offset, line), fenced) for the level-one and level-two headings outside code fences."""
    headings, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and line.strip() == token:
                fence = None  # a line with an info string after the run does not close a fence
        elif fence is None and re.match(r"^#{1,2} ", line):
            headings.append((offset, line.strip()))
        offset += len(line)
    return headings, fence


def section_span(text):
    """(start, end) of the one real section, None when absent; ambiguity raises."""
    headings, fence = split(text)
    indexes = [i for i, (_, title) in enumerate(headings) if title == HEADING]
    if fence is not None or len(indexes) > 1:
        raise ValueError('ambiguous section')
    if not indexes:
        return None
    index = indexes[0]
    return headings[index][0], headings[index + 1][0] if index + 1 < len(headings) else len(text)


def parse_section(text):
    """None when absent, else ({code: [[name, argv], ...]}, {codes with the local-receipt mode on}); any bad line raises."""
    span = section_span(text)
    if span is None:
        return None
    entries, receipts = {}, set()
    for line in text[span[0]:span[1]].splitlines()[1:]:
        if not line.strip():
            continue
        match = LINE.fullmatch(line)
        if not match:
            raise ValueError('unknown line')
        if match[2] == RECEIPT_MODE:
            if match[3] != 'on' or match[1] in receipts:
                raise ValueError('mode line')
            receipts.add(match[1])
            continue
        argv = json.loads(match[3])
        if check_argv(argv) != match[3]:
            raise ValueError('argument form')
        checks = entries.setdefault(match[1], [])
        if any(name == match[2] for name, _ in checks) or len(checks) >= MAX_CHECKS:
            raise ValueError('duplicate or too many checks')
        checks.append([match[2], argv])
    if receipts - set(entries):
        raise ValueError('mode without checks')
    return entries, receipts


def parse(text):
    """Return None when absent, else {code: [[name, argv], ...]} in stored order; any bad line raises."""
    parsed = parse_section(text)
    return None if parsed is None else parsed[0]


def read_section():
    """(entries, receipts, None) or (None, None, reason): absent, unreadable or invalid."""
    try:
        text = dr.read_data('host.md', CAP).decode('utf-8')
    except FileNotFoundError:
        return None, None, 'absent'
    except (OSError, ValueError, UnicodeError):
        return None, None, 'unreadable'
    try:
        parsed = parse_section(text)
    except (ValueError, TypeError, RecursionError):
        return None, None, 'invalid'
    if parsed is None:
        return None, None, 'absent'
    return parsed[0], parsed[1], None


# The project file: checks.json in the main checkout's project data folder, bound to an approved digest in user scope

def layout(root):
    """(main checkout root, git common folder) of a repository root, resolved the way
    `project_progress.repository_code` resolves identity, without running git."""
    root = Path(os.path.abspath(root))
    main, common = root, root / '.git'
    try:
        with pp.open_dir(root) as fd:
            link = pp.read_task(fd, '.git').strip()
        if len(link) <= 4096 and link.startswith('gitdir:'):
            gitdir = Path(os.path.abspath(root / link[len('gitdir:'):].strip()))
            common = gitdir
            with pp.open_dir(gitdir) as fd:
                shared = pp.read_task(fd, 'commondir').strip()
            if len(shared) <= 4096 and shared:
                shared = Path(os.path.abspath(gitdir / shared))
                with pp.open_dir(shared):
                    main, common = (shared.parent if shared.name == '.git' else shared), shared
    except (OSError, ValueError):
        pass
    return main, common


def code_of(main):
    return hashlib.sha256(str(main).encode('utf-8')).hexdigest()[:8]


@contextmanager
def project_folder(main, create=False):
    """An fd of the project data folder under <main> opened with no-follow descent from the filesystem root; each folder owned by
    this account and not writable by others. Created folders are 0700. A link anywhere on the path is refused."""
    with pp.open_dir(main) as top:
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


def read_project_file(folder):
    """The project file's bytes; FileNotFoundError when absent, ValueError when linked, unsafe or too large."""
    fd = os.open(PROJECT_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022
                or info.st_size > PROJECT_LIMIT):
            raise ValueError('unsafe project file')
        data = os.read(fd, PROJECT_LIMIT + 1)
        if len(data) > PROJECT_LIMIT:
            raise ValueError('project file too large')
        return data
    finally:
        os.close(fd)


def read_project_bytes(main):
    with project_folder(main) as folder:
        return read_project_file(folder)


def _object(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate key')
    return dict(pairs)


def _constant(value):
    raise ValueError('constant')


def parse_project(raw):
    """(checks as [[name, argv], ...], local receipt) of the closed schema; anything else raises."""
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
    if (not isinstance(data, dict) or set(data) != PROJECT_KEYS or type(data['version']) is not int
            or data['version'] != 1 or type(data['local_receipt']) is not bool or not isinstance(data['checks'], list)):
        raise ValueError('project file')
    checks = []
    for item in data['checks']:
        if not isinstance(item, dict) or set(item) != {'name', 'argv'}:
            raise ValueError('check')
        checks.append([item['name'], item['argv']])
    check_list(checks)
    return checks, data['local_receipt']


def render_project(checks, receipt):
    """The exact bytes a writer stores for this list and mode, in stored order."""
    check_list(checks)
    if type(receipt) is not bool:
        raise ValueError('mode')
    data = {'version': 1, 'checks': [{'name': name, 'argv': list(argv)} for name, argv in checks],
            'local_receipt': receipt}
    return (json.dumps(data, indent=2, ensure_ascii=True) + '\n').encode()


# An approval record that names no file: the list was removed while a legacy entry could not be cleaned up.
REMOVED = '0' * 64


def read_approved(code):
    """The approved SHA-256 of this repository's project file; FileNotFoundError when none, ValueError when invalid."""
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise ValueError('invalid code')
    with dr.data_folder(APPROVED, private=True) as folder:
        record = json.loads(dr.read_file(folder, code + '.json', RECEIPT_LIMIT), object_pairs_hook=_object)
    if (not isinstance(record, dict) or set(record) != APPROVED_KEYS or not isinstance(record['sha256'], str)
            or not DIGEST.fullmatch(record['sha256']) or type(record['approved']) is not int or record['approved'] < 0):
        raise ValueError('invalid approval')
    return record['sha256']


def write_approved(code, sha256):
    if not isinstance(code, str) or not CODE.fullmatch(code) or not isinstance(sha256, str) \
            or not DIGEST.fullmatch(sha256):
        raise ValueError('invalid approval')
    record = {'sha256': sha256, 'approved': int(time.time())}
    with dr.data_folder(APPROVED, create=True, private=True) as folder:
        dr.atomic_write(folder, code + '.json', json.dumps(record, sort_keys=True).encode())


def has_approval(code):
    """True when any approval record exists for this repository, or one that cannot be read (deny on doubt)."""
    try:
        read_approved(code)
    except FileNotFoundError:
        return False
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return True
    return True


def remove_approved(code):
    """Remove this repository's approved digest, if any; a missing record or folder is fine."""
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise ValueError('invalid code')
    try:
        with dr.data_folder(APPROVED, private=True) as folder:
            try:
                os.unlink(code + '.json', dir_fd=folder)
            except FileNotFoundError:
                return
            os.fsync(folder)
    except FileNotFoundError:
        return


def read_project(code, root):
    """None when this repository never moved off the legacy section; else (checks, receipt, reason).

    Once an approval record exists the project file alone decides: a file that disappeared reads as unset and never
    revives the legacy entry it replaced.

    A file whose bytes do not match the approved digest, or with none, reads as unset with CHANGED: this is what stops
    a committed or branch-supplied file from choosing commands. Never repaired here.
    """
    main, _ = layout(root)
    if code_of(main) != code:
        return [], False, 'invalid code'
    try:
        raw = read_project_bytes(main)
    except FileNotFoundError:
        try:
            recorded = read_approved(code)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
            return [], False, 'unreadable'
        return [], False, 'no entry' if recorded == REMOVED else CHANGED
    except (OSError, ValueError):
        return [], False, 'unreadable'
    try:
        approved = read_approved(code)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        approved = None
    if approved is None or approved != hashlib.sha256(raw).hexdigest():
        return [], False, CHANGED
    try:
        checks, receipt = parse_project(raw)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return [], False, 'invalid'
    return checks, receipt, None


def checks_for(repository_code, root=None):
    """Ordered (name, argv) pairs and None, or an empty list and a reason: absent, invalid, unreadable, no entry or
    CHANGED.

    `root` is the repository root of the caller's checkout; with it the project file is read first, and the legacy
    section only when there is no project file. An invalid file or section counts as unset and is never repaired.
    """
    if not isinstance(repository_code, str) or not CODE.fullmatch(repository_code):
        return [], 'invalid code'
    if root is not None:
        found = read_project(repository_code, root)
        if found is not None:
            checks, _, reason = found
            return ([], reason) if reason else ([(name, argv) for name, argv in checks], None)
    entries, _, reason = read_section()
    if reason:
        return [], reason
    if repository_code not in entries:
        return [], 'no entry'
    return [(name, argv) for name, argv in entries[repository_code]], None


def receipt_mode(repository_code, root=None):
    """True only when a valid, approved file (or, without one, a valid legacy section) turns the local-receipt mode on
    for this repository; every doubt is off."""
    if not isinstance(repository_code, str) or not CODE.fullmatch(repository_code):
        return False
    if root is not None:
        found = read_project(repository_code, root)
        if found is not None:
            return found[2] is None and found[1] is True
    _, receipts, reason = read_section()
    return reason is None and repository_code in receipts


# The local receipt

def validate_receipt(record):
    if (not isinstance(record, dict) or set(record) != RECEIPT_KEYS or record['kind'] != 'checks'
            or not isinstance(record['code'], str) or not CODE.fullmatch(record['code'])
            or not isinstance(record['head'], str) or not HEAD.fullmatch(record['head'])
            or not isinstance(record['digest'], str) or not DIGEST.fullmatch(record['digest'])
            or type(record['created']) is not int or record['created'] < 0):
        raise ValueError('invalid checks receipt')
    return record


def write_receipt(code, head, digest):
    record = validate_receipt({'kind': 'checks', 'code': code, 'head': head, 'digest': digest,
                               'created': int(time.time())})
    with dr.data_folder(RECEIPTS, create=True, private=True) as folder:
        dr.atomic_write(folder, code + '.json', json.dumps(record, sort_keys=True).encode())
    return record


def remove_receipt(code):
    """Remove this repository's receipt, if any, in one unlink; a missing receipt or folder is fine."""
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise ValueError('invalid code')
    try:
        with dr.data_folder(RECEIPTS, private=True) as folder:
            try:
                os.unlink(code + '.json', dir_fd=folder)
            except FileNotFoundError:
                return
            os.fsync(folder)
    except FileNotFoundError:
        return


def read_receipt(code):
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise ValueError('invalid code')
    with dr.data_folder(RECEIPTS, private=True) as folder:
        record = json.loads(dr.read_file(folder, code + '.json', RECEIPT_LIMIT))
    return validate_receipt(record)


def receipt_status(code, head, root=None):
    """None when the mode is off for this repository; else (matched, reason) for the pull request head."""
    if not receipt_mode(code, root=root):
        return None
    if not isinstance(head, str) or not HEAD.fullmatch(head):
        return False, 'pull request head unknown'
    checks, reason = checks_for(code, root=root)
    if reason:
        return False, 'no check list'
    try:
        record = read_receipt(code)
    except FileNotFoundError:
        return False, 'no local receipt'
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return False, 'local receipt unreadable or invalid'
    if record['code'] != code:
        return False, 'local receipt is for another repository'
    if record['head'] != head:
        return False, 'local receipt is for another head'
    if record['digest'] != list_digest(checks):
        return False, 'local receipt is for another check list'
    return True, 'matches'
