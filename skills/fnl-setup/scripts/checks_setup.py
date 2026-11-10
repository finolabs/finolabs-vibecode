#!/usr/bin/env python3
"""Detect, preview and apply one repository's entry in the canonical host's Checks section; run no command, make no network call.

A check is a short name and a JSON argument array, never a shell string. Only this script writes `## Checks`.
"""
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import compact_setup as cs
import project_progress as pp
import setup_features as sf

CAP = sf.CAP
STATE = 'state/checks-setup'
HEADING = '## Checks'
NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
CODE = re.compile(r'[0-9a-f]{8}')
LINE = re.compile(r'- ([0-9a-f]{8}): ([a-z0-9][a-z0-9-]{0,31}) = (.+)')
MAX_CHECKS = 20
MAX_ARGV = 1024
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'mksh', 'fish', 'csh', 'tcsh', 'ash', 'cmd', 'powershell', 'pwsh'}
LAUNCHERS = {'env', 'xargs', 'nohup', 'nice', 'timeout', 'time', 'sudo', 'doas', 'exec', 'eval', 'command',
             'busybox', 'script', 'watch'}
INTERPRETER = re.compile(r'python[0-9.]*|node|nodejs|deno|bun|perl[0-9.]*|ruby[0-9.]*|php[0-9.]*')
INLINE = re.compile(r'-[cerEp].*|--(?:eval|print)(?:=.*)?|-[bBdEiIOPqsSuvx]+c.*|eval')
SHELL_FLAG = re.compile(r'-c.*|--call(?:=.*)?|--shell-mode')
PLAN_KEYS = {'code', 'checks', 'root', 'created', 'sha256', 'mode', 'backup'}
SOURCE_LIMIT = 256 * 1024
MAX_WORKFLOWS = 50
MAX_TEST_FILES = 20
MAX_EVIDENCE = 200
EVIDENCE_WIDTH = 120
CI_HEADING = 'found in CI, add with --check if you want it'
PREVIEW_NOTICE = ("Review every array before you approve. These commands run the repository's own code, as cloud CI does; nothing runs now.\nThe refusal of shells, launchers and inline code is a best-effort guard, not a sandbox: an allowed program can still start a shell.\nWhat holds: the plugin never runs an array through a shell itself, and a repository cannot change the stored list.")
PACKAGE_SCRIPTS = ('lint', 'test', 'typecheck', 'build')
MAKE_TARGETS = ('test', 'lint', 'check')
LOCKFILES = (('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'), ('bun.lockb', 'bun'), ('bun.lock', 'bun'))


# The stored argument form

def program_name(path):
    """Lowercase base name without a Windows suffix, splitting on both kinds of slash."""
    name = re.split(r'[\\/]', path)[-1].lower()
    return re.sub(r'\.(?:exe|cmd|bat|com|ps1)$', '', name)


def refused_program(argv):
    """True when the argument array hands control to a shell, a launcher or inline code (deny on doubt)."""
    name = program_name(argv[0])
    if name in SHELLS or name in LAUNCHERS:
        return True
    rest = argv[1:]
    if name == 'yarn' and 'exec' in rest:
        return True
    runs_package = name == 'npx' or (name in ('npm', 'pnpm') and any(arg in ('exec', 'x', 'dlx') for arg in rest))
    if runs_package and any(SHELL_FLAG.fullmatch(arg) for arg in rest):
        return True
    return bool(INTERPRETER.fullmatch(name)) and any(INLINE.fullmatch(arg) for arg in argv[1:])


def check_argv(argv):
    """Refuse anything that is not a bounded argument list, or that hands a string to a shell, a launcher or inline code."""
    if not isinstance(argv, list) or not argv or len(argv) > 64:
        raise ValueError('argument array')
    for item in argv:
        if not isinstance(item, str) or re.search(r'[\x00-\x1f\x7f]', item):
            raise ValueError('argument')
    if not argv[0]:
        raise ValueError('program')
    encoded = json.dumps(argv, separators=(',', ':'), ensure_ascii=True)
    if len(encoded.encode()) > MAX_ARGV:
        raise ValueError('argument array too long')
    if refused_program(argv):
        raise ValueError('shell, launcher or inline code')
    return encoded


def check_list(checks):
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        raise ValueError('checks')
    names = set()
    for item in checks:
        if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str):
            raise ValueError('check')
        if not NAME.fullmatch(item[0]) or item[0] in names:
            raise ValueError('check name')
        check_argv(item[1])
        names.add(item[0])


