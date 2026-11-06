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
    return hashlib.sha256(str(root).encode('utf-8')).hexdigest()[:8]


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
        match = re.match(r'^#{1,6} User Story ([0-9]{1,3}) \(P([1-9])\)(?:[ \t].*)?$', line)
        if match:
            story = 'US' + str(int(match[1]))
            values[story] = None if story in seen else int(match[2])
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


def read_task(root_fd, relative):
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
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > LIMIT:
            raise ValueError('task file skipped')
        chunks, size = [], 0
        while size <= LIMIT:
            chunk = os.read(fd, min(65536, LIMIT + 1 - size))
            if not chunk:
                return b''.join(chunks).decode('utf-8', 'replace')
            chunks.append(chunk)
            size += len(chunk)
        raise ValueError('task file skipped')
    finally:
        os.close(fd)


def parse(text, feature):
    tasks, phase, seen = [], None, set()
    for line in text.splitlines():
        if len(line) > 4096:
            continue
        heading = re.match(r'^#{2,3} Phase ([0-9]{1,2})\b', line)
        if heading:
            phase = int(heading[1])
        box = re.match(r'^\s*- \[( |x|X)\] ', line)
        if not box:
            continue
        # Include lookahead beyond the window so a cut token cannot become a shorter id.
        prefix = line[box.end():box.end() + 85]
        ident, story = TASK.search(prefix), STORY.search(prefix)
        if not ident or ident.end() > 80 or int(ident[1]) in seen:
            continue
        seen.add(int(ident[1]))
        tasks.append({'id': ident[0], 'story': story[0] if story and story.end() <= 80 else None, 'phase': phase,
                      'state': 'done' if box[1] != ' ' else 'todo', 'runs': [], 'sessions': []})
        if len(tasks) == 200:
            break
    def counts(key):
        values = sorted({r[key] for r in tasks if r[key] is not None})
        return [{key: value, 'done': sum(r['state'] == 'done' for r in tasks if r[key] == value),
                 'total': sum(r[key] == value for r in tasks)} for value in values]
    return {'feature': feature, 'tasks': tasks, 'total': len(tasks),
            'done': sum(r['state'] == 'done' for r in tasks), 'phases': counts('phase'), 'stories': counts('story')}


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
            index[(feature['feature'], number)] = task
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
            result['label'] = labels.get(repo, 'repo ' + str(repo)[:4])
            if records:
                ledger = records()
                if ledger is not None:
                    try:
                        starts, finishes = ledger.load()
                    except (OSError, ValueError, TypeError):
                        result['skipped'].append('ledger unavailable')
            paths = []
            with open_dir(root) as fd:
                try:
                    specs = os.open('specs', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                    try:
                        with os.scandir(specs) as entries:
                            names = []
                            for entry in entries:
                                if len(names) == 200:
                                    result['skipped'].append('entry limit')
                                    break
                                names.append(entry.name)
                        for name in sorted(names):
                            if name == 'archive':
                                continue
                            paths.append(('specs/' + name + '/tasks.md', int(name[:3]) if re.match(r'^[0-9]{3}-', name) else len(paths) + 1))
                    finally:
                        os.close(specs)
                except FileNotFoundError:
                    pass
                except OSError:
                    result['skipped'].append('task file skipped')
                custom = settings.get('Task file')
                if custom:
                    try:
                        parts = safe_parts(custom)
                        if len(parts) >= 2 and parts[:2] == ('specs', 'archive'):
                            raise ValueError('unsafe task path')
                        custom = str(Path(custom))
                        if os.path.commonpath((os.path.realpath(root), os.path.realpath(root / custom))) != os.path.realpath(root):
                            raise ValueError('unsafe task path')
                        if custom not in [path for path, _ in paths]:
                            name = Path(custom).parent.name
                            feature = int(name[:3]) if re.match(r'^[0-9]{3}-', name) else len(paths) + 1
                            paths.insert(0, (custom, feature))
                    except ValueError:
                        result['skipped'].append('unsafe task path')
                files = 0
                for relative, feature in paths:
                    if files >= 20:
                        result['skipped'].append('file limit')
                        break
                    try:
                        parsed = parse(read_task(fd, relative), feature)
                        files += 1
                    except (OSError, ValueError):
                        result['skipped'].append('task file skipped')
                        continue
                    tags = {}
                    sibling = str(Path(relative).with_name('spec.md'))
                    if sibling != relative:
                        if files < 20:
                            try:
                                tags = priorities(read_task(fd, sibling))
                                files += 1
                            except FileNotFoundError:
                                pass
                            except (OSError, ValueError):
                                result['skipped'].append('spec file skipped')
                        else:
                            result['skipped'].append('file limit')
                    for story in parsed['stories']:
                        story['priority'] = tags.get(story['story'])
                    result['features'].append(parsed)
            result.update(join(result['features'], settings.get('Ledger project', root.name), repo,
                               starts or {}, finishes or {}, events, now or datetime.now(timezone.utc)))
            result['in_progress'] = sum(t['state'] == 'in progress' for f in result['features'] for t in f['tasks'])
            result['done'] = bool(result['features']) and all(f['done'] == f['total'] for f in result['features'])
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
