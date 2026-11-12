#!/usr/bin/env python3
"""Local autopilot lease, action classification and private action log; no execution.

Rule table (each row names its enforcer; unknown input always fails closed):

| Rule | Enforcer |
| --- | --- |
| Setup is one canonical ## Autopilot key/value section; Merge has no default, hours are 1..24 | settings, start |
| State stays outside Git, private (directories 0700/files 0600), no links, atomic and serialized | private_folder, read_private, write_private, data_root, flock |
| One live lease for the machine; a second start reports it and changes nothing; stop removes it and leaves a stop marker; starting clears that marker | start, stop |
| Missing/expired/stopped/changed setup or exhausted runs, wall/runtime minutes or rolling-hour actions denies every check | lease_guard |
| Tags, releases, publish/deploy, recursive deletion, force/default-branch pushes are Tier 3, except: closed tag, release and npm/pnpm publish forms whose every applicable category is `decide`, and a deploy matching a `Non-production targets` entry exactly with no production or live word; categories come from the program and subcommand, never from free-text data | classify_argv, command_categories, is_deploy, release_command, permits |
| Categories are `stop` or `decide`; missing, unknown and the two fixed rows are `stop`; excerpt consent is its own key | settings |
| The ladder's two forms: this install's judge.py at the away-decision site with validated options, and delegate_env.py with one closed read-only argv per family, in Hosts and not the coordinator's, whose program is the family's owner-approved executable recorded for the quota probe and re-checked at check time (no bare name, PATH lookup, other path or time-cap wrapper); the brief follows a literal `--` (Codex, Claude) or is the value of -p (Antigravity), never starts with `-`, and passes the secret and machine-path screens, and no sensitive name in it has an assigned value | ladder_command, judge_command, advisor_command, approved_program, quota_probe.checked_executable, brief_ok |
| Decision attempts follow a closed schema and reach the ledger with no question or option text; reviews need a recorded id | attempt, decide, review |
| A precedent packet holds at most eight excerpts and 8 KB; a secret or machine path drops an excerpt; excerpts need the separate consent | packet_check |
| Credentials/env names, .github, hooks, agent instructions, settings, host/setup/lease files are Tier 3 anywhere in argv or paths | protected |
| Any path inside this install's own skill script folders is protected (a new module could shadow an import of a trusted wrapper); only relative source/test/docs/script files in enumerated roots/extensions are known paths; security enforcer scripts deny edits; everything else is Tier 3 | classify_paths |
| Read-only Git/gh queries use closed verbs and option sets; command/config overrides and unknown options deny | classify_argv, options |
| Git add of allowed paths, commit, origin push whose destination is an explicit refs/heads/<non-default branch> (a bare or abbreviated destination could resolve to a tag) and merge origin/main are Tier 1 | classify_argv, branch_context |
| PR create/edit require push permission; PR merge requires Merge=yes and one full --match-head-commit SHA | classify_argv |
| Only this install's ledger/record/heavy_run/merge_check script paths, with isolated Python, are allowed wrappers; nested heavy commands are classified too | script_command |
| Each Tier 1 check reserves one action; ledger start also reserves a run, even if the caller never executes | check |
| Log kinds/tiers and ids are enumerated/validated; notes lose controls, paths, command text and secret/assignment values, cap at 500; retention 30 days | log, safe_note, secret_patterns |
| Trusted PR authors, full independent review/check/local-test gate, changed paths (including staged commit paths), quota readings and actually calling check before execution remain caller obligations in this slice | agent judgment, advisory; merge_check --independent enforces its review condition |

A Tier 1 answer is a classification, not proof that a PR passed the full merge
gate or that its author is trusted. This script has no author input and never
checks out/tests a PR. It never executes argv, reads credentials, reads the
process environment, or persists argv/paths/settings contents. The live tick,
quota probe, scheduler, notices and host backstop are outside this first part.
Counters are reservations, not evidence that a command ran. Setup changes need
a new lease. There is no status command or long-lived process.
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
import unicodedata
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root as dr
import parallel_slots as slots
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
HOST_FAMILIES = {'Claude Code': 'claude', 'Codex': 'codex', 'Antigravity': 'antigravity'}
PROGRAMS = {'claude': 'claude', 'codex': 'codex', 'antigravity': 'agy'}
MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,79}')
LABEL = re.compile(r'[A-Za-z0-9._-](?:[A-Za-z0-9 ._-]{0,58}[A-Za-z0-9._-])?')
DECISION_ID = re.compile(r'q[0-9]{8}-[0-9]{6}-[0-9a-f]{4}')
DISPATCH_ID = re.compile(r'd[0-9]{8}-[0-9]{6}-[0-9a-f]{4}')
ADVISOR = re.compile(r'(?:claude|codex|antigravity)[a-z0-9]{0,24}')
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
EXTENSIONS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html', '.md', '.txt', '.json', '.toml', '.yaml', '.yml'}
MAX_LOG = 8 * 1024 * 1024
ENFORCERS = {'autopilot.py', 'data_root.py', 'parallel_slots.py', 'secret_patterns.py', 'merge_check.py',
             'review_config.py', 'review_route.py', 'post_review.py', 'heavy_gate.py', 'run_env.py', 'ledger.py',
             'record.py', 'verify_claim.py', 'git_metadata.py', 'quota_probe.py', 'heavy_run.py', 'delegate_env.py',
             'auto_gate.py', 'mode.py', 'judge.py', 'log_scan.py', 'route_task.py', 'brief_check.py', 'assignments.py',
             'away_lease.py', 'away_gate_hook.py'}
ENFORCERS = {name.casefold() for name in ENFORCERS}  # case-insensitive filesystems name one file many ways


def now():
    return time.time()


def settings():
    text = dr.read_data('host.md', slots.HOST_LIMIT).decode('utf-8')
    start, body, end = slots.host_section(text, 'Autopilot')
    if start == body == end:
        raise ValueError('Autopilot setup is missing')
    result, seen = {**DEFAULTS, **{c: 'stop' for c in CATEGORIES}, CONSENT: 'no', TARGETS: []}, set()
    for line in text[body:end].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'- ([A-Za-z -]+): (.+)', line)
        if not match or match[1] not in {*DEFAULTS, 'Merge', *CATEGORIES, CONSENT, TARGETS} or match[1] in seen:
            raise ValueError('Autopilot setup is invalid')
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
                raise ValueError('Autopilot setup has an invalid limit')
            value = int(value)
        elif key == 'Hosts':
            hosts = value.split(', ')
            if len(hosts) != len(set(hosts)) or not set(hosts) <= {'Claude Code', 'Codex', 'Antigravity'}:
                raise ValueError('Autopilot setup has invalid hosts')
        elif value not in {'Task choice': {'choose', 'listed'}, 'Push and pull requests': {'yes', 'no'},
                            'Merge': {'yes', 'no'}, 'Trusted authors': {'own'}}[key]:
            raise ValueError('Autopilot setup has an invalid choice')
        result[key] = value
    if 'Merge' not in seen:
        raise ValueError('Autopilot setup needs an explicit Merge answer')
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
        raise ValueError('Autopilot data root is invalid')
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
        print(f'Autopilot already live until {until}; this lease covers every session on this machine. '
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
    print('Autopilot started\n' + '\n'.join(f'- {key}: {value}' for key, value in summary.items()))


def stop(folder):
    removed = read_private(folder, 'lease.json') is not None
    read_private(folder, 'stop')
    write_private(folder, 'stop', b'')
    if removed:
        os.unlink('lease.json', dir_fd=folder)
        os.fsync(folder)
    print('Autopilot stopped: stop marker written; lease ' + ('removed' if removed else 'already absent'))


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
    if (counters['runs'] >= applied['Max runs']
            or max(counters['runtime_minutes'], (current - lease['start']) / 60) >= applied['Max runtime minutes']
            or len(counters['hour_actions']) >= applied['Max actions per hour']):
        return 'limit', lease, applied
    return None, lease, applied


def protected(value):
    """Lexical check before command parsing; examine ref:path and --option=path too."""
    original = value
    value = value.lower().replace('\\', '/')
    parts = re.split(r'[/:=\s]+', value)
    exact = {'.github', '.git', '.ssh', '.aws', '.gnupg', '.claude', '.codex', '.agents',
             'claude.md', 'claude.local.md', 'agents.md', 'agents.override.md', 'gemini.md',
             'skill.md', 'host.md', 'lease.json', 'log.jsonl', 'root.json', 'stop',
             '.netrc', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519', 'pre-commit', 'pre-push', 'commit-msg', 'post-commit',
             'prepare-commit-msg', 'post-checkout', 'post-merge', 'settings', 'config', 'hooks'}
    return any(p in exact or p.startswith(('.env', 'credentials', 'secrets', 'settings.', 'config.', 'setup.', 'hooks.'))
               or p.endswith(('.pem', '.key', '.p12', '.pfx', '.env'))
               or 'credential' in p or re.search(r'(?:^|[_.-])(?:token|password|secret)(?:[_.-]|$)', p)
               for p in parts) or bool(secret_patterns.PREFIX.search(original)) or any(
                   secret_patterns.NAME.fullmatch(p) and secret_patterns.SENSITIVE.search(p)
                   for p in re.split(r'[=:\s]+', value.upper()))


def plugin_code(name):
    """True for any path inside this install's script folders, so a new module cannot join a trusted import namespace."""
    try:
        full = os.path.abspath(os.path.join(os.getcwd(), name)).casefold()
        base = Path(__file__).resolve().parent.parent.parent
        # Both the lexical folder and, for a linked sibling skill, the checkout it resolves to hold trusted modules.
        folders = {folder for scripts in base.glob('*/scripts') for folder in (scripts, scripts.resolve())}
        return any(full == str(folder).casefold() or full.startswith(str(folder).casefold() + os.sep)
                   for folder in folders)
    except (OSError, ValueError):
        return True


