#!/usr/bin/env python3
"""Local agent inventory: fixed --version calls, no model probes, preview unless --yes."""

import argparse
import datetime
import difflib
import hashlib
import selectors
import time
import os
import re
import shutil
import stat
import sys
import subprocess
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

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


def section_ranges(text, heading):
    fence = None
    headings = []
    offset = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if marker:
            run, tail = marker.groups()
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not tail.strip():
                fence = None
        elif fence is None and re.match(r"^#{1,2} ", line):
            headings.append((offset, line.rstrip("\r\n")))
        offset += len(line)
    return [(start, headings[i + 1][0] if i + 1 < len(headings) else len(text))
            for i, (start, line) in enumerate(headings) if line.rstrip() == "## " + heading]


def section(text):
    matches = section_ranges(text, HEADING)
    if len(matches) > 1:
        raise ValueError("duplicate inventory")
    return text[slice(*matches[0])] if matches else ""


def cell(value):
    # CLI output and user model labels are data, never instructions or Markdown.
    return " ".join("".join(c if c.isprintable() and c not in "|`<>" else " " for c in value).split())[:200] or "unverified"


def inventory(host, previous, confirmed):
    models = {}
    stored = {}
    for line in previous.splitlines():
        cells = [v.strip() for v in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] in AGENTS.values():
            models[cells[0]] = cells[3]
            stored[cells[0]] = cells
    rows = ["## " + HEADING, "", "Coordinator: " + AGENTS[host], "",
            "| Agent | Present | Version | Allowed models (confirmed by user) | Checked |",
            "| --- | --- | --- | --- | --- |"]
    today = datetime.date.today().isoformat()
    search_path = os.pathsep.join(p for p in os.get_exec_path() if os.path.isabs(p))
    for key, name in AGENTS.items():
        executable = None
        try:
            executable = shutil.which(EXECUTABLES[key], path=search_path) if search_path else None
        except OSError:
            pass
        version = "unverified"
        if executable:
            try:
                with subprocess.Popen([executable, "--version"], stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, shell=False) as process:
                    output = b""
                    deadline = time.monotonic() + 3
                    try:
                        with selectors.DefaultSelector() as selector:
                            selector.register(process.stdout, selectors.EVENT_READ)
                            while len(output) < 4096:
                                remaining = deadline - time.monotonic()
                                if remaining <= 0 or not selector.select(remaining):
                                    raise subprocess.TimeoutExpired(executable, 3)
                                chunk = os.read(process.stdout.fileno(), 4096 - len(output))
                                if not chunk:
                                    break
                                output += chunk
                        if len(output) == 4096:
                            process.kill()
                        returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                if returncode == 0:
                    candidate = cell(output.decode("utf-8", errors="replace")[:200])
                    if re.fullmatch(r"[0-9A-Za-z.+_ ()-]{1,80}", candidate):
                        version = candidate
            except (OSError, subprocess.TimeoutExpired):
                pass
        allowed = cell(confirmed.get(key, models.get(name, "unverified")))
        checked = today
        old_row = stored.get(name)
        if old_row and old_row[:4] == [name, "yes" if executable else "no", version, allowed]:
            try:
                age = (datetime.date.today() - datetime.date.fromisoformat(old_row[4])).days
            except ValueError:
                age = None
            if age is not None and 0 <= age <= 7:
                checked = old_row[4]
        rows.append(f'| {name} | {"yes" if executable else "no"} | {version} | {allowed} | {checked} |')
    return "\n".join(rows) + "\n\n"


def replace_section(text, heading, body):
    """Replace a unique level-two section, preserving all bytes outside it."""
    decoded = text.decode("utf-8")
    matches = section_ranges(decoded, heading)
    if len(matches) > 1:
        raise ValueError("duplicate heading")
    newline = b"\r\n" if b"\r\n" in text else b"\n"
    section = ("## " + heading + "\n\n" + body.strip() + "\n\n").encode().replace(b"\n", newline)
    if matches:
        start, end = matches[0]
        return decoded[:start].encode() + section + decoded[end:].encode()
    separator = b"" if not text or text.endswith(newline * 2) else (newline if text.endswith(newline) else newline * 2)
    return text + separator + section


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
    parser.add_argument("--digest", help="SHA-256 prefix printed by the preview")
    try:
        args = parser.parse_args()
        confirmed = {}
        for entry in args.models:
            key, value = entry.split("=", 1)
            if key not in AGENTS or not value.strip():
                raise ValueError("invalid confirmation")
            confirmed[key] = value
        root, source = dr.data_root()
        print(f"Data root: {root} ({source})")
        if source == "invalid":
            raise ValueError("invalid data root")
        path = root / "host.md"
        try:
            text = dr.read_data("host.md").decode("utf-8")
        except FileNotFoundError:
            text = ""
        old = section(text)
        new = inventory(args.host, old, confirmed)
        digest = hashlib.sha256(new.encode()).hexdigest()
        print("Digest: " + digest)
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
                if not args.digest or not re.fullmatch(r"[0-9a-fA-F]{8,64}", args.digest) or not digest.startswith(args.digest.lower()):
                    print("Digest missing or mismatched; nothing written.")
                    return 0
                def update(current):
                    if current != text.encode():
                        raise ValueError("host changed since preview")
                    return replace_section(current, HEADING, new.split("\n", 1)[1])
                with dr.data_folder(create=True) as folder:
                    try:
                        current = dr.read_file(folder, "host.md", 262144)
                    except FileNotFoundError:
                        current = b""
                    dr.atomic_write(folder, "host.md", update(current))
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
