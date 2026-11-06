#!/usr/bin/env python3
"""Read a bounded, content-free snapshot of processes named claude, codex or agy."""
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import sys
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

ROOTS = ('claude', 'codex', 'agy')
APPS = ('Claude', 'Codex', 'Antigravity')
CHILDREN = frozenset(('node', 'python', 'python3', 'bash', 'zsh', 'sh', 'git', 'npm', 'pnpm',
                      'npx', 'pytest', 'cargo', 'go', 'make', 'docker', 'ssh', 'rg', 'grep'))
LIMIT = 256 * 1024
SECONDS = 2


def section(text):
    """Only one real heading is authoritative; fenced examples never opt in."""
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None:
            lines.append(line)
    parts = re.split(r"^#{1,2} (.+?)\s*$", "\n".join(lines), flags=re.M)
    found = [parts[i+1].strip() for i in range(1, len(parts), 2) if parts[i] == 'Agent snapshot']
    return found[0] if len(found) == 1 else ''


def enabled():
    if os.environ.get('FNL_AGENT_SNAPSHOT', '').lower() == 'off':
        return False
    try:
        return section(dr.read_data('host.md').decode()) == '- Snapshot: on'
    except (OSError, ValueError, UnicodeError):
        return False


def empty(reason='', at=None):
    return {'time': at or datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'processes': [], 'apps': {}, 'reason': reason}


def elapsed(value):
    match = re.fullmatch(r'(?:(\d+)-)?(?:(\d+):)?(\d{1,2}):(\d{2})', value)
    if not match:
        raise ValueError('elapsed')
    days, hours, minutes, seconds = (int(n or 0) for n in match.groups())
    if minutes >= 60 or seconds >= 60 or (days and hours >= 24):
        raise ValueError('elapsed')
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def parse(raw, uid, at):
    result = empty(at=at)
    rows, children = {}, defaultdict(list)
    # Only the last field may contain spaces. Never expose it, even on errors.
    for line in raw.splitlines():
        parts = line.split(None, 4)
        if len(parts) != 5:
            continue
        try:
            owner, pid, parent = (int(n) for n in parts[:3])
            age = elapsed(parts[3])
        except ValueError:
            continue
        if owner != uid or pid <= 0 or parent < 0 or pid in rows:
            continue
        name = parts[4].rsplit('/', 1)[-1]
        rows[pid] = (parent, age, name)
        children[parent].append(pid)
    apps = Counter(row[2] for row in rows.values() if row[2] in APPS)
    result['apps'] = dict(apps)
    for pid, (_, age, name) in rows.items():
        if name not in ROOTS:
            continue
        counts, seen = Counter(), {pid}
        queue = deque((child, 1) for child in children[pid])
        while queue and len(seen) <= 500:
            child, depth = queue.popleft()
            if child in seen:
                continue
            seen.add(child)
            child_name = rows[child][2]
            counts[child_name if child_name in CHILDREN else 'other'] += 1
            if depth < 6:
                queue.extend((c, depth + 1) for c in children[child])
        result['processes'].append({'family': name, 'elapsed_seconds': age, 'descendants': dict(counts)})
    return result


def resolve_ps():
    for path in ('/usr/bin/ps', '/bin/ps'):
        try:
            info = os.lstat(path)
            if (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                    and not info.st_mode & 0o022 and info.st_mode & 0o111):
                return path
        except OSError:
            pass
    return None


def execute(path):
    """Bound pipe reads as well as wall time; never buffer unlimited communicate() output."""
    with tempfile.TemporaryDirectory(prefix='fnl-process-') as folder:
        process = subprocess.Popen([path, '-axo', 'uid=,pid=,ppid=,etime=,comm='],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, cwd=folder,
                                   start_new_session=True)
        deadline, output = time.monotonic() + SECONDS, bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise TimeoutError()
                    chunk = os.read(process.stdout.fileno(), min(65536, LIMIT + 1 - len(output)))
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > LIMIT:
                        raise ValueError('output cap')
            try:
                code = process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise TimeoutError() from None
            if code:
                raise OSError('exit')
            return bytes(output)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.stdout.close()
            process.wait()


def snapshot():
    path = resolve_ps()
    if path is None:
        return empty('ps unavailable')
    try:
        return parse(execute(path).decode('utf-8', errors='replace'), os.getuid(), empty()['time'])
    except TimeoutError:
        return empty('ps timed out')
    except ValueError:
        return empty('ps output too large')
    except OSError:
        return empty('ps failed')


if __name__ == '__main__':
    # Collection is opt-in; the refresh calls snapshot only after both consents.
    print(json.dumps(empty('snapshot off')))
