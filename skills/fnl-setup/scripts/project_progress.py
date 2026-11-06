#!/usr/bin/env python3
"""Bounded local task metadata. Project text is transient, never dashboard data."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import sys
import threading
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

LIMIT = 512 * 1024
SECONDS = 1
TASK = re.compile(r'(?<![A-Za-z0-9])T([0-9]{1,4})(?![A-Za-z0-9])')
STORY = re.compile(r'(?<![A-Za-z0-9])US[0-9]{1,3}(?![A-Za-z0-9])')
FEATURE = re.compile(r'(?<![A-Za-z0-9])[0-9]{3}(?![A-Za-z0-9])')
RANGE = re.compile(r'(?<![A-Za-z0-9])T([0-9]{1,4})-T([0-9]{1,4})(?![A-Za-z0-9])')
TOKEN = re.compile(r'[A-Za-z0-9._-]{1,40}')
IDENT = re.compile(r'[A-Za-z0-9_-]{1,80}')
AGENTS = ('claude', 'claude-session', 'codex', 'antigravity', 'subagent')
HOSTS = ('claude', 'codex', 'antigravity')
OUTCOMES = ('accepted', 'rejected', 'timeout', 'stalled', 'error', 'blocked', 'needs-permission', 'quota', 'cancelled')
NOTICE = ('Project progress now reads this repository\'s task list and the ledger; nothing leaves your machine; '
          'turn off with Project progress: off in host.md under ## Project progress, or FNL_PROGRESS=off.')


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
            link = read_task(fd, '.git').strip()
        if len(link) <= 4096 and link.startswith('gitdir:'):
            gitdir = Path(os.path.abspath(root / link[len('gitdir:'):].strip()))
            with open_dir(gitdir) as fd:
                common = read_task(fd, 'commondir').strip()
            if len(common) <= 4096 and common:
                shared = Path(os.path.abspath(gitdir / common))
                # Refuse symlinked metadata ancestors just like the project reader.
                with open_dir(shared):
                    identity = shared.parent if shared.name == '.git' else shared
    except (OSError, ValueError):
        pass
    return hashlib.sha256(str(identity).encode('utf-8')).hexdigest()[:8]


def project_labels(text):
    _, body, end = host_section(text, 'Project labels')
    labels = {}
    for line in text[body:end].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'- ([0-9a-f]{8}): ([A-Za-z0-9 ._-]{1,40})', line)
        if not match or match[1] in labels or not match[2].strip():
            raise ValueError('ambiguous labels')
        labels[match[1]] = match[2]
    return labels


def registered_projects(folder=None):
    """Read a bounded closed code-to-name map; unsafe or malformed state names nothing."""
    try:
        raw = dr.read_file(folder, 'projects.json', 8192) if folder is not None else dr.read_data('state/projects.json', 8192)
        names = json.loads(raw)
        if (not isinstance(names, dict) or len(names) > 50 or any(
                not re.fullmatch(r'[0-9a-f]{8}', code) or not isinstance(name, str)
                or not LABEL.fullmatch(name) or not name.strip()
                for code, name in names.items())):
            return {}
        return names
    except (OSError, ValueError, UnicodeError):
        return {}


def register_here(cwd):
    """Caller requires consent and an explicit status invocation, never a hook."""
    root = find_root(cwd)
    if root is None:
        return
    name = re.sub(r'[^A-Za-z0-9 ._-]', '-', root.name).strip()[:40].strip()
    if not name:
        return
    code = repository_code(root)
    try:
        with dr.data_folder('state', create=True, private=True) as folder:
            fcntl.flock(folder, fcntl.LOCK_EX)
            names = registered_projects(folder)
            if code not in names and len(names) >= 50:
                return
            names[code] = name
            dr.atomic_write(folder, 'projects.json', json.dumps(names, sort_keys=True).encode('ascii'))
    except (OSError, ValueError):
        return


def set_label(cwd, label):
    if not isinstance(label, str) or not LABEL.fullmatch(label) or not label.strip():
        raise ValueError('invalid label')
    root = find_root(cwd)
    if root is None:
        raise ValueError('no repository')
    code = repository_code(root)
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        text = dr.read_file(folder, 'host.md', 262144).decode('utf-8')
        labels = project_labels(text)
        labels[code] = label
        start, _, end = host_section(text, 'Project labels')
        newline = '\r\n' if '\r\n' in text else '\n'
        section = '## Project labels\n\n' + ''.join('- ' + k + ': ' + v + '\n' for k, v in sorted(labels.items())) + '\n'
        text = text[:start] + (newline if start == end and text and not text.endswith(newline * 2) else '') + section.replace('\n', newline) + text[end:]
        raw = text.encode('utf-8')
        if len(raw) > 262144:
            raise ValueError('host cap')
        dr.atomic_write(folder, 'host.md', raw)
    return label


def priorities(text):
    """Keep a priority number only; no part of the heading text escapes."""
    values, seen = {}, set()
    for line in text.splitlines():
        if len(line) > 4096:
            continue
        match = re.match(r'^#{1,6} User Story ([0-9]{1,3})(?: \(P([1-9])\)(?:[ \t].*)?| - .{0,4000}\(Priority: P([1-9])\))$', line)
        if match:
            story = 'US' + str(int(match[1]))
            values[story] = None if story in seen else int(match[2] or match[3])
            seen.add(story)
    return values


def config():
    if os.environ.get('FNL_PROGRESS', '').lower() == 'off':
        return None
    try:
        text = dr.read_data('host.md', 262144).decode('utf-8')
        _, body, end = host_section(text)
        values = {}
        for line in text[body:end].splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r'(?:- )?(Project progress|Task file|Ledger project): (.+)', line)
            if not match or match[1] in values:
                return None
            values[match[1]] = match[2]
        if values.get('Project progress', 'on') != 'on':
            return None
        return values
    except (OSError, ValueError, UnicodeError):
        return None


def enabled():
    return config() is not None


def configure(choice, yes=False, dry_run=False):
    """Write only the preference in our canonical host section, with the snapshot writer's lock."""
    if choice not in ('on', 'off') or (not yes and not dry_run):
        raise ValueError('confirmation required')
    section = '## Project progress\n\n- Project progress: ' + choice + '\n\n'
    if dry_run:
        return section
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            text = dr.read_file(folder, 'host.md', 262144).decode('utf-8')
        except FileNotFoundError:
            text = ''
        start, body, end = host_section(text)
        newline = '\r\n' if '\r\n' in text else '\n'
        content = text[body:end]
        matches = re.findall(r'^(?:- )?Project progress:.*$', content, re.M)
        if len(matches) > 1:
            raise ValueError('ambiguous host')
        if start == end:
            text += (newline * 2 if text and not text.endswith(newline) else newline if text and not text.endswith(newline * 2) else '')
            text += section.replace('\n', newline)
        else:
            replacement = '- Project progress: ' + choice
            if matches:
                content = re.sub(r'^(?:- )?Project progress:[^\r\n]*', replacement, content, count=1, flags=re.M)
            else:
                content = newline + replacement + newline + content
            text = text[:body] + content + text[end:]
        raw = text.encode('utf-8')
        if len(raw) > 262144:
            raise ValueError('host cap')
        dr.atomic_write(folder, 'host.md', raw)
    return section


