#!/usr/bin/env python3
"""Opt-in Antigravity PreInvocation stop; size only, local, fail open."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

MESSAGE = 'The conversation is large. Run /compact, or start a fresh session with a short handover, then continue.'
STOP = {'injectSteps': [{'errorMessage': {'userMessage': MESSAGE}}], 'terminationBehavior': 'terminate'}


def limit_bytes(text):
    """Only a single real section and unambiguous opt-in grant consent."""
    active, seen, fence, lines = False, False, None, []
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        if re.match(r'^#{1,2} ', line):
            active = line.strip() == '## Compaction stop'
            if active:
                if seen:
                    return None
                seen = True
        elif active and line.strip():
            lines.append(line.strip().removeprefix('- '))
    enabled = [line for line in lines if line.startswith('Enabled:')]
    limits = [line for line in lines if line.startswith('Limit bytes:')]
    if enabled != ['Enabled: yes'] or len(limits) != 1:
        return None
    match = re.fullmatch(r'Limit bytes: ([0-9]+)', limits[0])
    if match and 50000 <= int(match[1]) <= 20000000:
        return int(match[1])
    return None


def read_event():
    if sys.stdin.isatty():
        return None
    try:
        fd = sys.stdin.fileno()
    except (OSError, ValueError):
        raw = sys.stdin.buffer.read(65537)
    else:
        deadline, raw = time.monotonic() + 0.5, b''
        while len(raw) <= 65536:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                return None
            chunk = os.read(fd, min(8192, 65537 - len(raw)))
            if not chunk:
                break
            raw += chunk
    return json.loads(raw) if len(raw) <= 65536 else None


def safe_mark(info):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 64)


def decide(event):
    if os.environ.get('FNL_COMPACT_STOP') == 'off':
        return {}
    if (not isinstance(event, dict) or type(event.get('invocationNum')) is not int
            or event['invocationNum'] != 0):
        return {}
    limit = limit_bytes(dr.read_data('host.md').decode('utf-8'))
    if limit is None:
        return {}
    session, value = event.get('conversationId'), event.get('transcriptPath')
    if not isinstance(session, str) or not session or not isinstance(value, str):
        return {}
    path = Path(value)
    brain = dr.account_home() / '.gemini/antigravity-cli/brain'
    if not path.is_absolute() or not path.resolve(strict=True).is_relative_to(brain):
        return {}
    info = path.lstat()  # Never open the transcript, even to measure it.
    if not stat.S_ISREG(info.st_mode):
        return {}
    size = info.st_size
    name = hashlib.sha256(session.encode('utf-8')).hexdigest()[:16] + '.json'
    with dr.data_folder('state/compact-stop', create=size > limit, private=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            info = os.stat(name, dir_fd=folder, follow_symlinks=False)
        except FileNotFoundError:
            mark = None
        else:
            if not safe_mark(info):
                return {}
            mark = json.loads(dr.read_file(folder, name, 64))
            if type(mark) is not int or mark < 0:
                return {}
        if mark is not None and size < mark:
            os.unlink(name, dir_fd=folder)
            os.fsync(folder)
            return {}
        if size <= limit or (mark is not None and (size * 10 < mark * 11 or size - mark < 20000)):
            return {}
        files = []
        for entry in os.listdir(folder):
            if re.fullmatch(r'[0-9a-f]{16}\.json', entry):
                info = os.stat(entry, dir_fd=folder, follow_symlinks=False)
                if not safe_mark(info):
                    return {}
                if entry != name:
                    files.append((info.st_mtime, entry))
        dr.atomic_write(folder, name, str(size).encode('ascii'))
        files.append((os.stat(name, dir_fd=folder, follow_symlinks=False).st_mtime, name))
        for _, entry in sorted(files)[:max(0, len(files) - 200)]:
            os.unlink(entry, dir_fd=folder)
        return STOP


def main():
    result = {}
    try:
        if sys.argv[1:] == ['--host', 'antigravity', '--event', 'PreInvocation']:
            result = decide(read_event())
    except Exception:
        pass
    try:
        print(json.dumps(result, separators=(',', ':')))
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
