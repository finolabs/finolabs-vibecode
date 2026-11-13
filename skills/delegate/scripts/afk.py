#!/usr/bin/env python3
"""Local afk lease, action classification and private action log; no execution.

Rule table (each row names its enforcer; unknown input always fails closed):

| Rule | Enforcer |
| --- | --- |
| Setup is one canonical ## afk key/value section (an older ## Autopilot heading is not read); Merge has no default, hours are 1..24 | settings, start |
| State stays outside Git, private (directories 0700/files 0600), no links, atomic and serialized | private_folder, read_private, write_private, data_root, flock |
| One live lease for the machine; a second start reports it and changes nothing; stop removes it and leaves a stop marker; starting clears that marker | start, stop |
| Missing/expired/stopped/changed setup or exhausted runs, wall/runtime minutes or rolling-hour actions denies every check; spent runs or runtime say `exhausted`, the rolling-hour cap says `limit`; a missing, expired, stopped or exhausted lease adds one fixed `end` line telling the caller to stop its loop | lease_guard, check |
| Tags, releases, publish/deploy, recursive deletion, force/default-branch pushes are Tier 3, except: closed tag, release and npm/pnpm publish forms whose every applicable category is `decide`, and a deploy matching a `Non-production targets` entry exactly with no production or live word; categories come from the program and subcommand, never from free-text data | classify_argv, command_categories, is_deploy, release_command, permits |
| Categories are `stop` or `decide`; missing, unknown and the two fixed rows are `stop`; excerpt consent is its own key | settings |
| The ladder's two forms: this install's judge.py at the away-decision site with validated options, and delegate_env.py with one closed read-only argv per family, in Hosts and not the coordinator's, whose program is the family's owner-approved executable recorded for the quota probe and re-checked at check time (no bare name, PATH lookup, other path or time-cap wrapper); the brief follows a literal `--` (Codex, Claude) or is the value of -p (Antigravity), never starts with `-`, and passes the secret and machine-path screens, and no sensitive name in it has an assigned value | ladder_command, judge_command, advisor_command, approved_program, quota_probe.checked_executable, brief_ok |
| Decision attempts follow a closed schema and reach the ledger with no question or option text; reviews need a recorded id | attempt, decide, review |
| A precedent packet holds at most eight excerpts and 8 KB; a secret or machine path drops an excerpt; excerpts need the separate consent | packet_check |
| Hard names (credentials/env/key names, .git, .github, .claude, .codex, git hook names, host/lease/log state) are Tier 3 anywhere in argv or paths; soft names (hooks, settings, config, setup, SKILL.md, CLAUDE.md, AGENTS.md) too, except in a source path of this check's own checkout on a non-default work branch with Push and pull requests or Merge yes, and never inside this install; the one exact script path of this install's own trusted wrapper is spared (the install may lie under ~/.claude or ~/.codex) | protected, own_wrapper_index, source_mode |
| An argv path operand inside a checkout of this repository (its own, the main checkout or a linked worktree `project_store.identity` validates; never a lexical .claude/worktrees allow) is judged by its path relative to that checkout's root; `git -C <folder>` is judged as the same command run in that folder | token_protected, checkout_of, check |
| Any path inside this install's own skill script folders is protected (a new module could shadow an import of a trusted wrapper), and so is every path, read from the check's folder, in this install's own checkout on every branch (the checkout `project_store.identity` validates for it is the plugin root, so its linked worktrees stay editable); only relative source/test/docs/script files in enumerated roots/extensions are known paths; security enforcer scripts deny edits; everything else is Tier 3; a git verb that changes a work tree, index or HEAD (not `worktree remove` of another worktree) is protected when it would run in that checkout, by its folder or `git -C` | classify_paths, token_protected, install_owned, WORK_TREE_VERBS |
| On a non-default work branch with Push and pull requests or Merge yes, a source path (skills/**, scripts/**, top-level CLAUDE.md and AGENTS.md, .<host>-plugin/*.json) of this check's own checkout is a known path, enforcer scripts included; the default branch, this install's own checkout and the hard names stay Tier 3 | source_mode, source_path, classify_paths |
| Read-only Git/gh queries use closed verbs and option sets; command/config overrides and unknown options deny | classify_argv, options |
| Git add of allowed paths, commit, origin push whose destination is an explicit refs/heads/<non-default branch> (a bare or abbreviated destination could resolve to a tag) and whose effective destination (origin's single pushurl, else its url) is the verified target, and merge origin/main into a work branch of a found repository (the synchronization exemption) are Tier 1 | classify_argv, branch_context |
| A local branch merge ([--no-ff] [--no-edit], refs/heads/<b> or an unambiguous bare name that exists only as a branch) is Tier 1 only into a named non-default branch with effective Merge=yes | local_merge, local_branch |
| One identity per check (found, absent or unknown; a rejected linked worktree is unknown) feeds settings, branch and remote reads | project_store.identity, effective, Context |
| The five project values start strict; a positively absent approval gives user values; an approved valid `autopilot` object whose record carries this checkout's full identity digest and whose recorded origin binding equals origin now replaces them key by key; anything else stays strict; the lease hash covers host.md only | effective, project_store.autopilot_binding, project_store.bound |
| PR merge/create/edit/comment need exactly one `--repo github.com/OWNER/NAME` equal to the verified target; create needs one validated `--head`; implicit targets are Tier 3 | target_check, head_check, project_store.origin_target |
| Title and body values of PR create/edit/comment, and `git commit -m` messages, are data (one exact `fnl-router` line included): newlines, tabs and a leading `-` pass; other controls, a backtick, `$(` and `$` before a letter, `_` or `{` deny; a review gate marker (`<!--`, optional space, `fnl-`) is `forbidden`; a secret, machine path or sensitive assignment is `unsafe`; one `--body-file` (gh) or `-F` (git commit) must be a regular file of at most 64 KiB inside the check's own checkout, outside the data root, with no link from that root down, whose text passes the control, marker, secret and path screens, read only for that verdict; comments follow `Repository comments` | text_values, text_ok, file_place, body_file, pr_text, commit_text |
| With Merge yes: `git worktree remove [--] <path>` of a linked worktree of this repository whose HEAD is a full SHA a `log --kind merge --pr <number> --head` entry of this lease recorded, itself refused unless an allowed `gh pr merge` check of this lease pinned that number and head (never forced, the main checkout, the current checkout or a worktree holding this install) and `git branch -d [--] <branch>` (never -D, the current or a default branch) are Tier 1; `git rm [-r] [-q] [--] <paths>` on a work branch classifies each path like a change | worktree_remove, head_commit, merged_heads, branch_delete, tracked_remove |
| `effective` prints the same context read-only for the advisory Task choice and Trusted authors | show_effective |
| The current branch is resolved through its symbolic refs (at most 5, no cycle); any default-branch name on the way makes it the default branch | branch_context |
| Project roots take the built-in roots' path rules; top-level README.md, CHANGELOG.md and CONTRIBUTING.md are known paths; every path rule (roots, documents, protected names, links) applies to the operand's path relative to the checkout root of the check's validated identity, read from cwd, and with no identity no path is known | classify_paths, repository_path |
| PR create/edit require push permission; PR merge requires Merge=yes and one full --match-head-commit SHA | classify_argv |
| Only this install's ledger/record/heavy_run/merge_check script paths, with isolated Python, are allowed wrappers; nested heavy commands are classified too | script_command |
| Only a Tier 1 check reserves an action (a ledger start also a run), even if the caller never executes; a denied check reserves nothing; check exits 0 on Tier 1 and 3 on Tier 3 with the same JSON | check, main |
| Log kinds/tiers and ids are enumerated/validated; `--head` is a full SHA on the merge kind only; notes lose controls, paths, command text and secret/assignment values, cap at 500; retention 30 days | log, safe_note, secret_patterns |
| Trusted PR authors, full independent review/check/local-test gate, changed paths (including staged commit paths), quota readings and actually calling check before execution remain caller obligations in this slice | agent judgment, advisory; merge_check --independent enforces its review condition |

A Tier 1 answer is a classification, not proof that a PR passed the full merge
gate or that its author is trusted. This script has no author input and never
checks out/tests a PR. It never executes argv, reads credentials, reads the
process environment, or persists argv/paths/settings contents. The live tick,
quota probe, scheduler, notices and host backstop are outside this first part.
Counters are reservations, not evidence that a command ran. Setup changes need
a new lease. There is no long-lived process. `check` classifies; it cannot
guarantee that a later command runs with the same working directory, metadata or
environment.
"""
import argparse
from contextlib import contextmanager
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import NamedTuple
import unicodedata
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root as dr
import parallel_slots as slots
import project_store as store
import secret_patterns
from away_lease import finite, private_info, read_lease, read_private  # the one safe lease reader

DEFAULTS = {'Hosts': 'Claude Code', 'Task choice': 'choose', 'Push and pull requests': 'yes',
            'Trusted authors': 'own', 'Lease hours': 8, 'Max runs': 20,
            'Max runtime minutes': 480, 'Max actions per hour': 30, 'Quota floor percent': 15}
# Closed categories of docs/specs/away-decisions.md "Where it must stop": name -> fixed at stop.
# Setup writes each starting choice; a missing or unknown value, and any value of a fixed row, is stop.
CATEGORIES = {'Production': True, 'Real users and customer data': True, 'Unrecoverable deletion': False,
              'Messages outside the repository': False, 'Tags and releases': False, 'Publishing': False,
              'Shared settings': False, 'Recoverable deletion': False, 'Repository comments': False}
CONSENT = 'Excerpts leave the machine'
TARGETS = 'Non-production targets'
HOST_FAMILIES = {'Claude Code': 'claude', 'Codex': 'codex', 'Antigravity': 'antigravity', 'ZCode': 'zcode'}
PROGRAMS = {'claude': 'claude', 'codex': 'codex', 'antigravity': 'agy', 'zcode': 'zcode'}
MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,79}')
LABEL = re.compile(r'[A-Za-z0-9._-](?:[A-Za-z0-9 ._-]{0,58}[A-Za-z0-9._-])?')
DECISION_ID = re.compile(r'q[0-9]{8}-[0-9]{6}-[0-9a-f]{4}')
DISPATCH_ID = re.compile(r'd[0-9]{8}-[0-9]{6}-[0-9a-f]{4}')
ADVISOR = re.compile(r'(?:claude|codex|antigravity|zcode)[a-z0-9]{0,24}')
FIELDS = ('by', 'option', 'of', 'probability', 'dispatch', 'model')
# The closed attempt schema of "Record for analysis": (rung, settled) -> (required, optional).
ATTEMPTS = {('rule', 'yes'): ({'by', 'option', 'of'}, set()), ('rule', 'no'): ({'by'}, set()),
            ('jev', 'yes'): ({'by', 'option', 'of', 'probability'}, set()), ('jev', 'no'): ({'by', 'probability'}, set()),
            ('jev', 'unavailable'): ({'by'}, set()),
            ('advisor', 'yes'): ({'by', 'option', 'of', 'dispatch', 'model'}, set()),
            ('advisor', 'no'): ({'by', 'dispatch', 'model'}, set()),
            ('host', 'yes'): ({'by', 'option', 'of', 'model'}, set()), ('park', 'yes'): ({'by'}, set())}
