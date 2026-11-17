#!/usr/bin/env python3
"""Preview and apply only the canonical host's Assignment matrix section; run no command, make no network call."""
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import datetime
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
import setup_features as sf

CAP = sf.CAP
STATE = 'state/matrix-setup'
ROLES_HEADING = '## Agent roles'
LEVELS_HEADING = '## Agent levels'
LEGACY = (ROLES_HEADING, LEVELS_HEADING)
# `## Route judgment` (retired 0.3.2) held only the instruction-check consent; `migrate` moves it to its own section.
ROUTE_HEADING = '## Route judgment'
INSTRUCTION_HEADING = '## Instruction check'
INSTRUCTION_LINE = re.compile(r'- Instruction check: (on|off)(?:[ .].*)?')
INSTRUCTION_DATE = re.compile(r'\b(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b')
LEGACY_ROLE = {'code review': 'code-review', 'security review': 'security-review', 'navigator': 'navigator'}
ROLE_LINE = re.compile(r'- (code review|security review|navigator): (.*)')
JUDGE_LINE = re.compile(r'- judge: (.*)')
PLAN_KEYS = {'kind', 'values', 'dropped', 'root', 'created', 'sha256', 'mode', 'backup', 'instruction', 'route'}
# `## Agent levels` is no longer read for routing (0.3.1); only `migrate` reads it, to carry the levels over.
LEVELS_ENTRY = re.compile(r'- (claude|codex|antigravity|claude[a-z0-9]{1,24}): levels ([1-5])-([1-5])')
LEVELS_CONSENT = re.compile(r'- Consent: (?:yes \((\d{4}-\d{2}-\d{2})\)|(no))')
LEVELS_MAX = 8


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


def transform(raw, values, remove=(), instruction=None):
    """Rewrite the matrix (when values is given), drop the `remove` sections and append the instruction section."""
    text = raw.decode('utf-8') if raw is not None else ''
    newline = '\r\n' if '\r\n' in text else '\n'
    own = sections(text, am.HEADING) if values is not None else []
    edits = []
    for title in remove:
        spans = sections(text, title)
        if len(spans) > 1:
            raise ValueError('legacy section')
        edits.extend((start, end, '') for start, end in spans)
    if len(own) > 1:
        raise ValueError('ambiguous host section')
    if own:
        edits.append((own[0][0], own[0][1], am.render(values).replace('\n', newline)))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    added = [] if own else [am.render(values)] if values is not None else []
    if instruction is not None:
        if sections(text, INSTRUCTION_HEADING):
            raise ValueError('instruction section exists')
        added.append(f'{INSTRUCTION_HEADING}\n\n{instruction}\n')
    for section in added:
        separator = newline * (2 if not text.endswith(newline) else 1) if text and not text.endswith(newline * 2) else ''
        text = text + separator + section.replace('\n', newline)
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


def legacy_levels(text):
    """Strictly read the legacy Agent levels entries for `migrate`; None when absent, ValueError when unreadable."""
    headings, fence = sf.split(text)
    indexes = [i for i, (_, title) in enumerate(headings) if title == LEVELS_HEADING]
    if fence is not None or len(indexes) > 1:
        raise ValueError('ambiguous section')
    if not indexes:
        return None
    index = indexes[0]
    end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
    consent, installs = None, []
    for line in text[headings[index][0]:end].splitlines()[1:]:
        if not line.strip():
            continue
        match = LEVELS_CONSENT.fullmatch(line)
        if match:
            if consent is not None:
                raise ValueError('duplicate consent')
            consent = 'yes' if match[1] else 'no'
            if match[1]:
                time.strptime(match[1], '%Y-%m-%d')
            continue
        match = LEVELS_ENTRY.fullmatch(line)
        if not match:
            raise ValueError('unknown line')
        name, low, high = match[1], int(match[2]), int(match[3])
        if not low <= high or any(name == item[0] for item in installs):
            raise ValueError('levels')
        installs.append((name, low, high))
    if consent is None or len(installs) > LEVELS_MAX or (consent == 'yes') != bool(installs):
        raise ValueError('consent')
    return installs


def build_migration(text):
    """Map the legacy sections to matrix values (consent left for a new yes); return values, dropped lines and notes."""
    roles = legacy_section_lines(text, ROLES_HEADING)
    levels_lines = legacy_section_lines(text, LEVELS_HEADING)
    if roles is None and levels_lines is None:
        raise ValueError('nothing to migrate')
    dropped, notes, agents, judge = [], [], {}, None
    if levels_lines is not None:
        try:
            legacy = legacy_levels(text) or []
        except ValueError:
            legacy = []
            dropped.append('dropped: Agent levels section unreadable')
        for name, low, high in legacy:
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


