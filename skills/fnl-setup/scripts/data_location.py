#!/usr/bin/env python3
"""Preview or copy plugin data to an empty, account-owned local folder."""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

FILES = {"host.md", "ledger.jsonl"}
FOLDERS = {"state", "logs", "bin"}


def target_path(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("target must be absolute")
    current = path
    while not os.path.lexists(current):
        current = current.parent
    with dr.relocated_folder(current) as folder:
        if current == path and os.listdir(folder):
            raise ValueError("target must be empty")
    source = dr.consent_root()
    if source is None:
        raise ValueError("invalid data root")
    if path == source or source in path.parents or path in source.parents:
        raise ValueError("target must be separate from the source")
    return path


def file_hash(folder, name, output=None):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError("unsafe source file")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
            if output is not None:
                output.write(chunk)
    finally:
        os.close(fd)


def inventory(folder, prefix=Path()):
    result = {}
    for name in sorted(os.listdir(folder)):
        info = os.stat(name, dir_fd=folder, follow_symlinks=False)
        relative = prefix / name
        if stat.S_ISREG(info.st_mode) and (prefix.parts or name in FILES):
            result[str(relative)] = file_hash(folder, name)
        elif stat.S_ISDIR(info.st_mode) and (prefix.parts or name in FOLDERS):
            with dr.descend(folder, name) as child:
                result.update(inventory(child, relative))
    return result


def digest_for(target, files):
    body = json.dumps({"target": str(target), "files": files}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def preview(target):
    target = target_path(target)
    try:
        with dr.root_folder() as source:
            files = inventory(source)
    except FileNotFoundError:
        if os.path.lexists(dr.data_root()[0]):
            raise  # A disappearing source file is not an empty installation.
        files = {}
    return target, files, digest_for(target, files)


def apply(target, digest, yes=False):
    if not yes or not digest or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError("a clear yes and full 64-hex preview digest are required")
    target, files, expected = preview(target)
    if expected != digest.lower():
        raise ValueError("digest mismatch")
    # Validate the pointer size before creating or copying anything.
    identity = os.urandom(24).hex()
    if len(json.dumps({"root": str(target), "id": identity}).encode()) > dr.MAX_POINTER:
        raise ValueError("target is too long")
    with dr.relocated_folder(target, create=True) as destination:
        import fcntl
        fcntl.flock(destination, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if os.listdir(destination):
            raise ValueError("target must be empty")
        os.fchmod(destination, 0o700)
        if files:
            with dr.root_folder() as source:
                for relative, expected_hash in files.items():
                    path = Path(relative)
                    with dr.descend(source, path.parent) as old, dr.descend(
                            destination, path.parent, create=True) as new:
                        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=new)
                        with os.fdopen(fd, "wb") as stream:
                            copied_hash = file_hash(old, path.name, stream)
                            stream.flush()
                            os.fsync(stream.fileno())
                        if copied_hash != expected_hash:
                            raise ValueError("source changed during copy; pointer unchanged")
                if inventory(source) != files:
                    raise ValueError("source changed during copy; pointer unchanged")
        dr.atomic_write(destination, ".root-id", identity.encode())
        # Publish only after the copied bytes and root identity are durable.
        dr.write_pointer(target, identity)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "apply"))
    parser.add_argument("--to", required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--digest")
    args = parser.parse_args()
    try:
        if args.action == "preview":
            target, files, digest = preview(args.to)
            print("Target: " + str(target))
            for name in files:
                print(name)
            print("Digest: " + digest)
            print("Preview only; nothing written.")
        else:
            target = apply(args.to, args.digest, args.yes)
            print("Data root: " + str(target) + " (relocated)")
            print("The old folder is unchanged; remove it yourself when ready.")
    except (OSError, ValueError, UnicodeError) as error:
        print("Data location refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