SETTLE = 0.8
NUMBERS = {'Lease hours': (1, 24), 'Max runs': (1, 10000), 'Max runtime minutes': (1, 1440),
           'Max actions per hour': (1, 10000), 'Quota floor percent': (0, 100)}
KINDS = {'start': 1, 'stop': 1, 'action': 1, 'decision': 2, 'parked': 3,
         'run-start': 1, 'run-finish': 1, 'merge': 1, 'error': 3}
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}')
SHA = re.compile(r'[0-9a-f]{40}')
BRANCH = re.compile(r'(?:refs/heads/)?[A-Za-z0-9][A-Za-z0-9._/-]{0,160}')
ROOTS = {'src', 'lib', 'app', 'tests', 'docs', 'scripts', 'skills'}
DOCUMENTS = {'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md'}  # top-level documentation files that are known paths
# The project-scoped keys of settings.json `autopilot` and their host.md names; broken project settings turn them off.
PROJECT_KEYS = {'task-choice': 'Task choice', 'push-and-pull-requests': 'Push and pull requests', 'merge': 'Merge',
                'trusted-authors': 'Trusted authors'}
OFF = {'Task choice': 'listed', 'Push and pull requests': 'no', 'Merge': 'no', 'Trusted authors': 'own', 'Roots': []}
CONTEXT = 'Repository context'  # the applied-settings entry holding the check's Context
MERGED = 'Merged heads'  # the applied-settings entry holding the heads this lease's `log --kind merge` entries recorded
EXTENSIONS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html', '.md', '.txt', '.json', '.toml', '.yaml', '.yml'}
MAX_LOG = 8 * 1024 * 1024
ENFORCERS = {'afk.py','data_root.py', 'parallel_slots.py', 'secret_patterns.py', 'merge_check.py',
             'review_config.py', 'review_route.py', 'post_review.py', 'heavy_gate.py', 'run_env.py', 'ledger.py',
             'record.py', 'verify_claim.py', 'git_metadata.py', 'quota_probe.py', 'heavy_run.py', 'delegate_env.py',
             'auto_gate.py', 'mode.py', 'judge.py', 'log_scan.py', 'route_task.py', 'brief_check.py', 'assignments.py',
             'away_lease.py', 'away_gate_hook.py', 'project_store.py', 'project_progress.py'}
ENFORCERS = {name.casefold() for name in ENFORCERS}  # case-insensitive filesystems name one file many ways


def now():
    return time.time()


def settings():
    text = dr.read_data('host.md', slots.HOST_LIMIT).decode('utf-8')
    start, body, end = slots.host_section(text, 'afk')
    if start == body == end:
        raise ValueError('afk setup is missing')
    result, seen = {**DEFAULTS, **{c: 'stop' for c in CATEGORIES}, CONSENT: 'no', TARGETS: []}, set()
    for line in text[body:end].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'- ([A-Za-z -]+): (.+)', line)
        if not match or match[1] not in {*DEFAULTS, 'Merge', *CATEGORIES, CONSENT, TARGETS} or match[1] in seen:
            raise ValueError('afk setup is invalid')
        key, value = match.groups()
        seen.add(key)
        if key in CATEGORIES:
            value = 'decide' if value == 'decide' and not CATEGORIES[key] else 'stop'
        elif key == CONSENT:
            value = 'yes' if value == 'yes' else 'no'
        elif key == TARGETS:
            entries = value.split('; ')
            # Exact commands only; one unreadable entry empties the list, so every deploy fails closed to a person.
            value = entries if all(0 < len(e) <= 200 and e == e.strip() and e.isprintable() for e in entries) else []
        elif key in NUMBERS:
            lower, upper = NUMBERS[key]
            if not re.fullmatch(r'[0-9]{1,5}', value) or not lower <= int(value) <= upper:
                raise ValueError('afk setup has an invalid limit')
            value = int(value)
        elif key == 'Hosts':
            hosts = value.split(', ')
            if len(hosts) != len(set(hosts)) or not set(hosts) <= {'Claude Code', 'Codex', 'Antigravity'}:
                raise ValueError('afk setup has invalid hosts')
        elif value not in {'Task choice': {'choose', 'listed'}, 'Push and pull requests': {'yes', 'no'},
                            'Merge': {'yes', 'no'}, 'Trusted authors': {'own'}}[key]:
            raise ValueError('afk setup has an invalid choice')
        result[key] = value
    if 'Merge' not in seen:
        raise ValueError('afk setup needs an explicit Merge answer')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def permits(categories, applied):
    """Precedence row 3: an action goes on only when every category that applies to it is `decide`."""
    return bool(categories) and all(applied.get(c) == 'decide' for c in categories)


def write_private(folder, name, raw):
    private_info(folder, name)
    dr.atomic_write(folder, name, raw)