def parse_check(text):
    name, separator, value = text.partition('=')
    if not separator or not NAME.fullmatch(name):
        raise ValueError('check name')
    argv = json.loads(value)
    check_argv(argv)
    return [name, argv]


def render_line(code, name, argv):
    return f'- {code}: {name} = {check_argv(argv)}\n'


# The section

def section_span(text):
    """(start, end) of the one real section, None when absent; ambiguity raises."""
    headings, fence = sf.split(text)
    indexes = [i for i, (_, title) in enumerate(headings) if title == HEADING]
    if fence is not None or len(indexes) > 1:
        raise ValueError('ambiguous section')
    if not indexes:
        return None
    index = indexes[0]
    return headings[index][0], headings[index + 1][0] if index + 1 < len(headings) else len(text)


def parse(text):
    """Return None when absent, else {code: [[name, argv], ...]} in stored order; any bad line raises."""
    span = section_span(text)
    if span is None:
        return None
    entries = {}
    for line in text[span[0]:span[1]].splitlines()[1:]:
        if not line.strip():
            continue
        match = LINE.fullmatch(line)
        if not match:
            raise ValueError('unknown line')
        argv = json.loads(match[3])
        if check_argv(argv) != match[3]:
            raise ValueError('argument form')
        checks = entries.setdefault(match[1], [])
        if any(name == match[2] for name, _ in checks) or len(checks) >= MAX_CHECKS:
            raise ValueError('duplicate or too many checks')
        checks.append([match[2], argv])
    return entries


def render(entries):
    if not entries:
        return ''
    lines = ''.join(render_line(code, name, argv) for code in sorted(entries) for name, argv in entries[code])
    return f'{HEADING}\n\n{lines}\n'


def transform(raw, code, checks):
    """Replace only this repository's lines; checks None removes them, and the section when it empties."""
    text = raw.decode('utf-8') if raw is not None else ''
    entries = parse(text) or {}
    if checks is None:
        entries.pop(code, None)
    else:
        check_list(checks)
        entries[code] = checks
    newline = '\r\n' if '\r\n' in text else '\n'
    section = render(entries).replace('\n', newline)
    span = section_span(text)
    if span is not None:
        result = text[:span[0]] + section + text[span[1]:]
    elif section:
        separator = newline * (2 if not text.endswith(newline) else 1) if text and not text.endswith(newline * 2) else ''
        result = text + separator + section
    else:
        result = text
    encoded = result.encode('utf-8')
    if len(encoded) > CAP:
        raise ValueError('host too large')
    return encoded


def checks_for(repository_code):
    """Ordered (name, argv) pairs and None, or an empty list and a reason: absent, invalid, unreadable or no entry.

    An invalid section counts as unset as a whole and is never repaired here.
    """
    if not isinstance(repository_code, str) or not CODE.fullmatch(repository_code):
        return [], 'invalid code'
    try:
        text = dr.read_data('host.md', CAP).decode('utf-8')
    except FileNotFoundError:
        return [], 'absent'
    except (OSError, ValueError, UnicodeError):
        return [], 'unreadable'
    try:
        entries = parse(text)
    except (ValueError, TypeError, RecursionError):
        return [], 'invalid'
    if entries is None:
        return [], 'absent'
    if repository_code not in entries:
        return [], 'no entry'
    return [(name, argv) for name, argv in entries[repository_code]], None


# Preview, digest, apply

def read_host(folder):
    raw, mode = cs.read_target(folder, 'host.md')
    if raw is not None and len(raw) > CAP:
        raise ValueError('host too large')
    return raw, mode


def repository(root):
    found = pp.find_root(root or os.getcwd())
    if found is None:
        raise ValueError('no repository')
    return pp.repository_code(found)


def preview(code, checks):
    if checks is not None:
        check_list(checks)
    root = dr.consent_root()
    if root is None:
        raise ValueError('invalid data root')
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw, mode = read_host(folder)
        transform(raw, code, checks)
        plan = {'code': code, 'checks': checks, 'root': str(root), 'created': time.time(),
                'sha256': cs.content_hash(raw), 'mode': mode, 'backup': cs.backup_name(folder, 'host.md')}
    value = cs.digest(plan)
    with dr.data_folder(STATE, create=True, private=True) as state:
        try:
            cs.read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, 'preview.json', json.dumps({'plan': plan, 'digest': value}).encode())
    print('Target: ' + str(root / 'host.md'))
    if checks is None:
        print(f'Remove every check of repository {code} from {HEADING}.')
    else:
        print(HEADING + ' entry for repository ' + code + ':')
        print(''.join(render_line(code, name, argv) for name, argv in checks), end='')
        print(PREVIEW_NOTICE)
    print('Backup: ' + str(root / plan['backup']))
    print('Digest: ' + value)
    print('Preview expires in 60 minutes; host configuration unchanged.')


