#!/usr/bin/env python3
"""Read advisory parallel capacity from canonical local config and ledger only."""

import argparse
from contextlib import contextmanager
import hashlib
import os
import stat
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root as dr

FAMILIES = ('claude', 'codex', 'antigravity')
AGENTS = {'claude': 'claude', 'claude-session': 'claude', 'subagent': 'claude',
          'codex': 'codex', 'antigravity': 'antigravity'}
HOST_LIMIT = 262144
LEDGER_LIMIT = 4 * 1024 * 1024
DEFAULT_LIMIT = 5


INSTRUCTION_FILES = ('CLAUDE.MD', 'CLAUDE.LOCAL.MD', 'AGENTS.MD', 'AGENTS.OVERRIDE.MD', 'GEMINI.MD',
                     'COPILOT-INSTRUCTIONS.MD', 'CONVENTIONS.MD', '.CURSORRULES', '.WINDSURFRULES', '.CLINERULES')

# Keep repository identity and strict settings in parity with project_progress.
def host_section(text, title="Project progress"):
    """Return authoritative section bounds, ignoring fenced examples; ambiguity fails closed."""
    headings, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None and re.match(r'^#{1,2} ', line):
            headings.append((offset, offset + len(line), line.strip()))
        offset += len(line)
    indexes = [i for i, (_, _, heading) in enumerate(headings) if heading == '## ' + title]
    if fence is not None or len(indexes) > 1:
        raise ValueError('ambiguous host')
    if not indexes:
        return len(text), len(text), len(text)
    index = indexes[0]
    start, body, _ = headings[index]
    end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
    return start, body, end


LABEL = re.compile(r'[A-Za-z0-9 ._-]{1,40}')


def repository_code(root):
    """Use the metrics identity for linked worktrees, without running git."""
    identity = root
    try:
        with open_dir(root) as fd:
            link = read_metadata(fd, '.git').strip()
        if len(link) <= 4096 and link.startswith('gitdir:'):
            gitdir = Path(os.path.abspath(root / link[len('gitdir:'):].strip()))
            with open_dir(gitdir) as fd:
                common = read_metadata(fd, 'commondir').strip()
            if len(common) <= 4096 and common:
                shared = Path(os.path.abspath(gitdir / common))
                # Refuse symlinked metadata ancestors just like the project reader.
                with open_dir(shared):
                    identity = shared.parent if shared.name == '.git' else shared
    except (OSError, ValueError):
        pass
    return hashlib.sha256(str(identity).encode('utf-8')).hexdigest()[:8]


def valid_setting(key, value):
    if not isinstance(value, str):
        return False
    if key == 'parallel':
        return bool(re.fullmatch(r'[0-9]{1,2}', value) and 1 <= int(value) <= 32)
    if key == 'parallel-caps':
        seen = set()
        for item in value.split(','):
            match = re.fullmatch(r'(claude|codex|antigravity)=([0-9]{1,2})', item.strip())
            if not match or not 1 <= int(match[2]) <= 32 or match[1] in seen:
                return False
            seen.add(match[1])
        return True
    if key == 'ledger':
        return bool(LABEL.fullmatch(value) and value.strip())
    if key == 'tasks':
        return bool(re.fullmatch(r'[A-Za-z0-9._/-]{1,120}', value) and value.endswith('.md')
                    and all(part not in ('', '.', '..') for part in value.split('/'))
                    and value.split('/')[:2] != ['specs', 'archive']
                    and value.split('/')[-1].upper() not in INSTRUCTION_FILES)
    return False


def project_settings(text):
    """One malformed entry invalidates the entire section, never just that key."""
    _, body, end = host_section(text, 'Project settings')
    entries = {}
    lines = [line for line in text[body:end].splitlines() if line.strip()]
    if len(lines) > 100:
        raise ValueError('invalid project settings')
    for line in lines:
        match = re.fullmatch(r'- ([0-9a-f]{8}) (ledger|tasks|parallel|parallel-caps): (.*)', line)
        if not match or not valid_setting(match[2], match[3]) or (match[1], match[2]) in entries:
            raise ValueError('invalid project settings')
        entries[(match[1], match[2])] = match[3]
    return entries


@contextmanager
def open_dir(path):
    """Open every absolute component without following symlinks, including ancestors."""
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def find_root(cwd):
    start = Path(os.path.abspath(cwd))
    for depth, folder in enumerate((start, *start.parents)):
        if depth >= 20:
            break
        try:
            with open_dir(folder) as fd:
                try:
                    info = os.stat('.git', dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode):
                    return folder
        except OSError:
            return None
    return None


