#!/usr/bin/env python3
"""Pause new work before the machine restarts or shuts down, and report what recorded work remains.

`start [restart|shutdown] [--in MINUTES]` writes the pause marker and ends an active afk lease; `status
[--checkpoint SESSION]...` reports the marker, the open ledger dispatches, the heavy-job facts, the checkpoints and
a verdict about recorded work only; `resume` removes the marker. The marker is `pause.json` in the private state
folder of the canonical data root and holds a start time, a kind and a deadline, nothing else. While it is active
`heavy_run.py run` refuses to start a command. Nothing here stops a process, runs a program or uses the network.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root as dr

MARKER = 'pause.json'
KINDS = ('restart', 'shutdown', 'none')
LIMIT = 512
LIFETIME = 24 * 3600
SKEW = 300
SESSION = re.compile(r'[A-Za-z0-9-]{8,64}')
DISPATCH = re.compile(r'[A-Za-z0-9-]{1,40}')
HANDOVER = re.compile(r'[0-9a-f]{16}\.md')
CACHE_LIMIT = 16 * 1024 * 1024
CACHE_MAX_AGE = 900
FAMILIES = ('claude', 'codex', 'agy')


def now():
    return time.time()


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:  # an integer too large for a float is invalid, never an error
        return False


def read_marker(folder):
    """Raw bytes of a private regular marker owned by this account, at most LIMIT bytes; FileNotFoundError if absent."""
    fd = os.open(MARKER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o077 or info.st_size > LIMIT):
            raise ValueError('unsafe marker')
        raw = os.read(fd, LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('marker too large')
        return raw
    finally:
        os.close(fd)


def marker_state():
    """(missing|active|expired|invalid, data). Only `active` is a pause; a damaged marker is never one."""
    try:
        with dr.data_folder('state', private=True) as folder:
            raw = read_marker(folder)
    except FileNotFoundError:
        return 'missing', None
    except (OSError, ValueError, UnicodeError):
        return 'invalid', None
    try:
        data = json.loads(raw.decode('utf-8'))
        if (not isinstance(data, dict) or set(data) != {'started', 'kind', 'deadline'}
                or not number(data['started']) or not number(data['deadline']) or data['kind'] not in KINDS):
            return 'invalid', None
    except (ValueError, UnicodeError, RecursionError, ArithmeticError):
        return 'invalid', None
    age = now() - data['started']
    if age < -SKEW:
        return 'invalid', None
    return ('expired' if age > LIFETIME else 'active'), data


def paused():
    return marker_state()[0] == 'active'


def write_marker(kind, deadline):
    raw = json.dumps({'started': now(), 'kind': kind, 'deadline': deadline}, separators=(',', ':')).encode()
    with dr.data_folder('state', create=True, private=True) as folder:
        dr.atomic_write(folder, MARKER, raw)


def end_afk():
    """Say whether an active afk lease was ended, through afk's own stop logic."""
    try:
        import afk
        import contextlib
        import io
        with afk.private_folder() as folder:
            existed = afk.read_private(folder, 'lease.json') is not None
            if existed:
                with contextlib.redirect_stdout(io.StringIO()):
                    afk.stop(folder)
        return 'afk lease ended' if existed else 'no afk lease'
    except Exception:
        return 'afk lease not checked'


def minutes_since(stamp):
    return max(0, int((now() - stamp) // 60))


def open_dispatches():
    """[(id, age minutes or None, budget or None)], or None when the ledger cannot be read."""
    try:
        import ledger
        from datetime import datetime, timezone
        starts, finishes = ledger.load()
    except Exception:
        return None
    rows = []
    for ident, start in starts.items():
        if ident in finishes:
            continue
        try:
            age = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(start['ts'])).total_seconds() / 60)
        except (ValueError, TypeError, KeyError):
            age = None
        budget = start.get('budget_min')
        rows.append((ident if isinstance(ident, str) and DISPATCH.fullmatch(ident) else '(invalid id)', age,
                     budget if type(budget) is int and budget > 0 else None))
    return rows


def dispatch_line(row):
    ident, age, budget = row
    text = '  dispatch %s: age %s/%s min' % (ident, '?' if age is None else '%d' % age, '?' if budget is None else budget)
    return text + (' stalled' if age is not None and budget is not None and age > budget else '')


