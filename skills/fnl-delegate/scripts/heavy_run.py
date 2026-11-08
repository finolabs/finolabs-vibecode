#!/usr/bin/env python3
"""Run one heavy command at a time on this machine.

`run [--label L] [--pass-env NAME]... -- <command...>` waits for the machine-wide lock and for load and free
memory to allow a start, then runs the command and returns its exit status. `status` reports whether the lock is
held. Exit 64: detached work refused; 75: the wait cap ended; 78: the lock location is unsafe; 124: stopped after the
maximum run time; 2: bad usage.

The lock is a kernel advisory lock on one regular file in the plugin's fixed anchor folder, so it does not move
when the data root is relocated. The child and its descendants inherit the descriptor, so the lock outlives a
killed wrapper while any of them still runs and has not closed it. A wrapper that is still alive also waits until
the command's process group is empty. Nothing here prints or stores the environment or the command.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

import data_root
import parallel_slots as slots
import run_env

LOCK_NAME = 'heavy.lock'
LABEL = re.compile(r'[A-Za-z0-9 ._-]{1,40}')
DEFAULTS = {'load': 12.0, 'memory_gb': 3.0, 'wait_minutes': 40.0, 'max_minutes': 90.0}
BOUNDS = {'load': (1.0, 256.0), 'memory_gb': (0.0, 64.0), 'wait_minutes': (1.0, 720.0), 'max_minutes': (1.0, 720.0)}
KEYS = {'Load limit': 'load', 'Memory minimum GB': 'memory_gb', 'Wait cap minutes': 'wait_minutes', 'Max job minutes': 'max_minutes'}
TOOLS = {'vm_stat': '/usr/bin/vm_stat', 'ps': '/bin/ps'}


class Refused(Exception):
    """The lock location is not a private regular file owned by this account."""


def limits():
    """Defaults, overridden by valid entries under `## Heavy jobs` in the canonical host config."""
    result = dict(DEFAULTS)
    try:
        text = data_root.read_data('host.md').decode('utf-8')
    except (OSError, ValueError, UnicodeError):
        return result
    in_section = False
    for line in text.splitlines():
        if line.startswith('## '):
            in_section = line.strip() == '## Heavy jobs'
            continue
        match = re.fullmatch(r'(?:- )?(Load limit|Memory minimum GB|Wait cap minutes|Max job minutes): (\d{1,6}(?:\.\d{1,3})?)', line.strip())
        if in_section and match:
            key, value = KEYS[match[1]], float(match[2])
            if BOUNDS[key][0] <= value <= BOUNDS[key][1]:
                result[key] = value
    return result


def read_load():
    try:
        return os.getloadavg()[0]
    except OSError:
        return None


def read_free_gb():
    """Free, inactive and speculative memory in GB from `vm_stat`; None when it cannot be read."""
    try:
        done = subprocess.run([TOOLS['vm_stat']], env=run_env.environment(), capture_output=True, timeout=5, text=True)
        page = int(re.search(r'page size of (\d+) bytes', done.stdout)[1])
        pages = sum(int(re.search(r'Pages %s:\s+(\d+)' % name, done.stdout)[1]) for name in ('free', 'inactive', 'speculative'))
        return pages * page / 2 ** 30
    except (OSError, subprocess.SubprocessError, TypeError, ValueError, IndexError):
        return None


def open_lock():
    """Open the lock file under the fixed anchor; refuse anything but a private regular file we own."""
    try:
        with data_root.anchor_folder(create=True) as folder:
            fd = os.open(LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=folder)
    except (OSError, ValueError) as error:
        raise Refused('lock location refused') from error
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or info.st_mode & 0o077):
        os.close(fd)
        raise Refused('lock location refused')
    return fd


def lock_identity():
    fd = open_lock()
    try:
        info = os.fstat(fd)
        return info.st_dev, info.st_ino
    finally:
        os.close(fd)


def lock_state():
    """'held' or 'free' from a non-blocking probe; 'refused' when the location is unsafe."""
    try:
        fd = open_lock()
    except Refused:
        return 'refused'
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 'held'
        fcntl.flock(fd, fcntl.LOCK_UN)
        return 'free'
    finally:
        os.close(fd)


def process_age(pid):
    """Seconds since the process started, from `ps`; None when it is gone or unreadable."""
    try:
        done = subprocess.run([TOOLS['ps'], '-o', 'etime=', '-p', str(pid)], env=run_env.environment(),
                              capture_output=True, timeout=5, text=True)
        match = re.fullmatch(r'\s*(?:(?:(\d+)-)?(\d+):)?(\d+):(\d+)\s*', done.stdout)
        days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
        return ((days * 24 + hours) * 60 + minutes) * 60 + seconds
    except (OSError, subprocess.SubprocessError, AttributeError, ValueError):
        return None


def source(label, command, max_seconds, child=None):
    """What an investigator needs to find who started the job: no paths, no arguments, no environment values."""
    repo = name = None
    try:
        root = slots.find_root(os.getcwd())
        if root is not None:
            repo = slots.repository_code(root)
            name = root.name if slots.LABEL.fullmatch(root.name) else None
    except (OSError, ValueError):
        pass
    dispatch = os.environ.get('FNL_DISPATCH_ID')
    exe = os.path.basename(command[0]) if command else ''
    now = int(time.time())
    return {'v': 1, 'pid': os.getpid(), 'child': child, 'started': now, 'deadline': now + int(max_seconds),
            'label': label, 'repo': repo, 'repo_name': name,
            'dispatch': dispatch if dispatch and re.fullmatch(r'[A-Za-z0-9-]{1,40}', dispatch) else None,
            'exe': exe if re.fullmatch(r'[A-Za-z0-9._+-]{1,40}', exe) else None}


def holder():
    """The recorded source when its process is alive and started before the record; else None."""
    try:
        fd = open_lock()
    except Refused:
        return None
    try:
        raw = os.pread(fd, 1024, 0)
    finally:
        os.close(fd)
    try:
        data = json.loads(raw.decode('utf-8'))
        ok = (isinstance(data, dict) and data.get('v') == 1
              and all(isinstance(data.get(key), int) and not isinstance(data.get(key), bool) for key in ('pid', 'started', 'deadline'))
              and LABEL.fullmatch(data.get('label', '')))
    except (UnicodeError, ValueError):
        return None
    if not ok:
        return None
    age = process_age(data['pid'])
    if age is None or time.time() - age > data['started'] + 5:
        return None
    return data


def describe(data):
    """One investigator-friendly block; every value was validated when read."""
    now = int(time.time())
    lines = ['  label: %s' % data['label']]
    if data.get('repo') or data.get('repo_name'):
        lines.append('  repo: %s (%s)' % (data.get('repo_name') or 'unnamed', data.get('repo') or 'no code'))
    if data.get('dispatch'):
        lines.append('  dispatch: %s' % data['dispatch'])
    if data.get('exe'):
        lines.append('  command: %s' % data['exe'])
    lines.append('  pid: %d%s' % (data['pid'], ', child %d' % data['child'] if isinstance(data.get('child'), int) else ''))
    running = max(0, now - data['started'])
    limit = data['deadline'] - data['started']
    over = now - data['deadline']
    lines.append('  running: %d s of at most %d s%s' % (running, limit, ' (overdue by %d s)' % over if over > 0 else ''))
    return '\n'.join(lines)


def record(fd, data):
    raw = (json.dumps(data, separators=(',', ':')) + '\n').encode('utf-8')
    if len(raw) <= 1024:
        os.ftruncate(fd, 0)
        os.pwrite(fd, raw, 0)


def resource_wait(config):
    """None when a start is allowed, else the reason to keep waiting."""
    load = read_load()
    if load is not None and load >= config['load']:
        return 'load %.1f is at or above %.1f' % (load, config['load'])
    free = read_free_gb()
    if free is not None and free < config['memory_gb']:
        return 'free memory %.1f GB is below %.1f GB' % (free, config['memory_gb'])
    return None


def detached(argv):
    """True for Docker or Compose commands that ask for detached work."""
    base = os.path.basename(argv[0]) if argv else ''
    args = None
    if base == 'docker-compose':
        args = argv[1:]
    elif base == 'docker':
        if argv[1:2] == ['compose']:
            args = argv[2:]
        elif argv[1:2] == ['run']:
            args = argv[1:]
        elif argv[1:3] == ['container', 'run']:
            args = ['run'] + argv[3:]
    if args is None:
        return False
    sub = next((word for word in args if not word.startswith('-')), None)
    if sub not in ('up', 'run'):
        return False
    for word in args[args.index(sub) + 1:]:
        if word == '--':
            break
        if word == '--detach' or word.startswith('--detach=') or (word.startswith('-') and not word.startswith('--') and 'd' in word[1:]):
            return True
    return False


def run(args):
    if not LABEL.fullmatch(args.label):
        print('heavy_run: label must be 1 to 40 plain characters', file=sys.stderr)
        return 2
    try:
        extra = [run_env.validate_name(name) for name in args.pass_env]
        run_env.environment(names=extra)
    except ValueError:
        print('heavy_run: refused environment name', file=sys.stderr)
        return 2
    if not args.command:
        print('heavy_run: a command is required after --', file=sys.stderr)
        return 2
    if detached(args.command):
        print('heavy_run: detached launches are refused; wrap a foreground script that starts, tests and tears down', file=sys.stderr)
        return 64
    config = limits()
    wait = args.wait_seconds if args.wait_seconds is not None else config['wait_minutes'] * 60
    max_seconds = args.max_seconds if args.max_seconds is not None else (
        args.max_minutes if args.max_minutes is not None else config['max_minutes']) * 60
    try:
        fd = open_lock()
    except Refused as error:
        print('heavy_run: %s' % error, file=sys.stderr)
        return 78
    deadline = time.monotonic() + wait
    reason = None
    while True:
        reason = resource_wait(config)
        if reason is None:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                reason = 'another heavy job holds the lock'
        if time.monotonic() >= deadline:
            who = holder()
            tail = ' (holder: %s, repo %s, %d s running)' % (who['label'], who.get('repo_name') or who.get('repo') or 'unknown',
                                                           max(0, int(time.time()) - who['started'])) if who else ''
            print('heavy_run: gave up waiting: %s%s' % (reason, tail), file=sys.stderr)
            os.close(fd)
            return 75
        time.sleep(args.poll)
    try:
        child = subprocess.Popen(args.command, env=run_env.environment(names=extra), pass_fds=(fd,), start_new_session=True)
    except OSError:
        os.close(fd)
        print('heavy_run: could not start the command', file=sys.stderr)
        return 127
    record(fd, source(args.label, args.command, max_seconds, child.pid))

    def forward(number, _frame):
        try:
            os.killpg(child.pid, number)
        except OSError:
            pass

    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, forward)
    timed_out = False
    try:
        try:
            status = child.wait(timeout=max_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            forward(signal.SIGTERM, None)
            try:
                status = child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                forward(signal.SIGKILL, None)
                status = child.wait()
            forward(signal.SIGKILL, None)
        # Keep the lock while anything the command left running in its own process group is alive.
        while True:
            try:
                os.killpg(child.pid, 0)
            except OSError:
                break
            time.sleep(min(args.poll, 0.2))
    finally:
        os.close(fd)
    if timed_out:
        print('heavy_run: stopped after the maximum run time', file=sys.stderr)
        return 124
    return status if status >= 0 else 128 - status


def status():
    state = lock_state()
    if state == 'refused':
        print('heavy lock: location refused')
        return 78
    if state == 'free':
        print('heavy lock: free')
    else:
        who = holder()
        print('heavy lock: held, owner unknown' if not who else 'heavy lock: held\n' + describe(who))
    load, free = read_load(), read_free_gb()
    print('load: %s' % ('unknown' if load is None else '%.1f' % load))
    print('memory: %s' % ('unknown' if free is None else '%.1f GB free' % free))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='heavy_run.py')
    parser.add_argument('--poll', type=float, default=15.0, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest='action', required=True)
    runner = sub.add_parser('run')
    runner.add_argument('--label', default='heavy job')
    runner.add_argument('--pass-env', action='append', default=[], metavar='NAME')
    runner.add_argument('--max-minutes', type=float, default=None, help='stop the command after this long (default 90)')
    runner.add_argument('--wait-seconds', type=float, default=None, help=argparse.SUPPRESS)
    runner.add_argument('--max-seconds', type=float, default=None, help=argparse.SUPPRESS)
    runner.add_argument('command', nargs=argparse.REMAINDER)
    sub.add_parser('status')
    args = parser.parse_args(argv)
    if args.action == 'status':
        return status()
    if args.command[:1] == ['--']:
        args.command = args.command[1:]
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
