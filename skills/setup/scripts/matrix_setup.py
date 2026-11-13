#!/usr/bin/env python3
"""Preview and apply only the canonical host's Assignment matrix section; run no command, make no network call."""
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import fnmatch
import json
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assignments as am
import data_root as dr
import compact_setup as cs
import levels_setup as ls
import setup_features as sf

CAP = sf.CAP
STATE = 'state/matrix-setup'
ROLES_HEADING = '## Agent roles'
LEVELS_HEADING = '## Agent levels'
LEGACY = (ROLES_HEADING, LEVELS_HEADING)
LEGACY_ROLE = {'code review': 'code-review', 'security review': 'security-review', 'navigator': 'navigator'}
ROLE_LINE = re.compile(r'- (code review|security review|navigator): (.*)')
JUDGE_LINE = re.compile(r'- judge: (.*)')
PLAN_KEYS = {'kind', 'values', 'dropped', 'root', 'created', 'sha256', 'mode', 'backup'}


class Dropped(ValueError):
    """Unmapped legacy lines remain unacknowledged."""


def today():
    return time.strftime('%Y-%m-%d')


def validate(values):
    am.validate(values)


def sections(text, title):
    """Offsets (start, end) of every real section with this title; refuse an open fence."""
    found, unclosed = am.headings(text)
    if unclosed:
        raise ValueError('ambiguous host section')
    spans = []
    for index, (start, name) in enumerate(found):
        if name == title:
            spans.append((start, found[index + 1][0] if index + 1 < len(found) else len(text)))
    return spans


def transform(raw, values, remove=()):
    text = raw.decode('utf-8') if raw is not None else ''
    newline = '\r\n' if '\r\n' in text else '\n'
    section = am.render(values).replace('\n', newline)
    own = sections(text, am.HEADING)
    edits = []
    for title in remove:
        spans = sections(text, title)
        if len(spans) > 1:
            raise ValueError('legacy section')
        edits.extend((start, end, '') for start, end in spans)
    if len(own) > 1:
        raise ValueError('ambiguous host section')
    if own:
        edits.append((own[0][0], own[0][1], section))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    if not own:
        separator = newline * (2 if not text.endswith(newline) else 1) if text and not text.endswith(newline * 2) else ''
        text = text + separator + section
    encoded = text.encode('utf-8')
    if len(encoded) > CAP:
        raise ValueError('host too large')
    return encoded


def read_host(folder):
    raw, mode = cs.read_target(folder, 'host.md')
    if raw is not None and len(raw) > CAP:
        raise ValueError('host too large')
    return raw, mode


def build_values(lines, judge, consent):
    if len(lines) > am.MAX_AGENTS or judge not in ('jev', 'host') or consent not in ('yes', 'no'):
        raise ValueError('values')
    if any(not isinstance(line, str) or '\n' in line or '\r' in line for line in lines):
        raise ValueError('values')
    first = f'- Consent: yes ({today()})' if consent == 'yes' else '- Consent: no'
    text = f'{am.HEADING}\n{first}\n- Judge: {judge}\n' + ''.join(f'- {line}\n' for line in lines)
    matrix = am.parse(text)
    if matrix.state != 'valid':
        raise ValueError('values')
    return matrix.to_values()


def legacy_section_lines(text, title):
    spans = sections(text, title)
    if len(spans) > 1:
        raise ValueError('legacy section')
    if not spans:
        return None
    return [line for line in text[spans[0][0]:spans[0][1]].splitlines()[1:] if line.strip()]


def build_migration(text):
    """Map the legacy sections to matrix values (consent left for a new yes); return values, dropped lines and notes."""
    roles = legacy_section_lines(text, ROLES_HEADING)
    levels_lines = legacy_section_lines(text, LEVELS_HEADING)
    if roles is None and levels_lines is None:
        raise ValueError('nothing to migrate')
    dropped, notes, agents, judge = [], [], {}, None
    if levels_lines is not None:
        try:
            legacy = ls.parse(text)
        except ValueError:
            legacy = None
            dropped.append('dropped: Agent levels section unreadable')
        for name, low, high in (legacy or {'installs': []})['installs']:
            agents[name] = {'levels': (low, high), 'works': [], 'model': None, 'roles': []}
    assigned = set()
    for number, line in enumerate(roles or [], 1):
        where = f'dropped: Agent roles line {number}'
        role = ROLE_LINE.fullmatch(line)
        verdict = JUDGE_LINE.fullmatch(line)
        if role:
            name, key = role[2], LEGACY_ROLE[role[1]]
            if key in assigned:
                dropped.append(f'{where}: duplicate role')
            elif not am.NAME.fullmatch(name):
                dropped.append(f'{where}: agent not accepted')
            elif name not in agents and len(agents) >= am.MAX_AGENTS:
                dropped.append(f'{where}: too many agents')
            else:
                if name not in agents:
                    agents[name] = {'levels': (1, 5), 'works': [], 'model': None, 'roles': []}
                    notes.append(f'{name}: no levels recorded; levels 1-5 shown, edit them if wrong')
                agents[name]['roles'].append(key)
                assigned.add(key)
        elif verdict and judge is None and verdict[1] in ('jev', 'host'):
            judge = verdict[1]
        else:
            dropped.append(f'{where}: unrecognized or repeated line')
    values = {'consent': 'no', 'date': '', 'judge': judge or 'host', 'agents': agents}
    validate(values)
    return values, dropped, notes


