#!/usr/bin/env python3
"""Preview, apply or remove Claude Code's own deny rules for the afk credential floor (docs/specs/afk-decider.md D,
decision 6). It adds or removes only the fixed rules below in `permissions.deny` of the settings files the user names,
after a preview with a digest and a backup; every other key stays as it was. Blocking stays the host's job."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import compact_setup as common
import data_root as dr

Refusal = common.Refusal
# The credential floor as Claude Code permission rules; tests keep this list equal to afk.py's FLOOR_RULES.
FLOOR_RULES = ('Read(~/.netrc)', 'Read(~/.git-credentials)', 'Read(~/.npmrc)', 'Read(~/.pypirc)', 'Read(~/.pgpass)',
               'Read(~/.ssh/**)', 'Read(~/.aws/**)', 'Read(~/.azure/**)', 'Read(~/.gnupg/**)', 'Read(~/.kube/**)',
               'Read(~/.docker/config.json)', 'Read(~/.config/gh/**)', 'Read(**/.env)', 'Read(**/.env.local)',
               'Read(**/.dev.vars)', 'Bash(printenv:*)', 'Bash(env)', 'Bash(security:*)', 'Bash(gh auth token:*)',
               'Bash(op:*)', 'Bash(pass:*)', 'Bash(vault:*)')
STATE = 'state/afk-native-rules'


def settings(raw):
    data = json.loads(raw, object_pairs_hook=common.json_object,
                      parse_float=common.json_float, parse_constant=common.json_constant) if raw is not None else {}
    if not isinstance(data, dict):
        raise Refusal('settings must be a JSON object')
    return data


def transform(raw, remove):
    """The settings with the floor rules added to (or removed from) `permissions.deny`; raw unchanged when nothing
    changes. Any other permission entry and key is kept in place."""
    data = settings(raw)
    permissions = data.get('permissions', {})
    if not isinstance(permissions, dict):
        raise Refusal('permissions must be a JSON object')
    deny = permissions.get('deny', [])
    if not isinstance(deny, list) or not all(isinstance(rule, str) for rule in deny):
        raise Refusal('permissions.deny must be a list of rules')
    if remove:
        updated = [rule for rule in deny if rule not in FLOOR_RULES]
    else:
        updated = deny + [rule for rule in FLOOR_RULES if rule not in deny]
    if updated == deny:
        return raw
    permissions = dict(permissions)
    if updated:
        permissions['deny'] = updated
    else:
        permissions.pop('deny', None)
    data = dict(data)
    if permissions:
        data['permissions'] = permissions
    else:
        data.pop('permissions', None)
    return (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def preview(folders, remove=False):
    folders = folders or [dr.account_home() / '.claude']
    if not 1 <= len(folders) <= 4:
        raise Refusal('one to four config folders required')
    root = dr.consent_root()
    if root is None:
        raise Refusal('invalid data root')
    targets, displays, identities = [], [], set()
    for folder_path in folders:
        path = common.checked_path(str(Path(folder_path) / 'settings.json'), 'claude')
        with dr.relocated_folder(path.parent) as folder:
            info = os.fstat(folder)
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise Refusal('duplicate config folder')
            identities.add(identity)
            raw, mode = common.read_target(folder, path.name)
            result = transform(raw, remove)
            backup = common.backup_name(folder, path.name)
            targets.append({'path': str(path), 'sha256': common.content_hash(raw), 'mode': mode, 'backup': backup})
            displays.append((path, raw, result, backup))
    plan = {'created': time.time(), 'root': str(root), 'remove': remove, 'rules': list(FLOOR_RULES), 'targets': targets}
    value = common.digest(plan)
    with dr.data_folder(STATE, create=True, private=True) as state:
        try:
            common.read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, 'preview.json', json.dumps({'plan': plan, 'digest': value}).encode())
    for path, raw, result, backup in displays:
        print(f"Target: {path}\nExists: {'yes' if raw is not None else 'no'}")
        print(('Remove from' if remove else 'Add to') + ' permissions.deny: ' + ', '.join(FLOOR_RULES))
        print('Change: ' + ('none' if result == raw else 'yes'))
        print(f'Backup: {path.parent / backup}' + (' (not needed)' if raw is None or result == raw else ''))
    print('Claude Code then refuses these reads and commands in every session of that config folder, '
          'with or without an afk lease.')
    print('Digest: ' + value)


def apply(value, yes):
    if not yes or not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', value):
        raise Refusal('clear yes and full 64-hex preview digest required')
    value = value.lower()
    with ExitStack() as stack:
        state = stack.enter_context(dr.data_folder(STATE, private=True))
        saved = json.loads(common.read_plan(state), object_pairs_hook=common.json_object,
                           parse_float=common.json_float, parse_constant=common.json_constant)
        if (not isinstance(saved, dict) or set(saved) != {'plan', 'digest'}
                or saved['digest'] != value or common.digest(saved['plan']) != value):
            raise Refusal('digest mismatch; preview again')
        plan = saved['plan']
        if (not isinstance(plan, dict) or set(plan) != {'created', 'root', 'remove', 'rules', 'targets'}
                or type(plan['remove']) is not bool or plan['rules'] != list(FLOOR_RULES)):
            raise Refusal('invalid or changed plan; preview again')
        if plan['root'] != str(dr.consent_root()):
            raise Refusal('data root changed; preview again')
        if type(plan['created']) not in (int, float) or not 0 <= time.time() - plan['created'] <= 3600:
            raise Refusal('preview expired; preview again')
        targets = plan['targets']
        if not isinstance(targets, list) or not 1 <= len(targets) <= 4:
            raise Refusal('invalid targets')
        ready, identities = [], set()
        for target in targets:
            if not isinstance(target, dict) or set(target) != {'path', 'sha256', 'mode', 'backup'}:
                raise Refusal('invalid target')
            path = common.checked_path(target['path'], 'claude')
            folder = stack.enter_context(dr.relocated_folder(path.parent))
            info = os.fstat(folder)
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise Refusal('duplicate config folder')
            identities.add(identity)
            raw, mode = common.read_target(folder, path.name)
            if common.content_hash(raw) != target['sha256'] or mode != target['mode']:
                raise Refusal('target changed; preview again')
            if (not isinstance(target['backup'], str)
                    or not re.fullmatch(r'settings\.json\.bak-\d{8}(?:-[1-9][0-9]*)?', target['backup'])):
                raise Refusal('invalid backup name')
            ready.append((folder, path, target, raw, mode, transform(raw, plan['remove'])))
        for folder, path, target, raw, mode, result in ready:
            if result == raw:
                print('No difference: ' + str(path))
                continue
            current, current_mode = common.read_target(folder, path.name)
            if current != raw or current_mode != mode:
                raise Refusal('target changed; preview again')
            if raw is not None:
                fd = os.open(target['backup'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            common.write_target(folder, path.name, result, mode if raw is not None else 0o600)
            print(f'Updated: {path}')
        os.unlink('preview.json', dir_fd=state)
        os.fsync(state)


def main():
    try:
        parser = common.Parser(description=__doc__)
        commands = parser.add_subparsers(dest='action', required=True)
        pre = commands.add_parser('preview')
        pre.add_argument('--folder', action='append', default=[])
        pre.add_argument('--remove', action='store_true')
        app = commands.add_parser('apply')
        app.add_argument('--digest', required=True)
        app.add_argument('--yes', action='store_true')
        args = parser.parse_args()
        if args.action == 'preview':
            preview(args.folder, args.remove)
        else:
            apply(args.digest, args.yes)
        return 0
    except Refusal as error:
        print('afk native rules refused: ' + str(error), file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print('afk native rules refused: unsafe, unreadable or invalid file or plan', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
