#!/usr/bin/env python3
"""Safe away-lease reader, MERGE OK receipts, the permission hook's approval store and away ledger appender, shared
by afk.py, merge_check.py, the question gate, the afk stop and permission hooks and session start.

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


PERMITS = 'permits.json'  # permission approvals and denials of the afk permission hook (docs/specs/afk-decider.md B)
PERMIT_TTL = 1800  # seconds a permission approval stays usable
MAX_PERMITS = 256
DIGEST = re.compile(r'[0-9a-f]{64}')


def _permit_entries(folder, lease, current):
    """This lease's entries: unexpired approvals and its denials; anything malformed is dropped."""
    try:
        entries = json.loads(read_private(folder, PERMITS) or b'[]')
    except (ValueError, TypeError):
        return []
    if not isinstance(entries, list):
        return []
    kept = []
    for e in entries:
        if (isinstance(e, dict) and set(e) == {'kind', 'digest', 'time', 'lease'} and e['kind'] in ('approval', 'denied')
                and isinstance(e['digest'], str) and DIGEST.fullmatch(e['digest']) and finite(e['time'])
                and e['lease'] == lease['start'] and lease['start'] <= e['time'] <= current
                and (e['kind'] == 'denied' or current - e['time'] < PERMIT_TTL)):
            kept.append(e)
    return kept[-MAX_PERMITS:]


def _permits_locked(change, current):
    """Run `change(entries, lease)` under the permits lock during a live lease and save what it returns; returns its
    answer. Without a live lease it writes nothing and returns None."""
    lease = live_lease(current)
    if lease is None:
        return None
    import fcntl  # imported here so the lease reader stays importable where fcntl is missing
    with dr.data_folder(STATE, private=True) as folder:
        private_info(folder, 'permits.lock')
        lock = os.open('permits.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=folder)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            entries = _permit_entries(folder, lease, current)
            answer, entries = change(entries, lease)
            private_info(folder, PERMITS)
            dr.atomic_write(folder, PERMITS, json.dumps(entries[-MAX_PERMITS:], separators=(',', ':')).encode())
        finally:
            os.close(lock)
    return answer


def record_permit(value, current):
    """Record a permission approval for one request digest during a live lease (afk.py `--approve-request`); it expires
    after PERMIT_TTL or with the lease and is consumed only by the permission hook. False without a live lease."""
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError('a permission approval names one 64-hex request digest')
    answer = _permits_locked(lambda entries, lease: (True, entries + [
        dict(kind='approval', digest=value, time=current, lease=lease['start'])]), current)
    return bool(answer)


def answer_permit(value, current):
    """The permission hook's answer for one request digest: 'allow' consumes a recorded approval once; 'deny' records
    a first denial; 'park' answers a second denial with no approval recorded in between. None without a live lease."""
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError('invalid request digest')

    def change(entries, lease):
        approvals = [e for e in entries if e['kind'] == 'approval' and e['digest'] == value]
        if approvals:
            used = approvals[0]
            # One approval is used; the request's earlier denial is cleared with it.
            return 'allow', [e for e in entries if e is not used and not (e['kind'] == 'denied' and e['digest'] == value)]
        if any(e['kind'] == 'denied' and e['digest'] == value for e in entries):
            return 'park', entries
        return 'deny', entries + [dict(kind='denied', digest=value, time=current, lease=lease['start'])]
    return _permits_locked(change, current)


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
