#!/usr/bin/env python3
"""Read review roles and posting state from canonical host.md; never write settings.

Setup alone writes these sections after confirmation. Invalid sections grant no
roles or posting capability. Dates describe checks, not permission or access.
"""
import datetime
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

FAMILIES = ("claude", "codex", "antigravity")
ROLES = ("code review", "security review", "navigator", "judge")
AGENTS = {"Claude Code": "claude", "Codex": "codex", "Antigravity": "antigravity"}


def section(text, heading, maximum=10):
    """Ignore fenced examples; refuse duplicate headings and oversized sections."""
    visible, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            continue
        if match:
            fence = match[1]
        else:
            visible.append(line)
    if fence:
        return None
    text = "\n".join(visible)
    parts = re.split(r"^## ([^\r\n]+?)[ \t]*\r?$", text, flags=re.M)
    found = [parts[i + 1] for i in range(1, len(parts), 2) if parts[i] == heading]
    if len(found) != 1:
        return None
    lines = found[0].strip().splitlines()
    return lines if len(lines) <= maximum else None


def machine_families(text):
    lines = section(text, "Agents on this machine", 30)
    if lines is None:
        return set(), set()
    seen, present = set(), set()
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] not in AGENTS:
            continue
        family = AGENTS[cells[0]]
        if family in seen or len(cells) != 5 or cells[1] not in {"yes", "no", "unverified"}:
            return set(), set()
        seen.add(family)
        if cells[1] == "yes":
            present.add(family)
    return seen, present


def present_families(text):
    return machine_families(text)[1]


def read_roles(text):
    lines = section(text, "Agent roles")
    roles = {}
    if lines is None:
        return {"judge": "host"}
    recorded, _ = machine_families(text)
    for line in lines:
        match = re.fullmatch(r"- (code review|security review|navigator|judge): ([a-z]+)", line)
        if not match or match[1] in roles:
            return {"judge": "host"}
        key, value = match.groups()
        allowed = {"jev", "host"} if key == "judge" else recorded
        if value not in allowed:
            return {"judge": "host"}
        roles[key] = value
    return {"judge": "host", **roles}


def read_posting(text, today=None):
    """Grammar: '- <family>: <state> (checked YYYY-MM-DD)'; whole-section fallback."""
    today = today or datetime.date.today()
    lines = section(text, "Review posting")
    result = {}
    if lines is None:
        return result
    for line in lines:
        match = re.fullmatch(r"- (claude|codex|antigravity): (yes|no|unverified) \(checked (\d{4}-\d{2}-\d{2})\)", line)
        if not match or match[1] in result:
            return {}
        family, value, checked = match.groups()
        try:
            date = datetime.date.fromisoformat(checked)
        except ValueError:
            return {}
        if date > today:
            return {}
        result[family] = value
    return result


def host_text():
    """Never honor a repository or environment host-config override."""
    try:
        if dr.consent_root() is None:
            return ""
        return dr.read_data("host.md", 262144).decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        return ""
