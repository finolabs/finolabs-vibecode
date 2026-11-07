#!/usr/bin/env python3
"""Local rule 4–6 log scanner. Never reproduce a finding in diagnostics."""
import argparse
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import run_env
import secret_patterns as sp

STATUSES = ('no_findings', 'findings', 'not_scanned')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        print('not_scanned')
        raise SystemExit(2)


def run_log_folder():
    return Path.cwd() / '.finolabs' / 'logs'


@contextmanager
def folder_descriptor(root=None):
    root = Path(root) if root is not None else run_log_folder()
    if not root.is_absolute() or '..' in root.parts:
        raise ValueError('refused')
    # Resolve no symlink components, including the parent of the logs directory.
    fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(root.parts[1:]):
            if index >= len(root.parts) - 3:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if (info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode)
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError('refused')
        yield fd
    finally:
        os.close(fd)


def check_file(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
        raise ValueError('refused')
    return info


def same_file(folder, name, info):
    current = os.stat(name, dir_fd=folder, follow_symlinks=False)
    if (current.st_dev, current.st_ino, current.st_nlink, current.st_uid, current.st_size,
        current.st_mtime_ns, current.st_ctime_ns) != (
            info.st_dev, info.st_ino, 1, os.getuid(), info.st_size, info.st_mtime_ns, info.st_ctime_ns):
        raise ValueError('refused')


@contextmanager
def opened_log(path, root=None):
    root = Path(root) if root is not None else run_log_folder()
    path = Path(os.path.abspath(path))
    # Only immediate children, never resolve a path through an attacker-controlled symlink.
    if path.parent != root or path.name in ('.', '..'):
        raise ValueError('refused')
    with folder_descriptor(root) as folder:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
        try:
            info = check_file(fd)
            same_file(folder, path.name, info)
            yield folder, fd, info
        finally:
            os.close(fd)


def scan_descriptor(fd):
    info = check_file(fd)
    if info.st_size > sp.MAX_BYTES:
        return dict(status='not_scanned', hits=[], text=None, digest=None)
    os.lseek(fd, 0, os.SEEK_SET)
    chunks, size = [], 0
    while size <= sp.MAX_BYTES:
        chunk = os.read(fd, min(65536, sp.MAX_BYTES + 1 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
    raw = b''.join(chunks)
    after = check_file(fd)
    if (size > sp.MAX_BYTES or b'\0' in raw or
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns) !=
            (info.st_size, info.st_mtime_ns, info.st_ctime_ns)):
        return dict(status='not_scanned', hits=[], text=None, digest=None)
    try:
        text = raw.decode('utf-8')
        if any(ord(c) < 32 and c not in '\t\n\r\x1b' for c in text):
            raise ValueError()
    except (UnicodeError, ValueError):
        return dict(status='not_scanned', hits=[], text=None, digest=None)
    hits = sp.findings(text)
    return dict(status='findings' if hits else 'no_findings', hits=hits, text=text,
                digest=hashlib.sha256(raw).hexdigest())


def scan(path, root=None):
    """Guarded scan for ledger; an invalid file is a refusal, never a receipt."""
    with opened_log(path, root) as (folder, fd, info):
        result = scan_descriptor(fd)
        same_file(folder, Path(path).name, info)
        return result


def safe_view(result):
    if result['status'] == 'not_scanned':
        raise ValueError('refused')
    view = sp.redacted(result['text'], result['hits'])
    if sp.findings(view):
        raise ValueError('refused')
    return view


def is_open(path, own_fd):
    """Check descriptors without reading process arguments or environment."""
    if sys.platform.startswith('linux'):
        for process in Path('/proc').iterdir():
            if not process.name.isdigit():
                continue
            try:
                if process.stat().st_uid != os.getuid():
                    continue
                for entry in (process / 'fd').iterdir():
                    if int(process.name) == os.getpid() and int(entry.name) == own_fd:
                        continue
                    try:
                        if os.path.samefile(entry, path):
                            return True
                    except FileNotFoundError:
                        pass
            except FileNotFoundError:
                pass
        return False
    # lsof is a read-only descriptor query; it receives the same minimal allowlist.
    tool = '/usr/sbin/lsof'
    if not Path(tool).is_file():
        raise ValueError('refused')
    done = subprocess.run([tool, '-Fpf', '--', str(path)], capture_output=True,
                          timeout=5, env=run_env.environment())
    if done.returncode not in (0, 1):
        raise ValueError('refused')
    pid = None
    for line in done.stdout.decode('ascii', errors='strict').splitlines():
        if line.startswith('p'):
            pid = int(line[1:])
        elif line.startswith('f'):
            number = line[1:].rstrip('rwu')
            if pid != os.getpid() or number != str(own_fd):
                return True
    return False


def redact(path, *, yes=False, digest=None, root=None):
    with opened_log(path, root) as (folder, fd, info):
        if time.time() - info.st_mtime < 60 or is_open(Path(path), fd):
            raise ValueError('refused')
        result = scan_descriptor(fd)
        view = safe_view(result)
        if not yes:
            if digest is not None:
                raise ValueError('refused')
            same_file(folder, Path(path).name, info)
            return result
        if digest != result['digest']:
            raise ValueError('refused')
        temporary = '.redact-' + os.urandom(16).hex()
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         stat.S_IMODE(info.st_mode) & 0o600, dir_fd=folder)
        try:
            with os.fdopen(target, 'wb') as stream:
                os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode) & 0o600)
                stream.write(view.encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
            # Recheck descriptor and pathname immediately before publication.
            check_file(fd)
            same_file(folder, Path(path).name, info)
            if is_open(Path(path), fd):
                raise ValueError('refused')
            os.replace(temporary, Path(path).name, src_dir_fd=folder, dst_dir_fd=folder)
            os.fsync(folder)
        finally:
            try:
                os.unlink(temporary, dir_fd=folder)
            except FileNotFoundError:
                pass
        return result


def emit(result, index=1):
    print(f"{result['status']} file={index}")
    for hit in result['hits']:
        name = f" name={hit['name']}" if hit['name'] else ''
        print(f"{hit['kind']} file={index} line={hit['line']}{name}")


def main():
    parser = Parser(description=__doc__, allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    scan_parser = sub.add_parser('scan')
    scan_parser.add_argument('logs', nargs='+')
    show_parser = sub.add_parser('show')
    show_parser.add_argument('log')
    redact_parser = sub.add_parser('redact')
    redact_parser.add_argument('log')
    redact_parser.add_argument('--yes', action='store_true')
    redact_parser.add_argument('--digest')
    args = parser.parse_args()
    try:
        if args.command == 'scan':
            status = 0
            for index, path in enumerate(args.logs, 1):
                try:
                    result = scan(path)
                except (OSError, ValueError):
                    result = dict(status='not_scanned', hits=[])
                emit(result, index)
                status |= result['status'] != 'no_findings'
            return int(status)
        if args.command == 'show':
            result = scan(args.log)
            try:
                view = safe_view(result)
            except ValueError:
                print('not_scanned')
                return 2
            print(view, end='')
        else:
            result = redact(args.log, yes=args.yes, digest=args.digest)
            emit(result)
            if not args.yes:
                print('digest=' + result['digest'])
                print('transcript_stores: ~/.codex/sessions ~/.claude/projects')
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        print('not_scanned')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
