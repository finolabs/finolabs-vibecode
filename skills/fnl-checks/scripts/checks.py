#!/usr/bin/env python3
"""Run or show the current repository's stored checks; optionally write a local receipt.

Usage, from inside the repository:
  checks.py run [--changed] [--base <ref>]   run the stored list in order, stop at the first failure
  checks.py show                             print the stored list and the local-receipt mode
  checks.py usage --from <runs.json> [--files-from <paths.json>] [--limit-minutes N]
                                             summarise CI runs and minutes from files; no network, no process

Each check is an argument array from `## Checks` of the canonical host config (written only by fnl-setup's
`checks_setup.py`), launched through `heavy_run.py`'s canonical form with no shell and an allowlisted environment;
the checks' own output streams through. `--changed` keeps only the checks the change since the base touches: a
`python -m unittest discover -s tests` check keeps its discovery and gets one `--pattern <file>` run per module
`select_tests.py` names, only when the tests folder is flat (see `layout_covered`); every other check, unittest form
and layout runs whole.
A run of the whole list first removes any earlier receipt for the repository, so the latest full run decides; when
the repository's local-receipt mode is on, a passing run of the whole list on a clean tree whose head did not
move writes a receipt (repository code, head, list digest) in the private state folder. One whole-list run per
repository at a time: it holds a private lock file beside the receipt from before the removal until the receipt is
written or declined, and a second one refuses. `--changed` neither writes nor removes a receipt and takes no lock.
It edits no file of the
repository and makes no network call. Exits: 0 passed, 1 a check failed, 2 refused or unknown, 3 invalid list or malformed
usage input.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import checks_list as cl
import project_progress as pp
import run_env
import select_tests

HEAVY = Path(__file__).resolve().parent / 'heavy_run.py'
MODULE = re.compile(r'tests\.test_[A-Za-z0-9_]{1,100}')
DEFAULT_BASE = 'origin/main'


class Refused(Exception):
    pass


def launch_argv(name, argv):
    """The canonical heavy_run.py launch form; the check's own argument array follows `--` unchanged."""
    return [sys.executable, '-I', str(HEAVY), 'run', '--label', 'check ' + name, '--', *argv]


def run_one(name, argv, root):
    done = subprocess.run(launch_argv(name, argv), cwd=root, env=run_env.environment(), check=False)
    return done.returncode


def git(root, *args):
    """(exit code, stdout) of a read-only git query with a fixed prefix; never raises for a git failure."""
    try:
        done = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                               '-C', str(root), *args], capture_output=True, text=True, encoding='utf-8',
                              timeout=60, check=False, env=run_env.environment())
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return 1, ''
    return done.returncode, done.stdout


def head(root):
    code, out = git(root, 'rev-parse', '--verify', 'HEAD^{commit}')
    out = out.strip()
    return out if code == 0 and cl.HEAD.fullmatch(out) else None


def clean(root):
    code, out = git(root, 'status', '--porcelain', '--untracked-files=all')
    return code == 0 and not out.strip()


def repository():
    root = pp.find_root(os.getcwd())
    if root is None:
        raise Refused('not inside a git repository')
    return root, pp.repository_code(root)


def full_run_lock(code):
    """An open fd holding an exclusive, non-blocking flock on `state/checks-receipts/<code>.lock`, a private
    regular file owned by this account; Refused when another full run holds it or the file is unsafe."""
    import data_root as dr
    import fcntl
    import stat
    if not isinstance(code, str) or not cl.CODE.fullmatch(code):
        raise Refused('invalid repository code')
    try:
        with dr.data_folder(cl.RECEIPTS, create=True, private=True) as folder:
            fd = os.open(code + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600,
                         dir_fd=folder)
    except (OSError, ValueError):
        raise Refused('the full-run lock could not be opened; nothing was run') from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o077):
            raise Refused('the full-run lock could not be opened; nothing was run')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("another full run of this repository's checks is in progress") from None
        except OSError:
            raise Refused('the full-run lock could not be taken; nothing was run') from None
    except BaseException:
        os.close(fd)
        raise
    return fd


DISCOVERY_OPTIONS = {'-s': 'tests', '-p': 'test_*.py'}


