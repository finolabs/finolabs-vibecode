#!/usr/bin/env python3
"""Run one heavy command at a time on this machine.

`run [--label L] [--pass-env NAME]... -- <command...>` waits for the machine-wide lock and for load and free
memory to allow a start, then runs the command and returns its exit status. `status` reports whether the lock is
held. Exit 64: detached work refused; 75: the wait cap ended; 78: the lock location is unsafe; 124: stopped after the
maximum run time; 2: bad usage.

The lock is a kernel advisory lock on one regular file in the plugin's fixed anchor folder, so it does not move
when the data root is relocated. The wrapper holds it until the command's process group is empty or the maximum
run time ends. If the wrapper is killed, the lock file also records the command's process group; a later start that
gets the kernel lock still waits for as long as that group is alive, whatever the command did with the inherited
descriptor and however old the record is. A recycled process group id can keep a start waiting until the wait cap
(exit 75); the message says why and `status` shows it. The only gap is the instant between starting the command
and writing that record. Nothing here prints or stores the environment or the command.
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

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root
import parallel_slots as slots
import run_env

LOCK_NAME = 'heavy.lock'
LABEL = re.compile(r'[A-Za-z0-9 ._-]{1,40}')
CODE = re.compile(r'[A-Za-z0-9_-]{1,40}')
DISPATCH = re.compile(r'[A-Za-z0-9-]{1,40}')
PID_LIMIT = 2 ** 31
EXE = re.compile(r'[A-Za-z0-9._+-]{1,40}')
DEFAULTS = {'load': 12.0, 'memory_gb': 3.0, 'wait_minutes': 40.0, 'max_minutes': 90.0}
BOUNDS = {'load': (1.0, 256.0), 'memory_gb': (0.0, 64.0), 'wait_minutes': (1.0, 720.0), 'max_minutes': (1.0, 720.0)}
KEYS = {'Load limit': 'load', 'Memory minimum GB': 'memory_gb', 'Wait cap minutes': 'wait_minutes', 'Max job minutes': 'max_minutes'}
TOOLS = {'vm_stat': '/usr/bin/vm_stat', 'ps': '/bin/ps', 'memory_pressure': '/usr/bin/memory_pressure',
         'sysctl': '/usr/sbin/sysctl'}


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
    """Free GB by the kernel's own figure, else by the `vm_stat` estimate; None when neither is readable."""
    kernel = kernel_free_gb()
    return kernel if kernel is not None else vm_stat_free_gb()


def kernel_free_gb():
    """`memory_pressure` free percentage times `hw.memsize`, in GB; None when either cannot be read or parsed.

    Only the one percentage line (0 to 100) and the byte count are parsed; nothing else is kept."""
    try:
        env = run_env.environment()
        pressure = subprocess.run([TOOLS['memory_pressure']], env=env, capture_output=True, timeout=5, text=True)
        sized = subprocess.run([TOOLS['sysctl'], '-n', 'hw.memsize'], env=env, capture_output=True, timeout=5, text=True)
        if pressure.returncode != 0 or sized.returncode != 0:
            return None
        found = re.search(r'^System-wide memory free percentage:\s*(\d{1,3})%', pressure.stdout, re.MULTILINE)
        total = int(sized.stdout.strip())
        if found is None or int(found[1]) > 100 or total <= 0:
            return None
        return int(found[1]) / 100 * total / 2 ** 30
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        return None


def vm_stat_free_gb():
    """Memory the kernel can give back without a start-time cost, in GB, from `vm_stat`; None when unreadable.

    free + the larger of (inactive + speculative) and the file-backed pages. File-backed pages (the clean file cache,
    speculative ones included) are droppable even while active, which inactive + speculative alone misses; taking the
    larger of the two avoids counting the same page twice. Purgeable pages are not added: they can already sit inside
    the inactive count and their overlap cannot be measured, so the fallback stays conservative. Compressed memory is
    never added: it is already holding data. The file-backed line is optional (0 when absent)."""
    try:
        done = subprocess.run([TOOLS['vm_stat']], env=run_env.environment(), capture_output=True, timeout=5, text=True)
        page = int(re.search(r'page size of (\d+) bytes', done.stdout)[1])

        def pages(label, required=True):
            found = re.search(r'^%s:\s+(\d+)' % label, done.stdout, re.MULTILINE)
            if found is None and required:
                raise ValueError(label)
            return int(found[1]) if found else 0

        total = pages('Pages free') + max(pages('Pages inactive') + pages('Pages speculative'), pages('File-backed pages', False))
        return total * page / 2 ** 30
    except (OSError, subprocess.SubprocessError, TypeError, ValueError, IndexError):
        return None