def write_plan(plan, shown):
    value = cs.digest(plan)
    root = dr.consent_root()
    with dr.data_folder(STATE, create=True, private=True) as state:
        try:
            cs.read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, 'preview.json', json.dumps({'plan': plan, 'digest': value}).encode())
    print('Target: ' + str(root / 'host.md'))
    print(shown, end='')
    print('Backup: ' + str(root / plan['backup']))
    print('Digest: ' + value)
    print('Preview expires in 60 minutes; host configuration unchanged.')


def preview(kind, values, dropped=(), notes=()):
    validate(values)
    root = dr.consent_root()
    if root is None:
        raise ValueError('invalid data root')
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw, mode = read_host(folder)
        transform(raw, values, LEGACY if kind == 'migrate' else ())
        plan = {'kind': kind, 'values': values, 'dropped': list(dropped), 'root': str(root), 'created': time.time(),
                'sha256': cs.content_hash(raw), 'mode': mode, 'backup': cs.backup_name(folder, 'host.md')}
    shown = am.render(values)
    if kind == 'migrate':
        shown += 'Consent is not inherited: a new yes is needed, so apply requires --consent yes and then writes the Consent line.\n'
        shown += 'The Agent roles and Agent levels sections are removed in the same write; the backup keeps them.\n'
    shown += ''.join(f'Note: {note}\n' for note in notes) + ''.join(f'{line}\n' for line in dropped)
    if dropped:
        shown += 'Unmapped legacy lines are listed above; apply refuses (exit 3) until you acknowledge them with --ack-dropped.\n'
    write_plan(plan, shown)


def apply(value, consent, acknowledged):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{12,64}', value):
        raise ValueError('at least 12 hex digits of the preview digest required')
    with dr.data_folder(STATE, private=True) as state:
        fcntl.flock(state, fcntl.LOCK_EX | fcntl.LOCK_NB)
        saved = json.loads(cs.read_plan(state))
        if not isinstance(saved, dict) or set(saved) != {'plan', 'digest'}:
            raise ValueError('invalid preview')
        plan = saved['plan']
        digest = cs.digest(plan)
        if saved['digest'] != digest or not digest.startswith(value):
            raise ValueError('digest mismatch; preview again')
        if not isinstance(plan, dict) or set(plan) != PLAN_KEYS or plan['kind'] not in ('set', 'migrate'):
            raise ValueError('invalid plan')
        validate(plan['values'])
        dropped = plan['dropped']
        if not isinstance(dropped, list) or any(not isinstance(item, str) for item in dropped):
            raise ValueError('invalid plan')
        if plan['root'] != str(dr.consent_root()):
            raise ValueError('data root changed; preview again')
        if type(plan['created']) not in (int, float) or not 0 <= time.time() - plan['created'] <= 3600:
            raise ValueError('preview expired; preview again')
        if not isinstance(plan['backup'], str) or not re.fullmatch(r'host\.md\.bak-\d{8}(?:-[1-9][0-9]*)?', plan['backup']):
            raise ValueError('invalid backup')
        values, remove = plan['values'], ()
        if plan['kind'] == 'migrate':
            if consent != 'yes' or values['consent'] != 'no':
                raise ValueError('a new consent is required')
            if dropped and not acknowledged:
                raise Dropped('unmapped legacy lines')
            values, remove = dict(values, consent='yes', date=today()), LEGACY
        with dr.root_folder() as folder:
            fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw, mode = read_host(folder)
            if cs.content_hash(raw) != plan['sha256'] or mode != plan['mode']:
                raise ValueError('host changed; preview again')
            if plan['kind'] == 'migrate' and raw is not None and sections(raw.decode('utf-8'), am.HEADING):
                raise ValueError('matrix exists')
            result = transform(raw, values, remove)
            if result != raw:
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
    print('Assignment matrix saved; no command was run.')