@contextmanager
def private_folder():
    root = dr.consent_root()
    if root is None:
        raise ValueError('afk data root is invalid')
    # The default anchor also must not be inside a repository.
    with dr.root_folder(create=True):
        pass
    with dr.relocated_folder(root):
        pass
    with dr.data_folder('state', create=True, private=True) as state:
        with dr.descend(state, 'autopilot', create=True, private=True) as folder:
            private_info(folder, 'lock')
            fd = os.open('lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=folder)
            try:
                private_info(folder, 'lock')
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield folder
            finally:
                os.close(fd)


def save_lease(folder, lease):
    write_private(folder, 'lease.json', json.dumps(lease, separators=(',', ':')).encode())


def start(folder, args):
    applied = settings()
    hours = applied['Lease hours']
    if args.hours is not None:
        if not re.fullmatch(r'[0-9]{1,2}', args.hours) or not 1 <= int(args.hours) <= hours:
            raise ValueError('Lease hours must be 1..24 and cannot exceed setup')
        hours = int(args.hours)
    current = now()
    previous = read_lease(folder)
    read_private(folder, 'stop')
    if previous and previous['expiry'] > current:
        # One lease covers the machine: a second session joins it instead of starting, extending or failing.
        from datetime import datetime, timezone
        until = datetime.fromtimestamp(previous['expiry'], timezone.utc).isoformat(timespec='minutes')
        print(f'afk already live until {until}; this lease covers every session on this machine. '
              'Nothing was changed: work under it (check before each action, Decide for every question).')
        return
    lease = dict(id=uuid.uuid4().hex, start=current, expiry=current + hours * 3600,
                 settings_hash=digest(applied), counters=dict(runs=0, runtime_minutes=0, actions=0, hour_actions=[]))
    save_lease(folder, lease)
    try:
        os.unlink('stop', dir_fd=folder)
    except FileNotFoundError:
        pass
    summary = {**applied, 'Lease hours': hours, TARGETS: '; '.join(applied[TARGETS]) or 'none'}
    print('afk started\n' + '\n'.join(f'- {key}: {value}' for key, value in summary.items()))


def stop(folder):
    removed = read_private(folder, 'lease.json') is not None
    read_private(folder, 'stop')
    write_private(folder, 'stop', b'')
    if removed:
        os.unlink('lease.json', dir_fd=folder)
        os.fsync(folder)
    print('afk stopped: stop marker written; lease ' + ('removed' if removed else 'already absent'))


ENDED = {'no-lease', 'expired', 'stopped', 'exhausted'}
ENDED_LINE = 'The away lease has ended: stop any loop or wakeup you started for it, then report to the user.'


def lease_guard(folder, current):
    if read_private(folder, 'stop') is not None:
        return 'stopped', None, None
    lease = read_lease(folder)
    if lease is None:
        return 'no-lease', None, None
    if current >= lease['expiry']:
        return 'expired', lease, None
    if current < lease['start']:
        return 'limit', lease, None
    try:
        applied = settings()
    except (OSError, ValueError, UnicodeError):
        return 'setup-changed', lease, None
    if digest(applied) != lease['settings_hash']:
        return 'setup-changed', lease, applied
    counters = lease['counters']
    if any(t > current for t in counters['hour_actions']):
        return 'limit', lease, applied
    counters['hour_actions'] = [t for t in counters['hour_actions'] if current - 3600 < t <= current]
    # Spent runs or runtime never come back before the lease ends; the rolling-hour cap does.
    if (counters['runs'] >= applied['Max runs']
            or max(counters['runtime_minutes'], (current - lease['start']) / 60) >= applied['Max runtime minutes']):
        return 'exhausted', lease, applied
    if len(counters['hour_actions']) >= applied['Max actions per hour']:
        return 'limit', lease, applied
    return None, lease, applied


# Protected names that live config, state, credentials or Git internals use: Tier 3 everywhere.
HARD = {'.github', '.git', '.ssh', '.aws', '.gnupg', '.claude', '.codex', '.agents',
        'claude.local.md', 'agents.override.md', 'gemini.md', 'host.md', 'lease.json', 'log.jsonl', 'root.json', 'stop',
        '.netrc', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519', 'pre-commit', 'pre-push', 'commit-msg', 'post-commit',
        'prepare-commit-msg', 'post-checkout', 'post-merge'}
# Names the plugin's own source also uses; a source path on a work branch is spared them (`source_path`).
SOFT = {'claude.md', 'agents.md', 'skill.md', 'settings', 'config', 'hooks'}
SOFT_PREFIXES = ('settings.', 'config.', 'setup.', 'hooks.')
# The plugin's own source in a repository, relative to its checkout root: editable on a work branch.
SOURCE = re.compile(r'(?:skills|scripts)/[A-Za-z0-9_./-]+|\.[a-z0-9]+-plugin/[A-Za-z0-9_.-]+\.json|CLAUDE\.md|AGENTS\.md')


def protected(value, source=False):
    """Lexical check before command parsing; examine ref:path and --option=path too. `source` spares the soft names."""
    original = value
    value = value.lower().replace('\\', '/')
    parts = re.split(r'[/:=\s]+', value)
    exact = HARD if source else HARD | SOFT
    prefixes = ('.env', 'credentials', 'secrets') + (() if source else SOFT_PREFIXES)
    return any(p in exact or p.startswith(prefixes)
               or p.endswith(('.pem', '.key', '.p12', '.pfx', '.env'))
               or 'credential' in p or re.search(r'(?:^|[_.-])(?:token|password|secret)(?:[_.-]|$)', p)
               for p in parts) or bool(secret_patterns.PREFIX.search(original)) or any(
                   secret_patterns.NAME.fullmatch(p) and secret_patterns.SENSITIVE.search(p)
                   for p in re.split(r'[=:\s]+', value.upper()))


def plugin_code(name, base=None):
    """True for any path inside this install's script folders, so a new module cannot join a trusted import namespace.
    A work branch's copy of those scripts in another checkout is a different path and is not covered."""
    try:
        full = os.path.abspath(os.path.join(base or os.getcwd(), name)).casefold()
        base = Path(__file__).resolve().parent.parent.parent
        # Both the lexical folder and, for a linked sibling skill, the checkout it resolves to hold trusted modules.
        folders = {folder for scripts in base.glob('*/scripts') for folder in (scripts, scripts.resolve())}
        return any(full == str(folder).casefold() or full.startswith(str(folder).casefold() + os.sep)
                   for folder in folders)
    except (OSError, ValueError):
        return True


def install_root():
    """The running install's plugin root: the folder that holds `skills/delegate/scripts/afk.py`."""
    return Path(__file__).resolve().parents[3]


def install_owned(name, base=None):
    """True when a path read from `base` lies in this install's own checkout, on every branch: the checkout
    `project_store.identity` validates for it (by its nearest existing folder, lexical and resolved) is the install
    root itself, so a linked worktree of the install's repository, even under its `.claude/worktrees`, is not. With
    no validated identity, a path under the install root is owned. On doubt, True. Link and folder metadata only."""
    try:
        install = str(install_root()).casefold()  # a case-insensitive filesystem names one folder many ways
        full = Path(os.path.abspath(os.path.join(base or os.getcwd(), name)))
        folder = full
        while not os.path.lexists(folder) and folder != folder.parent:
            folder = folder.parent
        for candidate in {folder, Path(os.path.realpath(folder))}:
            if not candidate.is_dir() or candidate.is_symlink():
                candidate = candidate.parent
            found, ident = store.identity(str(candidate))
            if found == 'found':
                if os.path.realpath(ident.checkout).casefold() == install:
                    return True
            else:
                real = os.path.realpath(candidate).casefold()
                if real == install or real.startswith(install.rstrip(os.sep) + os.sep):
                    return True
        return False
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return True


def path_operand(token, base=None):
    """True when an argv token reads as a path: absolute, existing from `base`, or a relative name with a slash whose
    first component exists there. Revisions, branch names, numbers and placeholders are not paths."""
    if not plain(token) or token.startswith('-') or len(token) > 4096:
        return False
    if os.path.isabs(token):
        return True
    base = base or os.getcwd()
    return os.path.lexists(os.path.join(base, token)) or (
        '/' in token and os.path.lexists(os.path.join(base, token.split('/')[0])))


class Context(NamedTuple):
    """The policy context of one check: how the repository resolved, its validated identity, which values apply and
    the GitHub repository a mutation may name (None: no GitHub mutation or push qualifies)."""
    repository: str  # found, absent or unknown
    ident: object  # project_store.Identity when found, else None
    state: str  # user, project, strict or no-repository
    target: object  # 'github.com/<owner>/<name>' or None
    cwd: object = None  # the folder operands are read from (the working directory, or a checked `git -C` folder)


UNKNOWN = Context('unknown', None, 'strict', None)


def context_of(applied):
    found = applied.get(CONTEXT)
    return found if isinstance(found, Context) else UNKNOWN


def effective(applied, cwd):
    """The five project-scoped values and the repository context of one check (docs/specs/autopilot.md "Project scope").

    Starts from the strict vector and leaves it only once each prerequisite holds: a validated identity
    (`project_store.identity`), then either a positively absent approval (user values, no extra roots) or approved
    settings whose `autopilot` object is valid, whose approval record carries this identity's full main checkout
    digest (`project_store.bound`; the short code only names the file) and whose recorded origin binding equals the
    origin read now (explicit project values replace user values, omitted keys inherit). Unknown identity, an
    unreadable or unbound approval, a digest mismatch, invalid settings, a changed origin or any error keeps the whole
    strict vector. Positively no repository
    keeps the user values with no context to act on, so no repository mutation qualifies. Read on every check, never
    stored in the lease.
    """
    # A strict context keeps the check's folder, so the work-tree gate never falls back to the process's own cwd.
    strict = {**applied, **OFF, CONTEXT: UNKNOWN._replace(cwd=cwd if isinstance(cwd, str) else None)}
    try:
        cwd = str(cwd)
        found, ident = store.identity(cwd)
        if found == 'absent':
            return {**applied, 'Roots': [], CONTEXT: Context('absent', None, 'no-repository', None, cwd)}
        if found != 'found':
            return strict
        state, values, _, record = store.autopilot_binding(ident)
        target = store.origin_target(ident)
        if state == 'unset' or state == 'approved' and 'autopilot' not in values:
            return {**applied, 'Roots': [], CONTEXT: Context('found', ident, 'user', target, cwd)}
        project = values.get('autopilot') if state == 'approved' else None
        if (not store.valid_autopilot(project) or 'target' not in record or record['target'] != target
                or not store.bound(record, ident)):
            return {**strict, CONTEXT: Context('found', ident, 'strict', None, cwd)}
        result = dict(applied)
        for key, name in PROJECT_KEYS.items():
            if key in project:
                result[name] = project[key]
        result['Roots'] = [r for r in project.get('roots', []) if not protected(r)]
        result[CONTEXT] = Context('found', ident, 'project', target, cwd)
        return result
    except (OSError, ValueError, TypeError, UnicodeError, KeyError, RecursionError):
        return strict


def repository_path(name, context):
    """A plain relative operand read from cwd, as a path relative to the checkout root of the check's validated
    identity; None when the check has no identity, the operand is not plain or it lies outside that checkout."""
    if (context.ident is None or not re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', name) or Path(name).is_absolute()
            or any(p in {'', '.', '..'} for p in name.split('/'))):
        return None
    try:
        return Path(os.path.abspath(os.path.join(context.cwd or os.getcwd(), name))).relative_to(context.ident.checkout)
    except ValueError:
        return None


def checkout_of(token, base):
    """(Identity, relative path) of a path operand read from `base` and lying in a checkout `project_store.identity`
    validates (a linked worktree only in its canonical reciprocal layout); None for anything else or on doubt. No
    component from that checkout root down to the operand may be a link. Link and folder metadata only."""
    if (not plain(token) or len(token) > 4096 or any(c in token for c in ':=\\') or token.startswith('~')
            or '..' in token.split('/')):
        return None
    try:
        full = Path(os.path.abspath(os.path.join(base, token)))
        folder = full
        while not os.path.lexists(folder) and folder != folder.parent:
            folder = folder.parent
        if folder.is_symlink():
            return None
        if not folder.is_dir():
            folder = folder.parent
        found, ident = store.identity(str(folder))
        if found != 'found':
            return None
        relative = full.relative_to(ident.checkout)
        candidate = ident.checkout
        for part in relative.parts:
            candidate /= part
            if candidate.is_symlink():
                return None
        return ident, relative
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return None


def source_path(relative):
    """True for the plugin's own source (`SOURCE`), judged on the path relative to its checkout root."""
    return bool(SOURCE.fullmatch(relative.as_posix()))


def source_mode(applied):
    """Source paths are editable only on a non-default work branch with Push and pull requests or Merge yes."""
    if applied.get('Push and pull requests') != 'yes' and applied.get('Merge') != 'yes':
        return False
    try:
        current, default = branch_context(context_of(applied))
    except (OSError, ValueError, UnicodeError):
        return False
    return bool(current and default) and current not in {default, 'main', 'master', 'trunk'}


def token_protected(token, applied):
    """The argv protected check. A path operand inside a checkout of this check's repository (its own, its main
    checkout or a linked worktree) is judged by its path relative to that checkout's root, exactly as from inside it;
    a source path in this check's own checkout on a work branch is spared the soft names. Everything else is lexical.
    A path operand inside this install's own checkout (`install_owned`) is protected on every branch."""
    context = context_of(applied)
    base = context.cwd or os.getcwd()
    if path_operand(token, base) and install_owned(token, base):
        return True
    if not protected(token):
        return False
    if context.ident is None:
        return True
    found = checkout_of(token, base)
    if found is None or found[0].main != context.ident.main:
        return True
    ident, relative = found
    own = ident.checkout == context.ident.checkout and source_path(relative) and source_mode(applied)
    return protected(relative.as_posix(), own)


def no_links(path, context):
    """True when no component from the checkout root down to the path is a link (link metadata only, never a
    target or any file contents)."""
    candidate = context.ident.checkout
    for part in path.parts:
        candidate /= part
        if candidate.is_symlink():
            return False
    return True


def classify_paths(paths, roots=(), context=UNKNOWN, source=False):
    """Known single-file paths only. Each operand is read from cwd, then the protected, enforcer, root, document and
    link rules apply to its path relative to the checkout root of the check's validated identity, never to the
    operand alone, so a descendant cwd neither widens a root nor hides a protected ancestor. No identity: unknown.
    With `source` (a work branch, `source_mode`), a `SOURCE` path is a known path spared the soft names, the
    enforcer names and the top-level instruction files; this install's own script folders, and every path in this
    install's own checkout (`install_owned`), stay protected on every branch."""
    if not paths:
        return 'unknown'
    for name in paths:
        if not isinstance(name, str) or install_owned(name, context.cwd):
            return 'protected'
        relative = repository_path(name, context)
        own = source and relative is not None and source_path(relative)
        if protected(name, own):
            return 'protected'
        path = Path(name)
        if plugin_code(name, context.cwd) or not own and (
                path.name.casefold() in ENFORCERS or path.name.upper() in slots.INSTRUCTION_FILES):
            return 'protected'
        if own and path.name.upper() in slots.INSTRUCTION_FILES and len(relative.parts) != 1:
            return 'protected'  # only the top-level CLAUDE.md and AGENTS.md are source
        if (not re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', name) or path.is_absolute()
                or any(p in {'', '.', '..'} for p in name.split('/'))):
            return 'unknown'
        path = relative
        if path is None:
            return 'unknown'
        if protected(path.as_posix(), own):
            return 'protected'
        if own:
            if path.suffix not in EXTENSIONS:
                return 'unknown'
        elif len(path.parts) < 2:
            if path.as_posix() not in DOCUMENTS:
                return 'unknown'
        elif path.parts[0] not in ROOTS and path.parts[0] not in roots or path.suffix not in EXTENSIONS:
            return 'unknown'
        if not no_links(path, context):
            return 'protected'
        candidate = context.ident.checkout / path
        # A directory operand would stage everything below it, so only single files are a known path.
        if candidate.is_dir():
            return 'unknown'
    return 'allowed'


def options(tokens, flags=(), valued=(), *, positional=True):
    """Closed option grammar; return operands, or None for anything unrecognized."""
    operands, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        if token in flags:
            index += 1
            continue
        key, equal, value = token.partition('=')
        if key in valued:
            if not equal:
                index += 1
                if index >= len(tokens):
                    return None
                value = tokens[index]
            if not value or value.startswith('-'):
                return None
        elif token.startswith('-'):
            if not re.fullmatch(r'-[1-9][0-9]{0,3}', token) or '-N' not in flags:
                return None
        elif positional:
            operands.append(token)
        else:
            return None
        index += 1
    return operands


def git_dirs(context):
    """(git folder, common folder) of the check's validated identity; ValueError without one."""
    if context.ident is None:
        raise ValueError('no validated repository')
    return context.ident.git, context.ident.common


def branch_context(context):
    """Only local metadata of the context's identity, no Git process, config execution or credential helper."""
    git, common = git_dirs(context)
    with slots.open_dir(git) as fd:
        head = slots.read_metadata(fd, 'HEAD').strip()
    with slots.open_dir(common / 'refs/remotes/origin') as fd:
        default = slots.read_metadata(fd, 'HEAD').strip()
    default = default.removeprefix('ref: refs/remotes/origin/') if default.startswith('ref: refs/remotes/origin/') else None
    # Follow the branch symref chain to the branch a merge or push of HEAD would really update. Any name on the way
    # that is a default-branch name makes it that branch; a ref outside refs/heads, a cycle or a long chain is a
    # detached head (None), which every caller refuses.
    chain = []
    while head.startswith('ref: refs/heads/'):
        name = head.removeprefix('ref: refs/heads/')
        if name in chain or len(chain) >= 5 or not BRANCH.fullmatch(name) or '..' in name:
            return None, default
        chain.append(name)
        try:
            with slots.open_dir(common / 'refs/heads' / Path(name).parent) as fd:
                head = slots.read_metadata(fd, Path(name).name).strip()
        except FileNotFoundError:
            break  # packed (never symbolic) or unborn: the chain ends at this branch
    else:
        if chain and not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', head):
            return None, default
    if not chain:
        return None, default
    # Casefolded: on a case-insensitive filesystem refs/heads/MAIN is the same loose file as refs/heads/main.
    for name in chain:
        for kept in ('main', 'master', 'trunk', default):
            if kept and name.casefold() == kept.casefold():
                return kept, default
    return chain[-1], default


def flag_operands(tail, flag):
    """Every value given to a long `flag`, in the separate and the `=` forms."""
    return ([tail[i + 1] if i + 1 < len(tail) else '' for i, t in enumerate(tail) if t == flag]
            + [t[len(flag) + 1:] for t in tail if t.startswith(flag + '=')])


def target_check(tail, context):
    """'allowed' only for exactly one explicit `--repo github.com/OWNER/NAME` equal to the context's verified target,
    'forbidden' for another GitHub repository, else 'unknown'. gh's implicit choice (remotes, gh-resolved, GH_REPO) is
    never predicted: an explicit --repo takes precedence over all of them, so any form without one is Tier 3, and so
    are the short -R spellings, other hosts, URL forms, `.git` names and a repeated --repo."""
    if any(t.startswith('-R') for t in tail):
        return 'unknown'
    named = flag_operands(tail, '--repo')
    if len(named) != 1 or context.target is None:
        return 'unknown'
    match = re.fullmatch(r'([^/]+)/([^/]+)/([^/]+)', named[0])
    if not match or named[0].endswith('.git'):
        return 'unknown'
    target = store.repository_target(*match.groups())
    if target is None:
        return 'unknown'
    return 'allowed' if target == context.target else 'forbidden'


def head_check(tail, context):
    """`gh pr create` names its head explicitly (`--head <branch>`, once), so gh pushes nothing itself; the branch is a
    plain name that is not the default branch, `main`, `master` or `trunk`."""
    if any(t.startswith('-H') for t in tail):
        return 'unknown'
    heads = flag_operands(tail, '--head')
    if len(heads) != 1:
        return 'unknown'
    name = heads[0]
    if (not BRANCH.fullmatch(name) or name.startswith('refs/') or '..' in name or '//' in name or '/.' in name
            or name.endswith(('/', '.', '.lock', 'HEAD'))):
        return 'unknown'
    try:
        _, default = branch_context(context)
    except (OSError, ValueError, UnicodeError):
        return 'unknown'
    if any(kept and name.casefold() == kept.casefold() for kept in ('main', 'master', 'trunk', default)):
        return 'forbidden'
    return 'allowed' if default else 'unknown'


def local_branch(name, bare, context):
    """True when refs/heads/<name> exists (loose or packed) and, for a bare name, no ref git would pick first does."""
    _, common = git_dirs(context)

    def loose(ref):
        try:
            with slots.open_dir(common / Path(ref).parent) as fd:
                slots.read_metadata(fd, Path(ref).name)  # a folder, link or foreign file raises: deny on doubt
            return True
        except (FileNotFoundError, NotADirectoryError):
            return False
    try:
        with slots.open_dir(common) as fd:
            packed = slots.read_metadata(fd, 'packed-refs')
    except FileNotFoundError:
        packed = ''
    names = {line.split(' ', 1)[1].strip() for line in packed.splitlines() if ' ' in line and line[:1] not in '#^'}

    def has(ref):
        return ref in names or loose(ref)
    if not has('refs/heads/' + name):
        return False
    # git resolves a bare name as <git dir>/<name>, refs/<name> and refs/tags/<name> before refs/heads/<name>.
    return not bare or not any(has(ref) for ref in (name, 'refs/' + name, 'refs/tags/' + name))


def local_merge(tail, applied):
    """`git merge [--no-ff] [--no-edit] refs/heads/<branch>|<branch>` of a local branch into a work branch."""
    flags, operands = [t for t in tail if t.startswith('-')], [t for t in tail if not t.startswith('-')]
    if len(operands) != 1 or len(set(flags)) != len(flags) or not set(flags) <= {'--no-ff', '--no-edit'}:
        return 'unknown'
    explicit = operands[0].startswith('refs/heads/')
    name = operands[0].removeprefix('refs/heads/')
    if (not BRANCH.fullmatch(name) or name.startswith('refs/') or '..' in name or '//' in name
            or name.endswith(('/', '.', '.lock')) or '/.' in name):
        return 'unknown'
    # Git reads hexadecimal in any case as an object id (SHA-1 or SHA-256, abbreviated from 4 digits) before a branch.
    if not explicit and (re.fullmatch(r'[0-9a-fA-F]{4,64}', name) or name.endswith('HEAD')
                         or name.split('/')[0] in {'origin', 'tags', 'heads', 'remotes'}):
        return 'unknown'  # a bare name that could read as a commit id or another ref
    if applied['Merge'] != 'yes':
        return 'merge-disabled'
    context = context_of(applied)
    try:
        current, default = branch_context(context)
        if current in {None, default, 'main', 'master', 'trunk'}:
            return 'forbidden'  # never into the default branch or a detached head
        if not default or name == current or not local_branch(name, not explicit, context):
            return 'unknown'
    except (OSError, ValueError, UnicodeError):
        return 'unknown'
    return 'allowed'


def own_wrapper_index(argv):
    """Index of the script token when argv runs one of this install's own trusted wrappers, else None.

    The install folder itself may lie under ~/.claude or ~/.codex; only that one exact token is spared the
    lexical protected check, and every other token (including a nested command's) is still checked."""
    if len(argv) < 3 or argv[0] not in {'python3', sys.executable} or argv[1] != '-I':
        return None
    index = 3 if argv[2] == '-B' else 2
    if index >= len(argv):
        return None
    own = Path(__file__).resolve().parent
    trusted = {own / name for name in ('ledger.py', 'record.py', 'heavy_run.py', 'judge.py', 'delegate_env.py')}
    trusted.add(own.parent.parent / 'review-gate/scripts/merge_check.py')
    path = Path(argv[index])
    if (path not in trusted or path.is_symlink() or not path.is_file()
            or any(parent.is_symlink() for parent in (path.parent, path.parent.parent))):
        return None
    return index


def script_command(argv, applied):
    if argv[0] not in {'python3', sys.executable} or len(argv) < 3 or argv[1] != '-I':
        return 'unknown'
    index = 2
    if argv[index:index + 1] == ['-B']:
        index += 1
    if index >= len(argv):
        return 'unknown'
    path = Path(argv[index])
    own = Path(__file__).resolve().parent
    merge = own.parent.parent / 'review-gate/scripts/merge_check.py'
    allowed = {own / name for name in ('ledger.py', 'record.py', 'heavy_run.py')} | {merge}
    if (path not in allowed or path.is_symlink() or not path.is_file()
            or any(parent.is_symlink() for parent in (path.parent, path.parent.parent))):
        return 'unknown'  # a linked skill folder could supply a different import namespace
    tail = argv[index + 1:]
    if path.name == 'heavy_run.py':
        if tail == ['status']:
            return 'allowed'
        # Only the canonical form `run [--label L] [--pass-env N] [--max-minutes M] -- <command>`; the command
        # is always classified on its own, and any other spelling (including one with no separator) is unknown.
        if tail[:1] != ['run'] or '--' not in tail:
            return 'unknown'
        head, command = tail[1:tail.index('--')], tail[tail.index('--') + 1:]
        if not command or options(head, set(), {'--label', '--pass-env', '--max-minutes'}, positional=False) != []:
            return 'unknown'
        return classify_argv(command, applied)
    return 'allowed'


def plain(token):
    return isinstance(token, str) and 0 < len(token) <= 8192 and not any(
        unicodedata.category(c).startswith('C') for c in token)


def own_script(argv, names):
    """The script name when argv is `python3 -I [-B] <this install's script>`, else None."""
    if len(argv) < 3 or argv[0] not in {'python3', sys.executable} or argv[1] != '-I':
        return None, None
    index = 3 if argv[2] == '-B' else 2
    if index >= len(argv):
        return None, None
    path, own = Path(argv[index]), Path(__file__).resolve().parent
    if (path not in {own / name for name in names} or path.is_symlink() or not path.is_file()
            or any(parent.is_symlink() for parent in (path.parent, path.parent.parent))):
        return None, None
    return path.name, argv[index + 1:]


def flag_values(tokens, single, repeated=()):
    """`--flag value` pairs only; each single flag at most once. None for anything else."""
    values = {}
    if len(tokens) % 2:
        return None
    for flag, value in zip(tokens[::2], tokens[1::2]):
        if flag in repeated:
            values.setdefault(flag, []).append(value)
        elif flag in single and flag not in values:
            values[flag] = value
        else:
            return None
    return values


def evidence_path(name, context):
    """A known path, or a brief under the repository's own `.finolabs/briefs/`, both judged from the checkout root."""
    if not plain(name) or protected(name):
        return False
    if classify_paths([name], (), context) == 'allowed':
        return True
    path = repository_path(name, context)
    if path is None or not re.fullmatch(r'\.finolabs/briefs/[A-Za-z0-9_.-]{1,80}\.(?:md|json|txt)', path.as_posix()):
        return False
    return no_links(path, context) and not (context.ident.checkout / path).is_dir()


def judge_command(tail, applied):
    """`judge.py ask --site away-decision --question Q --option O (2 to 6) --evidence-file F [--judge jev]` only."""
    if tail[:1] != ['ask']:
        return 'unknown'
    values = flag_values(tail[1:], {'--site', '--question', '--evidence-file', '--judge'}, {'--option'})
    if (values is None or values.get('--site') != 'away-decision' or values.get('--judge', 'jev') != 'jev'
            or not {'--question', '--evidence-file', '--option'} <= set(values)):
        return 'unknown'
    question, options = values['--question'], values['--option']
    if (not all(plain(t) for t in (question, *options))
            or not evidence_path(values['--evidence-file'], context_of(applied))):
        return 'unknown'
    try:
        import judge
        judge.choice_fields('away-decision', question, options, '')
    except (ImportError, ValueError):
        return 'unknown'
    return 'allowed'


def brief_ok(brief):
    """At least as strict as the judge and packet paths: secrets, machine paths, and any sensitive-name assignment."""
    if (not isinstance(brief, str) or not 0 < len(brief.encode()) <= 65536
            or any(unicodedata.category(c).startswith('C') and c not in '\n\t' for c in brief)):
        return False
    return not screened(brief)


def approved_program(family, rest):
    """Length of the owner-approved executable that starts `rest`, else 0; nothing is run.

    The identity is the record setup wrote for the quota probe in the canonical host config (`Executable`, `Resolved`
    and its confirmed digest), re-checked now by quota_probe.checked_executable: owner and mode of every component,
    no repository, temporary or downloads folder, and an unchanged target. The program must be the absolute argv those
    checks return, or for a native program the recorded `Executable` path itself. Bare names, PATH lookups and other
    paths deny, and so does a time-cap wrapper such as perl, which has no such record.
    """
    import quota_probe
    agent = PROGRAMS[family]
    entry = quota_probe.canonical_config().get(agent)
    if entry is None:
        return 0
    try:
        checked = quota_probe.checked_executable(agent, entry)
    except (OSError, ValueError, UnicodeError):
        return 0
    forms = [checked] + ([[entry['executable']]] if len(checked) == 1 else [])
    for form in forms:
        if all(isinstance(t, str) and Path(t).is_absolute() for t in form) and rest[:len(form)] == form:
            return len(form)
    return 0


def advisor_command(tail, applied, coordinator):
    """`delegate_env.py --family F -- [hard cap] <program> <closed read-only argv>`, F in Hosts and not the coordinator's."""
    if len(tail) < 4 or tail[0] != '--family' or tail[2] != '--':
        return 'unknown'
    family, rest = tail[1], tail[3:]
    # ZCode has no verified read-only advisor form; never parse it with another family's grammar.
    if family == 'zcode':
        return 'unknown'
    hosts = {HOST_FAMILIES[h] for h in applied['Hosts'].split(', ')}
    if family not in PROGRAMS or family not in hosts or coordinator not in PROGRAMS or coordinator == family:
        return 'unknown'
    size = approved_program(family, rest)
    if not size:
        return 'unknown'
    args, brief = rest[size:], None
    # The brief sits behind an unambiguous boundary: Codex and Claude end their options with a literal `--` right
    # before it (`codex exec [OPTIONS] [PROMPT]`, `claude [options] [prompt]` with -p a switch); Antigravity takes it
    # as the value of -p. In every form a brief starting with `-` (an option, or `-` for unvalidated stdin) denies.
    if family == 'codex':
        if args[:1] != ['exec'] or len(args) < 3 or args[-2] != '--':
            return 'unknown'
        brief, values = args[-1], flag_values(args[1:-2], {'-m', '-c', '-s'})
        if (values is None or values.get('-s') != 'read-only' or '-m' not in values
                or not re.fullmatch(r'model_reasoning_effort=(?:low|medium|high|xhigh)', values.get('-c', 'model_reasoning_effort=high'))):
            return 'unknown'
        model = values['-m']
    else:
        if family == 'claude':
            if args[:1] != ['-p'] or len(args) < 3 or args[-2] != '--':
                return 'unknown'
            brief, values = args[-1], flag_values(args[1:-2], {'--model', '--output-format', '--permission-mode',
                                                                '--effort', '--max-turns', '--max-budget-usd'})
            required = {'--model', '--output-format', '--permission-mode'}
        else:
            values = flag_values(args, {'-p', '--model', '--output-format', '--mode', '--print-timeout'})
            required = {'-p', '--model', '--output-format', '--mode'}
            brief = values.get('-p') if values is not None else None
        if values is None or not required <= set(values) or values['--output-format'] != 'json':
            return 'unknown'
        if values.get('--permission-mode', values.get('--mode')) != 'plan':
            return 'unknown'
        if (values.get('--effort', 'high') not in {'low', 'medium', 'high', 'xhigh', 'max'}
                or not re.fullmatch(r'[1-9][0-9]{0,2}', values.get('--max-turns', '1'))
                or not re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{1,2})?', values.get('--max-budget-usd', '1'))
                or not re.fullmatch(r'[1-9][0-9]{0,2}m', values.get('--print-timeout', '30m'))):
            return 'unknown'
        model = values['--model']
    others = [t for t in rest if t is not brief]
    if (not isinstance(brief, str) or brief.startswith('-') or not MODEL.fullmatch(model) or not brief_ok(brief)
            or not all(plain(t) and not protected(t) for t in others)):
        return 'unknown'
    return 'allowed'


