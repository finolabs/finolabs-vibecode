#!/usr/bin/env python3
"""Read a repository's check list, its local-receipt mode and the local checks receipts.

The list lives in the main checkout's project data folder (`PROJECT_FOLDERS`), in `checks.json`, and counts only while its exact bytes match
the digest approved in the private state folder; nothing else is read, and the host config is never consulted.
Shared, read-mostly: `checks_setup.py` writes the file and its approval, `checks.py` writes a receipt,
`merge_check.py` reads both. A check is a short name and a JSON argument array, never a shell string. An invalid file
counts as unset and is never repaired here. Runs no command and makes no network call.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import project_store as store

NAME =re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
CODE = re.compile(r'[0-9a-f]{8}')
HEAD = re.compile(r'[0-9a-f]{40}|[0-9a-f]{64}')
DIGEST = re.compile(r'[0-9a-f]{64}')
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
PROJECT_FOLDERS = store.PROJECT_FOLDERS
PROJECT_FILE = 'checks.json'
PROJECT_LIMIT = 65536
PROJECT_KEYS = {'version', 'checks', 'local_receipt'}
APPROVED = 'state/checks-approved'
APPROVED_KEYS = {'sha256', 'approved'}
CHANGED = 'changed since it was approved'
AGAIN = 'run /setup add checks again'


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


# The project file: checks.json in the main checkout's project data folder, bound to an approved digest in user scope

def layout(root):
    """(main checkout root, git common folder) of a repository root, resolved and validated the way
    `project_progress.repository_code` resolves identity (`project_store.layout`), without running git."""
    return store.layout(root)


def code_of(main):
    return store.code_of(main)


def project_folder(main, create=False):
    """The project data folder under <main> (`project_store.project_folder`): no-follow descent, owner-checked, 0700."""
    return store.project_folder(main, create=create)


def read_project_file(folder):
    """The project file's bytes; FileNotFoundError when absent, ValueError when linked, unsafe or too large."""
    return store.read_project_file(folder, PROJECT_FILE, PROJECT_LIMIT)


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
    """(checks, receipt, reason): no file reads as 'no entry'.

    A file whose bytes do not match the approved digest, or with none, reads as unset with CHANGED: this is what stops
    a committed or branch-supplied file from choosing commands. Never repaired here.
    """
    main, _ = layout(root)
    if code_of(main) != code:
        return [], False, 'invalid code'
    try:
        raw = read_project_bytes(main)
    except FileNotFoundError:
        return [], False, 'no entry'
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


def checks_for(repository_code, root):
    """Ordered (name, argv) pairs and None, or an empty list and a reason: no entry, invalid, unreadable or CHANGED.

    `root` is the repository root of the caller's checkout. An invalid file counts as unset and is never repaired.
    """
    if not isinstance(repository_code, str) or not CODE.fullmatch(repository_code):
        return [], 'invalid code'
    checks, _, reason = read_project(repository_code, root)
    return ([], reason) if reason else ([(name, argv) for name, argv in checks], None)


def receipt_mode(repository_code, root):
    """True only when a valid, approved file turns the local-receipt mode on for this repository; every doubt is
    off."""
    if not isinstance(repository_code, str) or not CODE.fullmatch(repository_code):
        return False
    _, receipt, reason = read_project(repository_code, root)
    return reason is None and receipt is True


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


def receipt_status(code, head, root):
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
