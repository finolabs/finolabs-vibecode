#!/usr/bin/env python3
"""Safe away-lease reader and away ledger appender, shared by autopilot.py, the question gate and session start.

The reader takes no lock, creates nothing, never follows a link and accepts only private (0600)
regular files owned by the user. Every caller other than autopilot.py treats any error as no lease.
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


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def private_info(folder, name):
    try:
        info = os.stat(name, dir_fd=folder, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise ValueError('Autopilot state file is unsafe')
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
        raise ValueError('Autopilot lease is invalid')
    counters = value['counters']
    if (not isinstance(counters, dict) or set(counters) != {'runs', 'runtime_minutes', 'actions', 'hour_actions'}
            or any(type(counters[k]) is not int or counters[k] < 0 for k in ('runs', 'actions'))
            or not finite(counters['runtime_minutes']) or not isinstance(counters['hour_actions'], list)
            or len(counters['hour_actions']) > 10000
            or not all(finite(t) for t in counters['hour_actions'])):
        raise ValueError('Autopilot counters are invalid')
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