class ProgressTimeout(Exception):
    pass


@contextmanager
def budget():
    """A real wall timer interrupts even a stalled read; unavailable timers mean no scan.

    Do not replace another caller's alarm. Refresh runs on its CLI's main thread.
    """
    if (not hasattr(signal, 'setitimer') or threading.current_thread() is not threading.main_thread()
            or signal.getitimer(signal.ITIMER_REAL)[0]):
        raise ProgressTimeout()
    def expired(*_):
        raise ProgressTimeout()
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


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


def safe_parts(relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('unsafe task path')
    return path.parts


def read_task(root_fd, relative, limit=LIMIT):
    parts = safe_parts(relative)
    fd = os.dup(root_fd)
    try:
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(parts) - 1:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
            raise ValueError('task file skipped')
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - size))
            if not chunk:
                return b''.join(chunks).decode('utf-8', 'replace')
            chunks.append(chunk)
            size += len(chunk)
        raise ValueError('task file skipped')
    finally:
        os.close(fd)


def parse(text, feature):
    tasks, phase, phase_story, phase_priority, seen = [], None, None, None, set()
    story_priorities = {}
    for line in text.splitlines():
        if len(line) > 4096:
            continue
        heading = re.match(r'^#{2,3} Phase ([0-9]{1,2})\b', line)
        if heading:
            phase = int(heading[1])
            story_heading = re.search(r'\bUser Story ([0-9]{1,3})\b', line)
            priority = re.search(r'\(P([1-9])\)', line)
            phase_story = 'US' + str(int(story_heading[1])) if story_heading else None
            phase_priority = int(priority[1]) if priority else None
            if phase_story:
                story_priorities[phase_story] = phase_priority
        box = re.match(r'^\s*- \[( |x|X)\] ', line)
        if not box:
            continue
        # Include lookahead beyond the window so a cut token cannot become a shorter id.
        prefix = line[box.end():box.end() + 85]
        ident, story = TASK.search(prefix), STORY.search(prefix)
        if not ident or ident.end() > 80 or int(ident[1]) in seen:
            continue
        seen.add(int(ident[1]))
        tasks.append({'id': ident[0], 'story': story[0] if story and story.end() <= 80 else phase_story, 'phase': phase,
                      'state': 'done' if box[1] != ' ' else 'todo', 'runs': [], 'sessions': []})
        if len(tasks) == 200:
            break
    def counts(key):
        values = sorted({r[key] for r in tasks if r[key] is not None})
        return [{key: value, 'done': sum(r['state'] == 'done' for r in tasks if r[key] == value),
                 'total': sum(r[key] == value for r in tasks)} for value in values]
    return {'feature': feature, 'tasks': tasks, 'total': len(tasks),
            'done': sum(r['state'] == 'done' for r in tasks), 'phases': counts('phase'),
            'stories': [dict(row, priority=story_priorities[row['story']]) if row['story'] in story_priorities else row
                        for row in counts('story')]}


