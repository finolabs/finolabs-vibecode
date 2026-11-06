#!/usr/bin/env python3
"""Preview and install the optional Antigravity compaction stop."""
from contextlib import ExitStack
import difflib
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import compact_setup as cs
import data_root as dr

GROUP = 'finolabs-vibecode-compact-stop'
STATE = 'state/compact-stop-setup'


def validate_choice(host, limit):
    if host != 'antigravity':
        raise cs.Refusal('Antigravity only; Claude Code and Codex use compact_setup.py')
    if limit is not None and (type(limit) is not int or not 50000 <= limit <= 20000000):
        raise cs.Refusal('limit must be an integer from 50000 to 20000000 bytes')


INSTALLED_COPY = '.gemini/config/plugins/finolabs-vibecode'


def check_plugin_root(root):
    """The folder holding the hook script must be safe. A git work tree is refused, except the plugin's own
    entry in Antigravity's installed copy, which keeps the repository's .git directory: only that exact
    unresolved path, reached without a symlink, with a clean parent chain and a real .git directory."""
    try:
        with dr.relocated_folder(root):
            return
    except ValueError as error:
        if str(error) != 'root is a git work tree':
            raise  # a .git in any folder above, a symlink, a wrong owner or a writable folder
    if root != dr.account_home() / INSTALLED_COPY:
        raise cs.Refusal('plugin folder is inside a git work tree; use the installed copy of the plugin')
    with dr.relocated_folder(root.parent):
        pass  # every level above is a real folder, safely owned, writable only by the user, and has no .git
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise cs.Refusal('plugin folder is not private enough')
        if not stat.S_ISDIR(os.lstat('.git', dir_fd=fd).st_mode):
            raise cs.Refusal('plugin folder .git is not a directory')
    finally:
        os.close(fd)


def hook_command():
    root = Path(os.path.abspath(__file__)).parents[3]  # not resolved: a symlinked folder must be seen
    check_plugin_root(root)
    try:
        manifest = json.loads((root / '.claude-plugin/plugin.json').read_bytes())
    except (OSError, ValueError):
        raise cs.Refusal('install the whole finolabs-vibecode plugin') from None
    script = root / 'scripts/compact_stop_hook.py'
    if (not isinstance(manifest, dict) or manifest.get('name') != 'finolabs-vibecode'
            or not (root / 'scripts/metrics_hook.py').is_file() or not script.is_file()
            or script.resolve().parent != root / 'scripts'):
        raise cs.Refusal('install the whole finolabs-vibecode plugin')
    quoted = shlex.quote(str(script.resolve()))
    # Antigravity shell execution of hook commands remains unverified.
    return (f'[ -f {quoted} ] && python3 -I {quoted} --host antigravity --event PreInvocation'
            + " || echo '{}'")


def group(command):
    return {'PreInvocation': [{'type': 'command', 'command': command, 'timeout': 5}]}


def hooks_path():
    return dr.account_home() / '.gemini/config/hooks.json'


def backup_name(folder, name):
    base = name + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
    number = 1
    while True:
        candidate = base + f'-{number}'
        try:
            os.lstat(candidate, dir_fd=folder)
        except FileNotFoundError:
            return candidate
        number += 1


def hooks_change(raw, command, remove):
    """Replace only this top-level member; retain every other member's bytes."""
    text = raw.decode('utf-8') if raw is not None else '{}\n'
    decoder = json.JSONDecoder(object_pairs_hook=cs.json_object, parse_float=cs.json_float,
                               parse_constant=cs.json_constant)
    data = decoder.decode(text)
    if not isinstance(data, dict):
        raise cs.Refusal('JSON must be an object')
    own = None if remove else json.dumps(group(command), separators=(',', ':'), ensure_ascii=True)
    start = text.index('{') + 1
    pos, members = start, []
    # The complete strict parse above validates punctuation and duplicate keys.
    while True:
        key_start = pos
        while text[key_start].isspace():
            key_start += 1
        if text[key_start] == '}':
            suffix = text[pos:]
            break
        key, key_end = decoder.raw_decode(text, key_start)
        value_start = key_end
        while text[value_start].isspace():
            value_start += 1
        value_start += 1  # colon
        while text[value_start].isspace():
            value_start += 1
        _, end = decoder.raw_decode(text, value_start)
        after = end
        while text[after].isspace():
            after += 1
        member = text[pos:after]
        if key != GROUP:
            members.append(member)
        elif own is not None:
            members.append(text[pos:value_start] + own + text[end:after])
        if text[after] == '}':
            suffix = text[after:]
            break
        pos = after + 1
    if GROUP not in data and own is not None:
        members.append('\n  ' + json.dumps(GROUP) + ': ' + own + '\n')
    if remove and GROUP not in data:
        return raw
    return (text[:start] + ','.join(members) + suffix).encode('utf-8')