def build_route(text):
    """Read the retired `## Route judgment` for `migrate`: (instruction line or None, dropped, notes), or None when
    absent. Only a normalized `on`/`off` and its date carry over, so no other text of the section reaches the plan."""
    lines = legacy_section_lines(text, ROUTE_HEADING)
    if lines is None:
        return None
    dropped, notes, found = [], [], []
    # A comment anywhere in the file can span headings, so any comment marker carries nothing over.
    fenced = ('<!--' in text or '-->' in text or any(line.lstrip().startswith(('```', '~~~')) for line in lines))
    for number, line in enumerate(lines, 1):
        where = f'dropped: Route judgment line {number}'
        match = INSTRUCTION_LINE.fullmatch(line)
        if match and not fenced:
            found.append((number, match))
        elif re.fullmatch(r'- [Jj]udge: .*', line):
            notes.append(f'Route judgment line {number}: the judge line is not read; the matrix holds the judge')
        else:
            dropped.append(f'{where}: unrecognized line')
    instruction = None
    if len(found) == 1 and not sections(text, INSTRUCTION_HEADING):
        match = found[0][1]
        date = INSTRUCTION_DATE.search(match[0][len('- Instruction check: '):])
        instruction = f'- Instruction check: {match[1]}' + (f' ({date[1]})' if match[1] == 'on' and date else '')
    else:
        reason = 'Instruction check section exists' if found and sections(text, INSTRUCTION_HEADING) else 'repeated line'
        dropped.extend(f'dropped: Route judgment line {number}: {reason}' for number, _ in found)
    return instruction, dropped, notes


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


def removed(kind, route):
    return (LEGACY if kind == 'migrate' else ()) + ((ROUTE_HEADING,) if route else ())


def preview(kind, values, dropped=(), notes=(), instruction=None, route=False):
    if values is not None:
        validate(values)
    root = dr.consent_root()
    if root is None:
        raise ValueError('invalid data root')
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw, mode = read_host(folder)
        transform(raw, values, removed(kind, route), instruction)
        plan = {'kind': kind, 'values': values, 'dropped': list(dropped), 'root': str(root), 'created': time.time(),
                'sha256': cs.content_hash(raw), 'mode': mode, 'backup': cs.backup_name(folder, 'host.md'),
                'instruction': instruction, 'route': route}
    shown = am.render(values) if values is not None else ''
    if kind == 'migrate':
        shown += 'Consent is not inherited: a new yes is needed, so apply requires --consent yes and then writes the Consent line.\n'
        shown += 'The Agent roles and Agent levels sections are removed in the same write; the backup keeps them.\n'
    if route:
        shown += (f'{INSTRUCTION_HEADING}\n\n{instruction}\n' if instruction is not None else
                  'No Instruction check line carries over; record it again through setup if you want it on.\n')
        shown += 'The Route judgment section is removed in the same write; the backup keeps it.\n'
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
        if not isinstance(plan, dict) or set(plan) != PLAN_KEYS or plan['kind'] not in ('set', 'migrate', 'route'):
            raise ValueError('invalid plan')
        route, instruction = plan['route'], plan['instruction']
        if type(route) is not bool or (plan['kind'] == 'route') != (plan['values'] is None) or \
                (plan['kind'] == 'route' and not route) or (plan['kind'] == 'set' and route):
            raise ValueError('invalid plan')
        if instruction is not None and not (route and isinstance(instruction, str) and
                                            re.fullmatch(r'- Instruction check: (?:on(?: \([0-9/-]{10}\))?|off)', instruction)):
            raise ValueError('invalid plan')
        if plan['values'] is not None:
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
        values, remove = plan['values'], removed(plan['kind'], route)
        if plan['kind'] == 'migrate':
            if consent != 'yes' or values['consent'] != 'no':
                raise ValueError('a new consent is required')
            values = dict(values, consent='yes', date=today())
        if plan['kind'] != 'set' and dropped and not acknowledged:
            raise Dropped('unmapped legacy lines')
        with dr.root_folder() as folder:
            fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw, mode = read_host(folder)
            if cs.content_hash(raw) != plan['sha256'] or mode != plan['mode']:
                raise ValueError('host changed; preview again')
            if plan['kind'] == 'migrate' and raw is not None and sections(raw.decode('utf-8'), am.HEADING):
                raise ValueError('matrix exists')
            result = transform(raw, values, remove, instruction)
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
    print('Assignment matrix saved; no command was run.' if plan['kind'] != 'route' else
          'Instruction check moved and Route judgment removed; no command was run.')


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


def rules(matrix):
    """The `models` rules of each agent, one per line in order (first match wins), and where `then` cannot apply."""
    lines = []
    for name, entry in matrix.agents.items():
        for number, rule in enumerate(entry['models'], 1):
            lines.append(f'Models {name} {number}: {am.render_rule(rule)}')
        if name != 'antigravity' and any(rule['then'] for rule in entry['models']):
            lines.append(f'Note: {name} has one quota reading for the whole install, so its then never applies')
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
    print('\n'.join(table(matrix) + rules(matrix)))
    print(f'Judge: {matrix.judge}')
    print(f'Review posting: {posting_summary(text)}')
    allowed = allowed_models(text)
    for name, entry in matrix.agents.items():
        models = [entry['model']] if entry['model'] else []
        models += [m for rule in entry['models'] for m in (rule['model'], rule['then']) if m]
        for model in dict.fromkeys(models):
            if not any(fnmatch.fnmatchcase(model, item) for item in allowed):
                print(f"Unverified: {name} model {model} is not among the allowed models on this machine")
    return 0


