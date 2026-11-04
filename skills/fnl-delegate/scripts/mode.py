#!/usr/bin/env python3
"""Read optional host settings; print effective values as JSON, always exit 0."""

import json
import os
import re
import stat
from pathlib import Path

DEFAULTS = {"delegation_mode": "suggest", "routing": "on"}
SETTINGS = {"delegation_mode": ("Delegation mode", "FNL_DELEGATION_MODE", {"manual", "suggest", "auto"}),
            "routing": ("Routing", "FNL_ROUTING", {"on", "off"})}
MAX_BYTES = 262144


def host_text():
    """Bounded regular Markdown file only; refuse symlinks in every component."""
    path = Path(os.path.abspath(os.path.expanduser(os.environ.get(
        "ORCHESTRATION_HOST_CONFIG", "~/.finolabs/vibecode/host.md"))))
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


def effective():
    values = DEFAULTS.copy()
    try:
        text = host_text()
    except (OSError, UnicodeError, ValueError):
        text = ""
    # Ignore examples in fenced blocks, then collect complete second-level sections.
    text = re.sub(r"^```.*?^```[^\n]*$", "", text, flags=re.M | re.S)
    parts = re.split(r"^## (.+?)\s*$", text, flags=re.M)
    for key, (heading, variable, allowed) in SETTINGS.items():
        sections = [parts[i + 1].strip() for i in range(1, len(parts), 2) if parts[i] == heading]
        raw = os.environ[variable] if variable in os.environ else sections[0] if len(sections) == 1 else ""
        if raw in allowed:
            values[key] = raw
    return values


def main():
    try:
        print(json.dumps(effective()))
    except (OSError, UnicodeError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
