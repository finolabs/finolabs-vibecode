#!/usr/bin/env python3
"""Preview and apply only the canonical host's Agent levels section; run no command."""
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import compact_setup as cs
import setup_features as sf

CAP = sf.CAP
STATE = 'state/levels-setup'
HEADING = '## Agent levels'
NAME = re.compile(r'claude|codex|antigravity|claude[a-z0-9]{1,24}')
ENTRY = re.compile(r'- (claude|codex|antigravity|claude[a-z0-9]{1,24}): levels ([1-5])-([1-5])')
CONSENT = re.compile(r'- Consent: (?:yes \((\d{4}-\d{2}-\d{2})\)|(no))')
MAX_ENTRIES = 8


def validate(values):
    if not isinstance(values, dict) or set(values) != {'consent', 'date', 'installs'}:
        raise ValueError('values')
    installs = values['installs']
    if values['consent'] not in ('yes', 'no') or not isinstance(installs, list) or len(installs) > MAX_ENTRIES:
        raise ValueError('values')
    if values['consent'] == 'yes':
        time.strptime(values['date'], '%Y-%m-%d')
        if not installs:
            raise ValueError('no installs')
    elif installs:
        raise ValueError('installs without consent')
    names = set()
    for item in installs:
        if not isinstance(item, list) or len(item) != 3 or not isinstance(item[0], str):
            raise ValueError('install')
        name, low, high = item
        if not NAME.fullmatch(name) or name in names:
            raise ValueError('agent name')
        if type(low) is not int or type(high) is not int or not 1 <= low <= high <= 5:
            raise ValueError('levels')
        names.add(name)


def render(values):
    validate(values)
    first = f"- Consent: yes ({values['date']})" if values['consent'] == 'yes' else '- Consent: no'
    entries = ''.join(f'- {name}: levels {low}-{high}\n' for name, low, high in values['installs'])
    return f'{HEADING}\n\n{first}\n{entries}\n'


def parse(text):
    """Return None when the section is absent; raise ValueError when it is unreadable."""
    headings, fence = sf.split(text)
    indexes = [i for i, (_, title) in enumerate(headings) if title == HEADING]
    if fence is not None or len(indexes) > 1:
        raise ValueError('ambiguous section')
    if not indexes:
        return None
    index = indexes[0]
    end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
    body = text[headings[index][0]:end].splitlines()[1:]
    consent, installs = None, []
    for line in body:
        if not line.strip():
            continue
        match = CONSENT.fullmatch(line)
        if match:
            if consent is not None:
                raise ValueError('duplicate consent')
            consent = ('yes', match[1]) if match[1] else ('no', '')
            continue
        match = ENTRY.fullmatch(line)
        if not match:
            raise ValueError('unknown line')
        installs.append([match[1], int(match[2]), int(match[3])])
    if consent is None:
        raise ValueError('consent missing')
    values = {'consent': consent[0], 'date': consent[1], 'installs': installs}
    validate(values)
    return values


def transform(raw, values):
    text = raw.decode('utf-8') if raw is not None else ''
    headings, fence = sf.split(text)
    indexes = [i for i, (_, title) in enumerate(headings) if title == HEADING]
    if fence is not None or len(indexes) > 1:
        raise ValueError('ambiguous host section')
    newline = '\r\n' if '\r\n' in text else '\n'
    section = render(values).replace('\n', newline)
    if indexes:
        index = indexes[0]
        start = headings[index][0]
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        result = text[:start] + section + text[end:]
    else:
        separator = newline * (2 if not text.endswith(newline) else 1) if text and not text.endswith(newline * 2) else ''
        result = text + separator + section
    encoded = result.encode('utf-8')
    if len(encoded) > CAP:
        raise ValueError('host too large')
    return encoded


def read_host(folder):
    raw, mode = cs.read_target(folder, 'host.md')
    if raw is not None and len(raw) > CAP:
        raise ValueError('host too large')
    return raw, mode


def preview(values):
    validate(values)
    root = dr.consent_root()
    if root is None:
        raise ValueError('invalid data root')
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw, mode = read_host(folder)
        transform(raw, values)
        plan = {'values': values, 'root': str(root), 'created': time.time(),
                'sha256': cs.content_hash(raw), 'mode': mode, 'backup': cs.backup_name(folder, 'host.md')}
    value = cs.digest(plan)
    with dr.data_folder(STATE, create=True, private=True) as state:
        try:
            cs.read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, 'preview.json', json.dumps({'plan': plan, 'digest': value}).encode())
    print('Target: ' + str(root / 'host.md'))
    print(render(values), end='')
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
        if not isinstance(plan, dict) or set(plan) != {'values', 'root', 'created', 'sha256', 'mode', 'backup'}:
            raise ValueError('invalid plan')
        validate(plan['values'])
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
            result = transform(raw, plan['values'])
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
    print('Agent levels section saved; no command was run.')


def show():
    try:
        text = dr.read_data('host.md', CAP).decode('utf-8')
        values = parse(text)
    except FileNotFoundError:
        print('none')
        return 0
    except (OSError, ValueError, UnicodeError):
        print('unreadable')
        return 3
    print('none' if values is None else json.dumps(values, separators=(',', ':')))
    return 0


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
                    if (item.name != 'claude' and NAME.fullmatch(item.name) and item.name not in commands
                            and item.is_file() and os.access(item.path, os.X_OK)):
                        commands.append(item.name)
        except OSError:
            continue
    folders = []
    try:
        with os.scandir(dr.account_home()) as items:
            for item in items:
                match = FOLDER.fullmatch(item.name)
                if match and item.is_dir(follow_symlinks=False) and match[1] not in folders:
                    folders.append(match[1])
    except OSError:
        pass
    return {'commands': sorted(commands)[:LISTED], 'folders': sorted(folders)[:LISTED]}


def install(text):
    name, _, levels = text.partition(':')
    match = re.fullmatch(r'([1-5])-([1-5])', levels)
    if not match:
        raise ValueError('levels')
    return [name, int(match[1]), int(match[2])]


def main(argv=None):
    try:
        parser = cs.Parser(description=__doc__)
        commands = parser.add_subparsers(dest='action', required=True)
        pre = commands.add_parser('preview')
        pre.add_argument('--install', action='append', default=[], metavar='NAME:LOW-HIGH')
        pre.add_argument('--off', action='store_true')
        app = commands.add_parser('apply')
        app.add_argument('--yes', action='store_true')
        app.add_argument('--digest', required=True)
        commands.add_parser('show')
        commands.add_parser('candidates')
        args = parser.parse_args(argv)
        if args.action == 'show':
            return show()
        if args.action == 'candidates':
            print(json.dumps(candidates(), separators=(',', ':')))
            return 0
        if args.action == 'preview':
            installs = [install(item) for item in args.install]
            if args.off:
                values = {'consent': 'no', 'date': '', 'installs': []}
                if installs:
                    raise ValueError('off takes no installs')
            else:
                values = {'consent': 'yes', 'date': time.strftime('%Y-%m-%d'), 'installs': installs}
            preview(values)
        else:
            apply(args.digest, args.yes)
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print('Agent levels setup refused: invalid arguments, unsafe or changed file, or stale preview; preview again.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
