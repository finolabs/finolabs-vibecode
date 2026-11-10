#!/usr/bin/env python3
"""Detect, preview and apply one repository's entry in the canonical host's Checks section and its local-receipt
mode, and install or remove the optional git pre-push hook; make no network call.

A check is a short name and a JSON argument array, never a shell string. Only this script writes `## Checks`.
Detection, the list and the mode run no command; the hook commands run only fixed git queries, with no shell,
to find where git reads hooks.
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
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import checks_list as cl
import compact_setup as cs
import project_progress as pp
import run_env
import setup_features as sf

CAP = sf.CAP
STATE = 'state/checks-setup'
HOOK_STATE = 'state/checks-hook'
HEADING = cl.HEADING
NAME, CODE = cl.NAME, cl.CODE
MAX_CHECKS, MAX_ARGV = cl.MAX_CHECKS, cl.MAX_ARGV
PLAN_KEYS = {'code', 'checks', 'receipt', 'root', 'created', 'sha256', 'mode', 'backup'}
HOOK_KEYS = {'action', 'repo', 'hooks', 'content', 'existing', 'ours', 'backup', 'root', 'created'}
HOOK_MARK = '# fnl-checks pre-push hook'
HOOK_LIMIT = 65536
SAFE_PATH = re.compile(r'/[A-Za-z0-9/._+@ -]{1,1023}')  # no quote, so the path is safe inside single quotes
REF = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/@{}^~-]{0,199}')
RECEIPT_NOTICE = ("A passing checks.py run of the whole list (never from a --changed run), on a clean working tree whose head "
                  "did not move, writes a receipt in the private state folder; merge_check.py then accepts it in place of "
                  "missing or failing hosted checks, only for that head and this exact list.\n"
                  "What could go wrong: the receipt is self-reported. It proves only that this machine ran the list at that "
                  "head, on this operating system, and it gives a reviewer nothing they can check. It is meant for a "
                  "repository one person works on.")
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


# The stored argument form and the reader live in checks_list.py, shared with fnl-checks and fnl-review-gate.

program_name = cl.program_name
refused_program = cl.refused_program
check_argv = cl.check_argv
check_list = cl.check_list
section_span = cl.section_span
parse = cl.parse
checks_for = cl.checks_for


class Said(ValueError):
    """A refusal whose fixed message is printed as is."""


def parse_check(text):
    name, separator, value = text.partition('=')
    if not separator:
        raise ValueError('check name')
    cl.check_name(name)
    argv = json.loads(value)
    check_argv(argv)
    return [name, argv]


def render_line(code, name, argv):
    return f'- {code}: {name} = {check_argv(argv)}\n'


# The section

def render(entries, receipts=()):
    if not entries:
        return ''
    lines = ''
    for code in sorted(entries):
        lines += ''.join(render_line(code, name, argv) for name, argv in entries[code])
        if code in receipts:
            lines += f'- {code}: {cl.RECEIPT_MODE} = on\n'
    return f'{HEADING}\n\n{lines}\n'


def stored(text, code):
    """This repository's stored list as [[name, argv], ...]; an absent or invalid section or no entry raises."""
    parsed = cl.parse_section(text)
    if parsed is None or code not in parsed[0]:
        raise Said('this repository has no stored checks; save a list first')
    return parsed[0][code]


def transform(raw, code, checks, receipt=None):
    """Replace only this repository's lines; checks None removes them and the mode, and the section when it empties.

    receipt True turns the local-receipt mode on, False turns it off, None keeps it as stored.
    """
    text = raw.decode('utf-8') if raw is not None else ''
    parsed = cl.parse_section(text)
    entries, receipts = parsed if parsed is not None else ({}, set())
    if checks is None:
        if receipt is not None:
            raise ValueError('mode without checks')
        entries.pop(code, None)
        receipts.discard(code)
    else:
        check_list(checks)
        entries[code] = checks
        if receipt is True:
            receipts.add(code)
        elif receipt is False:
            receipts.discard(code)
        elif receipt is not None:
            raise ValueError('mode')
    newline = '\r\n' if '\r\n' in text else '\n'
    section = render(entries, receipts).replace('\n', newline)
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