def ladder_command(argv, applied, coordinator):
    """The two command forms the away ladder needs (judge and advisor), or None when argv is neither."""
    name, tail = own_script(argv, ('judge.py', 'delegate_env.py'))
    if name is None:
        return None
    return judge_command(tail, applied) if name == 'judge.py' else advisor_command(tail, applied, coordinator)


TAG = re.compile(r'v?[0-9A-Za-z][0-9A-Za-z._-]{0,63}')
REVISION = re.compile(r'HEAD|[0-9a-f]{7,40}')


DEPLOY = re.compile(r'deploy(?::[\w-]+)?')


def command_categories(argv):
    """Every category the command itself applies, read from its program and subcommand, never from free-text data."""
    categories = set()
    if argv[:2] in (['git', 'tag'], ['gh', 'release']):
        categories.add('Tags and releases')
    if argv[0] in {'npm', 'pnpm'} and argv[1:2] == ['publish']:
        categories.add('Publishing')
    return categories


def is_deploy(argv):
    """Git and gh have no deploy subcommand, so a deploy word there is data; elsewhere any such word fails closed."""
    return argv[0] not in {'git', 'gh'} and any(DEPLOY.fullmatch(t) for t in argv[1:])


def release_command(argv, applied, categories, deploy):
    """Precedence rows 2 to 5 for the command forms a script can read: tags, releases, publishing and deploys."""
    if categories and not permits(categories, applied):
        return 'forbidden'  # row 3: every applicable category must be decide
    if deploy:
        if any(re.search(r'prod|live', t, re.I) for t in argv):
            return 'forbidden'  # row 2: production or live, even when listed by mistake
        if ' '.join(argv) not in applied.get(TARGETS, []):
            return 'forbidden'  # row 4
        if not categories:
            return 'allowed'  # row 5
    tail = argv[2:]
    if argv[:2] == ['git', 'tag']:
        if tail in ([], ['-l'], ['--list']):
            return 'allowed'
        operands = options(tail, {'-a'}, {'-m', '--message'})
        if (operands and len(operands) <= 2 and TAG.fullmatch(operands[0])
                and all(REVISION.fullmatch(o) for o in operands[1:])):
            return 'allowed'
    elif argv[:2] == ['gh', 'release']:
        verb, rest = tail[:1], tail[1:]
        if verb == ['create']:
            operands = options(rest, {'--draft', '--verify-tag', '--prerelease'},
                               {'--title', '-t', '--notes', '-n', '--target', '--repo', '-R'})
            if operands is not None and len(operands) == 1 and TAG.fullmatch(operands[0]):
                return 'allowed'
        elif verb in (['view'], ['list']):
            operands = options(rest, set(), {'--repo', '-R', '--limit', '-L', '--json'})
            if operands is not None and len(operands) <= (verb == ['view']) and all(TAG.fullmatch(o) for o in operands):
                return 'allowed'
    elif argv[0] in {'npm', 'pnpm'} and argv[1:2] == ['publish']:
        values = flag_values(tail, {'--access', '--tag'})
        if values is not None and values.get('--access', 'public') in {'public', 'restricted'} and TAG.fullmatch(values.get('--tag', 'latest')):
            return 'allowed'
    return 'forbidden'


