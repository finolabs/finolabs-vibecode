#!/usr/bin/env python3
"""The afk overlay (docs/specs/afk-overlay.md): a local `AGENTS.afk.md` of override entries the owner approved.

Shared by the session-start hook, `afk.py start` and `stop`, and `instructions_write.py`. The reader prints the file
only while it is in force: a regular file at the top of the repository's main checkout, owned by the user, not group-
or world-writable, at most 8 KiB, not in the Git index, and whose SHA-256 equals the trust anchor that
`instructions_write.py` wrote after the owner's yes. It runs no Git process and sends nothing anywhere.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import unicodedata

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root as dr
import git_metadata
import project_store as store

NAME = 'AGENTS.afk.md'
EXCLUDE = b'AGENTS.afk.md*'
STATE = 'state/afk-overlay'
BACKUPS = 'state/afk-overlay/backups'
LIMIT = 8192
INDEX_LIMIT = 64 * 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}')
OFF = 'FNL_AFK_OVERLAY'

HEADER = ('afk overlay in force (AGENTS.afk.md, approved by the owner): while this lease is live, the rules it names '
          'replace those rules of this repository; every other rule still holds, and afk check stays the last gate.')
FOOTER = 'End of the afk overlay.'
NOT_IN_FORCE = ('An afk overlay is here but not in force (changed since setup or unsafe): ask before the actions it '
                'names, or run /setup add afk.')
STOPPED = "The afk overlay is no longer in force: the repository's normal instructions apply again."


def is_name(name):
    """True for `AGENTS.afk.md` and its backups in any letter case (case-insensitive file systems fold `ſ` too)."""
    return isinstance(name, str) and unicodedata.normalize('NFKC', name).casefold().startswith(NAME.casefold())


CONTROL = re.compile('[\x00-\x08\x0b-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]')


def unsafe_text(text):
    """True when overlay text holds control, escape or bidirectional characters (tab and newline are fine)."""
    return bool(CONTROL.search(text))


def disabled():
    return os.environ.get(OFF, '').strip().lower() == 'off'


def repository(cwd):
    """The validated Identity of the working folder's repository, else None (absent or unknown: no overlay)."""
    found, ident = store.identity(str(cwd))
    return ident if found == 'found' else None


def anchor_name(ident):
    return store.identity_digest(ident.main) + '.json'


def read_anchor(ident):
    """The recorded SHA-256, or None when there is no record. A record of any other shape raises."""
    try:
        with dr.data_folder(STATE, private=True) as folder:
            raw = dr.read_file(folder, anchor_name(ident), 4096)
    except FileNotFoundError:
        return None
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {'sha256', 'time'} or not isinstance(value['sha256'], str)
            or not HEX.fullmatch(value['sha256']) or type(value['time']) not in (int, float)
            or not math.isfinite(value['time'])):
        raise ValueError('afk overlay record is invalid')
    return value['sha256']


def write_anchor(ident, data):
    record = json.dumps({'sha256': hashlib.sha256(data).hexdigest(), 'time': time.time()}).encode()
    with dr.data_folder(STATE, create=True, private=True) as folder:
        dr.atomic_write(folder, anchor_name(ident), record)