def preview(code, checks, receipt=None):
    """checks None removes the entry; receipt True or False changes only the mode and keeps the stored list."""
    if checks is not None:
        check_list(checks)
    root = dr.consent_root()
    if root is None:
        raise ValueError('invalid data root')
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw, mode = read_host(folder)
        if receipt is not None:
            checks = stored(raw.decode('utf-8') if raw is not None else '', code)
        transform(raw, code, checks, receipt)
        plan = {'code': code, 'checks': checks, 'receipt': receipt, 'root': str(root), 'created': time.time(),
                'sha256': cs.content_hash(raw), 'mode': mode, 'backup': cs.backup_name(folder, 'host.md')}
    value = cs.digest(plan)
    with dr.data_folder(STATE, create=True, private=True) as state:
        try:
            cs.read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, 'preview.json', json.dumps({'plan': plan, 'digest': value}).encode())
    print('Target: ' + str(root / 'host.md'))
    if receipt is True:
        print(f'Turn the local-receipt mode on for repository {code} ({HEADING} line '
              f'"- {code}: {cl.RECEIPT_MODE} = on").')
        print(RECEIPT_NOTICE)
    elif receipt is False:
        print(f'Turn the local-receipt mode off for repository {code}; its check list stays as stored.')
    elif checks is None:
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
        if plan['receipt'] not in (None, True, False) or (plan['checks'] is None and plan['receipt'] is not None):
            raise ValueError('invalid plan')
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
            result = transform(raw, plan['code'], plan['checks'], plan['receipt'])
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
    print('local receipt: ' + ('on' if cl.receipt_mode(code) else 'off'))
    return 0


# The pre-push hook: the user's own git hook, installed and removed with a preview, a digest and a backup

def git_query(root, *args):
    """(exit code, stdout) of one fixed read-only git query; no shell, an allowlisted environment."""
    done = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args], capture_output=True,
                          text=True, encoding='utf-8', timeout=30, check=False, env=run_env.environment())
    return done.returncode, done.stdout.strip()


def hooks_folder(root):
    """(repository root, resolved hooks folder, linked worktree) where git really reads hooks; refuses core.hooksPath."""
    found = pp.find_root(root or os.getcwd())
    if found is None:
        raise ValueError('no repository')
    code, value = git_query(found, 'config', '--get', 'core.hooksPath')
    if code == 0:
        raise Said('core.hooksPath is set for this repository; another hook manager owns its hooks. '
                   'The installer refuses and never changes that setting.')
    if code != 1:
        raise ValueError('git config failed')
    answers = []
    for query in (('--git-path', 'hooks'), ('--absolute-git-dir',), ('--git-common-dir',)):
        code, value = git_query(found, 'rev-parse', *query)
        if code or not value or '\n' in value:
            raise ValueError('git rev-parse failed')
        answers.append(Path(value) if os.path.isabs(value) else found / value)
    hooks, git_dir, common = (Path(os.path.realpath(path)) for path in answers)
    return found, hooks, git_dir != common


