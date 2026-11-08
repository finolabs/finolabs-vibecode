#!/usr/bin/env python3
"""Local autopilot lease, action classification and private action log; no execution.

Rule table (each row names its enforcer; unknown input always fails closed):

| Rule | Enforcer |
| --- | --- |
| Setup is one canonical ## Autopilot key/value section; Merge has no default, hours are 1..24 | settings, start |
| State stays outside Git, private (directories 0700/files 0600), no links, atomic and serialized | private_folder, read_private, write_private, data_root, flock |
| One live lease; stop removes it and leaves a stop marker; starting clears that marker | start, stop |
| Missing/expired/stopped/changed setup or exhausted runs, wall/runtime minutes or rolling-hour actions denies every check | lease_guard |
| Tags, releases, publish/deploy, recursive deletion, force/default-branch pushes are Tier 3 | classify_argv |
| Credentials/env names, .github, hooks, agent instructions, settings, host/setup/lease files are Tier 3 anywhere in argv or paths | protected |
| Only relative source/test/docs/script files in enumerated roots/extensions are known paths; security enforcer scripts deny edits; everything else is Tier 3 | classify_paths |
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
import fcntl
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

DEFAULTS = {'Hosts': 'Claude Code', 'Task choice': 'choose', 'Push and pull requests': 'yes',
            'Trusted authors': 'own', 'Lease hours': 8, 'Max runs': 20,
            'Max runtime minutes': 480, 'Max actions per hour': 30, 'Quota floor percent': 15}
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
             'auto_gate.py', 'mode.py', 'judge.py', 'log_scan.py', 'route_task.py', 'brief_check.py'}
ENFORCERS = {name.casefold() for name in ENFORCERS}  # case-insensitive filesystems name one file many ways


def now():
    return time.time()


def settings():
    text = dr.read_data('host.md', slots.HOST_LIMIT).decode('utf-8')
    start, body, end = slots.host_section(text, 'Autopilot')
    if start == body == end:
        raise ValueError('Autopilot setup is missing')
    result, seen = dict(DEFAULTS), set()
    for line in text[body:end].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'- ([A-Za-z ]+): (.+)', line)
        if not match or match[1] not in {*DEFAULTS, 'Merge'} or match[1] in seen:
            raise ValueError('Autopilot setup is invalid')
        key, value = match.groups()
        seen.add(key)
        if key in NUMBERS:
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


def private_info(folder, name):
    try:
        info = os.stat(name, dir_fd=folder, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise ValueError('Autopilot state file is unsafe')
    return info


def read_private(folder, name, cap=65536):
    if private_info(folder, name) is None:
        return None
    return dr.read_file(folder, name, cap)


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


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def read_lease(folder):
    raw = read_private(folder, 'lease.json')
    if raw is None:
        return None
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {'id', 'start', 'expiry', 'settings_hash', 'counters'}
            or not isinstance(value['id'], str) or not re.fullmatch(r'[0-9a-f]{32}', value['id'])
            or not all(finite(value[k]) for k in ('start', 'expiry'))
            or not value['start'] < value['expiry'] <= value['start'] + 24 * 3600
            or not isinstance(value['settings_hash'], str) or not re.fullmatch(r'[0-9a-f]{64}', value['settings_hash'])):
        raise ValueError('Autopilot lease is invalid')
    counters = value['counters']
    if (not isinstance(counters, dict) or set(counters) != {'runs', 'runtime_minutes', 'actions', 'hour_actions'}
            or any(type(counters[k]) is not int or counters[k] < 0 for k in ('runs', 'actions'))
            or not finite(counters['runtime_minutes']) or not isinstance(counters['hour_actions'], list)
            or len(counters['hour_actions']) > 10000
            or not all(finite(t) for t in counters['hour_actions'])):
        raise ValueError('Autopilot counters are invalid')
    return value


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
        raise ValueError('Autopilot already has a live lease')
    lease = dict(id=uuid.uuid4().hex, start=current, expiry=current + hours * 3600,
                 settings_hash=digest(applied), counters=dict(runs=0, runtime_minutes=0, actions=0, hour_actions=[]))
    save_lease(folder, lease)
    try:
        os.unlink('stop', dir_fd=folder)
    except FileNotFoundError:
        pass
    summary = {**applied, 'Lease hours': hours}
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


def classify_paths(paths):
    if not paths:
        return 'unknown'
    for name in paths:
        if not isinstance(name, str) or protected(name):
            return 'protected'
        path = Path(name)
        if path.name.casefold() in ENFORCERS or path.name.upper() in slots.INSTRUCTION_FILES:
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
    merge = own.parent.parent / 'fnl-review-gate/scripts/merge_check.py'
    allowed = {own / name for name in ('ledger.py', 'record.py', 'heavy_run.py')} | {merge}
    if path not in allowed or path.is_symlink() or not path.is_file():
        return 'unknown'
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


def classify_argv(argv, applied):
    if (not isinstance(argv, list) or not argv or len(argv) > 256
            or any(not isinstance(t, str) or not t or len(t) > 8192
                   or any(unicodedata.category(c).startswith('C') for c in t) for t in argv)):
        return 'unknown'
    if any(t in {';', '&&', '||', '|', '>', '>>', '<'} or '$(' in t or '`' in t for t in argv):
        return 'unknown'
    if any(protected(t) for t in argv):
        return 'protected'
    command = argv[0]
    if (argv[:2] in (['git', 'tag'], ['gh', 'release'])
            or any(re.fullmatch(r'(?:publish|deploy)(?::[\w-]+)?', t) for t in argv[1:])
            or command == 'rm' and any(t.startswith('-') and ('r' in t[1:] or t == '--recursive') for t in argv[1:])):
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
            code = classify_argv(argv, applied)
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


def log(folder, args):
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
    current = now()
    record = dict(time=current, tier=KINDS[args.kind], kind=args.kind, **fields, note=safe_note(args.note or ''))
    raw = read_private(folder, 'log.jsonl', MAX_LOG)
    retained = []
    for line in (raw or b'').splitlines():
        old = json.loads(line)
        if not isinstance(old, dict) or not finite(old.get('time')):
            raise ValueError('Autopilot log is invalid')
        if current - 30 * 86400 <= old['time'] <= current:
            retained.append(line)
    retained.append(json.dumps(record, separators=(',', ':')).encode())
    payload = b'\n'.join(retained) + b'\n'
    if len(payload) > MAX_LOG:
        raise ValueError('Autopilot log is full')
    write_private(folder, 'log.jsonl', payload)
    print('Autopilot action logged')


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
    record = sub.add_parser('log', allow_abbrev=False)
    record.add_argument('--kind', required=True, choices=sorted(KINDS))
    for key in ('task', 'pr', 'run', 'note'):
        record.add_argument('--' + key)
    args = parser.parse_args(argv)
    try:
        with private_folder() as folder:
            if args.command == 'start':
                start(folder, args)
            elif args.command == 'stop':
                stop(folder)
            elif args.command == 'check':
                check(folder, args)
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
