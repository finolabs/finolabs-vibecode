#!/usr/bin/env python3
"""Claude Code Stop hook for the away mandate (docs/specs/afk-decider.md A); every failure prints nothing and exits 0,
so the turn ends as usual.

Only while a valid, unexpired away lease exists and FNL_AFK_STOP is not off, it sends the agent back once with one
fixed reason when its turn ends. It lets the stop through when the host says a stop hook already continued this turn
(`stop_hook_active`), when the lease log holds an `idle` record of this session written since its previous stop whose
repository digest is the hook input `cwd`'s repository and whose queue revision is that repository's current one
(docs/specs/afk-goals.md B: a `parked` record closes an item, not the turn), when the lease lets no action run any
more (judged as `afk.py check` judges it: a setup change after the lease started counts; Lease hours is the only
limit), and on any error. It reads only the lease, the lease log, the integer `revision` of that repository's queue,
the setup that `check` reads and the hook's `session_id`, `hook_event_name`, `stop_hook_active` and `cwd`; it keeps
one mark per session (a hash of its id and the time of its last stop, no content) and sends nothing anywhere.
"""

import os
import signal
import sys

INPUT_LIMIT = 64 * 1024
FOLDER = 'state/afk-stop'
MAX_MARKS = 200
MARK_LIMIT = 32
LOG_LIMIT = 8 * 1024 * 1024
REASON = ('The user is away under an afk lease: do not end the turn waiting for them. Settle any pending question or '
          'approval through afk "Decide" and continue with the next open item of this repository\'s afk queue. A park '
          'closes an item, not the turn. To end the turn, first record afk.py log --kind idle --session <this Session '
          'id>, which is accepted only when every item is done or parked.')


def session_hash(session):
    import hashlib
    return hashlib.sha256(session.encode('utf-8')).hexdigest()[:16]


def read_mark(name):
    """The time of this session's previous stop, or None."""
    import stat
    import data_root as dr
    try:
        with dr.data_folder(FOLDER, private=True) as folder:
            info = os.stat(name, dir_fd=folder, follow_symlinks=False)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MARK_LIMIT):
                raise ValueError('unsafe mark')
            raw = dr.read_file(folder, name, MARK_LIMIT).decode('ascii')
    except FileNotFoundError:
        return None
    import re
    if not re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,9})?', raw):
        raise ValueError('invalid mark')
    return float(raw)


def write_mark(name, current):
    import fcntl
    import re
    import data_root as dr
    with dr.data_folder(FOLDER, create=True, private=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX)
        marks = []
        for entry in os.listdir(folder):
            if re.fullmatch(r'[0-9a-f]{16}', entry) and entry != name:
                marks.append((os.stat(entry, dir_fd=folder, follow_symlinks=False).st_mtime_ns, entry))
        for _, entry in sorted(marks)[:max(0, len(marks) - MAX_MARKS + 1)]:
            os.unlink(entry, dir_fd=folder)
        dr.atomic_write(folder, name, ('%.3f' % current).encode('ascii'))


def recorded_since(name, since, current, cwd):
    """True when the lease log holds an `idle` record of this session after `since` for the repository of `cwd` at that
    repository's current queue revision (afk.py records both on an accepted idle)."""
    import json
    import away_lease
    import data_root as dr
    afk = afk_module()
    with dr.data_folder(away_lease.STATE, private=True) as folder:
        raw = away_lease.read_private(folder, 'log.jsonl', LOG_LIMIT) or b''
        entries = [json.loads(line) for line in raw.splitlines()]  # an unreadable log is an error, which lets it through
        key = None if cwd is None else afk.repository_digest(cwd)
        revision = None if key is None else afk.queue_revision(folder, key)
    if revision is None:
        return False
    for entry in reversed(entries):
        if not isinstance(entry, dict) or not away_lease.finite(entry.get('time')):
            continue
        if not since < entry['time'] <= current:
            continue
        if (entry.get('kind') == 'idle' and entry.get('session') == name and entry.get('repository') == key[:16]
                and type(entry.get('revision')) is int and entry['revision'] == revision):
            return True
    return False


def afk_module():
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'skills/delegate/scripts'))
    import afk
    return afk


def lease_over(current):
    """True when the lease lets no action run any more (afk.py `lease_over`)."""
    import away_lease
    import data_root as dr
    afk = afk_module()
    with dr.data_folder(away_lease.STATE, private=True) as folder:
        return afk.lease_over(folder, current)


def main():
    try:
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(3)
        if os.environ.get('FNL_AFK_STOP', '').strip().lower() in {'off', '0', 'false', 'no'}:
            return 0

        import json
        import time
        from pathlib import Path

        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get('hook_event_name', 'Stop') != 'Stop':
            return 0
        session, cwd = event.get('session_id'), event.get('cwd')
        if not isinstance(session, str) or not 0 < len(session) <= 128:
            return 0

        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import away_lease

        current = time.time()
        lease = away_lease.live_lease(current)
        if lease is None:
            return 0
        name = session_hash(session)
        previous = read_mark(name)
        # Every stop under the lease moves the mark, so the next turn needs a record of its own.
        write_mark(name, current)
        if event.get('stop_hook_active') is True:
            return 0
        since = lease['start'] if previous is None or previous < lease['start'] else previous
        if recorded_since(name, since, current, cwd if isinstance(cwd, str) and os.path.isabs(cwd) else None):
            return 0
        if lease_over(current):
            return 0
        # Claude Code's documented Stop decision, with exit 0.
        os.write(1, (json.dumps({'decision': 'block', 'reason': REASON}, separators=(',', ':')) + '\n').encode())
    except Exception:
        pass
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