# Closed metadata only: document text, names and links never leave this reader.
SOURCES = ('speckit', 'checkbox', 'docs/specs', 'docs/spec', 'specs', 'ledger', 'none')
STAGES = ('spec', 'plan', 'design', 'tasks', 'verify', 'review', 'ship', 'packages', 'work')
STATES = ('done', 'active', 'todo', 'unknown', 'deferred', 'needs-attention')
HINTS = ('draft', 'accepted', 'done', 'active', 'deferred', 'unknown')
DOC_LIMIT = 64 * 1024


def status_state(text):
    """Specific deferral/ongoing phrases precede generic completion words."""
    text = text.lower()
    if re.search(r'\b(?:deferred|moved to)\b', text):
        return 'deferred'
    if re.search(r'\b(?:in progress|in review|building|running locally|no pull request yet)\b', text):
        return 'active'
    if re.search(r'\b(?:implemented|merged|released|shipped|accepted|done)\b', text):
        return 'done'
    return 'unknown'


def status_line(text):
    return next((m[1] for line in text.splitlines() if len(line) <= 4096
                 and (m := re.match(r'^\s*(?:\*\*)?Status(?:\*\*)?:(?:\*\*)?\s*(.*)$', line, re.I))), '')


def stage(name, state, done=0, total=0):
    return dict(stage=name, state=state, done=done, total=total)


def directory_entries(fd, relative, skipped):
    """Bound enumeration and refuse links at every directory component."""
    child = os.dup(fd)
    try:
        for part in safe_parts(relative):
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=child)
            os.close(child)
            child = new
        entries = []
        with os.scandir(child) as scan:
            for entry in scan:
                if len(entries) == 200:
                    skipped.append('entry limit')
                    break
                entries.append((entry.name, entry.is_dir(follow_symlinks=False), entry.is_file(follow_symlinks=False)))
        return sorted(entries)
    except FileNotFoundError:
        return []
    except OSError:
        skipped.append('task file skipped')
        return []
    finally:
        os.close(child)