def heavy_facts():
    """(lines, blocked reasons, unknown reasons) from heavy_run's own read-only functions."""
    import heavy_run
    lines, blocked, unknown = [], [], []
    state = heavy_run.lock_state()
    if state == 'refused':
        unknown.append('heavy lock: location refused')
        lines.append('heavy lock: location refused')
    elif state == 'held':
        blocked.append('a heavy job holds the lock')
        try:
            who = heavy_run.holder()
            lines.append('heavy lock: held, owner unknown' if not who else 'heavy lock: held\n' + heavy_run.describe(who))
        except Exception:
            lines.append('heavy lock: held, owner unknown')
    else:
        orphan = None
        try:
            fd = heavy_run.open_lock()
            try:
                orphan = heavy_run.previous_group_running(fd)
            finally:
                os.close(fd)
        except (heavy_run.Refused, OSError):
            unknown.append('heavy lock: location refused')
        if orphan:
            blocked.append('a job from a stopped wrapper is still running')
            lines.append('heavy lock: free, but a job from a stopped wrapper is still running')
        elif orphan is not None:
            lines.append('heavy lock: free')
    processes = heavy_run.waiting_count()
    if processes is None:
        unknown.append('waiting: unknown')
        lines.append('waiting: unknown')
    else:
        waiting = max(0, processes - 1) if state == 'held' else processes
        lines.append('waiting: about %d' % waiting)
        if waiting:
            blocked.append('%d waiting wrapper%s' % (waiting, '' if waiting == 1 else 's'))
    return lines, blocked, unknown


def checkpoint_problem(session, started):
    """None when the handover exists, is within its read lifetime and was written after the marker started."""
    import handover_state
    if started is None:
        return 'no active pause'
    if not handover_state.read(session):
        return 'not readable'
    try:
        with dr.data_folder('state/handover', private=True) as folder:
            info = os.stat(handover_state.filename(session), dir_fd=folder, follow_symlinks=False)
    except (OSError, ValueError):
        return 'not readable'
    return None if info.st_mtime > started else 'older than the pause'


def host_section_on():
    """True when the one real `## Agent snapshot` heading holds `- Snapshot: on` (fenced examples ignored)."""
    try:
        text = dr.read_data('host.md').decode('utf-8')
    except (OSError, ValueError, UnicodeError):
        return False
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            if fence is None:
                fence = match[1]
            elif match[1][0] == fence[0] and len(match[1]) >= len(fence) and line.strip() == match[1]:
                fence = None  # a line with an info string after the run does not close a fence
        elif fence is None:
            lines.append(line)
    parts = re.split(r'^#{1,2} (.+?)\s*$', '\n'.join(lines), flags=re.M)
    found = [parts[i + 1].strip() for i in range(1, len(parts), 2) if parts[i] == 'Agent snapshot']
    return len(found) == 1 and found[0] == '- Snapshot: on'


def process_counts():
    """{family: count} from the dashboard's last snapshot, read as data only; None when not observed.

    No collection happens here. Metrics consent, the snapshot setting and both off switches must allow it, and the
    snapshot must be recent and without a failure reason."""
    try:
        if (os.environ.get('FNL_AGENT_SNAPSHOT', '').lower() == 'off' or os.environ.get('FNL_METRICS', '').lower() == 'off'
                or not host_section_on()):
            return None
        consent = json.loads(dr.read_data('state/consent.json', 4096))
        if (not isinstance(consent, dict) or consent.get('retention_days') not in (30, 90, 365)
                or not isinstance(consent.get('date'), str)):
            return None
        raw = dr.read_data('state/data.js', CACHE_LIMIT).decode('utf-8')
        running = json.loads(raw.removeprefix('window.FNL_DATA = ').removesuffix(';\n'))['running']
        snapshot = running['snapshot']
        from datetime import datetime
        taken = datetime.fromisoformat(snapshot['time']).timestamp()
        if snapshot['reason'] != '' or not 0 <= now() - taken <= CACHE_MAX_AGE:
            return None
        counts = dict.fromkeys(FAMILIES, 0)
        for row in running['processes']:
            if row['family'] in counts:
                counts[row['family']] += 1
        return counts
    except (OSError, ValueError, UnicodeError, KeyError, TypeError, AttributeError, RecursionError):
        return None


def brief(items, limit=5):
    """The first few reasons, then a count, so a long list of open records stays one readable line."""
    shown = '; '.join(items[:limit])
    return shown + ('; and %d more' % (len(items) - limit) if len(items) > limit else '')