def heavy_run_action(words):
    """True for `[/usr/bin/env] python* [options] .../heavy_run.py [options] run`; the program word must be Python."""
    if words and words[0] == '/usr/bin/env':
        words = words[1:]
    if not words or not os.path.basename(words[0]).startswith('python'):
        return False
    rest = [word for word in words[1:] if not word.startswith('-')]
    if not rest or os.path.basename(rest[0]) != 'heavy_run.py':
        return False
    after = words[words.index(rest[0]) + 1:]
    after = [word for word in after if word != '--poll' and not re.fullmatch(r'[0-9.]+', word)]
    return after[:1] == ['run']


def waiting_count():
    """Number of other `heavy_run.py run` processes, from `ps`; None when it cannot be read. Counts only; no text kept."""
    try:
        done = subprocess.run([TOOLS['ps'], '-axo', 'pid=,command='], env=run_env.environment(),
                              capture_output=True, timeout=5, text=True)
        if done.returncode != 0:
            return None
        count = 0
        for line in done.stdout.splitlines():
            words = line.split()
            if len(words) < 3 or not words[0].isdigit() or int(words[0]) == os.getpid():
                continue
            if heavy_run_action(words[1:]):
                count += 1
        return count
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def open_lock():
    """Open the lock file under the fixed anchor; refuse anything but a private regular file we own."""
    fd = None
    for attempt in range(5):
        try:
            with data_root.anchor_folder(create=True) as folder:
                fd = os.open(LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=folder)
            break
        except FileNotFoundError as error:
            # Two processes creating the file at the same instant can make macOS report a missing file once.
            if attempt == 4:
                raise Refused('lock location refused') from error
            time.sleep(0.01 * (attempt + 1))
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
            'dispatch': dispatch if dispatch and DISPATCH.fullmatch(dispatch) else None,
            'exe': exe if EXE.fullmatch(exe) else None}


def valid_record(data):
    """True only for a record whose every field has the expected type and format."""
    def whole(key, high=2 ** 40):
        value = data.get(key)
        return isinstance(value, int) and not isinstance(value, bool) and 1 <= value < high

    def text(key, pattern):
        value = data.get(key)
        return value is None or (isinstance(value, str) and pattern.fullmatch(value) is not None)

    return (isinstance(data, dict) and data.get('v') == 1 and whole('pid', PID_LIMIT) and whole('started') and whole('deadline')
            and data['deadline'] >= data['started'] and (data.get('child') is None or whole('child', PID_LIMIT))
            and isinstance(data.get('label'), str) and LABEL.fullmatch(data['label']) is not None
            and text('repo', CODE) and text('repo_name', LABEL) and text('dispatch', DISPATCH) and text('exe', EXE))


def read_record(fd):
    try:
        data = json.loads(os.pread(fd, 1024, 0).decode('utf-8'))
    except (UnicodeError, ValueError):
        return None
    return data if valid_record(data) else None


def group_alive(group):
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except (OSError, OverflowError, ValueError):
        return True
    return True


def holder():
    """The recorded source when its process is alive and started before the record; else None."""
    try:
        fd = open_lock()
    except Refused:
        return None
    try:
        data = read_record(fd)
    finally:
        os.close(fd)
    if data is None:
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


# Option arities of the supported CLIs: (long options taking a value, short letters taking a value, boolean options).
# An option that is in none of these makes the arity unknown, so a command that may start detached work is refused.
DOCKER_GLOBAL = ({'--config', '--context', '--host', '--log-level', '--tlscacert', '--tlscert', '--tlskey'}, set('Hcl'),
                 {'--debug', '--tls', '--tlsverify', '--version', '--help', '-D', '-v', '-h'})