def metadata_item(ordinal, state='unknown'):
    return dict(ordinal=ordinal, state=state, tasks=[], stories=[], phases=[], total=1,
                done=int(state == 'done'), stages=[stage('spec', state, int(state == 'done'), 1)])


def table_rows(text):
    for line in text.splitlines():
        if len(line) <= 4096 and line.strip().startswith('|'):
            yield [cell.strip() for cell in line.strip().strip('|').split('|')]


def package_cells(text):
    """Only package tables, not numeric schedules elsewhere in release documents."""
    in_packages = False
    for line in text.splitlines():
        if len(line) > 4096 or not line.strip().startswith('|'):
            in_packages = False
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) < 3:
            in_packages = False
            continue
        if cells[0] == '#' and re.fullmatch(r'Package', cells[1], re.I):
            in_packages = True
        elif in_packages and cells[0].isdigit():
            yield cells
        elif not all(re.fullmatch(r':?-+:?', cell.replace(' ', '')) for cell in cells):
            in_packages = False


def package_rows(text, remaining):
    released = bool(re.search(r'\breleased\b', status_line(text), re.I))
    rows = []
    for cells in package_cells(text):
        if len(rows) >= remaining:
            break
        state = 'done' if released else status_state(' '.join(cells))
        rows.append(dict(ordinal=int(cells[0]) if len(cells[0]) <= 6 else len(rows) + 1, state=state))
    return rows


def repository_documents(fd, skipped):
    """All candidate indexes precede loose docs; bounded links enrich metadata."""
    directories = ('docs/specs', 'docs/spec', 'specs')
    listings = {directory: [name for name, _, regular in directory_entries(fd, directory, skipped)
                           if regular and name.lower().endswith('.md')] for directory in directories}
    def read(directory, name):
        try:
            return read_task(fd, directory + '/' + name, DOC_LIMIT)
        except (OSError, ValueError):
            skipped.append('spec file skipped')
            return None
    indexes = {}
    selected = None
    for directory in directories:
        if 'index.md' not in listings[directory]:
            continue
        text = read(directory, 'index.md')
        indexes[directory] = text
        if text and any(index_link(cells) for cells in table_rows(text)):
            selected = directory
            break
    if selected is None:
        selected = next((d for d in directories if any(n != 'index.md' for n in listings[d])), None)
    if selected is None:
        return 'none', 'none', []
    names = [n for n in listings[selected] if n != 'index.md']
    documents = {}
    for name in names[:40]:
        text = read(selected, name)
        if text is not None:
            documents[name] = text
    if len(names) > 40:
        skipped.append('file limit')
    merged = set()
    for text in documents.values():
        released = bool(re.search(r'\breleased\b', status_line(text), re.I))
        for cells in package_cells(text):
            if released or status_state(' '.join(cells)) == 'done':
                merged.update(re.findall(r'\]\(([^()\s]+\.md)\)', ' '.join(cells)))
    items, remaining = [], 80
    for cells in table_rows(indexes.get(selected) or ''):
        name = index_link(cells)
        if name is None:
            continue
        if len(items) >= 40:
            skipped.append('file limit')
            break
        text = documents.get(name, '')
        own = status_state(status_line(text))
        state = 'done' if name in merged else own if own != 'unknown' else status_state(cells[1])
        item = metadata_item(len(items) + 1, state)
        packages = package_rows(text, remaining)
        remaining -= len(packages)
        if packages:
            add_packages(item, packages)
        items.append(item)
    if items:
        return selected, 'index', items
    for name, text in documents.items():
        item = metadata_item(len(items) + 1, 'done' if name in merged else status_state(status_line(text)))
        packages = package_rows(text, remaining)
        remaining -= len(packages)
        if packages:
            add_packages(item, packages)
        items.append(item)
    return (selected, 'status', items) if items else ('none', 'none', [])


def index_link(cells):
    if len(cells) < 2:
        return None
    match = re.search(r'\]\(([^()\s]+\.md)\)', cells[0])
    if not match or '/' in match[1] or match[1] in ('.', '..', 'index.md'):
        return None
    return match[1]