def unfenced(body):
    """Lines of a section body outside code fences; only a bare closing fence closes one, as in `assignments.py`."""
    fence = None
    for line in body.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and line.strip() == token:
                fence = None
        elif fence is None:
            yield line


def allowed_models(text):
    """Model patterns recorded in `## Agents on this machine`; the fourth table column, comma separated."""
    allowed = []
    for start, end in sections(text, '## Agents on this machine')[:1]:
        for line in unfenced(text[start:end]):
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if len(cells) >= 5 and not set(cells[3]) <= set('- '):
                allowed.extend(item.strip() for item in cells[3].split(','))
    return allowed


def posting_summary(text):
    """Family and state words from `## Review posting`; nothing else from that section is printed."""
    words = []
    for start, end in sections(text, '## Review posting')[:1]:
        for line in unfenced(text[start:end]):
            match = re.match(r'- (claude|codex|antigravity): (yes|no|unverified)\b', line)
            if match:
                words.append(f'{match[1]} {match[2]}')
    return ', '.join(words) or 'not recorded'


def table(matrix):
    lines = ['| Agent | Levels | Works on | Model | Roles |', '| --- | --- | --- | --- | --- |']
    for name, entry in matrix.agents.items():
        low, high = entry['levels']
        lines.append(f"| {name} | {low}-{high} | {', '.join(entry['works'])} | {entry['model'] or ''} | {', '.join(entry['roles']) or 'none'} |")
    return lines


def show():
    try:
        try:
            text = dr.read_data('host.md', CAP).decode('utf-8')
        except FileNotFoundError:
            text = ''
    except (OSError, ValueError, UnicodeError):
        print('unreadable')
        return 3
    matrix = am.parse(text)
    if matrix.state == 'absent':
        print('The assignment matrix is not set: no review roles, judge host; Agent roles is no longer read, and migrate converts it.')
        return 0
    if matrix.state == 'invalid':
        for reason in matrix.problems:
            print(f'Problem: {reason}')
        return 3
    print('\n'.join(table(matrix)))
    print(f'Judge: {matrix.judge}')
    print(f'Review posting: {posting_summary(text)}')
    allowed = allowed_models(text)
    for name, entry in matrix.agents.items():
        if entry['model'] and not any(fnmatch.fnmatchcase(entry['model'], item) for item in allowed):
            print(f"Unverified: {name} model {entry['model']} is not among the allowed models on this machine")
    return 0


def main(argv=None):
    try:
        parser = cs.Parser(description=__doc__)
        commands = parser.add_subparsers(dest='action', required=True)
        for name in ('validate', 'preview'):
            sub = commands.add_parser(name)
            sub.add_argument('--line', action='append', default=[], metavar='AGENT_LINE')
            sub.add_argument('--judge', required=True, choices=('jev', 'host'))
            sub.add_argument('--consent', required=True, choices=('yes', 'no'))
        app = commands.add_parser('apply')
        app.add_argument('--digest', required=True)
        app.add_argument('--consent', choices=('yes',))
        app.add_argument('--ack-dropped', action='store_true')
        commands.add_parser('migrate')
        commands.add_parser('show')
        commands.add_parser('candidates')
        args = parser.parse_args(argv)
        if args.action == 'show':
            return show()
        if args.action == 'candidates':
            print(json.dumps(ls.candidates(), separators=(',', ':')))
            return 0
        if args.action == 'validate':
            print(am.render(build_values(args.line, args.judge, args.consent)), end='')
            print('Valid; nothing written.')
        elif args.action == 'preview':
            preview('set', build_values(args.line, args.judge, args.consent))
        elif args.action == 'migrate':
            text = ''
            with dr.root_folder() as folder:
                raw, _ = read_host(folder)
                text = raw.decode('utf-8') if raw is not None else ''
            if sections(text, am.HEADING):
                raise ValueError('matrix exists')
            values, dropped, notes = build_migration(text)
            preview('migrate', values, dropped, notes)
        else:
            apply(args.digest, args.consent, args.ack_dropped)
        return 0
    except Dropped:
        print('Assignment matrix setup refused: unmapped legacy lines need --ack-dropped.', file=sys.stderr)
        return 3
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print('Assignment matrix setup refused: invalid arguments, unsafe or changed file, or stale preview; preview again.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