COMPOSE_GLOBAL = ({'--file', '--project-name', '--profile', '--project-directory', '--env-file', '--ansi', '--parallel',
                   '--progress'}, set('fp'),
                  {'--all-resources', '--compatibility', '--dry-run', '--verbose', '--no-ansi', '--help', '--version',
                   '-v', '-h'})
RUN_OPTIONS = ({'--add-host', '--annotation', '--attach', '--blkio-weight', '--blkio-weight-device', '--cap-add',
                '--cap-drop', '--cgroup-parent', '--cgroupns', '--cidfile', '--cpu-period', '--cpu-quota',
                '--cpu-rt-period', '--cpu-rt-runtime', '--cpu-shares', '--cpus', '--cpuset-cpus', '--cpuset-mems',
                '--detach-keys', '--device', '--device-cgroup-rule', '--device-read-bps', '--device-read-iops',
                '--device-write-bps', '--device-write-iops', '--dns', '--dns-option', '--dns-search', '--domainname',
                '--entrypoint', '--env', '--env-file', '--expose', '--gpus', '--group-add', '--health-cmd',
                '--health-interval', '--health-retries', '--health-start-interval', '--health-start-period',
                '--health-timeout', '--hostname', '--ip', '--ip6', '--ipc', '--isolation', '--kernel-memory', '--label',
                '--label-file', '--link', '--link-local-ip', '--log-driver', '--log-opt', '--mac-address', '--memory',
                '--memory-reservation', '--memory-swap', '--memory-swappiness', '--mount', '--name', '--net',
                '--net-alias', '--network', '--network-alias', '--oom-score-adj', '--pid', '--pids-limit', '--platform',
                '--publish', '--pull', '--restart', '--runtime', '--security-opt', '--shm-size', '--stop-signal',
                '--stop-timeout', '--storage-opt', '--sysctl', '--tmpfs', '--ulimit', '--user', '--userns', '--uts',
                '--volume', '--volume-driver', '--volumes-from', '--workdir'}, set('acehlmpuvw'),
               {'--detach', '--interactive', '--tty', '--rm', '--privileged', '--read-only', '--init', '--sig-proxy',
                '--oom-kill-disable', '--publish-all', '--no-healthcheck', '--quiet', '--disable-content-trust',
                '--help', '--no-deps', '--build', '--use-aliases', '--service-ports', '--quiet-pull', '--remove-orphans',
                '--no-TTY', '-d', '-i', '-t', '-P', '-q', '-T'})


class UnknownArity(Exception):
    """An option was met whose arity the tables do not describe."""


def options_until_positional(words, long_values, short_values, booleans):
    """(option tokens, remaining words) up to the first word that is not an option or an option's value."""
    flags, index = [], 0
    while index < len(words):
        word = words[index]
        if word == '--':
            return flags, words[index + 1:]
        if word.startswith('--'):
            name = word.split('=', 1)[0]
            flags.append(word)
            if name in long_values:
                if '=' not in word:
                    index += 1
            elif name not in booleans:
                raise UnknownArity(name)
        elif word.startswith('-') and len(word) > 1:
            for position, letter in enumerate(word[1:], 1):
                flags.append('-' + letter)
                if letter in short_values:
                    if position == len(word) - 1:
                        index += 1
                    break
                if '-' + letter not in booleans:
                    raise UnknownArity(letter)
        else:
            return flags, words[index:]
        index += 1
    return flags, []


FALSE_WORDS = {'0', 'f', 'F', 'false', 'FALSE', 'False'}


def asks_detach(flags):
    """True for -d, --detach and Compose's --wait (which implies detach), unless an explicit value is a false spelling."""
    for flag in flags:
        name, _, value = flag.partition('=')
        if name in ('-d', '--detach', '--wait') and (flag == name or value not in FALSE_WORDS):
            return True
    return False


def detached(argv):
    """True for Docker or Compose commands that ask for detached work, or whose options cannot be read with certainty."""
    base = os.path.basename(argv[0]) if argv else ''
    try:
        return _detached(argv, base)
    except UnknownArity:
        # Refuse only when the command could still start containers.
        return base in ('docker', 'docker-compose') and any(word in ('run', 'up') for word in argv[1:])