def add_packages(item, packages):
    done = sum(row['state'] == 'done' for row in packages)
    state = ('done' if done == len(packages) else 'active' if any(row['state'] == 'active' for row in packages) else
             'deferred' if all(row['state'] in ('done', 'deferred') for row in packages) else 'active' if done else 'unknown')
    item['packages'] = packages
    item['stages'].append(stage('packages', state, done, len(packages)))
    # A stated release/spec status remains its own stage; unfinished packages stay visible.
    item['state'] = state
    item['total'], item['done'] = len(packages), done


def ledger_items(project, starts, finishes):
    """Group exact transient task labels in start order; latest attempt sets state."""
    groups = {}
    ordered = sorted(((timestamp(run.get('ts')), ident, run) for ident, run in starts.items()
                      if isinstance(run, dict) and run.get('project') == project and timestamp(run.get('ts'))),
                     key=lambda row: row[0])
    for _, ident, run in ordered:
        label = run.get('task')
        if not isinstance(label, str) or not label.strip() or len(label) > 4096:
            continue
        if label not in groups:
            if len(groups) >= 80:
                continue
            groups[label] = metadata_item(len(groups) + 1)
        item = groups[label]
        finish = finishes.get(ident)
        outcome = finish.get('outcome') if isinstance(finish, dict) else 'open'
        state = ('done' if outcome == 'accepted' else 'active' if outcome == 'open' else
                 'deferred' if outcome == 'cancelled' else 'needs-attention' if outcome in
                 ('rejected', 'timeout', 'stalled', 'needs-permission', 'blocked', 'error', 'quota') else 'unknown')
        item.update(state=state, done=int(state == 'done'), stages=[stage('work', state, int(state == 'done'), 1)])
    return list(groups.values())


def speckit_items(fd, skipped):
    items = []
    folders = [(name, int(name[:3])) for name, folder, _ in directory_entries(fd, 'specs', skipped)
               if folder and re.fullmatch(r'[0-9]{3}-.+', name)]
    for name, number in folders[-60:]:
        base = 'specs/' + name
        entries = directory_entries(fd, base, skipped)
        files = {name for name, _, regular in entries if regular}
        dirs = {name for name, folder, _ in entries if folder}
        if not files.intersection(('spec.md', 'plan.md', 'tasks.md')):
            continue
        texts = {}
        for kind in ('spec', 'tasks'):
            if kind + '.md' not in files:
                continue
            try:
                texts[kind] = read_task(fd, base + '/' + kind + '.md')
            except (OSError, ValueError):
                skipped.append('spec file skipped' if kind == 'spec' else 'task file skipped')
        # Unsafe/oversized task-only files must not yield a phantom feature.
        if not texts and 'plan.md' not in files:
            continue
        item = parse(texts.get('tasks', ''), number)
        tags = priorities(texts.get('spec', ''))
        for story in item['stories']:
            story['priority'] = story.get('priority') or tags.get(story['story'])
        line = status_line(texts.get('spec', ''))
        if line:
            keyword = re.match(r'[A-Za-z]+', line)
            hint = keyword[0].lower() if keyword else 'unknown'
            item['status_hint'] = hint if hint in HINTS else status_state(line)
        item['artifacts'] = dict(spec='spec' in texts, plan='plan.md' in files,
            design=bool(files.intersection(('research.md', 'data-model.md')) or 'contracts' in dirs),
            tasks='tasks' in texts, verify=any(re.fullmatch(r'quickstart-results.*\.md', n) for n in files),
            ship=any(re.fullmatch(r'release-notes-.*\.md', n) for n in files))
        reviews = []
        for n in files:
            if re.fullmatch(r'review-(?:code|security|final-code|final-security|independent|design).*', n):
                reviews.append(n)
        item['review_counts'] = {
            'code': sum('security' not in n for n in reviews),
            'security': sum('security' in n for n in reviews),
            'code_final': any('final' in n and 'security' not in n for n in reviews),
            'security_final': any('final' in n and 'security' in n for n in reviews)}
        items.append(item)
    if len(folders) > 60:
        skipped.append('feature limit')
    return items