def read_metadata(root_fd, name):
    """Read .git/commondir with project_progress's bounded, owned-file rules."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
    try:
        info = os.fstat(fd)
        limit = 512 * 1024
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
            raise ValueError('invalid repository metadata')
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - size))
            if not chunk:
                return b''.join(chunks).decode('utf-8', 'replace')
            chunks.append(chunk)
            size += len(chunk)
        raise ValueError('invalid repository metadata')
    finally:
        os.close(fd)


def legacy_limits(text):
    """Detect the retired section, ignoring fenced examples and its contents."""
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None and line.strip() == '## Limits':
            return True
    return False


def parse_config(text, root=None):
    """Project settings are strict; absent settings use five with no caps."""
    entries = project_settings(text)
    code = repository_code(root) if root is not None else None
    total = entries.get((code, 'parallel'))
    limit = int(total) if total is not None else DEFAULT_LIMIT
    caps = {family: None for family in FAMILIES}
    value = entries.get((code, 'parallel-caps'))
    if value is not None:
        for item in value.split(','):
            family, count = item.strip().split('=')
            if int(count) > limit:
                raise ValueError('invalid cap')
            caps[family] = int(count)
    scope = None if root is None else dict(code=code, project=entries.get((code, 'ledger'), root.name))
    return dict(limit=limit, caps=caps, source='project settings' if total is not None else 'default',
                scope=scope, legacy_limits=legacy_limits(text))


def config(repo=None):
    if dr.consent_root() is None:
        raise ValueError('invalid root')
    try:
        text = dr.read_data('host.md', HOST_LIMIT).decode('utf-8')
    except FileNotFoundError:
        text = ''
    return parse_config(text, find_root(os.getcwd() if repo is None else repo))


def _stale(record, now):
    """A start older than its hard cap (budget plus a third, at least 10 minutes) is stale; unknown stays counted."""
    budget, started = record.get('budget_min'), record.get('ts')
    if type(budget) is not int or budget <= 0 or not isinstance(started, str):
        return False
    try:
        begun = datetime.fromisoformat(started)
    except ValueError:
        return False
    if begun.tzinfo is None:
        return False
    return (now - begun).total_seconds() / 60 > max(budget * 4 / 3, budget + 10)


def open_counts(raw, now=None, stale=None, scope=None, other=None):
    """Counts of open dispatches per family; `stale` (a dict) receives the per-family counts of stale ones left out."""
    now = now or datetime.now(timezone.utc)
    starts, finishes, records = {}, set(), {}
    for line in raw.decode('utf-8').splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (not isinstance(record, dict) or not isinstance(record.get('id'), str)
                or not record['id'] or record.get('event') not in ('start', 'finish')):
            raise ValueError('invalid ledger')
        identity = record['id']
        if record['event'] == 'finish':
            finishes.add(identity)
        else:
            agent = record.get('agent')
            if not isinstance(agent, str) or agent not in AGENTS:
                raise ValueError('invalid agent')
            family = AGENTS[agent]
            if identity in starts and (starts[identity] != family or
                    records[identity].get('project') != record.get('project')):
                raise ValueError('ambiguous start')
            starts[identity] = family
            records.setdefault(identity, record)
    counts = {family: 0 for family in FAMILIES}
    for identity in starts.keys() - finishes:
        matches = scope is None or (scope['project'] is not None and records[identity].get('project') == scope['project'])
        if _stale(records[identity], now):
            if stale is not None and matches:
                stale[starts[identity]] = stale.get(starts[identity], 0) + 1
            continue
        if matches:
            counts[starts[identity]] += 1
        elif other is not None:
            other['open'] = other.get('open', 0) + 1
    return counts


def status(repo=None):
    settings = config(repo)
    try:
        raw = dr.read_data('ledger.jsonl', LEDGER_LIMIT)
    except FileNotFoundError:
        raw = b''
    stale, other = {}, {}
    counts = open_counts(raw, stale=stale, scope=settings['scope'] or {'project': None}, other=other)
    opened = sum(counts.values())
    return dict(limit=settings['limit'], open=opened, stale=sum(stale.values()),
                free=max(0, settings['limit'] - opened),
                families={family: dict(open=counts[family], cap=settings['caps'][family],
                    free=None if settings['caps'][family] is None else max(0, settings['caps'][family] - counts[family]))
                    for family in FAMILIES}, source=settings['source'],
                scope=settings['scope'], other_projects=other.get('open', 0))


def fits(state, family, count=1):
    available = state['families'][family]['free']
    return count <= state['free'] and (available is None or count <= available)


def summary(repo=None):
    """Fixed words and integers only, including the default source in hook output."""
    try:
        state = status(repo)
        parts = []
        for family in FAMILIES:
            row = state['families'][family]
            parts.append(f"{family} {row['open']} open" +
                         (f" of cap {row['cap']}" if row['cap'] is not None else ''))
        tail = f"; {state['stale']} stale not counted" if state['stale'] else ''
        return f"{state['free']} free of {state['limit']} (" + ', '.join(parts) + f"; {state['source']}{tail})"
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return 'unknown'


def positive_count(value):
    if len(value) > 64 or not re.fullmatch(r'[0-9]+', value) or int(value) < 1:
        raise argparse.ArgumentTypeError('count must be a positive integer of at most 64 digits')
    return int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'check-config', 'check'):
        command = commands.add_parser(name)
        command.add_argument('--repo', type=Path)
        if name == 'check':
            check = command
    check.add_argument('--family', choices=FAMILIES, required=True)
    check.add_argument('--count', type=positive_count, default=1)
    args = parser.parse_args(argv)
    try:
        if args.command == 'check-config':
            settings = config(args.repo)
            print(json.dumps({key: settings[key] for key in ('limit', 'caps', 'source', 'legacy_limits')}))
            return 0 if settings['source'] == 'project settings' else 3
        state = status(args.repo)
        if args.command == 'status':
            print(json.dumps(state))
            return 0
        available = fits(state, args.family, args.count)
        print('Parallel slots: available' if available else 'Parallel slots: full')
        return 0 if available else 3
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print('Parallel slots: unknown' if args.command == 'check' else 'unknown')
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