def classify_paths(paths):
    if not paths:
        return 'unknown'
    for name in paths:
        if not isinstance(name, str) or protected(name):
            return 'protected'
        path = Path(name)
        if path.name.casefold() in ENFORCERS or path.name.upper() in slots.INSTRUCTION_FILES or plugin_code(name):
            return 'protected'
        if (not re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', name) or path.is_absolute()
                or any(p in {'', '.', '..'} for p in name.split('/'))
                or len(path.parts) < 2 or path.parts[0] not in ROOTS or path.suffix not in EXTENSIONS):
            return 'unknown'
        # Inspect link metadata only, never the target or any file contents.
        candidate = Path(os.getcwd())
        for part in path.parts:
            candidate /= part
            if candidate.is_symlink():
                return 'protected'
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


def branch_context():
    """Only local metadata, no Git process, config execution or credential helper."""
    root = slots.find_root(os.getcwd())
    if root is None:
        return None, None
    with slots.open_dir(root) as fd:
        info = os.stat('.git', dir_fd=fd, follow_symlinks=False)
        if stat.S_ISREG(info.st_mode):
            link = slots.read_metadata(fd, '.git').strip()
            if not link.startswith('gitdir: '):
                return None, None
            git = Path(os.path.abspath(root / link[8:]))
        elif stat.S_ISDIR(info.st_mode):
            git = root / '.git'
        else:
            return None, None
    with slots.open_dir(git) as fd:
        head = slots.read_metadata(fd, 'HEAD').strip()
        try:
            common = Path(os.path.abspath(git / slots.read_metadata(fd, 'commondir').strip()))
        except FileNotFoundError:
            common = git
    with slots.open_dir(common / 'refs/remotes/origin') as fd:
        default = slots.read_metadata(fd, 'HEAD').strip()
    current = head.removeprefix('ref: refs/heads/') if head.startswith('ref: refs/heads/') else None
    default = default.removeprefix('ref: refs/remotes/origin/') if default.startswith('ref: refs/remotes/origin/') else None
    return current, default


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