def _detached(argv, base):
    kind = None
    if base == 'docker-compose':
        words, kind = argv[1:], 'compose'
    elif base == 'docker':
        _flags, rest = options_until_positional(argv[1:], *DOCKER_GLOBAL)
        if rest[:1] == ['compose']:
            words, kind = rest[1:], 'compose'
        elif rest[:1] == ['run']:
            words, kind = rest[1:], 'run'
        elif rest[:2] == ['container', 'run']:
            words, kind = rest[2:], 'run'
    if kind is None:
        return False
    if kind == 'run':
        return asks_detach(options_until_positional(words, *RUN_OPTIONS)[0])
    _flags, rest = options_until_positional(words, *COMPOSE_GLOBAL)
    if rest[:1] == ['up']:
        for word in rest[1:]:
            if word == '--':
                break
            if asks_detach([word]) or (word.startswith('-') and not word.startswith('--') and 'd' in word[1:]):
                return True
    elif rest[:1] == ['run']:
        return asks_detach(options_until_positional(rest[1:], *RUN_OPTIONS)[0])
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
    for number in (args.poll, args.wait_seconds, args.max_seconds, args.max_minutes):
        if number is not None and not (0 < number < 10 ** 7):
            print('heavy_run: times must be positive finite numbers', file=sys.stderr)
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
            except BlockingIOError:
                reason = 'another heavy job holds the lock'
            else:
                if previous_group_running(fd):
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    reason = 'a heavy job started by a stopped wrapper is still running'
                elif time.monotonic() > deadline:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    reason = 'the wait cap ended before the start'
                else:
                    os.ftruncate(fd, 0)
                    break
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(args.poll, remaining))
        if remaining <= 0 or time.monotonic() >= deadline:
            who = holder()
            tail = ' (holder: %s, repo %s, %d s running)' % (who['label'], who.get('repo_name') or who.get('repo') or 'unknown',
                                                           max(0, int(time.time()) - who['started'])) if who else ''
            print('heavy_run: gave up waiting: %s%s' % (reason, tail), file=sys.stderr)
            os.close(fd)
            return 75
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
    limit = time.monotonic() + max_seconds
    timed_out, kill_at, status = False, None, None
    try:
        # One deadline covers the command and anything it left running in its process group.
        while True:
            if status is None:
                status = child.poll()
            if status is not None and not group_alive(child.pid):
                break
            now = time.monotonic()
            if not timed_out and now >= limit:
                timed_out, kill_at = True, now + 10
                forward(signal.SIGTERM, None)
            elif timed_out and now >= kill_at:
                forward(signal.SIGKILL, None)
                if now >= kill_at + 10:
                    break
            time.sleep(min(args.poll, 0.1))
        # Keep the record while any member of the group is still alive, so the next start keeps waiting.
        if not group_alive(child.pid):
            try:
                os.ftruncate(fd, 0)
            except OSError:
                pass
    finally:
        os.close(fd)
    if timed_out:
        print('heavy_run: stopped after the maximum run time', file=sys.stderr)
        return 124
    return status if status >= 0 else 128 - status


def previous_group_running(fd):
    """True when the record left by an earlier wrapper names a process group that is alive and within its deadline."""
    data = read_record(fd)
    return bool(data and data.get('child') and group_alive(data['child']))


def status():
    state = lock_state()
    if state == 'refused':
        print('heavy lock: location refused')
        return 78
    if state == 'free':
        orphan = False
        try:
            fd = open_lock()
            try:
                orphan = previous_group_running(fd)
            finally:
                os.close(fd)
        except Refused:
            pass
        print('heavy lock: free, but a job from a stopped wrapper is still running' if orphan else 'heavy lock: free')
    else:
        who = holder()
        print('heavy lock: held, owner unknown' if not who else 'heavy lock: held\n' + describe(who))
    processes = waiting_count()
    waiting = None if processes is None else max(0, processes - 1) if state == 'held' else processes
    print('waiting: %s' % ('unknown' if waiting is None else 'about %d' % waiting))
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
