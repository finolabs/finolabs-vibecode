"""Account-owned plugin storage. Environment variables never select trusted data."""

import json
import os
import pwd
import stat
from contextlib import contextmanager
from pathlib import Path

MAX_POINTER = 1024


def account_home():
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    if not home.is_absolute():
        raise ValueError("home must be absolute")
    return home


def default_root():
    return account_home() / ".finolabs/vibecode"


def _directory(fd, *, ancestor=False, private=False):
    info = os.fstat(fd)
    owners = {0, os.getuid()} if ancestor else {os.getuid()}
    if not stat.S_ISDIR(info.st_mode) or info.st_uid not in owners or info.st_mode & 0o022:
        raise ValueError("unsafe folder")
    if private and stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("folder must be private")


def _parts(relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("relative path required")
    return path.parts


@contextmanager
def descend(parent, relative, *, create=False, private=False):
    fd = os.dup(parent)
    try:
        for part in _parts(relative):
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            _directory(fd)
        _directory(fd, private=private)
        yield fd
    finally:
        os.close(fd)


@contextmanager
def anchor_folder(*, create=False):
    # Account home is the fixed anchor, not HOME or an XDG override.
    fd = os.open(account_home(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _directory(fd)
        with descend(fd, ".finolabs/vibecode", create=create) as folder:
            yield folder
    finally:
        os.close(fd)


def read_file(folder, name, limit):
    if len(_parts(name)) != 1:
        raise ValueError("one filename required")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o022 or info.st_size > limit):
            raise ValueError("unsafe file")
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - size))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
        raise ValueError("file too large")
    finally:
        os.close(fd)


@contextmanager
def relocated_folder(path, *, create=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute root required")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _directory(fd, ancestor=True)
        for index, part in enumerate(path.parts[1:]):
            try:
                os.stat(".git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError("root is inside a git work tree")
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            _directory(fd, ancestor=index < len(path.parts) - 2)
        _directory(fd)
        try:
            os.stat(".git", dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("root is a git work tree")
        yield fd
    finally:
        os.close(fd)


def _pointer():
    # Only absence selects the default. Unsafe or unreadable anchors fail closed.
    with anchor_folder() as folder:
        raw = read_file(folder, "root.json", MAX_POINTER)
    pointer = json.loads(raw)
    if (not isinstance(pointer, dict) or set(pointer) != {"root", "id"}
            or not isinstance(pointer["root"], str) or not isinstance(pointer["id"], str)
            or not pointer["id"] or len(pointer["id"]) > 128):
        raise ValueError("invalid pointer")
    return pointer


def data_root():
    """Return (Path, default|relocated|invalid); invalid permits no consent."""
    default = default_root()
    try:
        pointer = _pointer()
    except FileNotFoundError:
        return default, "default"
    except (OSError, ValueError, UnicodeError):
        return default, "invalid"
    try:
        with relocated_folder(pointer["root"]) as folder:
            if read_file(folder, ".root-id", MAX_POINTER).decode("utf-8") != pointer["id"]:
                raise ValueError("root identity mismatch")
        return Path(pointer["root"]), "relocated"
    except (OSError, ValueError, UnicodeError):
        return default, "invalid"


def consent_root():
    root, source = data_root()
    return None if source == "invalid" else root


@contextmanager
def root_folder(*, create=False):
    root, source = data_root()
    if source == "invalid":
        raise ValueError("invalid data root")
    if source == "default":
        with anchor_folder(create=create) as folder:
            # Recheck after opening, so a newly published pointer is not ignored.
            try:
                os.stat("root.json", dir_fd=folder, follow_symlinks=False)
            except FileNotFoundError:
                yield folder
            else:
                raise ValueError("data root changed")
    else:
        with relocated_folder(root) as folder:
            pointer = _pointer()
            if (Path(pointer["root"]) != root
                    or read_file(folder, ".root-id", MAX_POINTER).decode() != pointer["id"]):
                raise ValueError("data root changed")
            yield folder


@contextmanager
def data_folder(relative=".", *, create=False, private=False):
    with root_folder(create=create) as root:
        with descend(root, relative, create=create, private=private) as folder:
            yield folder


def read_data(relative, limit=262144):
    path = Path(relative)
    with data_folder(path.parent) as folder:
        return read_file(folder, path.name, limit)


def atomic_write(folder, name, data):
    if len(_parts(name)) != 1:
        raise ValueError("one filename required")
    temporary = ".write-" + os.urandom(12).hex()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=folder)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=folder, dst_dir_fd=folder)
        os.fsync(folder)
    finally:
        try:
            os.unlink(temporary, dir_fd=folder)
        except FileNotFoundError:
            pass


def write_data(relative, data):
    path = Path(relative)
    with data_folder(path.parent, create=True) as folder:
        atomic_write(folder, path.name, data)


def write_pointer(root, identity):
    payload = json.dumps({"root": str(root), "id": identity}).encode()
    if len(payload) > MAX_POINTER:
        raise ValueError("pointer too large")
    with relocated_folder(root) as folder:
        if read_file(folder, ".root-id", MAX_POINTER).decode() != identity:
            raise ValueError("root identity mismatch")
    with anchor_folder(create=True) as folder:
        atomic_write(folder, "root.json", payload)