def status(checkpoints):
    state, data = marker_state()
    out = []
    started = None
    if state == 'active':
        text = 'pause: active (%s), %d min elapsed' % (data['kind'], minutes_since(data['started']))
        if data['deadline']:
            left = math.ceil((data['deadline'] - now()) / 60)
            text += (', %d min to the deadline' % left if left > 0
                     else ', deadline passed: ask the user about each remaining run, one at a time')
        out.append(text)
        started = data['started']
        if data['kind'] == 'shutdown':
            out.append('handovers expire after 24 hours; offer a longer-lived note with the user\'s yes')
    else:
        out.append('pause: ' + state)
    blocked, unknown = [], []
    rows = open_dispatches()
    if rows is None:
        unknown.append('ledger: unreadable')
        out.append('open dispatches: unreadable')
    else:
        out.append('open dispatches: %d (the verdict excludes the coordinator\'s own record by the agent\'s judgment)' % len(rows))
        out.extend(dispatch_line(row) for row in rows)
        blocked.extend('open dispatch %s' % row[0] for row in rows)
    try:
        lines, heavy_blocked, heavy_unknown = heavy_facts()
    except Exception:
        lines, heavy_blocked, heavy_unknown = ['heavy facts: unreadable'], [], ['heavy facts: unreadable']
    out.extend(lines)
    blocked.extend(heavy_blocked)
    unknown.extend(heavy_unknown)
    out.append('checkpoints checked in this run: %d' % len(checkpoints))
    for session in checkpoints:
        try:
            problem = checkpoint_problem(session, started)
        except Exception:
            problem = 'not readable'
        out.append('checkpoint %s: %s' % (session, 'ok' if problem is None else problem))
        if problem is not None:
            unknown.append('checkpoint %s %s' % (session, problem))
    if blocked:
        out.append('verdict: blocked: ' + brief(blocked))
    elif unknown:
        out.append('verdict: unknown: ' + brief(unknown))
    else:
        out.append('verdict: no recorded work remains')
    out.append('This is a statement about recorded work, not a claim that the machine is safe: restarting is your call, '
               'and jobs started outside heavy_run.py and agent sessions are not covered.')
    out.append('agent processes seen, not identified: check these yourself before you restart')
    counts = process_counts()
    out.append('not observed' if counts is None else ', '.join('%s %d' % item for item in counts.items()))
    print('\n'.join(out))


def handover_summary():
    """(count, oldest age in minutes) of handover files within their read lifetime; never names."""
    ages = []
    try:
        with dr.data_folder('state/handover', private=True) as folder:
            for entry in os.listdir(folder):
                if not HANDOVER.fullmatch(entry):
                    continue
                info = os.stat(entry, dir_fd=folder, follow_symlinks=False)
                age = now() - info.st_mtime
                if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and 0 <= age < LIFETIME:
                    ages.append(age)
    except (OSError, ValueError):
        pass
    return len(ages), int(max(ages) // 60) if ages else None


def start(kind, minutes):
    previous, _ = marker_state()
    deadline = now() + minutes * 60 if minutes else 0
    write_marker(kind, deadline)
    lease = end_afk()
    print('pause started (%s)%s; %s%s; nothing is started or stopped' % (
        kind, ', deadline in %d min' % minutes if minutes else ', no deadline',
        lease,'; replaced an earlier marker' if previous != 'missing' else ''))


def resume():
    try:
        with dr.data_folder('state', private=True) as folder:
            os.unlink(MARKER, dir_fd=folder)
    except FileNotFoundError:
        pass
    count, oldest = handover_summary()
    print('pause removed; %d handover%s still within the 24-hour read lifetime%s' % (
        count, '' if count == 1 else 's', ', oldest %d min' % oldest if oldest is not None else ''))
    rows = open_dispatches()
    if rows is None:
        print('open dispatches: unreadable')
    else:
        print('open dispatches: %d; these may have ended without a finish line' % len(rows))
        for row in rows:
            print(dispatch_line(row))
    print('nothing is restarted; afk is not restarted')


def minutes_type(text):
    if not re.fullmatch(r'[0-9]{1,4}', text) or not 1 <= int(text) <= 1440:
        raise argparse.ArgumentTypeError('minutes must be an integer from 1 to 1440')
    return int(text)


def session_type(text):
    if not SESSION.fullmatch(text):
        raise argparse.ArgumentTypeError('invalid session id')
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(prog='pause.py', description=__doc__.split('\n\n')[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    begin = sub.add_parser('start', allow_abbrev=False)
    begin.add_argument('kind', nargs='?', choices=('restart', 'shutdown'), default='none')
    begin.add_argument('--in', dest='minutes', type=minutes_type)
    inspect = sub.add_parser('status', allow_abbrev=False)
    inspect.add_argument('--checkpoint', action='append', default=[], type=session_type)
    sub.add_parser('resume', allow_abbrev=False)
    args = parser.parse_args(argv)
    try:
        if args.command == 'start':
            start(args.kind, args.minutes)
        elif args.command == 'status':
            status(args.checkpoint)
        else:
            resume()
        return 0
    except (OSError, ValueError, UnicodeError):
        print('pause: refused: the state folder is missing, unsafe or unavailable', file=sys.stderr)
        return 3


if __name__ == '__main__':
    sys.exit(main())