CANDIDATE = re.compile(r'claude[a-z0-9]{1,24}')
FOLDER = re.compile(r'\.claude-([a-z0-9]{1,24})')
LISTED = 20


def candidates():
    """Names only: claude* programs on an absolute PATH and ~/.claude-* folders; runs nothing."""
    commands = []
    for entry in os.get_exec_path():
        if not os.path.isabs(entry) or len(commands) >= LISTED:
            continue
        try:
            with os.scandir(entry) as items:
                for item in items:
                    if (item.name != 'claude' and CANDIDATE.fullmatch(item.name) and item.name not in commands
                            and item.is_file() and os.access(item.path, os.X_OK)):
                        commands.append(item.name)
        except OSError:
            continue
    return {'commands': sorted(commands)[:LISTED], 'folders': config_folders()}


def config_folders():
    """Suffixes of ~/.claude-* folders (names only, never a path)."""
    folders = []
    try:
        with os.scandir(dr.account_home()) as items:
            for item in items:
                match = FOLDER.fullmatch(item.name)
                if match and item.is_dir(follow_symlinks=False) and match[1] not in folders:
                    folders.append(match[1])
    except OSError:
        pass
    return sorted(folders)[:LISTED]


# Display names of `## Agents on this machine`, as `agent_scan.py` writes them (AGENTS there; a test keeps them equal).
FAMILIES = {'Claude Code': 'claude', 'Codex': 'codex', 'Antigravity': 'antigravity', 'ZCode': 'zcode'}
STALE_DAYS = 30
SCAN_ADVICE = 'Run /setup scan to refresh the list of AI helpers before choosing.'


def inventory_rows(text):
    """Coordinator family and {family: (present, checked)} from the canonical inventory; ValueError when ambiguous."""
    spans = sections(text, '## Agents on this machine')
    if len(spans) > 1:
        raise ValueError('duplicate inventory')
    if not spans:
        return None, None
    coordinator, rows, seen = None, {}, set()
    for line in unfenced(text[spans[0][0]:spans[0][1]]):
        match = re.fullmatch(r'Coordinator: (.+)', line.strip())
        if match:
            coordinator = FAMILIES.get(match[1].strip())
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) != 5 or cells[0] not in FAMILIES:
            continue
        family = FAMILIES[cells[0]]
        present = {'yes': True, 'no': False}.get(cells[1], 'unverified')
        rows[family] = ('unverified', None) if family in seen else (present, cells[4])
        seen.add(family)
    return coordinator, rows


def choices():
    """Every helper name the matrix accepts, with family, presence and the coordinator mark; reads only host.md."""
    state, coordinator, rows = 'current', None, {}
    try:
        try:
            text = dr.read_data('host.md', CAP).decode('utf-8')
        except FileNotFoundError:
            text = ''
        coordinator, rows = inventory_rows(text)
    except (OSError, ValueError, UnicodeError):
        state, rows = 'unreadable', {}
    if state == 'current' and not rows:
        state, rows = 'missing', {}
    if state == 'current':
        now = datetime.date.fromisoformat(today())
        for _, checked in rows.values():
            try:
                age = (now - datetime.date.fromisoformat(checked or '')).days
            except ValueError:
                age = None
            if age is None or not 0 <= age <= STALE_DAYS:
                state = 'stale'
    helpers = []
    for family in FAMILIES.values():
        present = rows.get(family, ('unverified', None))[0]
        helpers.append({'name': family, 'family': family, 'present': present, 'coordinator': family == coordinator})
    claude = helpers[0]['present']
    for folder in config_folders():
        helpers.append({'name': 'claude' + folder, 'family': 'claude', 'present': claude,
                        'coordinator': coordinator == 'claude'})
    result = {'inventory': state, 'coordinator': coordinator, 'helpers': helpers}
    if state != 'current':
        result['advice'] = SCAN_ADVICE
    return result


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
        commands.add_parser('choices')
        args = parser.parse_args(argv)
        if args.action == 'show':
            return show()
        if args.action == 'candidates':
            print(json.dumps(candidates(), separators=(',', ':')))
            return 0
        if args.action == 'choices':
            print(json.dumps(choices(), separators=(',', ':')))
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
            route = build_route(text)
            instruction, extra, more = route if route is not None else (None, [], [])
            if sections(text, am.HEADING) or not (sections(text, ROLES_HEADING) or sections(text, LEVELS_HEADING)):
                if route is None:
                    raise ValueError('nothing to migrate')
                preview('route', None, extra, more, instruction, True)
            else:
                values, dropped, notes = build_migration(text)
                preview('migrate', values, dropped + extra, notes + more, instruction, route is not None)
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