def narrowable(argv):
    """True only for the forms the selector understands: `<python> -m unittest discover -s tests`, optionally with
    `-p test_*.py`, in either order. A bare `unittest` or `discover` starts at the repository root and recurses into
    every importable package, so it runs whole, as does every other form."""
    if not (len(argv) >= 3 and cl.program_name(argv[0]).startswith('python')
            and cl.INTERPRETER.fullmatch(cl.program_name(argv[0])) and argv[1:3] == ['-m', 'unittest']):
        return False
    rest = argv[3:]
    if not rest or rest[0] != 'discover' or len(rest) % 2 == 0:
        return False
    pairs = [(rest[i], rest[i + 1]) for i in range(1, len(rest), 2)]
    flags = [flag for flag, _ in pairs]
    return ('-s' in flags and len(set(flags)) == len(flags)
            and all(DISCOVERY_OPTIONS.get(flag) == value for flag, value in pairs))


def discovery_without_pattern(argv):
    """The stored `discover` argv with any `-p <pattern>` pair removed; `narrowable` has already checked its form."""
    kept = list(argv[:4])
    for index in range(4, len(argv), 2):
        if argv[index] != '-p':
            kept += argv[index:index + 2]
    return kept


def layout_covered(root, argv):
    """True when the selector's flat index of `tests/test_*.py` is exactly what discovery would find: no folder
    under `tests/` holds a Python file (discovery recurses into packages), and with the default pattern `test*.py`
    no top-level file matches it that `test_*.py` does not. Any doubt (a link, an unreadable folder) is False."""
    import fnmatch
    folder = Path(root) / 'tests'
    pattern = 'test_*.py' if '-p' in argv else 'test*.py'
    try:
        if folder.is_symlink() or not folder.is_dir():
            return False
        for entry in folder.iterdir():
            if entry.is_symlink():
                return False
            if entry.is_dir():
                if any(entry.rglob('*.py')):
                    return False
            elif fnmatch.fnmatchcase(entry.name, pattern) and not fnmatch.fnmatchcase(entry.name, 'test_*.py'):
                return False
    except OSError:
        return False
    return True


def narrow(checks, base, root):
    """[(label, argv)] to run and [(name, reason)] skipped, for the change since `base`."""
    if not select_tests.REF.fullmatch(base) or '..' in base:
        raise Refused('refused base')
    try:
        changed = select_tests.changed_files(base, root)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        raise Refused('git diff against the base failed; pass a known --base') from None
    if not changed:
        return [], [(name, 'no changed files') for name, _ in checks]
    modules, _ = select_tests.select(str(root), changed)
    plan, skipped = [], []
    for name, argv in checks:
        if (not narrowable(argv) or not layout_covered(root, argv)
                or not all(MODULE.fullmatch(module) for module in modules)):
            plan.append((name, argv))  # deny on doubt: an odd module name runs the check whole
        elif not modules:
            skipped.append((name, 'no Python test module names a changed file'))
        else:
            # Keep the stored discovery and change only its pattern: the start folder, import path and module names
            # stay those of the whole run, which a rewrite to `unittest tests.test_x` would change.
            stored = discovery_without_pattern(argv)
            for module in modules:
                plan.append((name, [*stored, '--pattern', module.removeprefix('tests.') + '.py']))
    return plan, skipped


def run(changed, base):
    root, code = repository()
    checks, reason = cl.checks_for(code)
    if reason:
        print(f'Repository {code}: no checks ({reason}); nothing was run. Set them with /fnl-setup add checks.',
              file=sys.stderr)
        return 3 if reason in ('invalid', 'unreadable') else 2
    if changed:
        return run_list(root, code, checks, changed, base)
    # One full run per repository at a time, separate from (and never inside) the heavy-job lock: taken before the
    # old receipt is removed and the first heavy_run launch, released after the new receipt is written or declined.
    lock = full_run_lock(code)
    try:
        return run_list(root, code, checks, changed, base)
    finally:
        os.close(lock)