def read_overlay(ident):
    """The bytes of `<main>/AGENTS.afk.md` read once through one no-follow descriptor, None when absent.

    `git_metadata.opened` refuses links and a leaf that is not a regular file owned by the user or that is group- or
    world-writable; the size is checked on that same descriptor.
    """
    path = Path(ident.main) / NAME
    try:
        os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return None
    with git_metadata.opened(path) as fd:
        if os.fstat(fd).st_size > LIMIT:
            raise ValueError('afk overlay is over the size cap')
        chunks, size = [], 0
        while size <= LIMIT:
            chunk = os.read(fd, LIMIT + 1 - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    data = b''.join(chunks)
    if len(data) > LIMIT:
        raise ValueError('afk overlay is over the size cap')
    return data


def _varint(raw, offset):
    """Git's offset varint (index v4 path prefix lengths)."""
    byte = raw[offset]
    offset += 1
    value = byte & 0x7f
    while byte & 0x80:
        byte = raw[offset]
        offset += 1
        value = ((value + 1) << 7) | (byte & 0x7f)
    return value, offset


def index_paths(raw):
    """Every path of a Git index (versions 2 to 4, SHA-1). A split index or any doubt raises."""
    if len(raw) < 32 or raw[:4] != b'DIRC':
        raise ValueError('not a git index')
    version, count = struct.unpack('>II', raw[4:12])
    if version not in (2, 3, 4):
        raise ValueError('unsupported git index version')
    end = len(raw) - 20
    offset, previous, paths = 12, b'', []
    for _ in range(count):
        start = offset
        if offset + 62 > end:
            raise ValueError('truncated git index')
        flags = struct.unpack('>H', raw[offset + 60:offset + 62])[0]
        offset += 62
        if flags & 0x4000:
            if version < 3:
                raise ValueError('extended flags in a version 2 index')
            offset += 2
        if version == 4:
            strip, offset = _varint(raw, offset)
            if strip > len(previous):
                raise ValueError('bad index path prefix')
            stop = raw.index(b'\x00', offset, end)
            path = previous[:len(previous) - strip] + raw[offset:stop]
            offset = stop + 1
        else:
            stop = raw.index(b'\x00', offset, end)
            path = raw[offset:stop]
            offset = start + ((stop - start) // 8 + 1) * 8
        if offset > end:
            raise ValueError('truncated git index')
        paths.append(path)
        previous = path
    while offset + 8 <= end:
        signature = raw[offset:offset + 4]
        size = struct.unpack('>I', raw[offset + 4:offset + 8])[0]
        if signature == b'link':
            raise ValueError('split git index is not supported')
        offset += 8 + size
    if offset != end:
        raise ValueError('bad git index extensions')
    return paths


def tracked(ident):
    """True when the index of the main checkout lists `AGENTS.afk.md` (any letter case); no index means False."""
    index = Path(ident.common) / 'index'
    try:
        os.stat(index, follow_symlinks=False)
    except FileNotFoundError:
        return False
    raw = git_metadata.bounded(index, INDEX_LIMIT)
    return NAME.casefold() in {path.decode('utf-8', 'replace').casefold() for path in index_paths(raw)}


def state(cwd):
    """('none'|'in-force'|'not-in-force', text). 'none': no repository, no file or the off switch."""
    if disabled():
        return 'none', None
    ident = repository(cwd)
    if ident is None:
        return 'none', None
    try:
        data = read_overlay(ident)
    except (OSError, ValueError):
        return 'not-in-force', None
    if data is None:
        return 'none', None
    try:
        recorded = read_anchor(ident)
        if recorded is None or tracked(ident) or hashlib.sha256(data).hexdigest() != recorded:
            return 'not-in-force', None
        text = data.decode('utf-8')
        if unsafe_text(text):
            return 'not-in-force', None
    except (OSError, ValueError, UnicodeError, IndexError, struct.error):
        return 'not-in-force', None
    return 'in-force', text


def lines(cwd):
    """The text to print while a lease is live: the framed overlay, the fixed not-in-force line, or nothing."""
    kind, text = state(cwd)
    if kind == 'in-force':
        return HEADER + '\n' + text.rstrip('\n') + '\n' + FOOTER + '\n'
    if kind == 'not-in-force':
        return NOT_IN_FORCE + '\n'
    return ''


def present(cwd):
    """True when the main checkout holds a file of the overlay's name (for the stop line); False on any doubt."""
    try:
        ident = repository(cwd)
        return ident is not None and os.path.lexists(Path(ident.main) / NAME)
    except (OSError, ValueError):
        return False


def _section(text, heading):
    found, inside = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            inside = line.rstrip() == '## ' + heading
            continue
        if inside:
            found.append(line)
    return found


def mode(ident):
    """`open` or `strict` for this repository, as afk.py resolves it: the user's `## afk` `- Mode:` line (absent
    means open), replaced by an approved, bound repository `autopilot` `mode`. Any doubt raises."""
    text = dr.read_data('host.md', 262144).decode('utf-8')
    if sum(line.rstrip() == '## afk' for line in text.splitlines()) != 1:
        raise ValueError('afk setup is missing or ambiguous')
    values = [m[1] for m in (re.fullmatch(r'- Mode: (.+)', line) for line in _section(text, 'afk')) if m]
    if len(values) > 1 or values and values[0] not in ('open', 'strict'):
        raise ValueError('afk mode is invalid')
    result = values[0] if values else 'open'
    found, settings, _, record = store.autopilot_binding(ident)
    project = settings.get('autopilot') if found == 'approved' else None
    if (isinstance(project, dict) and 'mode' in project and store.valid_autopilot(project)
            and store.bound(record, ident) and record.get('target') == store.origin_target(ident)):
        result = project['mode']
    return result


def write_refused(ident):
    """A reason the overlay may not be written now, else None. While a lease is live only an `open` repository may
    write it; an unreadable lease, data root or mode fails closed."""
    try:
        import away_lease
        live = away_lease.live_lease(time.time())
    except Exception:
        return 'the away lease state cannot be read'
    if live is None:
        return None
    try:
        return None if mode(ident) == 'open' else 'an away lease is live in strict mode; stop it first'
    except Exception:
        return 'the afk mode of this repository cannot be read while a lease is live'


def ensure_excluded(ident):
    """Add `AGENTS.afk.md*` to the main checkout's `.git/info/exclude` once; True when present afterwards."""
    common = Path(ident.common)
    if common != Path(ident.main) / '.git':
        return False
    with git_metadata.opened(common, directory=True) as git:
        try:
            os.mkdir('info', 0o755, dir_fd=git)
        except FileExistsError:
            pass
        info = os.open('info', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=git)
        try:
            if os.fstat(info).st_uid != os.getuid() or os.fstat(info).st_mode & 0o022:
                return False
            try:
                raw = dr.read_file(info, 'exclude', 262144)
                current = stat.S_IMODE(os.stat('exclude', dir_fd=info, follow_symlinks=False).st_mode)
            except FileNotFoundError:
                raw, current = b'', 0o644
            if EXCLUDE in {line.strip() for line in raw.splitlines()}:
                return True
            if raw and not raw.endswith(b'\n'):
                raw += b'\n'
            dr.atomic_write(info, 'exclude', raw + EXCLUDE + b'\n')
            fd = os.open('exclude', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=info)
            try:
                os.fchmod(fd, current)
            finally:
                os.close(fd)
            return True
        finally:
            os.close(info)


def backup(data):
    """Keep a replaced overlay in the private state, never beside the file; returns the backup name."""
    with dr.data_folder(BACKUPS, create=True, private=True) as folder:
        name = time.strftime('%Y%m%d-%H%M%S') + '-' + os.urandom(4).hex() + '.md'
        dr.atomic_write(folder, name, data)
        return name


if __name__ == '__main__':
    # `status`: one word for `/setup check` (none, in-force or not-in-force); prints no file text or path.
    if sys.argv[1:] != ['status']:
        print('usage: afk_overlay.py status', file=sys.stderr)
        raise SystemExit(2)
    try:
        print(state(os.getcwd())[0])
    except Exception:
        print('not-in-force')