def evidence_path(name):
    if not plain(name) or protected(name):
        return False
    if classify_paths([name]) == 'allowed':
        return True
    if not re.fullmatch(r'\.finolabs/briefs/[A-Za-z0-9_.-]{1,80}\.(?:md|json|txt)', name):
        return False
    candidate = Path(os.getcwd())
    for part in Path(name).parts:
        candidate /= part
        if candidate.is_symlink():
            return False
    return not candidate.is_dir()


def judge_command(tail):
    """`judge.py ask --site away-decision --question Q --option O (2 to 6) --evidence-file F [--judge jev]` only."""
    if tail[:1] != ['ask']:
        return 'unknown'
    values = flag_values(tail[1:], {'--site', '--question', '--evidence-file', '--judge'}, {'--option'})
    if (values is None or values.get('--site') != 'away-decision' or values.get('--judge', 'jev') != 'jev'
            or not {'--question', '--evidence-file', '--option'} <= set(values)):
        return 'unknown'
    question, options = values['--question'], values['--option']
    if not all(plain(t) for t in (question, *options)) or not evidence_path(values['--evidence-file']):
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
    return judge_command(tail) if name == 'judge.py' else advisor_command(tail, applied, coordinator)


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


def classify_argv(argv, applied, coordinator=None):
    if not isinstance(argv, list) or not argv or len(argv) > 256 or not all(isinstance(t, str) and t for t in argv):
        return 'unknown'
    ladder = ladder_command(argv, applied, coordinator)
    if ladder is not None:
        return ladder  # its data tokens (question, options, brief) are checked by the form itself
    if any(len(t) > 8192 or any(unicodedata.category(c).startswith('C') for c in t) for t in argv):
        return 'unknown'
    if any(t in {';', '&&', '||', '|', '>', '>>', '<'} or '$(' in t or '`' in t for t in argv):
        return 'unknown'
    if any(protected(t) for t in argv):
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
            try:
                current, default = branch_context()
            except (OSError, ValueError):
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
            return 'allowed' if applied['Push and pull requests'] == 'yes' else 'push-disabled'
        if verb == 'merge':
            if tail not in (['origin/main'], ['--no-edit', 'origin/main']):
                return 'unknown'
            try:
                current, default = branch_context()
            except (OSError, ValueError):
                return 'unknown'
            return 'allowed' if current and default and current not in {default, 'main', 'master', 'trunk'} else 'forbidden'
        if verb == 'add':
            return classify_paths(tail[1:] if tail[:1] == ['--'] else tail)
        if verb == 'commit':
            return 'allowed' if tail and options(tail, {'--amend', '--no-edit'}, {'-m', '--message'}, positional=False) == [] else 'unknown'
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
                    if classify_paths([operand]) != 'allowed':
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
            return 'allowed' if operands is not None and len(operands) == 1 and operands[0].isdigit() else 'unknown'
        if group == 'pr' and verb in {'create', 'edit'}:
            if applied['Push and pull requests'] != 'yes':
                return 'push-disabled'
            operands = options(tail, {'--draft', '--fill'}, {'--title', '-t', '--body', '-b', '--base', '-B', '--head', '-H', '--repo', '-R', '--add-label', '--remove-label'})
            return 'allowed' if operands is not None and (not operands or len(operands) == 1 and operands[0].isdigit()) else 'unknown'
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
        if args.argv_json is not None:
            try:
                argv = json.loads(args.argv_json)
            except ValueError:
                argv = None
            code = classify_argv(argv, applied, args.coordinator)
        else:
            argv = None
            code = classify_paths(args.paths)
        if code == 'allowed':
            counters = lease['counters']
            counters['actions'] += 1
            counters['hour_actions'].append(current)
            if argv and any(Path(t).name == 'ledger.py' for t in argv) and 'start' in argv:
                counters['runs'] += 1
            save_lease(folder, lease)
    print(json.dumps({'tier': 1 if code == 'allowed' else 3, 'code': code}, separators=(',', ':')))