def run_list(root, code, checks, changed, base):
    digest = cl.list_digest(checks)
    mode = cl.receipt_mode(code)
    start_head, start_clean = (head(root), clean(root)) if mode and not changed else (None, False)
    if changed:
        plan, skipped = narrow(checks, base, root)
    else:
        plan, skipped = list(checks), []
        # The latest full run decides: drop any earlier receipt before the first check, so a failed rerun leaves none.
        try:
            cl.remove_receipt(code)
        except (OSError, ValueError):
            raise Refused('the earlier local receipt could not be removed; nothing was run') from None
    for name, why in skipped:
        print(f'skipped {name}: {why}')
    for name, argv in plan:
        print(f'check {name}: {cl.check_argv(list(argv))}', flush=True)
        result = run_one(name, argv, root)
        if result != 0:
            print(f'check {name} failed with exit code {result}; later checks were not run.', flush=True)
            if mode:
                print('no local receipt: a check failed')
            return 1
    print(f'{len(plan)} checks passed' + (f', {len(skipped)} skipped' if skipped else '') + '.')
    if not mode:
        return 0
    if changed:
        print('no local receipt: a --changed run covers only part of the list')
        return 0
    end_head = head(root)
    current, reason = cl.checks_for(code)
    if not start_clean or not clean(root):
        why = 'the working tree is not clean'
    elif start_head is None or end_head != start_head:
        why = 'the head moved during the run'
    elif reason or cl.list_digest(current) != digest or not cl.receipt_mode(code):
        why = 'the check list or its mode changed during the run'
    else:
        try:
            cl.write_receipt(code, start_head, digest)
        except (OSError, ValueError):
            print('no local receipt: the private state folder could not be written')
            return 0
        print(f'local receipt written for {start_head[:12]}: self-reported, it proves only that this machine '
              'ran the whole list at that head.')
        return 0
    print('no local receipt: ' + why)
    return 0


def show():
    _, code = repository()
    checks, reason = cl.checks_for(code)
    if reason:
        print(f'Repository {code}: no checks ({reason}).')
        return 3 if reason in ('invalid', 'unreadable') else 0
    print(f'Repository {code}:')
    for name, argv in checks:
        print(f'{name} = {cl.check_argv(list(argv))}')
    print('local receipt: ' + ('on' if cl.receipt_mode(code) else 'off'))
    return 0


# What the minutes cost: read a run list the agent produced with the host's own command; no network, no process

