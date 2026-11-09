#!/usr/bin/env python3
"""Show, record or clear a declined setup feature in the `## Setup features` section of host.md.

A `declined` line only stops a bare `/fnl-setup` from offering that feature again. It is not a consent,
grants nothing, and `/fnl-setup add <feature>` always asks again. Written only by fnl-setup.
"""
import argparse
try:
    import fcntl
except ImportError:
    raise ImportError("finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; on Windows run it under WSL.") from None
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

FEATURES = ("delegation", "roles", "quota", "autopilot", "metrics", "compaction", "companions", "project")
HEADING = "## Setup features"
# Read the old name only; CLI choices and rendered records stay canonical.
ALIASES = {"review-tools": "companions"}
LINE = re.compile(r"- (" + "|".join((*FEATURES, *ALIASES)) + r"): declined")
CAP = 262144


def split(text):
    """Return (headings as (offset, line), fenced) for the level-one and level-two headings outside code fences."""
    headings, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and line.strip() == token:
                fence = None  # a line with an info string after the run does not close a fence
        elif fence is None and re.match(r"^#{1,2} ", line):
            headings.append((offset, line.strip()))
        offset += len(line)
    return headings, fence


def parse(text):
    """Strict parse: the declined features, or None when the section is absent, duplicated or malformed."""
    headings, fence = split(text)
    indexes = [i for i, (_, heading) in enumerate(headings) if heading == HEADING]
    if len(indexes) != 1 or fence is not None:
        return None
    index = indexes[0]
    end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
    body = text[headings[index][0]:end].splitlines()[1:]
    lines = [line.rstrip() for line in body if line.strip()]
    if len(lines) > 10:
        return None
    found = []
    for line in lines:
        match = LINE.fullmatch(line)
        if not match:
            return None
        name = ALIASES.get(match[1], match[1])
        if name in found:
            return None
        found.append(name)
    return found


def read_host():
    try:
        return dr.read_data("host.md", CAP).decode()
    except FileNotFoundError:
        return ""


def declined():
    """Declined features from the canonical host config; an unreadable section means none."""
    try:
        return parse(read_host()) or []
    except (OSError, ValueError, UnicodeError):
        return []


def render(features):
    return HEADING + "\n\n" + "".join("- %s: declined\n" % name for name in FEATURES if name in features) + "\n"


def checked_headings(text):
    headings, fence = split(text)
    indexes = [i for i, (_, heading) in enumerate(headings) if heading == HEADING]
    if fence is not None or len(indexes) > 1 or (indexes and parse(text) is None):
        raise ValueError("malformed Setup features section; repair it before changing the record")
    return headings, indexes


def write(features, dry_run):
    section = render(features) if features else ""
    if dry_run:
        checked_headings(read_host())
        return section or "(section removed)\n"
    with dr.root_folder(create=True) as folder:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            text = dr.read_file(folder, "host.md", CAP).decode()
        except FileNotFoundError:
            text = ""
        headings, indexes = checked_headings(text)
        newline = "\r\n" if "\r\n" in text else "\n"
        section = section.replace("\n", newline)
        if indexes:
            index = indexes[0]
            end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
            text = text[:headings[index][0]] + section + text[end:]
        elif section:
            text += (newline * 2 if text and not text.endswith(newline) else newline if text and not text.endswith(newline * 2) else "") + section
        raw = text.encode()
        if len(raw) > CAP:
            raise ValueError("host cap")
        dr.atomic_write(folder, "host.md", raw)
    return section


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("show")
    for name in ("decline", "clear"):
        sub = commands.add_parser(name)
        sub.add_argument("feature", choices=FEATURES)
        sub.add_argument("--yes", action="store_true")
        sub.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        current = declined()
        if args.action == "show":
            print("declined: " + (", ".join(current) or "none"))
            return 0
        if not args.yes and not args.dry_run:
            raise ValueError("confirmation required")
        if dr.consent_root() is None:
            raise ValueError("root")
        wanted = set(current) | {args.feature} if args.action == "decline" else set(current) - {args.feature}
        result = write(wanted, args.dry_run)
        print(result if args.dry_run else "Setup feature record saved (%s %s); nothing else was changed." % (args.action, args.feature))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        detail = " malformed Setup features section; repair it first;" if str(error).startswith("malformed Setup features") else ""
        print("Setup feature record refused;" + detail + " nothing saved.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