def section(limit):
    return ('## Compaction stop\n\nEnabled: ' + ('no' if limit is None else 'yes')
            + ('\n' if limit is None else f'\nLimit bytes: {limit}\n') + '\n')


def host_change(raw, limit):
    # Same fenced-heading handling as quota_setup, without loading its probe.
    text = raw.decode('utf-8') if raw is not None else ''
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
            headings.append((offset, line.strip()))
        offset += len(line)
    matches = [i for i, (_, title) in enumerate(headings) if title == '## Compaction stop']
    if len(matches) > 1:
        raise cs.Refusal('duplicate compaction stop section')
    newline = '\r\n' if '\r\n' in text else '\n'
    new = section(limit).replace('\n', newline)
    if matches:
        i = matches[0]
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        result = text[:headings[i][0]] + new + text[end:]
    else:
        separator = newline * (2 if not text.endswith(newline) else 1) if text and not text.endswith(newline * 2) else ''
        result = text + separator + new
    if len(result.encode()) > 262144:
        raise cs.Refusal('host file too large')
    return result.encode()


def checked_root():
    root = dr.consent_root()
    if root is None:
        raise cs.Refusal('invalid data root')
    # Validate existing ancestors without creating anything during preview.
    ancestor = root
    while not os.path.lexists(ancestor):
        ancestor = ancestor.parent
    with dr.relocated_folder(ancestor):
        pass
    return root


def read_host():
    try:
        with dr.root_folder() as folder:
            return cs.read_target(folder, 'host.md')
    except FileNotFoundError:
        return None, 0o600


def preview(host, limit):
    validate_choice(host, limit)
    root = checked_root()
    command = hook_command() if limit is not None else None  # removal needs no script, so a missing folder cannot block it
    path = hooks_path()
    with dr.relocated_folder(path.parent) as folder:
        raw, mode = cs.read_target(folder, path.name)
        backup = backup_name(folder, path.name)
    old_host, host_mode = read_host()
    new_host = host_change(old_host, limit)
    new_hooks = hooks_change(raw, command, limit is None)
    plan = {'host': host, 'limit': limit, 'created': time.time(), 'root': str(root),
            'path': str(path), 'sha256': cs.content_hash(raw), 'mode': mode, 'backup': backup,
            'host_sha256': cs.content_hash(old_host), 'host_mode': host_mode, 'command': command}
    value = cs.digest(plan)
    with dr.data_folder(STATE, create=True, private=True) as state:
        try:
            cs.read_plan(state)
        except FileNotFoundError:
            pass
        dr.atomic_write(state, 'preview.json', json.dumps({'plan': plan, 'digest': value}).encode())
    # Show only our hooks group: a changed line may contain other groups' secrets.
    print('Target: ' + str(path))
    for label, content in (('Before', raw), ('After', new_hooks)):
        data = json.loads(content) if content is not None else {}
        print(label + ' group: ' + GROUP)
        print(json.dumps(data.get(GROUP), indent=2, ensure_ascii=True))
    print('Other groups (unchanged): ' + json.dumps(
        [name for name in data if name != GROUP], ensure_ascii=True))
    for label, before, after in ((str(root / 'host.md'), old_host, new_host),):
        print('Target: ' + label)
        if before == after:
            print('No difference.')
        else:
            print(''.join(difflib.unified_diff((before or b'').decode().splitlines(keepends=True),
                                             (after or b'').decode().splitlines(keepends=True),
                                             fromfile='before', tofile='after', n=0)), end='\n')
    print('Group: ' + GROUP + '\nCommand: ' + (command if command is not None else '(removal)'))
    print('Limit bytes: ' + (str(limit) if limit is not None else 'removed'))
    print('A byte proxy only; the system prompt is not counted. No default is recommended.')
    print('Backup: ' + str(path.parent / backup))
    print('Digest: ' + value)