def apply(value, yes):
    if not yes or not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{12,64}', value):
        raise ValueError('clear yes and at least 12 hex digits of the preview digest required')
    with dr.data_folder(STATE, private=True) as state:
        fcntl.flock(state, fcntl.LOCK_EX | fcntl.LOCK_NB)
        saved = json.loads(cs.read_plan(state))
        if not isinstance(saved, dict) or set(saved) != {'plan', 'digest'}:
            raise ValueError('invalid preview')
        plan = saved['plan']
        digest = cs.digest(plan)
        if saved['digest'] != digest or not digest.startswith(value):
            raise ValueError('digest mismatch; preview again')
        if not isinstance(plan, dict) or set(plan) != PLAN_KEYS or not isinstance(plan['code'], str) \
                or not CODE.fullmatch(plan['code']):
            raise ValueError('invalid plan')
        if plan['checks'] is not None:
            check_list(plan['checks'])
        if plan['root'] != str(dr.consent_root()):
            raise ValueError('data root changed; preview again')
        if type(plan['created']) not in (int, float) or not 0 <= time.time() - plan['created'] <= 3600:
            raise ValueError('preview expired; preview again')
        if not isinstance(plan['backup'], str) or not re.fullmatch(r'host\.md\.bak-\d{8}(?:-[1-9][0-9]*)?', plan['backup']):
            raise ValueError('invalid backup')
        with dr.root_folder() as folder:
            fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw, mode = read_host(folder)
            if cs.content_hash(raw) != plan['sha256'] or mode != plan['mode']:
                raise ValueError('host changed; preview again')
            result = transform(raw, plan['code'], plan['checks'])
            if result != (raw or b''):
                if raw is not None:
                    fd = os.open(plan['backup'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
                    with os.fdopen(fd, 'wb') as stream:
                        os.fchmod(stream.fileno(), mode)
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
                cs.write_target(folder, 'host.md', result, mode)
        os.unlink('preview.json', dir_fd=state)
        os.fsync(state)
    print('Checks section saved; no command was run.')


def show(root):
    code = repository(root)
    checks, reason = checks_for(code)
    if reason:
        print(f'Repository {code}: no checks ({reason}).')
        return 3 if reason in ('invalid', 'unreadable') else 0
    print(f'Repository {code}:')
    for name, argv in checks:
        print(f'{name} = {check_argv(argv)}')
    return 0


# Detection: read files only, never run them

def read_source(root_fd, relative, skipped):
    try:
        return pp.read_task(root_fd, relative, SOURCE_LIMIT)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        skipped.append({'where': relative, 'reason': 'unreadable, linked or too large'})
        return None


def unquote(value):
    """The text of a plainly quoted YAML scalar, else the value without a trailing comment; never raises."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        inner = value[1:-1]
        if value[0] == "'":
            return inner.replace("''", "'")
        try:
            decoded = json.loads(value)
        except ValueError:
            return inner
        return decoded if isinstance(decoded, str) else inner
    return re.sub(r'\s+#.*$', '', value)


def evidence_line(text):
    """One line fit to show: control and direction characters replaced, at most EVIDENCE_WIDTH characters."""
    return re.sub(r'[\x00-\x1f\x7f-\x9f​-‏ -‮⁦-⁩]', '?', text.strip())[:EVIDENCE_WIDTH]


RUN_KEY = re.compile(r'( *)(?:- +)?(run):(?:[ \t]+(.*))?')
JOB_KEY = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(?:#.*)?')
BLOCK = re.compile(r'[|>](?:[1-9]?[+-]?|[+-]?[1-9]?)[ \t]*(?:#.*)?')


def ci_runs(text):
    """Yield (job or None, first line) for each `run:` key under `jobs:`; parses nothing else and converts nothing."""
    lines = text.splitlines()
    in_jobs, job_indent, job = False, None, None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        indent = len(line) - len(line.lstrip(' '))
        if indent == 0:
            in_jobs = re.fullmatch(r'jobs:[ \t]*(?:#.*)?', stripped) is not None
            job_indent, job = None, None
            continue
        if not in_jobs:
            continue
        if job_indent is None or indent <= job_indent:
            job_indent = indent
            match = JOB_KEY.fullmatch(stripped)
            job = match[1] if match else None
            continue
        match = RUN_KEY.fullmatch(line)
        if not match:
            continue
        value = (match[3] or '').strip()
        if not value:
            continue  # a mapping such as defaults.run, or a plain scalar on later lines: not shown
        if BLOCK.fullmatch(value):
            column = match.start(2)
            first = next((item for item in lines[index + 1:] if item.strip()), '')
            if len(first) - len(first.lstrip(' ')) <= column:
                continue
            value = first
        else:
            value = unquote(value)
        shown = evidence_line(value)
        if shown:
            yield job, shown


def detect_workflows(root_fd, sources, ci, skipped):
    """List each workflow `run:` step's first line as evidence for the user; never turn one into a check."""
    folder = '.github/workflows'
    try:
        with _subdir(root_fd, folder) as fd:
            names = sorted(name for name in os.listdir(fd) if re.fullmatch(r'[A-Za-z0-9._-]{1,100}\.ya?ml', name))
    except (FileNotFoundError, NotADirectoryError):
        return
    except OSError:
        skipped.append({'where': folder, 'reason': 'unreadable or linked'})
        return
    for name in names[:MAX_WORKFLOWS]:
        relative = f'{folder}/{name}'
        text = read_source(root_fd, relative, skipped)
        if text is None:
            continue
        sources.append(relative)
        for job, line in ci_runs(text):
            if len(ci) >= MAX_EVIDENCE:
                return
            ci.append({'file': relative, 'job': job, 'line': line})


class _subdir:
    """Open a relative folder under root_fd without following symlinks."""
    def __init__(self, root_fd, relative):
        self.root_fd, self.parts, self.fd = root_fd, pp.safe_parts(relative), None

    def __enter__(self):
        fd = os.dup(self.root_fd)
        try:
            for part in self.parts:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                os.close(fd)
                fd = child
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd
        return fd

    def __exit__(self, *_):
        os.close(self.fd)


def exists(root_fd, name, folder=False):
    try:
        info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) if folder else stat.S_ISREG(info.st_mode)


def detect_package(root_fd, sources, checks, skipped):
    text = read_source(root_fd, 'package.json', skipped)
    if text is None:
        return
    sources.append('package.json')
    try:
        scripts = json.loads(text).get('scripts', {})
    except (ValueError, AttributeError):
        skipped.append({'where': 'package.json', 'reason': 'not valid JSON'})
        return
    if not isinstance(scripts, dict):
        skipped.append({'where': 'package.json', 'reason': 'scripts is not a map'})
        return
    manager = next((tool for lock, tool in LOCKFILES if exists(root_fd, lock)), 'npm')
    for name in PACKAGE_SCRIPTS:
        if isinstance(scripts.get(name), str):
            checks.append((f'{manager}-{name}', [manager, 'run', name]))


def _table(value):
    return value if isinstance(value, dict) else {}


def _strings(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def requirement_name(text):
    """The normalized distribution name a requirement string or a dependency key starts with."""
    match = re.match(r'\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)', text)
    return re.sub(r'[-_.]+', '-', match[1]).lower() if match else ''


def pyproject_declares_pytest(data):
    """True when pyproject.toml declares pytest as a dependency or configures it."""
    project, tool = _table(data.get('project')), _table(data.get('tool'))
    names = _strings(project.get('dependencies'))
    for groups in (_table(project.get('optional-dependencies')), _table(data.get('dependency-groups'))):
        for value in groups.values():
            names += _strings(value)
    poetry = _table(tool.get('poetry'))
    names += list(_table(poetry.get('dependencies')))
    for group in _table(poetry.get('group')).values():
        names += list(_table(_table(group).get('dependencies')))
    return isinstance(tool.get('pytest'), dict) or any(requirement_name(name) == 'pytest' for name in names)


def unittest_evidence(root_fd, skipped):
    """True when a test module under tests/ imports unittest; reads at most MAX_TEST_FILES files."""
    try:
        with _subdir(root_fd, 'tests') as fd:
            names = sorted(name for name in os.listdir(fd) if re.fullmatch(r'test[A-Za-z0-9_]{0,100}\.py', name))
    except OSError:
        return False
    for name in names[:MAX_TEST_FILES]:
        text = read_source(root_fd, f'tests/{name}', skipped)
        if text and re.search(r'^[ \t]*(?:import[ \t]+unittest\b|from[ \t]+unittest\b)', text, re.M):
            return True
    return False


def detect_python(root_fd, sources, checks, skipped):
    """pytest only when declared, unittest only from explicit evidence, else a skip that says so."""
    first, pytest = None, False
    text = read_source(root_fd, 'pyproject.toml', skipped)
    if text is not None:
        sources.append('pyproject.toml')
        first = 'pyproject.toml'
        try:
            import tomllib
            data = tomllib.loads(text)
        except ImportError:
            skipped.append({'where': 'pyproject.toml', 'reason': 'needs Python 3.11 or later to read'})
            data = None
        except ValueError:
            skipped.append({'where': 'pyproject.toml', 'reason': 'not valid TOML'})
            data = None
        pytest = isinstance(data, dict) and pyproject_declares_pytest(data)
    for name, section in (('pytest.ini', 'pytest'), ('setup.cfg', 'tool:pytest')):
        text = read_source(root_fd, name, skipped)
        if text is None:
            continue
        sources.append(name)
        first = first or name
        if re.search(r'^\[' + re.escape(section) + r'\][ \t]*$', text, re.M):
            pytest = True
    if first is None:
        return
    if pytest:
        checks.append(('pytest', ['python3', '-m', 'pytest']))
    elif unittest_evidence(root_fd, skipped):
        checks.append(('unittest', ['python3', '-m', 'unittest', 'discover', '-s', 'tests']))
    else:
        skipped.append({'where': first, 'reason': 'test runner not declared'})


def detect_makefile(root_fd, sources, checks, skipped):
    text = read_source(root_fd, 'Makefile', skipped)
    if text is None:
        return
    sources.append('Makefile')
    targets = set(re.findall(r'^(test|lint|check)\s*:(?![:=])', text, re.M))
    for name in MAKE_TARGETS:
        if name in targets:
            checks.append((f'make-{name}', ['make', name]))


def detect(root):
    found = pp.find_root(root or os.getcwd())
    if found is None:
        raise ValueError('no repository')
    sources, found_checks, skipped, ci = [], [], [], []
    with pp.open_dir(found) as root_fd:
        detect_workflows(root_fd, sources, ci, skipped)
        for reader in (detect_package, detect_python, detect_makefile):
            reader(root_fd, sources, found_checks, skipped)
    checks, names, seen = [], set(), []
    for name, argv in found_checks:
        if argv in seen or len(checks) >= MAX_CHECKS:
            continue
        try:
            check_argv(argv)
        except ValueError:
            reason = 'runs a shell, a launcher or inline code' if isinstance(argv, list) and argv \
                and isinstance(argv[0], str) and refused_program(argv) else 'not a valid argument array'
            skipped.append({'where': f'check {name}', 'reason': reason})
            continue
        unique, number = name, 1
        while unique in names:
            number += 1
            unique = f'{name[:29]}-{number}'
        names.add(unique)
        seen.append(argv)
        checks.append({'name': unique, 'argv': argv})
    return {'sources': sources, 'checks': checks, 'ci': ci, 'skipped': skipped}


def print_detected(result):
    for source in result['sources']:
        print('Source: ' + source)
    if not result['checks']:
        print('No checks found in the files read.')
    for item in result['checks']:
        print(f"Check: {item['name']} = {check_argv(item['argv'])}")
    for item in result['skipped']:
        print(f"Skipped: {item['where']}: {item['reason']}")
    if result['ci']:
        print(CI_HEADING)
        for item in result['ci']:
            job = f" (job {item['job']})" if item['job'] else ''
            print(f"  {item['file']}{job}: {item['line']}")
    print('Nothing was run.')


def main(argv=None):
    try:
        parser = cs.Parser(description=__doc__)
        commands = parser.add_subparsers(dest='action', required=True)
        found = commands.add_parser('detect')
        found.add_argument('--root')
        found.add_argument('--json', action='store_true')
        pre = commands.add_parser('preview')
        pre.add_argument('--root')
        pre.add_argument('--check', action='append', default=[], metavar='NAME=JSON_ARRAY')
        app = commands.add_parser('apply')
        app.add_argument('--yes', action='store_true')
        app.add_argument('--digest', required=True)
        for name in ('show', 'remove'):
            commands.add_parser(name).add_argument('--root')
        args = parser.parse_args(argv)
        if args.action == 'detect':
            result = detect(args.root)
            if args.json:
                print(json.dumps(result, separators=(',', ':')))
            else:
                print_detected(result)
            return 0
        if args.action == 'show':
            return show(args.root)
        if args.action == 'preview':
            checks = [parse_check(item) for item in args.check]
            preview(repository(args.root), checks)
        elif args.action == 'remove':
            preview(repository(args.root), None)
        else:
            apply(args.digest, args.yes)
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print('Checks setup refused: invalid arguments, shell string, unsafe or changed file, invalid Checks section, '
              'or stale preview; preview again.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