USAGE_LIMIT = 5 * 1024 * 1024
MAX_RUNS = 5000
RUN_REQUIRED = {'databaseId', 'event', 'workflowName', 'startedAt', 'updatedAt'}
RUN_ALLOWED = RUN_REQUIRED | {'headBranch', 'conclusion', 'createdAt', 'status'}
UTC_TIME = re.compile(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?Z')


class Malformed(Exception):
    pass


def read_json(path, what):
    """The parsed JSON of a regular file of at most USAGE_LIMIT bytes; Refused when it cannot be read."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        raise Refused(f'{what} could not be opened') from None
    with os.fdopen(fd, 'rb') as stream:
        import stat
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise Refused(f'{what} is not a regular file')
        raw = stream.read(USAGE_LIMIT + 1)
    if len(raw) > USAGE_LIMIT:
        raise Malformed(f'{what} is over 5 MB')
    def unique(pairs):
        keys = [key for key, _ in pairs]
        if len(set(keys)) != len(keys):
            raise ValueError('duplicate key')
        return dict(pairs)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
    except (UnicodeError, ValueError, RecursionError):
        raise Malformed(f'{what} is not valid JSON') from None


def utc_time(value):
    """Seconds since the epoch of a strict ISO 8601 UTC time such as 2026-11-01T10:00:00Z (optional fraction)."""
    import datetime
    match = UTC_TIME.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise Malformed('a time is not ISO 8601 UTC (YYYY-MM-DDTHH:MM:SSZ)')
    try:
        moment = datetime.datetime(*(int(part) for part in match.groups()[:6]), tzinfo=datetime.timezone.utc)
    except ValueError:
        raise Malformed('a time is not a valid date') from None
    return moment.timestamp() + (float('0.' + match[7]) if match[7] else 0.0)


UNNAMED = '(unnamed workflow)'


def read_runs(path):
    data = read_json(path, 'the run list')
    if not isinstance(data, list):
        raise Malformed('the run list is not a JSON array')
    if len(data) > MAX_RUNS:
        raise Malformed('the run list has more than 5,000 runs')
    runs, seen = [], set()
    for item in data:
        if not isinstance(item, dict) or not RUN_REQUIRED <= set(item) or not set(item) <= RUN_ALLOWED:
            raise Malformed('a run lacks a required field or has an unknown one')
        identifier = item['databaseId']
        if type(identifier) is not int or identifier < 0 or identifier in seen:
            raise Malformed('a run has an invalid or repeated databaseId')
        seen.add(identifier)
        for key, shortest in (('event', 1), ('workflowName', 0)):  # gh reports some ruleset runs with no name
            if not isinstance(item[key], str) or not shortest <= len(item[key]) <= 200 or not item[key].isprintable():
                raise Malformed(f'a run has an invalid {key}')
        start, end = utc_time(item['startedAt']), utc_time(item['updatedAt'])
        if 'createdAt' in item:
            utc_time(item['createdAt'])
        if end < start:
            raise Malformed('a run ends before it starts')
        runs.append({'id': identifier, 'event': item['event'], 'workflow': item['workflowName'] or UNNAMED,
                     'start': start, 'end': end, 'minutes': -int(-(end - start) // 60)})
    return runs


def read_files(path):
    data = read_json(path, 'the changed-paths map')
    if not isinstance(data, dict) or len(data) > MAX_RUNS:
        raise Malformed('the changed-paths map is not a JSON object of at most 5,000 runs')
    files = {}
    for key, paths in data.items():
        if not re.fullmatch(r'0|[1-9][0-9]{0,19}', key) or not isinstance(paths, list) or len(paths) > 10000 \
                or not all(isinstance(item, str) and 0 < len(item) <= 4096 for item in paths):
            raise Malformed('the changed-paths map needs run ids mapped to lists of paths')
        files[int(key)] = paths
    return files


def by_minutes(totals):
    return sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))


def usage(source, files_source, limit):
    """Print runs, minutes per workflow and event, the document-only share and days left; 0, 2 or 3."""
    runs = read_runs(source)
    files = read_files(files_source) if files_source else None
    total = sum(run['minutes'] for run in runs)
    print(f'runs: {len(runs)}')
    print(f'minutes: {total} (each run from startedAt to updatedAt, rounded up to whole minutes; GitHub bills each '
          'job this way, so a run with parallel jobs costs more)')
    for title, key in (('by workflow:', 'workflow'), ('by event:', 'event')):
        totals = {}
        for run in runs:
            totals[run[key]] = totals.get(run[key], 0) + run['minutes']
        if totals:
            print(title)
            for name, minutes in by_minutes(totals):
                print(f'  {name}: {minutes}')
    if files is not None:
        documents = [run for run in runs if cl.document_only(files.get(run['id']))]
        unknown = sum(1 for run in runs if run['id'] not in files)
        spent = sum(run['minutes'] for run in documents)
        share = round(100 * spent / total) if total else 0
        print(f'document-only: {len(documents)} run{"" if len(documents) == 1 else "s"}, {spent} minutes '
              f'({share}% of minutes), {unknown} run{"" if unknown == 1 else "s"} without changed paths; '
              'documents are paths matching ' + ', '.join(cl.DOCUMENT_PATTERNS))
    if limit is not None:
        left = limit - total
        if not runs:
            print(f'limit: {limit} minutes, {left} left; no runs to measure a rate')
        elif left <= 0:
            print(f'limit: {limit} minutes; limit reached by the runs in this file')
        else:
            days = max((max(run['end'] for run in runs) - min(run['start'] for run in runs)) / 86400, 1.0)
            rate = total / days
            print(f'limit: {limit} minutes, {left} left; the runs span {days:.1f} days at {rate:.1f} minutes a day, '
                  f'about {left / rate:.0f} days left' if rate else f'limit: {limit} minutes, {left} left')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='action', required=True)
    runner = commands.add_parser('run')
    runner.add_argument('--changed', action='store_true')
    runner.add_argument('--base', default=DEFAULT_BASE)
    commands.add_parser('show')
    counter = commands.add_parser('usage')
    counter.add_argument('--from', dest='source', required=True)
    counter.add_argument('--files-from')
    counter.add_argument('--limit-minutes', type=int)
    args = parser.parse_args(argv)
    try:
        if args.action == 'usage':
            if args.limit_minutes is not None and not 0 < args.limit_minutes <= 10_000_000:
                raise Refused('--limit-minutes must be a positive whole number')
            try:
                return usage(args.source, args.files_from, args.limit_minutes)
            except Malformed as error:
                print(f'checks: malformed input: {error}', file=sys.stderr)
                return 3
        if args.action == 'show':
            return show()
        if args.base != DEFAULT_BASE and not args.changed:
            raise Refused('--base needs --changed')
        return run(args.changed, args.base)
    except Refused as error:
        print(f'checks: refused: {error}', file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        print(f'checks: refused: {type(error).__name__}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