def apply(value, yes):
    if not yes or not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', value):
        raise cs.Refusal('clear yes and full 64-hex preview digest required')
    value = value.lower()
    with ExitStack() as stack:
        state = stack.enter_context(dr.data_folder(STATE, private=True))
        fcntl.flock(state, fcntl.LOCK_EX | fcntl.LOCK_NB)
        saved = json.loads(cs.read_plan(state))
        if (not isinstance(saved, dict) or set(saved) != {'plan', 'digest'}
                or saved['digest'] != value or cs.digest(saved['plan']) != value):
            raise cs.Refusal('digest mismatch; preview again')
        plan = saved['plan']
        if not isinstance(plan, dict) or set(plan) != {'host', 'limit', 'created', 'root', 'path', 'sha256', 'mode', 'backup', 'host_sha256', 'host_mode', 'command'}:
            raise cs.Refusal('invalid plan')
        validate_choice(plan['host'], plan['limit'])
        if plan['root'] != str(checked_root()) or plan['command'] != (hook_command() if plan['limit'] is not None else None):
            raise cs.Refusal('root or command changed; preview again')
        if type(plan['created']) not in (int, float) or not 0 <= time.time() - plan['created'] <= 3600:
            raise cs.Refusal('preview expired; preview again')
        path = hooks_path()
        if plan['path'] != str(path):
            raise cs.Refusal('invalid target path; preview again')
        folder = stack.enter_context(dr.relocated_folder(path.parent))
        host_folder = stack.enter_context(dr.root_folder())
        fcntl.flock(host_folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw, mode = cs.read_target(folder, path.name)
        old_host, host_mode = cs.read_target(host_folder, 'host.md')
        if (cs.content_hash(raw) != plan['sha256'] or mode != plan['mode']
                or cs.content_hash(old_host) != plan['host_sha256'] or host_mode != plan['host_mode']):
            raise cs.Refusal('target changed; preview again')
        if not re.fullmatch(re.escape(path.name) + r'\.bak-[0-9]{8}-[0-9]{6}-[1-9][0-9]*', plan['backup']):
            raise cs.Refusal('invalid backup name')
        new_host = host_change(old_host, plan['limit'])
        new_hooks = hooks_change(raw, plan['command'], plan['limit'] is None)
        if raw is not None and new_hooks != raw:
            # Exclusive creation refuses an existing backup before changing host.md.
            fd = os.open(plan['backup'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), mode & 0o600)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        cs.write_target(host_folder, 'host.md', new_host, host_mode)
        if new_hooks != raw:
            cs.write_target(folder, path.name, new_hooks, mode)
        os.unlink('preview.json', dir_fd=state)
        os.fsync(state)
    print('Compaction stop configuration saved.')


def main():
    try:
        parser = cs.Parser(description=__doc__)
        commands = parser.add_subparsers(dest='action', required=True)
        pre = commands.add_parser('preview')
        pre.add_argument('--host', default='antigravity')
        choice = pre.add_mutually_exclusive_group(required=True)
        choice.add_argument('--limit', type=int)
        choice.add_argument('--remove', action='store_true')
        app = commands.add_parser('apply')
        app.add_argument('--digest', required=True)
        app.add_argument('--yes', action='store_true')
        args = parser.parse_args()
        if args.action == 'preview':
            preview(args.host, args.limit)
        else:
            apply(args.digest, args.yes)
        return 0
    except cs.Refusal as error:
        print('Compaction stop setup refused: ' + str(error), file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        print('Compaction stop setup refused: unsafe, unreadable or invalid file or plan', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