def safe_note(note):
    if len(note) > 8192:
        raise ValueError('Autopilot note is too large')
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
        raise ValueError('Autopilot label is invalid')
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
        raise ValueError('Autopilot decision needs rung, settled, project, topic and precedents')
    given = {f for f in FIELDS if getattr(args, f) is not None}
    if (rung, settled) == ('advisor', 'unavailable'):
        required, optional = ({'by'}, {'dispatch'}) if 'by' in given else (set(), set())
    elif (rung, settled) in ATTEMPTS:
        required, optional = ATTEMPTS[rung, settled]
    else:
        raise ValueError('Autopilot decision rung and result do not match')
    if not required <= given <= required | optional:
        raise ValueError('Autopilot decision fields do not match the schema')
    if not re.fullmatch(r'[0-8]', args.precedents):
        raise ValueError('Autopilot precedents count is invalid')
    fields = dict(rung=rung, settled=settled, precedents=int(args.precedents), topic=label(args.topic))
    if 'by' in given:
        valid = {'rule': args.by == 'rule', 'jev': args.by == 'jev', 'advisor': bool(ADVISOR.fullmatch(args.by)),
                 'host': args.by in PROGRAMS, 'park': args.by in PROGRAMS}[rung]
        if not valid:
            raise ValueError('Autopilot decider is invalid')
        fields['by'] = args.by
    if 'of' in given:
        if not re.fullmatch(r'[2-6]', args.of) or not re.fullmatch(r'[1-6]', args.option) or int(args.option) > int(args.of):
            raise ValueError('Autopilot option is invalid')
        fields.update(option=int(args.option), of=int(args.of))
    if 'probability' in given:
        # A bounded plain decimal, so the value judge.ask_choice returns (up to 17 significant digits) round-trips.
        if not re.fullmatch(r'[01](?:\.[0-9]{1,20})?', args.probability):
            raise ValueError('Autopilot probability is invalid')
        probability = float(args.probability)
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('Autopilot probability is invalid')
        if (settled == 'yes') != (probability >= SETTLE):
            raise ValueError('Autopilot probability does not match the result')
        fields['probability'] = probability
    if 'dispatch' in given:
        if not DISPATCH_ID.fullmatch(args.dispatch):
            raise ValueError('Autopilot dispatch id is invalid')
        fields['dispatch'] = args.dispatch
    if 'model' in given:
        if not MODEL.fullmatch(args.model):
            raise ValueError('Autopilot model is invalid')
        fields['model'] = args.model
    return fields