TEXT_FLAGS = {'--title', '-t', '--body', '-b'}
COMMIT_TEXT_FLAGS = {'-m', '--message'}  # a commit message is data like a PR body
TEXT_LIMIT = 65536
# A review gate marker (`<!-- fnl-... -->`): only post_review.py posts one, so PR or commit text carrying it is refused.
MARKER = re.compile(r'<!--\s*fnl-', re.I)
# The one marker a pull request body must carry (`coding-router`; merge_check.py's ROUTER): one exact line is data.
ROUTER_LINE = re.compile(r'<!-- fnl-router depth=(MIN|NORMAL|DEEP) trigger=(none|contract|security|privacy|permission|'
                         r'migration|dependency|uncertainty|consumers|irreversible|calculation|prediction|input) -->')
# Inline argv text passes through a shell in many callers: command substitution and parameter expansion deny.
EXPANSION = re.compile(r'\$\(|\$[A-Za-z_{]|`')


def text_values(argv):
    """For `gh pr create|edit|comment` and `git commit`: argv with each title, body and message value replaced by a placeholder, and the values.
    Left to right like gh's parser; a flag-looking value of another option then fails that option's grammar."""
    if argv[:2] == ['git', 'commit']:
        flags, start = COMMIT_TEXT_FLAGS, 2
    elif argv[:2] == ['gh', 'pr'] and argv[2:3] in (['create'], ['edit'], ['comment']):
        flags, start = TEXT_FLAGS, 3
    else:
        return argv, []
    out, values, index = argv[:start], [], start
    while index < len(argv):
        token = argv[index]
        key, equal, value = token.partition('=')
        if equal and key in flags:  # `-b=value` and `-m=value` carry text too
            out.append(key + '=text')
            values.append(value)
        elif token in flags and index + 1 < len(argv):
            out += [token, 'text']
            values.append(argv[index + 1])
            index += 1
        else:
            out.append(token)
        index += 1
    return out, values


def text_ok(value, inline=True):
    """'allowed' for title, body or message data: newlines, tabs and a leading `-` are data; a review gate marker is
    'forbidden'; other controls, and inline a backtick, `$(` or `$` before a letter, `_` or `{`, are 'unknown'; a
    secret, machine path or sensitive assignment is 'unsafe'. File text (`inline` false) skips the shell screen."""
    lines = value.split('\n')
    routers = [i for i, line in enumerate(lines) if ROUTER_LINE.fullmatch(line)]
    rest = '\n'.join(line for i, line in enumerate(lines) if i not in routers[:1])
    if len(routers) > 1 or MARKER.search(rest):
        return 'forbidden'
    if (not 0 < len(value) <= TEXT_LIMIT or inline and EXPANSION.search(value)
            or any(unicodedata.category(c).startswith('C') and c not in '\n\t' for c in value)):
        return 'unknown'
    return 'unsafe' if screened(value) else 'allowed'