def feature_stages(item):
    artifacts = item['artifacts']
    started = item['done'] > 0 or any(t['state'] in ('in progress', 'accepted, not ticked') for t in item['tasks'])
    item['state'] = 'done' if item['total'] > 0 and item['done'] == item['total'] and artifacts['verify'] else 'active' if started else 'todo'
    rows = []
    for name in ('spec', 'plan', 'design', 'tasks', 'verify', 'review', 'ship'):
        if name == 'review':
            count = item['review_counts']['code'] + item['review_counts']['security']
            if count:
                rows.append(stage(name, 'done', count, count))
        elif artifacts[name]:
            if name == 'tasks':
                state = 'done' if item['total'] > 0 and item['done'] == item['total'] else 'active' if started else 'todo'
                rows.append(stage(name, state, item['done'], item['total']))
            else:
                rows.append(stage(name, 'done', 1, 1))
    item['stages'] = rows


def item_done(item):
    return item.get('state') == 'done'


def label_ids(label):
    if not isinstance(label, str) or len(label) > 4096:
        return set(), set()
    features = {int(m[0]) for m in FEATURE.finditer(label)}
    ids = set()
    for match in RANGE.finditer(label):
        lo, hi = map(int, match.groups())
        if not 0 <= hi - lo < 20:
            return features, set()  # never link a truncated range, including its endpoints
        ids.update(range(lo, hi + 1))
    ids.update(int(m[1]) for m in TASK.finditer(label))
    return features, ids


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def join(features, project, repo, starts, finishes, events, now):
    """Only exact project + numeric feature + numeric task keys link ledger records."""
    index, by_task = {}, {}
    for feature in features:
        for task in feature['tasks']:
            number = int(task['id'][1:])
            index[(feature.get('feature'), number)] = task
            by_task.setdefault(number, []).append(task)
    sessions = {}
    for event in events:
        if event.get('repo') != repo or not IDENT.fullmatch(str(event.get('sid', ''))):
            continue
        at = timestamp(event.get('ts'))
        if at is None:
            continue
        sid = event['sid']
        row = sessions.setdefault(sid, {'id': sid[:8], 'host': 'unknown', 'first': at, 'last': at, 'dispatch': None, 'tasks': set()})
        row['first'], row['last'] = min(row['first'], at), max(row['last'], at)
        if event.get('event') == 'session_start':
            row['host'] = event.get('host') if event.get('host') in HOSTS else 'unknown'
            row['dispatch'] = event.get('dispatch')
        elif event.get('event') == 'task' and re.fullmatch(r'T[0-9]{1,4}', str(event.get('id', ''))):
            row['tasks'].add(int(event['id'][1:]))
    def session_data(row):
        return {'id': row['id'], 'host': row['host'], 'first': row['first'].isoformat(), 'last': row['last'].isoformat()}
    linked, outcomes, without, unlinked = set(), Counter(), 0, 0
    for ident, run in starts.items():
        if run.get('project') != project:
            continue
        feature_ids, task_ids = label_ids(run.get('task'))
        if not feature_ids:
            without += 1
        targets = [row for (feature, task), row in index.items() if feature in feature_ids and task in task_ids]
        if not targets:
            unlinked += 1
            continue
        if not isinstance(ident, str) or not IDENT.fullmatch(ident):
            continue
        at = timestamp(run.get('ts'))
        if at is None:
            continue
        finish = finishes.get(ident)
        ended = timestamp(finish.get('ts')) if isinstance(finish, dict) else None
        outcome = finish.get('outcome') if isinstance(finish, dict) and finish.get('outcome') in OUTCOMES else 'other' if finish else 'open'
        outcomes[outcome] += 1
        rounds = finish.get('rework_rounds', 0) if isinstance(finish, dict) else 0
        row = {'id': ident, 'agent': run.get('agent') if run.get('agent') in AGENTS else 'other',
               'model': run['model'] if isinstance(run.get('model'), str) and TOKEN.fullmatch(run['model']) else 'other',
               'start': at.isoformat(), 'finish': ended.isoformat() if ended else None, 'outcome': outcome,
               'rework_rounds': rounds if type(rounds) is int and rounds >= 0 else 0,
               'elapsed_seconds': max(0, int(((ended or now) - at).total_seconds()))}
        for task in targets:
            task['runs'].append(row)
            if task['state'] != 'done':
                if outcome == 'open':
                    task['state'] = 'in progress'
                elif outcome == 'accepted' and task['state'] != 'in progress':
                    task['state'] = 'accepted, not ticked'
            for sid, session in sessions.items():
                if session['dispatch'] == ident:
                    if session_data(session) not in task['sessions']:
                        task['sessions'].append(session_data(session))
                    linked.add(sid)
    for sid, session in sessions.items():
        for number in session['tasks']:
            candidates = by_task.get(number, [])
            if len(candidates) == 1:
                if session_data(session) not in candidates[0]['sessions']:
                    candidates[0]['sessions'].append(session_data(session))
                linked.add(sid)
    return {'labels_without_feature': without, 'unlinked_runs': unlinked, 'outcomes': dict(outcomes),
            'sessions_without_task': [session_data(row) for sid, row in sessions.items() if sid not in linked],
            'sessions': {'active_24h': sum(0 <= (now - r['last']).total_seconds() < 86400 for r in sessions.values()),
                         'idle': sum((now - r['last']).total_seconds() >= 86400 for r in sessions.values())}}