def decide(folder, args, current):
    """Record one ladder attempt in the ledger; the first attempt generates the decision id and prints it."""
    fields = attempt(args)
    project = label(args.project)
    lease = None if read_private(folder, 'stop') is not None else read_lease(folder)
    if lease is None or not lease['start'] <= current < lease['expiry']:
        raise ValueError('Autopilot decision needs a live lease')
    if args.decision is None:
        identifier = time.strftime('q%Y%m%d-%H%M%S-', time.localtime(current)) + os.urandom(2).hex()
    elif recorded_decision(args.decision):
        identifier = args.decision
    else:
        raise ValueError('Autopilot decision id is unknown')
    import away_lease
    away_lease.append_ledger(dict(event='decision', id=identifier, ts=iso(current), project=project,
                                  lease_start=lease['start'], **fields))
    return identifier


def review(folder, args):
    if not recorded_decision(args.decision):
        raise ValueError('Autopilot decision id is unknown')
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
                raise ValueError('Autopilot id is invalid')
            fields[key] = value
    if args.pr is not None:
        if not re.fullmatch(r'[1-9][0-9]{0,9}', args.pr):
            raise ValueError('Autopilot pull request id is invalid')
        fields['pr'] = int(args.pr)
    note = safe_note(args.note or '')
    raw = read_private(folder, 'log.jsonl', MAX_LOG)
    retained = []
    for line in (raw or b'').splitlines():
        old = json.loads(line)
        if not isinstance(old, dict) or not finite(old.get('time')):
            raise ValueError('Autopilot log is invalid')
        if current - 30 * 86400 <= old['time'] <= current:
            retained.append(line)
    # Every other check passes before the decision line reaches the ledger.
    identifier = decide(folder, args, current) if args.kind == 'decision' else None
    if identifier:
        fields['decision'] = identifier
    record = dict(time=current, tier=KINDS[args.kind], kind=args.kind, **fields, note=note)
    retained.append(json.dumps(record, separators=(',', ':')).encode())
    payload = b'\n'.join(retained) + b'\n'
    if len(payload) > MAX_LOG:
        raise ValueError('Autopilot log is full')
    write_private(folder, 'log.jsonl', payload)
    print(identifier if identifier else 'Autopilot action logged')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    begin = sub.add_parser('start', allow_abbrev=False)
    begin.add_argument('--hours')
    sub.add_parser('stop', allow_abbrev=False)
    inspect = sub.add_parser('check', allow_abbrev=False)
    group = inspect.add_mutually_exclusive_group(required=True)
    group.add_argument('--argv-json')
    group.add_argument('--paths', nargs='+')
    inspect.add_argument('--coordinator', choices=sorted(PROGRAMS), help="the coordinator's own family")
    record = sub.add_parser('log', allow_abbrev=False)
    record.add_argument('--kind', required=True, choices=sorted(KINDS))
    for key in ('task', 'pr', 'run', 'note', 'decision', 'rung', 'settled', 'precedents', 'topic', 'project', *FIELDS):
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
                check(folder, args)
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
            return 0
        print('Autopilot refused: setup or private state is missing, invalid, unsafe or already active')
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
