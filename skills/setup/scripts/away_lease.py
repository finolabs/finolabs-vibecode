#!/usr/bin/env python3
"""Safe away-lease reader, MERGE OK receipts and away ledger appender, shared by afk.py, merge_check.py, the question
gate and session start.

The reader takes no lock, creates nothing, never follows a link and accepts only private (0600)
regular files owned by the user. Every caller other than afk.py treats any error as no lease.
"""
import json
import math
import os
import re
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root as dr

STATE = 'state/autopilot'
RECEIPTS = 'merge-ok.json'  # merge_check.py's MERGE OK receipts, read by afk.py before a merge
RECEIPT_TTL = 900  # seconds a receipt stays valid
MAX_RECEIPTS = 32
SHA = re.compile(r'[0-9a-f]{40}')


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def private_info(folder, name):
    try:
        info = os.stat(name, dir_fd=folder, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise ValueError('afk state file is unsafe')
    return info


def read_private(folder, name, cap=65536):
    if private_info(folder, name) is None:
        return None
    return dr.read_file(folder, name, cap)


def read_lease(folder):
    raw = read_private(folder, 'lease.json')
    if raw is None:
        return None
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {'id', 'start', 'expiry', 'settings_hash', 'counters'}
            or not isinstance(value['id'], str) or not re.fullmatch(r'[0-9a-f]{32}', value['id'])
            or not all(finite(value[k]) for k in ('start', 'expiry'))
            or not value['start'] < value['expiry'] <= value['start'] + 24 * 3600
            or not isinstance(value['settings_hash'], str) or not re.fullmatch(r'[0-9a-f]{64}', value['settings_hash'])):
        raise ValueError('afk lease is invalid')
    counters = value['counters']
    # Per-project counters (docs/specs/afk-per-project.md "A"): full identity digest or `unknown` -> entry.
    if not isinstance(counters, dict) or len(counters) > 64 or not all(
            isinstance(key, str) and re.fullmatch(r'[0-9a-f]{64}|unknown', key) and isinstance(entry, dict)
            and set(entry) == {'runs', 'actions', 'hour_actions', 'first'}
            and all(type(entry[k]) is int and entry[k] >= 0 for k in ('runs', 'actions'))
            and (entry['first'] is None or finite(entry['first']))
            and isinstance(entry['hour_actions'], list) and len(entry['hour_actions']) <= 10000
            and all(finite(t) for t in entry['hour_actions'])
            for key, entry in counters.items()):
        raise ValueError('afk counters are invalid')
    return value


def live_lease(current):
    """The lease when a valid, unexpired one exists and no stop marker does; else None. Errors propagate."""
    if dr.consent_root() is None:
        return None
    try:
        with dr.data_folder(STATE, private=True) as folder:
            if read_private(folder, 'stop') is not None:
                return None
            lease = read_lease(folder)
    except FileNotFoundError:
        return None
    if lease is None or not lease['start'] <= current < lease['expiry']:
        return None
    return lease


def merge_receipts(folder, current):
    """The (target, pull request, head) triples of MERGE OK receipts younger than RECEIPT_TTL; empty on any doubt."""
    try:
        entries = json.loads(read_private(folder, RECEIPTS) or b'[]')
        return {(e['repo'], e['pr'], e['head']) for e in entries
                if isinstance(e, dict) and isinstance(e.get('repo'), str) and type(e.get('pr')) is int
                and isinstance(e.get('head'), str) and SHA.fullmatch(e['head'])
                and finite(e.get('time')) and current - RECEIPT_TTL <= e['time'] <= current}
    except (OSError, ValueError, TypeError, KeyError):
        return set()


def record_merge_ok(target, pr, head, current):
    """During a live lease, record that merge_check.py printed MERGE OK with --independent for this pull request and
    head of `target` (`github.com/<owner>/<name>`, casefolded). Without a live lease it writes nothing; False then."""
    if (live_lease(current) is None or type(pr) is not int or not SHA.fullmatch(head)
            or not re.fullmatch(r'github\.com/[^/]+/[^/]+', target)):
        return False
    import fcntl  # imported here so the lease reader stays importable where fcntl is missing
    with dr.data_folder(STATE, private=True) as folder:
        private_info(folder, 'merge-ok.lock')
        lock = os.open('merge-ok.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=folder)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)  # one read-modify-write at a time, so no receipt is lost
            try:
                kept = [e for e in json.loads(read_private(folder, RECEIPTS) or b'[]')
                        if isinstance(e, dict) and finite(e.get('time')) and current - RECEIPT_TTL <= e['time'] <= current]
            except (ValueError, TypeError):
                kept = []
            kept = (kept + [dict(repo=target, pr=pr, head=head, time=current)])[-MAX_RECEIPTS:]
            private_info(folder, RECEIPTS)
            dr.atomic_write(folder, RECEIPTS, json.dumps(kept, separators=(',', ':')).encode())
        finally:
            os.close(lock)
    return True


def append_ledger(record):
    """Append one line to the dispatch ledger in the canonical data root, as ledger.py does."""
    with dr.data_folder(create=True) as folder:
        fd = os.open('ledger.jsonl', os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                     0o600, dir_fd=folder)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise ValueError('unsafe ledger')
            stream.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
