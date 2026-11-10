#!/usr/bin/env python3
"""Read the canonical host's `## Checks` section, its local-receipt mode lines and the local checks receipts.

Shared, read-mostly: `checks_setup.py` writes the section, `checks.py` writes a receipt, `merge_check.py` reads both.
A check is a short name and a JSON argument array, never a shell string. An invalid section counts as unset as a
whole and is never repaired here. Runs no command and makes no network call.
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


def checks_for(repository_code):
    """Ordered (name, argv) pairs and None, or an empty list and a reason: absent, invalid, unreadable or no entry.

    An invalid section counts as unset as a whole and is never repaired here.
    """
    if not isinstance(repository_code, str) or not CODE.fullmatch(repository_code):
        return [], 'invalid code'
    entries, _, reason = read_section()
    if reason:
        return [], reason
    if repository_code not in entries:
        return [], 'no entry'
    return [(name, argv) for name, argv in entries[repository_code]], None


def receipt_mode(repository_code):
    """True only when a valid section turns the local-receipt mode on for this repository; every doubt is off."""
    if not isinstance(repository_code, str) or not CODE.fullmatch(repository_code):
        return False
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


def receipt_status(code, head):
    """None when the mode is off for this repository; else (matched, reason) for the pull request head."""
    if not receipt_mode(code):
        return None
    if not isinstance(head, str) or not HEAD.fullmatch(head):
        return False, 'pull request head unknown'
    checks, reason = checks_for(code)
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
