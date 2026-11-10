#!/usr/bin/env python3
"""Run or show the current repository's stored checks; optionally write a local receipt.

Usage, from inside the repository:
  checks.py run [--changed] [--base <ref>]   run the stored list in order, stop at the first failure
  checks.py show                             print the stored list and the local-receipt mode

Each check is an argument array from `## Checks` of the canonical host config (written only by fnl-setup's
`checks_setup.py`), launched through `heavy_run.py`'s canonical form with no shell and an allowlisted environment;
the checks' own output streams through. `--changed` keeps only the checks the change since the base touches: a
`python -m unittest` check is narrowed to the modules `select_tests.py` names, every other check runs whole.
A run of the whole list first removes any earlier receipt for the repository, so the latest full run decides; when
the repository's local-receipt mode is on, a passing run of the whole list on a clean tree whose head did not
move writes a receipt (repository code, head, list digest) in the private state folder. `--changed` neither writes
nor removes one. It edits no file of the
repository and makes no network call. Exits: 0 passed, 1 a check failed, 2 refused or unknown, 3 invalid list.
"""
import argparse
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


def is_unittest(argv):
    return bool(cl.INTERPRETER.fullmatch(cl.program_name(argv[0]))) and argv[1:3] == ['-m', 'unittest']


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
        if not is_unittest(argv) or not all(MODULE.fullmatch(module) for module in modules):
            plan.append((name, argv))  # deny on doubt: an odd module name runs the check whole
        elif not modules:
            skipped.append((name, 'no Python test module names a changed file'))
        else:
            for group in select_tests.groups(modules):
                plan.append((name, [argv[0], '-m', 'unittest', *group]))
    return plan, skipped


def run(changed, base):
    root, code = repository()
    checks, reason = cl.checks_for(code)
    if reason:
        print(f'Repository {code}: no checks ({reason}); nothing was run. Set them with /fnl-setup add checks.',
              file=sys.stderr)
        return 3 if reason in ('invalid', 'unreadable') else 2
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='action', required=True)
    runner = commands.add_parser('run')
    runner.add_argument('--changed', action='store_true')
    runner.add_argument('--base', default=DEFAULT_BASE)
    commands.add_parser('show')
    args = parser.parse_args(argv)
    try:
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
