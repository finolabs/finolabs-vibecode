#!/usr/bin/env python3
"""Read host settings as JSON; show sources or set confirmed sections, always exit 0."""

import argparse
import json
import os
import re
import stat
from pathlib import Path

DEFAULTS = {"delegation_mode": "suggest", "routing": "on", "auto_gate": "off"}
SETTINGS = {"delegation_mode": ("Delegation mode", "FNL_DELEGATION_MODE", {"manual", "suggest", "auto"}),
            "routing": ("Routing", "FNL_ROUTING", {"on", "off"}),
            "auto_gate": ("Auto gate", "FNL_AUTO_GATE", {"on", "off"})}
MAX_BYTES = 262144


def config_path():
    """The override, else the default file, else the older XDG file while only that one exists."""
    explicit = os.environ.get("ORCHESTRATION_HOST_CONFIG")
    path = Path(os.path.abspath(os.path.expanduser(explicit or "~/.finolabs/vibecode/host.md")))
    if not explicit and not os.path.lexists(path):
        xdg = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
        return Path(os.path.abspath(os.path.expanduser(xdg))) / "finolabs-vibecode/host.md"
    return path


def host_text():
    """Bounded regular Markdown file only; refuse symlinks in every component."""
    path = config_path()
    if path.suffix.lower() != ".md" or any(
        p.lower().startswith((".env", "credentials", "secrets")) or
        p.lower() in {".aws", ".ssh", ".gnupg"} for p in path.parts
    ):
        return ""
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:]):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(path.parts) - 2:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return ""
        data = os.read(fd, MAX_BYTES + 1)
        return data.decode("utf-8") if len(data) <= MAX_BYTES else ""
    finally:
        os.close(fd)


def gate_host_text():
    """Read opt-in only from the account home, without creating any folders."""
    import pwd

    home = pwd.getpwuid(os.getuid()).pw_dir
    if not os.path.isabs(home):
        raise ValueError("home must be absolute")
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise ValueError("foreign home")
        for part in (".finolabs", "vibecode", "host.md"):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if part != "host.md":
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid != os.getuid():
                raise ValueError("foreign config component")
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return ""
        data = os.read(fd, MAX_BYTES + 1)
        return data.decode("utf-8") if len(data) <= MAX_BYTES else ""
    finally:
        os.close(fd)


def effective(details=False, keys=None, gate_opt_in=False):
    values = {key: DEFAULTS[key] for key in (DEFAULTS if keys is None else keys)}
    sources = {}
    overridden = {}
    try:
        text = gate_host_text() if gate_opt_in else host_text()
    except (OSError, UnicodeError, ValueError):
        text = ""
    # Ignore examples in fenced blocks, then collect complete second-level sections.
    text = re.sub(r"^```.*?^```[^\n]*$", "", text, flags=re.M | re.S)
    parts = re.split(r"^## (.+?)\s*$", text, flags=re.M)
    for key in values:
        heading, variable, allowed = SETTINGS[key]
        sections = [parts[i + 1].strip() for i in range(1, len(parts), 2) if parts[i] == heading]
        override = variable in os.environ
        env_value = os.environ.get(variable, "")
        if key == "auto_gate":
            # The environment is an off switch, never an opt-in.
            override = env_value.lower() in {"off", "0", "false", "no"}
            env_value = "off"
        overridden[key] = override
        raw = env_value if override else sections[0] if len(sections) == 1 else ""
        if raw in allowed:
            values[key] = raw
        sources[key] = (variable + (" (invalid; default used)" if raw not in allowed else "")
                        if override else "host config" if raw in allowed else "default")
    return {key: {"value": value, "source": sources[key],
                  "file_overridden": overridden[key]}
            for key, value in values.items()} if details else values


def replace_section(text, heading, body):
    """Replace a unique level-two section, preserving all bytes outside it."""
    pattern = re.compile(rb"^## " + re.escape(heading.encode()) + rb"[ \t]*\r?$.*?(?=^#{1,2} |\Z)", re.M | re.S)
    matches = list(pattern.finditer(text))
    if len(matches) > 1:
        raise ValueError("duplicate heading")
    newline = b"\r\n" if b"\r\n" in text else b"\n"
    section = ("## " + heading + "\n\n" + body.strip() + "\n\n").encode().replace(b"\n", newline)
    if matches:
        match = matches[0]
        return text[:match.start()] + section + text[match.end():]
    return text + (newline if text and not text.endswith(newline * 2) else b"") + section


def atomic_write(path, transform):
    """Anchor traversal and replacement to directory descriptors; refuse every symlink."""
    path = Path(os.path.abspath(path))
    if path.suffix.lower() != ".md" or any(
        p.lower().startswith((".env", "credentials", "secrets")) or
        p.lower() in {".aws", ".ssh", ".gnupg"} for p in path.parts
    ):
        raise ValueError("excluded path")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    temporary = None
    try:
        for part in path.parts[1:-1]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        try:
            source = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            old = b""
            permissions = 0o600
        else:
            try:
                info = os.fstat(source)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                    raise ValueError("not a bounded regular file")
                old = os.read(source, MAX_BYTES + 1)
                old.decode("utf-8")
                if len(old) > MAX_BYTES:
                    raise ValueError("file too large")
                permissions = stat.S_IMODE(info.st_mode)
            finally:
                os.close(source)
        new = transform(old)
        if new == old:
            return False
        # Random name, exclusive creation in the already opened parent.
        temporary = ".host-" + os.urandom(12).hex()
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         permissions, dir_fd=fd)
        with os.fdopen(target, "wb") as stream:
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        # Recheck the final component before replacing it.
        try:
            if stat.S_ISLNK(os.stat(path.name, dir_fd=fd, follow_symlinks=False).st_mode):
                raise ValueError("symlink refused")
        except FileNotFoundError:
            pass
        os.replace(temporary, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        temporary = None
        os.fsync(fd)
        return True
    finally:
        if temporary:
            os.unlink(temporary, dir_fd=fd)
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("show", "set"), nargs="?")
    parser.add_argument("--delegation-mode", choices=sorted(SETTINGS["delegation_mode"][2]))
    parser.add_argument("--routing", choices=("on", "off"))
    parser.add_argument("--auto-gate", choices=("on", "off"))
    parser.add_argument("--yes", action="store_true", help="write only after the user confirmed the shown change")
    try:
        args = parser.parse_args()
        if args.action is None:
            print(json.dumps(effective()))
        else:
            state = effective(details=True)
            for key, row in state.items():
                proposed = getattr(args, key) if args.action == "set" else None
                print(f'{SETTINGS[key][0]}: {row["value"]}' +
                      (f' -> {proposed}' if proposed else "") + f' (source: {row["source"]})')
                if row["file_overridden"]:
                    print(f'{SETTINGS[key][1]} overrides the file; writing the file has no effect while it is set.')
            if args.action == "set":
                changes = {k: getattr(args, k) for k in SETTINGS if getattr(args, k)}
                if not changes:
                    print("No change requested.")
                elif not args.yes:
                    print("Preview only; a clear yes is required before writing.")
                else:
                    path = config_path()
                    if not os.path.lexists(path) and "ORCHESTRATION_HOST_CONFIG" not in os.environ:
                        path = Path(os.path.abspath(os.path.expanduser("~/.finolabs/vibecode/host.md")))
                    def update(text):
                        for key, value in changes.items():
                            text = replace_section(text, SETTINGS[key][0], value)
                        return text
                    print("Updated host settings." if atomic_write(path, update) else "No difference.")
    except SystemExit:
        pass
    except (OSError, UnicodeError, ValueError):
        print("Settings unavailable or unsafe path; nothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