def open_hooks(hooks):
    fd = os.open(str(hooks), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        os.close(fd)
        raise Said('the hooks folder is not owned by you or is writable by others')
    return fd


def read_hook(fd):
    """The current pre-push hook's bytes, None when absent; a link or an unsafe file is refused."""
    try:
        info = os.stat('pre-push', dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise Said('pre-push is not a regular file; move it yourself first')
    return dr.read_file(fd, 'pre-push', HOOK_LIMIT)


def ours(raw):
    return raw is not None and raw.startswith(('#!/bin/sh\n' + HOOK_MARK).encode())


def checked_script(value):
    """An absolute, real, owner-only regular file named checks.py whose path needs no quoting."""
    path = str(value)
    if (not SAFE_PATH.fullmatch(path) or os.path.basename(path) != 'checks.py' or '/../' in path + '/'
            or os.path.realpath(path) != path):
        raise ValueError('checks script')
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError('checks script')
    return path


def hook_text(script, base):
    python = sys.executable
    if not SAFE_PATH.fullmatch(python or ''):
        raise ValueError('interpreter path')
    if base is not None and (not REF.fullmatch(base) or '..' in base):
        raise ValueError('base')
    return ('#!/bin/sh\n' + HOOK_MARK + ': runs the stored checks for the change before a push.\n'
            '# Installed by checks_setup.py hook install; remove it with checks_setup.py hook remove.\n'
            '# git push --no-verify skips it.\n'
            f"exec '{python}' -I '{script}' run --changed" + (f" --base '{base}'" if base else '') + '\n')


def hook_preview(root, action, script=None, base=None):
    data = dr.consent_root()
    if data is None:
        raise ValueError('invalid data root')
    found, hooks, linked = hooks_folder(root)
    content = hook_text(checked_script(script), base) if action == 'install' else None
    fd = open_hooks(hooks)
    try:
        existing = read_hook(fd)
        if action == 'remove' and existing is None:
            raise Said('there is no pre-push hook to remove')
        if action == 'remove' and not ours(existing):
            raise Said("the pre-push hook is not this plugin's; it is left alone")
        backup = cs.backup_name(fd, 'pre-push') if existing is not None else None
    finally:
        os.close(fd)
    plan = {'action': action, 'repo': str(found), 'hooks': str(hooks), 'content': content,
            'existing': cs.content_hash(existing), 'ours': ours(existing), 'backup': backup, 'root': str(data),
            'created': time.time()}
    value = cs.digest(plan)
    with dr.data_folder(HOOK_STATE, create=True, private=True) as state:
        dr.atomic_write(state, 'preview.json', json.dumps({'plan': plan, 'digest': value}).encode())
    print('Hooks folder: ' + str(hooks))
    print('Git reads this folder for every worktree of this repository, so the hook applies to all of them.')
    if linked:
        print('This checkout is a linked worktree; the folder above belongs to the main repository.')
    if existing is None:
        print('Existing pre-push hook: none')
    elif ours(existing):
        print("Existing pre-push hook: this plugin's hook; it is backed up and replaced" if action == 'install'
              else "Existing pre-push hook: this plugin's hook; it is backed up and removed")
    else:
        print('Existing pre-push hook: a different hook; apply needs --replace-existing, and a backup is kept')
    if content is not None:
        print('Hook script:')
        print(content, end='')
        print('Before every push it runs checks.py run --changed: the stored checks the change touches. '
              'git push --no-verify skips it.')
    else:
        print('Remove the pre-push hook; git push then runs no checks.')
    if backup:
        print('Backup: ' + str(hooks / backup))
    print('Digest: ' + value)
    print('Preview expires in 60 minutes; nothing changed.')


def hook_apply(value, yes, replace):
    if not yes or not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{12,64}', value):
        raise ValueError('clear yes and at least 12 hex digits of the preview digest required')
    with dr.data_folder(HOOK_STATE, private=True) as state:
        fcntl.flock(state, fcntl.LOCK_EX | fcntl.LOCK_NB)
        saved = json.loads(cs.read_plan(state))
        if not isinstance(saved, dict) or set(saved) != {'plan', 'digest'}:
            raise ValueError('invalid preview')
        plan = saved['plan']
        digest = cs.digest(plan)
        if saved['digest'] != digest or not digest.startswith(value):
            raise ValueError('digest mismatch; preview again')
        if not isinstance(plan, dict) or set(plan) != HOOK_KEYS or plan['action'] not in ('install', 'remove'):
            raise ValueError('invalid plan')
        if plan['root'] != str(dr.consent_root()):
            raise ValueError('data root changed; preview again')
        if type(plan['created']) not in (int, float) or not 0 <= time.time() - plan['created'] <= 3600:
            raise ValueError('preview expired; preview again')
        content = plan['content']
        if plan['action'] == 'install':
            if not isinstance(content, str) or len(content) > 4096 or not ours(content.encode()):
                raise ValueError('invalid plan')
        elif content is not None:
            raise ValueError('invalid plan')
        backup = plan['backup']
        if backup is not None and (not isinstance(backup, str)
                                   or not re.fullmatch(r'pre-push\.bak-\d{8}(?:-[1-9][0-9]*)?', backup)):
            raise ValueError('invalid backup')
        found, hooks, _ = hooks_folder(plan['repo'])
        if str(hooks) != plan['hooks']:
            raise ValueError('hooks folder changed; preview again')
        fd = open_hooks(hooks)
        try:
            existing = read_hook(fd)
            if cs.content_hash(existing) != plan['existing'] or ours(existing) != plan['ours']:
                raise Said('the pre-push hook changed since the preview; preview again')
            if plan['action'] == 'install' and existing is not None and not ours(existing) and not replace:
                raise Said('a different pre-push hook exists; it is replaced only with --replace-existing')
            if existing is not None:
                if backup is None:
                    raise ValueError('invalid backup')
                info = os.stat('pre-push', dir_fd=fd, follow_symlinks=False)
                out = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                with os.fdopen(out, 'wb') as stream:
                    os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode) & 0o755)
                    stream.write(existing)
                    stream.flush()
                    os.fsync(stream.fileno())

            def still_previewed():
                # Re-read right before the replace or removal; a writer that ignores this between the re-read and
                # the change remains a residual race (references/features/checks.md).
                try:
                    current = read_hook(fd)
                except (Said, OSError, ValueError):
                    current = b''
                if current is None or cs.content_hash(current) != plan['existing']:
                    try:
                        os.unlink(backup, dir_fd=fd)  # the backup this apply just wrote; the hook is left alone
                    except FileNotFoundError:
                        pass
                    raise Said('the pre-push hook changed since the preview; preview again')

            if plan['action'] == 'install':
                temporary = '.pre-push-' + os.urandom(8).hex()
                out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                try:
                    with os.fdopen(out, 'wb') as stream:
                        stream.write(content.encode())
                        os.fchmod(stream.fileno(), 0o755)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if existing is None:
                        # Publish without clobbering: link fails when a hook appeared since the preview.
                        try:
                            os.link(temporary, 'pre-push', src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
                        except FileExistsError:
                            raise Said('a pre-push hook appeared since the preview; it is left alone. '
                                       'Preview again.') from None
                        os.unlink(temporary, dir_fd=fd)
                    else:
                        still_previewed()
                        os.replace(temporary, 'pre-push', src_dir_fd=fd, dst_dir_fd=fd)
                except BaseException:
                    try:
                        os.unlink(temporary, dir_fd=fd)
                    except FileNotFoundError:
                        pass
                    raise
            else:
                still_previewed()
                os.unlink('pre-push', dir_fd=fd)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.unlink('preview.json', dir_fd=state)
        os.fsync(state)
    print('Pre-push hook installed; git push --no-verify skips it.' if plan['action'] == 'install'
          else 'Pre-push hook removed.')


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
        mode = commands.add_parser('receipt')
        mode.add_argument('state', choices=('on', 'off'))
        mode.add_argument('--root')
        hook = commands.add_parser('hook').add_subparsers(dest='hook', required=True)
        install = hook.add_parser('install')
        install.add_argument('--root')
        install.add_argument('--checks-script', required=True)
        install.add_argument('--base')
        hook.add_parser('remove').add_argument('--root')
        done = hook.add_parser('apply')
        done.add_argument('--yes', action='store_true')
        done.add_argument('--replace-existing', action='store_true')
        done.add_argument('--digest', required=True)
        args = parser.parse_args(argv)
        if args.action == 'hook':
            if args.hook == 'install':
                hook_preview(args.root, 'install', args.checks_script, args.base)
            elif args.hook == 'remove':
                hook_preview(args.root, 'remove')
            else:
                hook_apply(args.digest, args.yes, args.replace_existing)
            return 0
        if args.action == 'receipt':
            preview(repository(args.root), None, args.state == 'on')
            return 0
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
    except Said as error:
        print(f'Checks setup refused: {error}', file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError,
            subprocess.SubprocessError):
        print('Checks setup refused: invalid arguments, shell string, unsafe or changed file, invalid Checks section, '
              'or stale preview; preview again.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
