#!/usr/bin/env python3
"""Local agent inventory: fixed --version calls, no model probes, preview unless --yes."""

import argparse
import datetime
import difflib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

MAX_BYTES = 262144
AGENTS = {"claude": "Claude Code", "codex": "Codex", "antigravity": "Antigravity"}
EXECUTABLES = {"claude": "claude", "codex": "codex", "antigravity": "agy"}
HEADING = "Agents on this machine"


def read_host(path):
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
            raise ValueError("not a bounded regular file")
        data = os.read(fd, MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("file too large")
        return data.decode("utf-8")
    except FileNotFoundError:
        return ""
    finally:
        os.close(fd)


def section(text):
    matches = list(re.finditer(r"^## Agents on this machine[ \t]*\r?$.*?(?=^#{1,2} |\Z)", text, re.M | re.S))
    if len(matches) > 1:
        raise ValueError("duplicate inventory")
    return matches[0].group() if matches else ""


def cell(value):
    # CLI output and user model labels are data, never instructions or Markdown.
    return " ".join("".join(c if c.isprintable() and c not in "|`<>" else " " for c in value).split())[:200] or "unverified"


def inventory(host, previous, confirmed):
    models = {}
    for line in previous.splitlines():
        cells = [v.strip() for v in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] in AGENTS.values():
            models[cells[0]] = cells[3]
    rows = ["## " + HEADING, "", "Coordinator: " + AGENTS[host], "",
            "| Agent | Present | Version | Allowed models (confirmed by user) | Checked |",
            "| --- | --- | --- | --- | --- |"]
    today = datetime.date.today().isoformat()
    for key, name in AGENTS.items():
        executable = shutil.which(EXECUTABLES[key])
        version = "unverified"
        if executable:
            try:
                result = subprocess.run([executable, "--version"], capture_output=True,
                                        timeout=3, shell=False)
                if result.returncode == 0:
                    version = cell((result.stdout or result.stderr).decode("utf-8", errors="replace")[:200])
            except (OSError, subprocess.TimeoutExpired):
                pass
        allowed = cell(confirmed.get(key, models.get(name, "unverified")))
        rows.append(f'| {name} | {"yes" if executable else "no"} | {version} | {allowed} | {today} |')
    return "\n".join(rows) + "\n\n"


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
    parser.add_argument("--host", choices=AGENTS, required=True)
    parser.add_argument("--models", action="append", default=[], metavar="AGENT=MODELS",
                        help="models explicitly confirmed by the user; repeat for each agent")
    parser.add_argument("--yes", action="store_true", help="write only after a clear yes to the preview")
    try:
        args = parser.parse_args()
        confirmed = {}
        for entry in args.models:
            key, value = entry.split("=", 1)
            if key not in AGENTS or not value.strip():
                raise ValueError("invalid confirmation")
            confirmed[key] = value
        path = Path(os.path.abspath(Path.home() / ".finolabs/vibecode/host.md"))
        text = read_host(path)
        old = section(text)
        new = inventory(args.host, old, confirmed)
        normalized = old.replace("\r\n", "\n")
        print("Version output is untrusted text. Models/effort are not probed.")
        if normalized == new:
            print("No difference.")
        else:
            diff = list(difflib.unified_diff(normalized.splitlines(), new.splitlines(),
                                        fromfile="current section", tofile="proposed section", lineterm=""))
            if len(diff) <= 34:
                print("\n".join(diff))
            else:
                print(f"Difference: replacing current section ({len(normalized.splitlines())} lines) with:")
                print(new.rstrip())
            if args.yes:
                def update(current):
                    if current != text.encode():
                        raise ValueError("host changed since preview")
                    return replace_section(current, HEADING, new.split("\n", 1)[1])
                atomic_write(path, update)
                print("Updated Agents on this machine.")
            else:
                print("Preview only; confirm models and a clear yes before writing.")
    except SystemExit:
        pass
    except (OSError, UnicodeError, ValueError):
        print("Scan unavailable or unsafe path; nothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