def completion_percent(done, total):
    """Unfinished work never rounds up to complete."""
    return min(100 if done == total else 99, done * 100 // total) if total else 0


def active_projects(events, repositories, labels, now):
    """Rebuild bounded repository activity from existing receipts, never keep session ids."""
    sessions = {}
    for event in events:
        repo, sid = event.get('repo'), event.get('sid')
        if (not isinstance(repo, str) or not re.fullmatch(r'[0-9a-f]{8}', repo)
                or not isinstance(sid, str) or not IDENT.fullmatch(sid)):
            continue
        at = timestamp(event.get('ts'))
        if at is None or at > now:
            continue
        row = sessions.setdefault((repo, sid), {'last': at, 'hosts': set()})
        row['last'] = max(row['last'], at)
        if event.get('event') == 'session_start' and event.get('host') in HOSTS:
            row['hosts'].add(event['host'])
    projects = {}
    for (repo, _), session in sessions.items():
        if not labels.get(repo) or not 0 <= (now - session['last']).total_seconds() < 86400:
            continue
        row = projects.setdefault(repo, {'last': session['last'], 'hosts': set(), 'sessions': 0})
        row['last'] = max(row['last'], session['last'])
        row['hosts'].update(session['hosts'])
        row['sessions'] += 1
    result = []
    for repo, row in sorted(projects.items(), key=lambda item: (-item[1]['last'].timestamp(), item[0]))[:12]:
        features = repositories.get(repo, {}).get('features', [])
        total, done = sum(f['total'] for f in features), sum(f['done'] for f in features)
        result.append({'repo': repo, 'label': labels[repo],
                       'hosts': [host for host in HOSTS if host in row['hosts']],
                       'sessions': row['sessions'], 'last': row['last'].isoformat(),
                       'percent': completion_percent(done, total) if total > done else None})
    return result


def empty(reason=''):
    return {'features': [], 'reason': reason, 'skipped': [], 'in_progress': 0}


def collect(cwd, repo, starts=None, finishes=None, events=(), now=None, records=None, repo_code=None):
    """All filesystem descent, parsing and joining share a one-second wall-clock budget."""
    try:
        with budget():
            settings = config()
            if settings is None:
                return empty('progress off')
            root = find_root(cwd)
            if root is None:
                return empty('no repository')
            result = empty()
            repo = repo_code(cwd) if repo_code else repo
            result['repo'] = repo
            try:
                labels = project_labels(dr.read_data('host.md', 262144).decode('utf-8'))
            except (OSError, ValueError, UnicodeError):
                labels = {}
            result['label'] = labels.get(repo, registered_projects().get(repo, ''))
            if records:
                ledger = records()
                if ledger is not None:
                    try:
                        starts, finishes = ledger.load()
                    except (OSError, ValueError, TypeError):
                        result['skipped'].append('ledger unavailable')
            with open_dir(root) as fd:
                result['features'] = speckit_items(fd, result['skipped'])
                result['source'], result['recognition'] = ('speckit', 'artifacts') if result['features'] else ('none', 'none')
                custom = settings.get('Task file')
                if custom:
                    try:
                        parts = safe_parts(custom)
                        if parts[:2] == ('specs', 'archive'):
                            raise ValueError('unsafe task path')
                        if not result['features']:
                            parent = Path(custom).parent.name
                            number = int(parent[:3]) if re.match(r'^[0-9]{3}-', parent) else 1
                            item = parse(read_task(fd, custom), number)
                            result['features'] = [item]
                            result['source'], result['recognition'] = 'checkbox', 'checkbox'
                    except (OSError, ValueError):
                        result['skipped'].append('unsafe task path')
                if not result['features']:
                    result['source'], result['recognition'], result['features'] = repository_documents(fd, result['skipped'])
                ledger_rows = ledger_items(settings.get('Ledger project', root.name), starts or {}, finishes or {})
                result['ledger_join'] = ('configured' if ledger_rows else 'configured-empty') if 'Ledger project' in settings else 'folder' if ledger_rows else 'none'
                result['work'] = dict(Counter(item['state'] for item in ledger_rows))
                if not result['features'] and ledger_rows:
                    result['features'], result['source'], result['recognition'] = ledger_rows, 'ledger', 'ledger'
            result.update(join(result['features'], settings.get('Ledger project', root.name), repo,
                               starts or {}, finishes or {}, events, now or datetime.now(timezone.utc)))
            for feature in result['features']:
                if 'artifacts' in feature:
                    feature_stages(feature)
                elif result['source'] == 'checkbox':
                    started = feature['done'] or any(t['state'] != 'todo' for t in feature['tasks'])
                    feature['state'] = 'done' if feature['total'] and feature['done'] == feature['total'] else 'active' if started else 'todo'
                    feature['stages'] = [stage('tasks', feature['state'], feature['done'], feature['total'])]
            result['in_progress'] = sum(t['state'] == 'in progress' for f in result['features'] for t in f['tasks'])
            result['done'] = bool(result['features']) and all(item_done(f) for f in result['features'])
            result['skipped'] = sorted(set(result['skipped']))
            return result
    except ProgressTimeout:
        return empty('progress timed out')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return empty('progress unavailable')


def notice(channel, version):
    """Independent one-time delivery flags for the page and the session-start line."""
    if channel not in ('dashboard', 'session') or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-dev)?', version):
        return False
    try:
        with dr.data_folder('state', create=True) as folder:
            fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                saved = json.loads(dr.read_file(folder, 'notices.json', 4096))
            except FileNotFoundError:
                saved = {}
            if not isinstance(saved, dict):
                return False
            key = 'project_progress_' + channel
            if saved.get(key) == version or (channel == 'dashboard' and saved.get(key) is True):
                return False
            # Closed schema, so unrelated/tampered text cannot be copied forward.
            saved = {k: v for k, v in saved.items()
                     if (k == 'project_progress_dashboard' and v is True)
                     or (k == 'project_progress_session' and isinstance(v, str)
                         and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-dev)?', v))}
            saved[key] = True if channel == 'dashboard' else version
            dr.atomic_write(folder, 'notices.json', (json.dumps(saved) + '\n').encode())
            return True
    except (OSError, ValueError, UnicodeError):
        return False


def installed_version():
    # Only the plugin's own manifest, never the repository being inspected.
    here = Path(__file__).resolve()
    for parent in (here.parents[1], here.parents[3]):
        try:
            value = json.loads((parent / '.claude-plugin/plugin.json').read_text())['version']
            if isinstance(value, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-dev)?', value):
                return value
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return 'unknown'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('choice', choices=('on', 'off', 'label'))
    parser.add_argument('--set', dest='label')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.choice == 'label':
            set_label(os.getcwd(), args.label)
            print('Project label saved.')
            return 0
        result = configure(args.choice, args.yes, args.dry_run)
        print(result if args.dry_run else 'Project progress preference saved.')
        return 0
    except (OSError, ValueError, UnicodeError):
        print('Project progress setup refused; no preference saved.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
