#!/usr/bin/env python3
"""Preview and apply only the canonical host's Autopilot section; start no lease."""
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
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

# Kept local so setup remains independently installable. Round-trip tests
# bind these choices and bounds to delegate's authoritative settings().
DEFAULTS = {'Hosts': 'Claude Code', 'Task choice': 'choose', 'Push and pull requests': 'yes',
            'Trusted authors': 'own', 'Lease hours': 8, 'Max runs': 20,
            'Max runtime minutes': 480, 'Max actions per hour': 30, 'Quota floor percent': 15}
NUMBERS = {'Lease hours': (1, 24), 'Max runs': (1, 10000), 'Max runtime minutes': (1, 1440),
           'Max actions per hour': (1, 10000), 'Quota floor percent': (0, 100)}
# Closed categories of "Where it must stop" in docs/specs/away-decisions.md: name -> fixed at stop.
# Each is written explicitly; it is decide only when its own answer names it, and a fixed row never is.
CATEGORIES = {'Production': True, 'Real users and customer data': True, 'Unrecoverable deletion': False,
              'Messages outside the repository': False, 'Tags and releases': False, 'Publishing': False,
              'Shared settings': False, 'Recoverable deletion': False, 'Repository comments': False}
MOVABLE = tuple(name for name, fixed in CATEGORIES.items() if not fixed)
CONSENT = 'Excerpts leave the machine'
TARGETS = 'Non-production targets'
MAX_TARGETS = 20
CAP = sf.CAP
STATE = 'state/autopilot-setup'


def validate(values):
    if not isinstance(values, dict) or set(values) != {*DEFAULTS, 'Merge', *CATEGORIES, CONSENT, TARGETS}:
        raise ValueError('explicit Merge answer and all settings required')
    for key, value in values.items():
        if key in CATEGORIES:
            if value not in (('stop',) if CATEGORIES[key] else ('stop', 'decide')):
                raise ValueError('invalid category choice')
        elif key == CONSENT:
            if value not in ('yes', 'no'):
                raise ValueError('invalid consent')
        elif key == TARGETS:
            # The reader splits on '; ' and empties the whole list on any unreadable entry, so refuse those here.
            if (not isinstance(value, list) or len(value) > MAX_TARGETS or len(value) != len(set(value))
                    or not all(isinstance(e, str) and 0 < len(e) <= 200 and e == e.strip() and e.isprintable()
                               and '; ' not in e for e in value)):
                raise ValueError('invalid targets')
        elif key in NUMBERS:
            low, high = NUMBERS[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError('invalid limit')
        elif key == 'Hosts':
            if not isinstance(value, str):
                raise ValueError('invalid hosts')
            hosts = value.split(', ')
            if len(hosts) != len(set(hosts)) or not set(hosts) <= {'Claude Code', 'Codex', 'Antigravity'}:
                raise ValueError('invalid hosts')
        elif value not in {'Task choice': ('choose', 'listed'), 'Push and pull requests': ('yes', 'no'),
                            'Merge': ('yes', 'no'), 'Trusted authors': ('own',)}[key]:
            raise ValueError('invalid choice')


def render(values):
    validate(values)
    keys = ['Hosts', 'Task choice', 'Push and pull requests', 'Merge', 'Trusted authors', *NUMBERS, *CATEGORIES, CONSENT]
    lines = ''.join(f'- {key}: {values[key]}\n' for key in keys)
    if values[TARGETS]:  # an empty list is no line: the reader's default is empty
        lines += f'- {TARGETS}: ' + '; '.join(values[TARGETS]) + '\n'
    return '## Autopilot\n\n' + lines + '\n'


def transform(raw, values):
    text = raw.decode('utf-8') if raw is not None else ''
    headings, fence = sf.split(text)
    indexes = [i for i, (_, title) in enumerate(headings) if title == '## Autopilot']
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
    print('afk section saved; no lease started.')


def main(argv=None):
    try:
        parser = cs.Parser(description=__doc__)
        commands = parser.add_subparsers(dest='action', required=True)
        pre = commands.add_parser('preview')
        pre.add_argument('--hosts', nargs='+', choices=('Claude Code', 'Codex', 'Antigravity'), default=['Claude Code'])
        pre.add_argument('--task-choice', choices=('choose', 'listed'), default='choose')
        pre.add_argument('--push-and-pull-requests', choices=('yes', 'no'), default='yes')
        pre.add_argument('--merge', choices=('yes', 'no'), required=True)
        pre.add_argument('--trusted-authors', choices=('own',), default='own')
        for key in NUMBERS:
            pre.add_argument('--' + key.lower().replace(' ', '-'), type=int, default=DEFAULTS[key])
        pre.add_argument('--decide', action='append', choices=MOVABLE, default=[])
        pre.add_argument('--non-production-target', action='append', default=[])
        pre.add_argument('--excerpts-leave-the-machine', choices=('yes', 'no'), default='no')
        app = commands.add_parser('apply')
        app.add_argument('--yes', action='store_true')
        app.add_argument('--digest', required=True)
        args = parser.parse_args(argv)
        if args.action == 'preview':
            values = {key: getattr(args, key.lower().replace(' ', '_')) for key in (*DEFAULTS, 'Merge')}
            values['Hosts'] = ', '.join(args.hosts)
            values.update({c: 'decide' if c in args.decide else 'stop' for c in CATEGORIES})
            values[CONSENT] = args.excerpts_leave_the_machine
            values[TARGETS] = args.non_production_target
            preview(values)
        else:
            apply(args.digest, args.yes)
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print('afk setup refused:invalid arguments, unsafe or changed file, or stale preview; preview again.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