def file_place(full, context):
    """True when `full` lies inside the check's own checkout, outside the data root, with no link in any component
    from that checkout root down (link metadata only)."""
    if context.ident is None:
        return False
    try:
        relative = full.relative_to(context.ident.checkout)
        if not relative.parts or not no_links(relative, context):
            return False
        real = Path(os.path.realpath(full))
        roots = {dr.default_root(), dr.data_root()[0]}
        return not any(real == r or r in real.parents for r in {Path(os.path.realpath(r)) for r in roots})
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return False


def body_file(name, context):
    """'allowed' for a regular file (never a link) of at most 64 KiB inside the check's own checkout (`file_place`),
    read from the check's folder, whose UTF-8 text passes `text_ok` as file text (carriage returns also allowed);
    a review gate marker is 'forbidden'; else 'unsafe'. Only the verdict leaves this function."""
    if not plain(name) or name.startswith('-') or '..' in name.split('/'):
        return 'unsafe'  # `..` after a link resolves elsewhere than the lexical path this check reads
    full = Path(os.path.abspath(os.path.join(context.cwd or os.getcwd(), name)))
    if not file_place(full, context):
        return 'unsafe'
    try:
        fd = os.open(full, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > TEXT_LIMIT:
                return 'unsafe'
            raw = os.read(fd, TEXT_LIMIT + 1)
        finally:
            os.close(fd)
        text = raw.decode('utf-8').replace('\r', '')
    except (OSError, ValueError, UnicodeError):
        return 'unsafe'
    if len(raw) > TEXT_LIMIT or not text:
        return 'unsafe'
    verdict = text_ok(text, inline=False)
    return verdict if verdict in {'allowed', 'forbidden'} else 'unsafe'


def commit_text(tail, context):
    """`git commit` grammar: at most one message source, `-m`/`--message` (repeatable) or one `-F <file>` passing
    `body_file`; any other option is 'unknown'."""
    if any(t.startswith('-F') and t != '-F' for t in tail):
        return 'unknown'  # git reads `-F=x` and `-Fx` as other file names
    if not tail or options(tail, {'--amend', '--no-edit', '-q', '--quiet'}, {'-m', '--message', '-F'},
                           positional=False) != []:
        return 'unknown'
    files = [tail[i + 1] for i, t in enumerate(tail) if t == '-F']
    if files and (len(files) > 1 or any(t in COMMIT_TEXT_FLAGS or t.startswith(('-m=', '--message=')) for t in tail)):
        return 'unknown'
    return body_file(files[0], context) if files else 'allowed'


def pr_text(tail, context):
    """At most one body source; a `--body-file`/`-F` must pass `body_file`."""
    files = flag_operands(tail, '--body-file') + [tail[i + 1] if i + 1 < len(tail) else '' for i, t in enumerate(tail) if t == '-F']
    bodies = sum(1 for t in tail if t in {'--body', '-b'} or t.startswith('--body='))
    if any(t.startswith('-F') and t != '-F' for t in tail) or len(files) + bodies > 1:
        return 'unknown'
    return body_file(files[0], context) if files else 'allowed'


def worktree_remove(tail, applied):
    """`git worktree remove [--] <path>`: a linked worktree of this repository whose HEAD is a full SHA a
    `log --kind merge --pr <number> --head` entry of this lease recorded, never its main checkout, the current checkout, a worktree
    that is or contains this install, or a forced removal; Merge must be yes."""
    if tail[:1] != ['remove']:
        return 'unknown'
    if any(t in {'-f', '--force'} or t.startswith('--force') or re.fullmatch(r'-[a-zA-Z]*f[a-zA-Z]*', t) for t in tail):
        return 'forbidden'
    rest = tail[1:]
    rest = rest[1:] if rest[:1] == ['--'] else rest
    if len(rest) != 1 or rest[0].startswith('-'):
        return 'unknown'
    if applied['Merge'] != 'yes':
        return 'merge-disabled'
    context = context_of(applied)
    if context.ident is None:
        return 'unknown'
    found = checkout_of(rest[0], context.cwd or os.getcwd())
    if found is None or found[1].parts or found[0].main != context.ident.main:
        return 'unknown'
    ident = found[0]
    if ident.checkout == ident.main or ident.git == ident.common:
        return 'forbidden'  # the main checkout
    if ident.checkout == context.ident.checkout:
        return 'unknown'
    try:
        tree = os.path.realpath(ident.checkout).casefold()
        if install_owned(str(ident.checkout)) or str(install_root()).casefold().startswith(tree.rstrip(os.sep) + os.sep):
            return 'forbidden'  # a worktree that is or contains this install
        head = head_commit(ident)
    except (OSError, ValueError, UnicodeError):
        return 'unknown'
    # Only the worktree of a pull request this lease merged: its HEAD is a head a `log --kind merge` entry recorded.
    return 'allowed' if head and head in applied.get(MERGED, ()) else 'unknown'


def head_commit(ident):
    """The full commit id a checkout's HEAD names (detached, or through one local branch ref, loose or packed), else
    None. Local metadata only, no Git process."""
    with slots.open_dir(ident.git) as fd:
        head = slots.read_metadata(fd, 'HEAD').strip()
    if head.startswith('ref: refs/heads/'):
        name = head.removeprefix('ref: ')
        if not BRANCH.fullmatch(name.removeprefix('refs/heads/')) or '..' in name:
            return None
        try:
            with slots.open_dir(ident.common / Path(name).parent) as fd:
                head = slots.read_metadata(fd, Path(name).name).strip()
        except FileNotFoundError:
            try:
                with slots.open_dir(ident.common) as fd:
                    packed = slots.read_metadata(fd, 'packed-refs')
            except FileNotFoundError:
                return None
            head = next((line.split(' ', 1)[0] for line in packed.splitlines()
                         if line[:1] not in '#^' and line.split(' ', 1)[1:] == [name]), '')
    return head if SHA.fullmatch(head) else None


def branch_delete(tail, applied):
    """`git branch -d [--] <branch>` of an existing local branch other than the current and default branches."""
    rest = tail[1:]
    rest = rest[1:] if rest[:1] == ['--'] else rest
    if len(rest) != 1:
        return 'unknown'
    name = rest[0]
    if (not BRANCH.fullmatch(name) or name.startswith('refs/') or '..' in name or '//' in name or '/.' in name
            or name.endswith(('/', '.', '.lock', 'HEAD'))):
        return 'unknown'
    if applied['Merge'] != 'yes':
        return 'merge-disabled'
    context = context_of(applied)
    try:
        current, default = branch_context(context)
        if any(kept and name.casefold() == kept.casefold() for kept in ('main', 'master', 'trunk', default)):
            return 'forbidden'
        if not default or not current or name == current or not local_branch(name, False, context):
            return 'unknown'
    except (OSError, ValueError, UnicodeError):
        return 'unknown'
    return 'allowed'


def tracked_remove(tail, applied):
    """`git rm [-r] [-q] [--] <paths>` on a work branch; each path is classified like a change."""
    index = 0
    while index < len(tail) and tail[index] in {'-r', '-q'} and tail[index] not in tail[:index]:
        index += 1
    rest = tail[index:]
    if rest[:1] == ['--']:
        rest = rest[1:]
    elif any(t.startswith('-') for t in rest):
        return 'unknown'  # any other option (--cached, -f, a repeated flag) is outside the grammar
    if not rest:
        return 'unknown'
    context = context_of(applied)
    try:
        current, default = branch_context(context)
    except (OSError, ValueError, UnicodeError):
        return 'unknown'
    if not current or not default or current in {default, 'main', 'master', 'trunk'}:
        return 'forbidden'
    return classify_paths(rest, applied.get('Roots', ()), context, source_mode(applied))


# git verbs that change a checkout's work tree, index or HEAD; never run inside this install's own checkout.
# `worktree` is not one: its only Tier 1 form removes another linked worktree, and worktree_remove refuses the install.
WORK_TREE_VERBS = {'merge', 'commit', 'add', 'rm', 'mv', 'checkout', 'switch', 'restore', 'reset',
                   'pull', 'rebase', 'cherry-pick', 'revert', 'stash', 'apply', 'am'}


def classify_argv(argv, applied, coordinator=None):
    if not isinstance(argv, list) or not argv or len(argv) > 256 or not all(isinstance(t, str) and t for t in argv):
        return 'unknown'
    ladder = ladder_command(argv, applied, coordinator)
    if ladder is not None:
        return ladder  # its data tokens (question, options, brief) are checked by the form itself
    argv, texts = text_values(argv)
    for value in texts:
        verdict = text_ok(value)
        if verdict != 'allowed':
            return verdict
    if any(len(t) > 8192 or any(unicodedata.category(c).startswith('C') for c in t) for t in argv):
        return 'unknown'
    if any(t in {';', '&&', '||', '|', '>', '>>', '<'} or '$(' in t or '`' in t for t in argv):
        return 'unknown'
    wrapper = own_wrapper_index(argv)
    if any(token_protected(t, applied) for i, t in enumerate(argv) if i != wrapper):
        return 'protected'
    command = argv[0]
    categories, deploy = command_categories(argv), is_deploy(argv)
    if categories or deploy:
        return release_command(argv, applied, categories, deploy)
    if command == 'rm' and any(t.startswith('-') and ('r' in t[1:] or t == '--recursive') for t in argv[1:]):
        return 'forbidden'
    if command in {'python3', sys.executable}:
        return script_command(argv, applied)
    if command == 'git' and len(argv) >= 2:
        verb, tail = argv[1], argv[2:]
        if verb in WORK_TREE_VERBS:
            context = context_of(applied)
            if install_owned('.', context.cwd or os.getcwd()):
                return 'protected'  # changes this install's own files without naming a path (a merge, a commit)
        if verb == 'push':
            if any(t.startswith(('--force', '--delete', '--mirror', '--all', '--tags')) or t.startswith('+')
                   or t in {'-f', '-d'} for t in tail):
                return 'forbidden'
            operands = options(tail, {'-u', '--set-upstream', '--porcelain'})
            if operands is None or len(operands) != 2 or operands[0] != 'origin':
                return 'unknown'
            refspec = operands[1].split(':')
            if len(refspec) > 2 or any(not BRANCH.fullmatch(b) or '..' in b or b.endswith('/') for b in refspec):
                return 'unknown'
            # Only the branch namespace: tags, remotes, notes and other full ref names are Tier 3.
            if any(b.startswith('refs/') and not b.startswith('refs/heads/')
                   or b.split('/')[0] in {'tags', 'remotes', 'notes', 'replace', 'stash', 'changes'} for b in refspec):
                return 'forbidden'
            context = context_of(applied)
            try:
                current, default = branch_context(context)
            except (OSError, ValueError, UnicodeError):
                return 'unknown'
            destination = refspec[-1]
            target = destination.removeprefix('refs/heads/')
            target = current if target == 'HEAD' else target
            if target in {'main', 'master', 'trunk', default}:
                return 'forbidden'
            if not default or not target:
                return 'unknown'
            # A bare or abbreviated destination can resolve to a tag, so only an explicit branch ref is a known push.
            if len(refspec) != 2 or not destination.startswith('refs/heads/'):
                return 'unknown'
            if applied['Push and pull requests'] != 'yes':
                return 'push-disabled'
            # Git pushes to origin's pushurl when one is set, else its url: that one destination must be the target.
            if context.target is None or store.push_target(context.ident) != context.target:
                return 'unknown'
            return 'allowed'
        if verb == 'merge':
            if tail not in (['origin/main'], ['--no-edit', 'origin/main']):
                return local_merge(tail, applied)
            # The synchronization exemption: a local merge of origin/main into a work branch needs no Merge setting.
            try:
                current, default = branch_context(context_of(applied))
            except (OSError, ValueError, UnicodeError):
                return 'unknown'
            return 'allowed' if current and default and current not in {default, 'main', 'master', 'trunk'} else 'forbidden'
        if verb == 'add':
            return classify_paths(tail[1:] if tail[:1] == ['--'] else tail, applied.get('Roots', ()),
                                  context_of(applied), source_mode(applied))
        if verb == 'worktree':
            return worktree_remove(tail, applied)
        if verb == 'branch' and tail[:1] == ['-d']:
            return branch_delete(tail, applied)
        if verb == 'rm':
            return tracked_remove(tail, applied)
        if verb == 'commit':
            return commit_text(tail, context_of(applied))
        query = {
            'status': ({'--short', '-s', '--porcelain', '--branch', '-b'}, set()),
            'log': ({'--oneline', '--stat', '--all', '--decorate', '--graph', '--no-decorate', '-N'}, {'-n', '--max-count', '--format', '--pretty'}),
            'diff': ({'--stat', '--name-only', '--name-status', '--cached', '--staged', '--check', '--no-ext-diff', '--no-textconv'}, set()),
            'show': ({'--stat', '--name-only', '--format=fuller', '--no-patch', '--no-ext-diff', '--no-textconv'}, {'--format'}),
            'rev-parse': ({'--show-toplevel', '--show-prefix', '--abbrev-ref', '--verify'}, set()),
            'ls-files': ({'--stage', '--cached', '--modified', '--others', '--exclude-standard'}, set()),
            'ls-tree': ({'-r', '--name-only'}, set()),
            'branch': ({'--show-current', '--list', '-a', '--all', '-r', '--remotes', '-v', '-vv'}, set()),
            'remote': ({'-v', '--verbose'}, set()),
        }
        if verb in query:
            operands = options(tail, query[verb][0] | {'--'}, query[verb][1])
            if operands is not None and (verb not in {'branch', 'remote'} or not operands):
                for operand in operands:
                    if operand == '--':
                        continue
                    # Revisions are an explicit grammar; path operands use the same path gate.
                    revision = r'(?:HEAD(?:[~^][0-9]*)?|[0-9a-f]{7,40}|origin/[A-Za-z0-9_./-]+)'
                    if re.fullmatch(revision + r'(?:\.\.\.?' + revision + r')?', operand):
                        continue
                    if classify_paths([operand], applied.get('Roots', ()), context_of(applied),
                                      source_mode(applied)) != 'allowed':
                        return 'unknown'
                return 'allowed'
        return 'unknown'
    if command == 'gh' and len(argv) >= 3:
        group, verb, tail = argv[1], argv[2], argv[3:]
        common = {'--repo', '-R', '--json', '--jq', '-q', '--template', '-t'}
        if group == 'pr' and verb == 'merge':
            if applied['Merge'] != 'yes':
                return 'merge-disabled'
            pins = [t.split('=', 1)[1] if t.startswith('--match-head-commit=') else tail[i + 1] if i + 1 < len(tail) else ''
                    for i, t in enumerate(tail) if t == '--match-head-commit' or t.startswith('--match-head-commit=')]
            if len(pins) != 1 or not SHA.fullmatch(pins[0]):
                return 'unpinned'
            if '--delete-branch' in tail and not permits({'Recoverable deletion'}, applied):
                return 'forbidden'  # row 3: the deletion is its own category beside Merge
            operands = options(tail, {'--squash', '--merge', '--rebase', '--delete-branch'}, {'--match-head-commit', '--repo', '-R'})
            if operands is None or len(operands) != 1 or not re.fullmatch(r'[1-9][0-9]{0,9}', operands[0]):
                return 'unknown'  # the same ASCII number grammar `log --pr` takes, so a pin names what gh merges
            return target_check(tail, context_of(applied))  # the permission is this context's target, never another
        if group == 'pr' and verb in {'create', 'edit'}:
            if applied['Push and pull requests'] != 'yes':
                return 'push-disabled'
            operands = options(tail, {'--draft', '--fill'}, {'--title', '-t', '--body', '-b', '--body-file', '-F', '--base', '-B', '--head', '-H', '--repo', '-R', '--add-label', '--remove-label'})
            # Create takes no operand; edit names one pull request by number (never the current branch's).
            expected = 0 if verb == 'create' else 1
            if operands is None or len(operands) != expected or not all(o.isdigit() for o in operands):
                return 'unknown'
            context = context_of(applied)
            if verb == 'create':
                head = head_check(tail, context)
                if head != 'allowed':
                    return head
            text = pr_text(tail, context)
            return text if text != 'allowed' else target_check(tail, context)
        if group == 'pr' and verb == 'comment':
            # `gh pr comment <number> --body|--body-file ... --repo github.com/OWNER/NAME`: its own category.
            if not permits({'Repository comments'}, applied):
                return 'forbidden'
            operands = options(tail, set(), {'--body', '-b', '--body-file', '-F', '--repo', '-R'})
            if operands is None or len(operands) != 1 or not operands[0].isdigit():
                return 'unknown'
            if not any(t in {'--body', '-b', '--body-file', '-F'} or t.startswith(('--body=', '--body-file=')) for t in tail):
                return 'unknown'  # without a body gh opens an editor
            context = context_of(applied)
            text = pr_text(tail, context)
            return text if text != 'allowed' else target_check(tail, context)
        queries = {'pr': {'view', 'checks', 'list', 'status', 'diff'}, 'issue': {'view', 'list', 'status'},
                   'repo': {'view'}, 'run': {'view', 'list'}}
        if verb in queries.get(group, set()):
            operands = options(tail, {'--watch', '--required', '--summary', '--comments', '--patch', '--stat'},
                               common | {'--state', '--limit', '-L', '--base', '--head', '--author', '--label', '--search', '--branch', '--status'})
            return 'allowed' if operands is not None else 'unknown'
    return 'unknown'


def check(folder, args):
    current = now()
    code, lease, applied = lease_guard(folder, current)
    if code is None:
        argv, cwd = None, os.getcwd()
        if args.argv_json is not None:
            try:
                argv = json.loads(args.argv_json)
            except ValueError:
                argv = None
            if isinstance(argv, list) and len(argv) >= 3 and argv[:2] == ['git', '-C']:
                # `git -C <folder> ...` is judged as the same command run in that folder, which must lie in a
                # checkout of this repository and not under a protected path; anything else is Tier 3.
                found = checkout_of(argv[2], cwd) if isinstance(argv[2], str) else None
                here = store.identity(cwd)
                if (found is None or here[0] != 'found' or found[0].main != here[1].main
                        or protected(found[1].as_posix()) or not os.path.isdir(os.path.join(cwd, argv[2]))):
                    code = 'unknown'
                else:
                    argv, cwd = ['git', *argv[3:]], os.path.abspath(os.path.join(cwd, argv[2]))
        if code is None:
            # The lease hash covers the user section only; the repository's project values are read on every check.
            applied = effective(applied, cwd)
            if isinstance(argv, list) and argv[:3] == ['git', 'worktree', 'remove']:
                applied[MERGED] = merged_heads(folder, lease, current)
            if args.argv_json is not None:
                code = classify_argv(argv, applied, args.coordinator)
            else:
                code = classify_paths(args.paths, applied['Roots'], context_of(applied), source_mode(applied))
        # Only a Tier 1 answer reserves an action (and, for a ledger start, a run); a denied check costs nothing.
        if code == 'allowed':
            counters = lease['counters']
            counters['actions'] += 1
            counters['hour_actions'].append(current)
            if argv and any(Path(t).name == 'ledger.py' for t in argv) and 'start' in argv:
                counters['runs'] += 1
            save_lease(folder, lease)
            if isinstance(argv, list) and argv[:3] == ['gh', 'pr', 'merge']:
                append_log(folder, merge_pin(argv, current), current)
    tier = 1 if code == 'allowed' else 3
    result = {'tier': tier, 'code': code}
    if code in ENDED:
        # A host loop can outlive the lease; the answer itself tells the caller to end it.
        result['end'] = ENDED_LINE
    print(json.dumps(result, separators=(',', ':')))
    return tier


def merged_heads(folder, lease, current):
    """The full head SHAs that `log --kind merge --pr <number> --head` entries recorded during this lease; empty on any doubt."""
    try:
        raw = read_private(folder, 'log.jsonl', MAX_LOG) or b''
        heads = set()
        for line in raw.splitlines():
            entry = json.loads(line)
            if (isinstance(entry, dict) and entry.get('kind') == 'merge' and isinstance(entry.get('head'), str)
                    and SHA.fullmatch(entry['head']) and finite(entry.get('time'))
                    and lease['start'] <= entry['time'] <= current):
                heads.add(entry['head'])
        return heads
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        return set()


def show_effective(folder):
    """Read-only: the five values `check` would apply in this working directory now, for advisory consumers (Task
    choice, Trusted authors). Reserves nothing and changes no counter; prints no path."""
    code, _, applied = lease_guard(folder, now())
    result = effective(applied if applied is not None else settings(), os.getcwd())
    context = result[CONTEXT]
    print(json.dumps({'lease': code or 'live', 'repository': context.repository, 'state': context.state,
                      'target': context.target, 'values': {name: result[name] for name in OFF}},
                     separators=(',', ':')))


def safe_note(note):
    if len(note) > 8192:
        raise ValueError('afk note is too large')
    note = ''.join(c for c in note if not unicodedata.category(c).startswith('C'))
    note = secret_patterns.redacted(note, secret_patterns.findings(note)).replace('\\', '/')
    # All assignments, even short values, may contain environment values.
    note = secret_patterns.PAIR.sub('[REDACTED]', note)
    note = re.sub(r'(?<!\w)(?:[A-Za-z]:)?(?:~?/|[A-Za-z0-9_.-]+/)[^\s,;]+', '[REDACTED]', note)
    if re.search(r'\b(?:git|gh|python3?|bash|sh|npm|npx|pnpm|wrangler|rm|curl)\s+\S', note):
        return '[REDACTED]'
    return note[:500]


def label(value):
    if not isinstance(value, str) or not LABEL.fullmatch(value) or secret_patterns.findings(value):
        raise ValueError('afk label is invalid')
    return value


def iso(current):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(current, timezone.utc).isoformat(timespec='seconds')


def recorded_decision(identifier):
    if not isinstance(identifier, str) or not DECISION_ID.fullmatch(identifier):
        return False
    import ledger
    return any(r['event'] == 'decision' and r['id'] == identifier for r in ledger.load_away())


def attempt(args):
    """Validate one attempt against the closed schema; return the fields stored in the ledger."""
    rung, settled = args.rung, args.settled
    if rung is None or settled is None or args.project is None or args.topic is None or args.precedents is None:
        raise ValueError('afk decision needs rung, settled, project, topic and precedents')
    given = {f for f in FIELDS if getattr(args, f) is not None}
    if (rung, settled) == ('advisor', 'unavailable'):
        required, optional = ({'by'}, {'dispatch'}) if 'by' in given else (set(), set())
    elif (rung, settled) in ATTEMPTS:
        required, optional = ATTEMPTS[rung, settled]
    else:
        raise ValueError('afk decision rung and result do not match')
    if not required <= given <= required | optional:
        raise ValueError('afk decision fields do not match the schema')
    if not re.fullmatch(r'[0-8]', args.precedents):
        raise ValueError('afk precedents count is invalid')
    fields = dict(rung=rung, settled=settled, precedents=int(args.precedents), topic=label(args.topic))
    if 'by' in given:
        valid = {'rule': args.by == 'rule', 'jev': args.by == 'jev', 'advisor': bool(ADVISOR.fullmatch(args.by)),
                 'host': args.by in PROGRAMS, 'park': args.by in PROGRAMS}[rung]
        if not valid:
            raise ValueError('afk decider is invalid')
        fields['by'] = args.by
    if 'of' in given:
        if not re.fullmatch(r'[2-6]', args.of) or not re.fullmatch(r'[1-6]', args.option) or int(args.option) > int(args.of):
            raise ValueError('afk option is invalid')
        fields.update(option=int(args.option), of=int(args.of))
    if 'probability' in given:
        # A bounded plain decimal, so the value judge.ask_choice returns (up to 17 significant digits) round-trips.
        if not re.fullmatch(r'[01](?:\.[0-9]{1,20})?', args.probability):
            raise ValueError('afk probability is invalid')
        probability = float(args.probability)
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('afk probability is invalid')
        if (settled == 'yes') != (probability >= SETTLE):
            raise ValueError('afk probability does not match the result')
        fields['probability'] = probability
    if 'dispatch' in given:
        if not DISPATCH_ID.fullmatch(args.dispatch):
            raise ValueError('afk dispatch id is invalid')
        fields['dispatch'] = args.dispatch
    if 'model' in given:
        if not MODEL.fullmatch(args.model):
            raise ValueError('afk model is invalid')
        fields['model'] = args.model
    return fields


def decide(folder, args, current):
    """Record one ladder attempt in the ledger; the first attempt generates the decision id and prints it."""
    fields = attempt(args)
    project = label(args.project)
    lease = None if read_private(folder, 'stop') is not None else read_lease(folder)
    if lease is None or not lease['start'] <= current < lease['expiry']:
        raise ValueError('afk decision needs a live lease')
    if args.decision is None:
        identifier = time.strftime('q%Y%m%d-%H%M%S-', time.localtime(current)) + os.urandom(2).hex()
    elif recorded_decision(args.decision):
        identifier = args.decision
    else:
        raise ValueError('afk decision id is unknown')
    import away_lease
    away_lease.append_ledger(dict(event='decision', id=identifier, ts=iso(current), project=project,
                                  lease_start=lease['start'], **fields))
    return identifier


def review(folder, args):
    if not recorded_decision(args.decision):
        raise ValueError('afk decision id is unknown')
    import away_lease
    away_lease.append_ledger(dict(event='decision_review', id=args.decision, ts=iso(now()), verdict=args.verdict))
    print('Decision review recorded')


def screened(value):
    """True when a value holds a secret, a machine path or a sensitive assignment."""
    try:
        if secret_patterns.findings(value):
            return True
    except ValueError:
        return True
    import judge
    return judge.sensitive(value) or judge.assigns_sensitive(value)


def packet_check(args):
    """Lint a precedent packet: at most eight excerpts and 8 KB; a secret or path drops an excerpt; consent first."""
    applied = settings()
    fd = os.open(args.file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            raise ValueError('Packet file is unsafe')
        raw = os.read(fd, 65537)
    finally:
        os.close(fd)
    packet = json.loads(raw.decode('utf-8'))
    if (not isinstance(packet, dict) or set(packet) != {'goal', 'excerpts'} or not isinstance(packet['goal'], str)
            or not 0 < len(packet['goal'].encode()) <= 2048 or not isinstance(packet['excerpts'], list)
            or len(packet['excerpts']) > 8):
        raise ValueError('Packet is invalid')
    excerpts = packet['excerpts']
    for item in excerpts:
        if (not isinstance(item, dict) or set(item) != {'decision', 'date', 'source'}
                or not all(isinstance(v, str) and 0 < len(v.encode()) <= 2048 for v in item.values())
                or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', item['date'])):
            raise ValueError('Packet excerpt is invalid')
    if len(json.dumps(excerpts, ensure_ascii=False).encode()) > 8192 or screened(packet['goal']):
        raise ValueError('Packet is too large or its goal is unsafe')
    if excerpts and applied[CONSENT] != 'yes':
        raise ValueError('Excerpts may not leave the machine without the separate consent')
    kept = [item for item in excerpts if not any(screened(v) for v in item.values())]
    print(json.dumps({'goal': packet['goal'], 'excerpts': kept, 'dropped': len(excerpts) - len(kept)}, ensure_ascii=False))


def log(folder, args):
    decision_flags = ('rung', 'settled', 'precedents', 'topic', 'project', 'decision', *FIELDS)
    if args.kind != 'decision' and any(getattr(args, key) is not None for key in decision_flags):
        raise ValueError('Decision fields belong to the decision kind')
    current = now()
    fields = {}
    for key in ('task', 'run'):
        value = getattr(args, key)
        if value is not None:
            if not ID.fullmatch(value) or secret_patterns.findings(value):
                raise ValueError('afk id is invalid')
            fields[key] = value
    if args.pr is not None:
        if not re.fullmatch(r'[1-9][0-9]{0,9}', args.pr):
            raise ValueError('afk pull request id is invalid')
        fields['pr'] = int(args.pr)
    if args.head is not None:
        # The merged pull request's full head SHA: the one worktree `git worktree remove` may then take away.
        if args.kind != 'merge' or not SHA.fullmatch(args.head) or args.pr is None:
            raise ValueError('afk head belongs to the merge kind with its --pr and is a full lowercase SHA')
        fields['head'] = args.head
    if args.kind == 'merge' and args.head is not None and (fields['pr'], args.head) not in merge_pins(folder, current):
        raise ValueError('afk merge head matches no allowed `gh pr merge` check of this lease')
    note = safe_note(args.note or '')
    # Every other check passes before the decision line reaches the ledger.
    identifier = decide(folder, args, current) if args.kind == 'decision' else None
    if identifier:
        fields['decision'] = identifier
    append_log(folder, dict(time=current, tier=KINDS[args.kind], kind=args.kind, **fields, note=note), current)
    print(identifier if identifier else 'afk action logged')


def append_log(folder, record, current):
    """Append one record to the private log, keeping the last 30 days; refuses an invalid or full log."""
    raw = read_private(folder, 'log.jsonl', MAX_LOG)
    retained = []
    for line in (raw or b'').splitlines():
        old = json.loads(line)
        if not isinstance(old, dict) or not finite(old.get('time')):
            raise ValueError('afk log is invalid')
        if current - 30 * 86400 <= old['time'] <= current:
            retained.append(line)
    retained.append(json.dumps(record, separators=(',', ':')).encode())
    payload = b'\n'.join(retained) + b'\n'
    if len(payload) > MAX_LOG:
        raise ValueError('afk log is full')
    write_private(folder, 'log.jsonl', payload)


def merge_pin(argv, current):
    """The `merge-pin` record of an allowed `gh pr merge <n> --match-head-commit <sha>` check (classify_argv has
    already required one number operand and one full pin)."""
    tail = argv[3:]
    pr = next(t for t in options(tail, {'--squash', '--merge', '--rebase', '--delete-branch'},
                                 {'--match-head-commit', '--repo', '-R'}))
    head = next(t.split('=', 1)[1] if t.startswith('--match-head-commit=') else tail[i + 1]
                for i, t in enumerate(tail) if t == '--match-head-commit' or t.startswith('--match-head-commit='))
    return dict(time=current, tier=1, kind='merge-pin', pr=int(pr), head=head, note='')


def merge_pins(folder, current):
    """The (pull request, head) pairs that allowed `gh pr merge` checks of the live lease pinned; empty on any doubt."""
    try:
        lease = read_lease(folder)
        if lease is None or read_private(folder, 'stop') is not None or not lease['start'] <= current < lease['expiry']:
            return set()
        pins = set()
        for line in (read_private(folder, 'log.jsonl', MAX_LOG) or b'').splitlines():
            entry = json.loads(line)
            if (isinstance(entry, dict) and entry.get('kind') == 'merge-pin' and type(entry.get('pr')) is int
                    and isinstance(entry.get('head'), str) and SHA.fullmatch(entry['head'])
                    and finite(entry.get('time')) and lease['start'] <= entry['time'] <= current):
                pins.add((entry['pr'], entry['head']))
        return pins
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        return set()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    begin = sub.add_parser('start', allow_abbrev=False)
    begin.add_argument('--hours')
    sub.add_parser('stop', allow_abbrev=False)
    sub.add_parser('effective', allow_abbrev=False)
    inspect = sub.add_parser('check', allow_abbrev=False)
    group = inspect.add_mutually_exclusive_group(required=True)
    group.add_argument('--argv-json')
    group.add_argument('--paths', nargs='+')
    inspect.add_argument('--coordinator', choices=sorted(PROGRAMS), help="the coordinator's own family")
    record = sub.add_parser('log', allow_abbrev=False)
    record.add_argument('--kind', required=True, choices=sorted(KINDS))
    for key in ('task', 'pr', 'run', 'head', 'note', 'decision', 'rung', 'settled', 'precedents', 'topic', 'project', *FIELDS):
        record.add_argument('--' + key)
    reviewed = sub.add_parser('review', allow_abbrev=False)
    reviewed.add_argument('--decision', required=True)
    reviewed.add_argument('verdict', choices=('kept', 'reversed'))
    packet = sub.add_parser('packet-check', allow_abbrev=False)
    packet.add_argument('--file', required=True)
    args = parser.parse_args(argv)
    try:
        with private_folder() as folder:
            if args.command == 'start':
                start(folder, args)
            elif args.command == 'stop':
                stop(folder)
            elif args.command == 'check':
                # Exit 0 only on Tier 1, so `check ... && command` never runs a denied command.
                return 0 if check(folder, args) == 1 else 3
            elif args.command == 'effective':
                show_effective(folder)
            elif args.command == 'review':
                review(folder, args)
            elif args.command == 'packet-check':
                packet_check(args)
            else:
                log(folder, args)
        return 0
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        if args.command == 'check':
            print(json.dumps({'tier': 3, 'code': 'unsafe'}, separators=(',', ':')))
            return 3
        print('afk refused: setup or private state is missing, invalid, unsafe or already active')
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
