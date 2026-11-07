#!/usr/bin/env python3
"""Route code then security reviews, without models, sockets or child processes.

Output is exactly '<family> <form> <reason>' per requested kind. Exit 0 means
routed, 1 needs a user decision (security-trigger same-family), 2 is unavailable
or invalid input. Quota uses quota_probe's status implementation only, in process.
The coordinator starts any due quota reading before invoking this script.

build_packet builds an in-memory reviewer packet from local git objects plus
coordinator-supplied criteria, decisions and known consumers. It is not an event
or receipt and is never persisted by this script.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import zlib
from datetime import datetime, timezone

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import quota_probe
import review_config as config
import git_metadata as metadata

ORDER = config.FAMILIES
FORMS = {"claude": "agent", "codex": "headless", "antigravity": "headless"}
OID = re.compile(r"[0-9a-f]{40}")
MAX_OBJECT = 16 * 1024 * 1024


def bounded(path, cap=MAX_OBJECT):
    return metadata.bounded(path, cap)


git_dirs = metadata.git_dirs


def resolve_ref(git, common, ref="HEAD", depth=0):
    if depth > 5:
        raise ValueError("ref cycle")
    if OID.fullmatch(ref):
        return ref
    if ref != "HEAD" and not re.fullmatch(r"refs/[A-Za-z0-9_/.-]+", ref):
        raise ValueError("invalid ref")
    if ".." in ref or ref.endswith("/"):
        raise ValueError("invalid ref")
    for directory in (git, common):
        try:
            value = bounded(directory / ref, 4096).decode().strip()
        except FileNotFoundError:
            continue
        if value.startswith("ref: "):
            return resolve_ref(git, common, value[5:], depth + 1)
        if OID.fullmatch(value):
            return value
        raise ValueError("invalid ref")
    try:
        for line in bounded(common / "packed-refs").decode().splitlines():
            if line.endswith(" " + ref) and OID.fullmatch(line[:40]):
                return line[:40]
    except FileNotFoundError:
        pass
    raise ValueError("unknown ref")


def inflate(data):
    unpacker = zlib.decompressobj()
    result = unpacker.decompress(data, MAX_OBJECT + 1)
    if len(result) > MAX_OBJECT or not unpacker.eof:
        raise ValueError("oversized or incomplete object")
    return result


def delta(base, patch):
    cursor = 0
    def variable():
        nonlocal cursor
        value = shift = 0
        while True:
            byte = patch[cursor]
            cursor += 1
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
            shift += 7
            if shift > 35:
                raise ValueError("delta size")
    if variable() != len(base):
        raise ValueError("delta base")
    size = variable()
    if size > MAX_OBJECT:
        raise ValueError("delta size")
    result = bytearray()
    while cursor < len(patch):
        opcode = patch[cursor]
        cursor += 1
        if opcode & 128:
            offset = length = 0
            for bit in range(4):
                if opcode & (1 << bit):
                    offset |= patch[cursor] << (8 * bit)
                    cursor += 1
            for bit in range(3):
                if opcode & (1 << (bit + 4)):
                    length |= patch[cursor] << (8 * bit)
                    cursor += 1
            length = length or 65536
            if offset + length > len(base):
                raise ValueError("delta copy")
            result.extend(base[offset:offset + length])
        elif opcode:
            result.extend(patch[cursor:cursor + opcode])
            cursor += opcode
        else:
            raise ValueError("delta opcode")
        if len(result) > size:
            raise ValueError("delta overflow")
    if len(result) != size:
        raise ValueError("delta size")
    return bytes(result)


def packed_object(common, pack, offset, depth):
    if depth > 50:
        raise ValueError("delta depth")
    with metadata.opened(pack) as fd, os.fdopen(os.dup(fd), "rb") as stream:
        stream.seek(offset)
        byte = stream.read(1)[0]
        kind, size, shift = (byte >> 4) & 7, byte & 15, 4
        while byte & 128:
            byte = stream.read(1)[0]
            size |= (byte & 127) << shift
            shift += 7
            if shift > 35:
                raise ValueError("pack size")
        base_offset = base_oid = None
        if kind == 6:
            byte = stream.read(1)[0]
            distance = byte & 127
            while byte & 128:
                byte = stream.read(1)[0]
                distance = ((distance + 1) << 7) | (byte & 127)
            base_offset = offset - distance
            if base_offset < 12 or base_offset >= offset:
                raise ValueError("pack offset")
        elif kind == 7:
            base_oid = stream.read(20).hex()
        data = inflate(stream.read(MAX_OBJECT + 65536))
    if len(data) != size:
        raise ValueError("pack size")
    if kind in {6, 7}:
        base_kind, base = (packed_object(common, pack, base_offset, depth + 1) if kind == 6
                           else git_object(common, base_oid, depth + 1))
        return base_kind, delta(base, data)
    if kind not in {1, 2, 3, 4}:
        raise ValueError("pack kind")
    return {1: "commit", 2: "tree", 3: "blob", 4: "tag"}[kind], data


def git_object(common, oid, depth=0):
    if not OID.fullmatch(oid):
        raise ValueError("invalid object")
    try:
        raw = inflate(bounded(common / "objects" / oid[:2] / oid[2:]))
        header, data = raw.split(b"\0", 1)
        kind, size = header.decode().split(" ")
        if int(size) != len(data) or hashlib.sha1(raw).hexdigest() != oid:
            raise ValueError("invalid object")
        return kind, data
    except FileNotFoundError:
        pass
    target = bytes.fromhex(oid)
    try:
        with metadata.opened(common / "objects/pack", directory=True) as fd:
            indexes = sorted(name for name in os.listdir(fd) if name.endswith(".idx"))
    except FileNotFoundError:
        indexes = []
    for name in indexes:
        index = common / "objects/pack" / name
        raw = bounded(index, 64 * 1024 * 1024)
        if raw[:8] != b"\xfftOc\0\0\0\2" or len(raw) < 1032:
            raise ValueError("unsupported pack index")
        count = struct.unpack_from(">I", raw, 1028)[0]
        if 1032 + count * 28 + 40 > len(raw):
            raise ValueError("invalid pack index")
        lo, hi = 0, count
        while lo < hi:
            mid = (lo + hi) // 2
            candidate = raw[1032 + mid * 20:1052 + mid * 20]
            if candidate < target:
                lo = mid + 1
            else:
                hi = mid
        if lo == count or raw[1032 + lo * 20:1052 + lo * 20] != target:
            continue
        offset = struct.unpack_from(">I", raw, 1032 + count * 24 + lo * 4)[0]
        if offset & 0x80000000:
            offset = struct.unpack_from(">Q", raw, 1032 + count * 28 + (offset & 0x7fffffff) * 8)[0]
        kind, data = packed_object(common, index.with_suffix(".pack"), offset, depth)
        header = f"{kind} {len(data)}\0".encode()
        if hashlib.sha1(header + data).hexdigest() != oid:
            raise ValueError("invalid packed object")
        return kind, data
    raise ValueError("missing object")


def author_family(checkout, ledger_text=None, *, base=None, head="HEAD"):
    """Require a head-bound local ledger and consistent trailers across base..head.

Trailers are corroboration only: repository authors cannot choose their family.
Legacy ledger records without an exact head never establish authorship.
"""
    git, common = git_dirs(checkout)
    head = resolve_ref(git, common, head)
    if ledger_text is None:
        try:
            ledger_text = dr.read_data("ledger.jsonl", MAX_OBJECT).decode()
        except FileNotFoundError:
            ledger_text = ""
    families = set()
    for line in ledger_text.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("head") != head:
            continue
        family = record.get("agent")
        family = "claude" if family in ("claude-session", "subagent") else family
        if family not in ORDER:
            raise ValueError("unverified ledger author")
        families.add(family)
    if len(families) != 1:
        raise ValueError("unverified ledger author")
    author = families.pop()
    if base is None:
        raise ValueError("review base required")
    base = resolve_ref(git, common, base)

    def ancestry(start):
        seen, pending = set(), [start]
        while pending:
            oid = pending.pop()
            if oid in seen:
                continue
            if len(seen) >= 10000:
                raise ValueError("oversized commit range")
            seen.add(oid)
            kind, commit = git_object(common, oid)
            if kind != "commit":
                raise ValueError("not a commit")
            headers = commit.split(b"\n\n", 1)[0]
            pending.extend(p.decode() for p in re.findall(rb"^parent ([0-9a-f]{40})$", headers, re.M))
        return seen

    excluded = ancestry(base)
    reviewed = ancestry(head) - excluded
    if not reviewed:
        raise ValueError("empty review range")
    for oid in reviewed:
        _, commit = git_object(common, oid)
        message = commit.split(b"\n\n", 1)[1].decode("utf-8", "replace").replace("\r\n", "\n").rstrip()
        trailers = message.split("\n\n")[-1].splitlines()
        found = set()
        for line in trailers:
            match = re.fullmatch(r"Co-Authored-By: (Codex|Claude(?: [A-Za-z0-9.-]+)*|Antigravity) <[^<>\s]+>", line, re.I)
            if match:
                found.add(match[1].split()[0].lower())
        if found != {author}:
            raise ValueError("unverified or conflicting trailers")
    return author


def blocked_families(lines, current=None):
    """Consume status output only; stale cache is unverified, never exclusion."""
    current = current or datetime.now(timezone.utc)
    blocked, installs = set(), {}
    for line in lines:
        marker = re.fullmatch(r"Quota (claude|codex|agy): rate-limit marker ([^;]+); out of quota until ([^ ]+) \(advisory\)", line)
        if marker:
            if quota_probe.timestamp(marker[2]) <= current < quota_probe.timestamp(marker[3]):
                blocked.add("antigravity" if marker[1] == "agy" else marker[1])
            continue
        match = re.fullmatch(r"Quota (claude|codex|agy)/([^:]+): measured ([^;]+); (.+)", line)
        if not match:
            continue
        family = "antigravity" if match[1] == "agy" else match[1]
        age = (current - quota_probe.timestamp(match[3])).total_seconds()
        if age < 0 or age > 8 * 3600:
            continue
        pools = re.findall(r"(?:^|; )([a-zA-Z0-9_-]+) ([^:;]+): (\d+)% remaining, resets ([^ ;]+)", match[4])
        relevant = [pool for pool in pools if family != "claude" or pool[0] == "week-all"]
        depleted = any(int(p[2]) < 10 and quota_probe.timestamp(p[3]) > current for p in relevant)
        installs.setdefault(family, []).append(depleted)
    blocked.update(f for f, depleted in installs.items() if depleted and all(depleted))
    return blocked


def route(author, text, quota_lines, *, lane=False, kinds=("code", "security")):
    if author not in ORDER:
        raise ValueError("unverified author")
    present = config.present_families(text)
    if not present:
        raise ValueError("no present family")
    roles, posting = config.read_roles(text), config.read_posting(text)
    blocked = blocked_families(quota_lines)
    other = [f for f in ORDER if f in present and f != author and f not in blocked]
    # Posting is only a tie-break between otherwise valid independent fallbacks.
    other.sort(key=lambda f: posting.get(f) != "yes")
    def choose(kind):
        assigned = roles.get(kind + " review")
        if assigned in other:
            return assigned, "assigned"
        if other:
            return other[0], "capability"
        if author in present and author not in blocked:
            return author, "same-family"
        raise ValueError("no available family")
    picks = {kind: choose("code" if lane else kind) for kind in kinds}
    combined = len(picks) == 2 and picks["code"][0] == picks["security"][0]
    rows = []
    for kind in kinds:
        family, reason = picks[kind]
        reason += "-lane" if lane else ""
        reason += "-one-run-two-comments" if combined else ""
        rows.append((family, FORMS[family], reason))
    return rows


def build_packet(checkout, base, head, criteria, decisions, known_consumers):
    """Script-built git facts; supplied text stays in memory, outside telemetry."""
    git, common = git_dirs(checkout)
    base, head = resolve_ref(git, common, base), resolve_ref(git, common, head)
    def files(commit):
        kind, data = git_object(common, commit)
        if kind != "commit":
            raise ValueError("not a commit")
        root = re.match(rb"tree ([0-9a-f]{40})\n", data)
        if not root:
            raise ValueError("missing tree")
        found = {}
        def walk(oid, prefix="", depth=0):
            if depth > 40 or len(found) > 10000:
                raise ValueError("oversized tree")
            kind, data = git_object(common, oid)
            if kind != "tree":
                raise ValueError("not a tree")
            cursor = 0
            while cursor < len(data):
                end = data.index(b"\0", cursor)
                mode, name = data[cursor:end].split(b" ", 1)
                name = name.decode("utf-8", "replace")
                if name in {".", ".."} or "/" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
                    raise ValueError("unsafe tree name")
                child = data[end + 1:end + 21].hex()
                cursor = end + 21
                path = prefix + name
                if mode == b"40000":
                    walk(child, path + "/", depth + 1)
                else:
                    found[path] = (mode.decode(), child)
        walk(root[1].decode())
        return found
    before, after = files(base), files(head)
    stat = []
    for name in sorted(before.keys() | after.keys()):
        if before.get(name) == after.get(name):
            continue
        versions = []
        for tree in (before, after):
            entry = tree.get(name)
            versions.append(git_object(common, entry[1])[1] if entry and entry[0] != "160000" else b"")
        if any(b"\0" in v for v in versions):
            stat.append({"file": name, "binary": True})
        else:
            lines = [v.decode("utf-8", "replace").splitlines() for v in versions]
            if any(len(v) > 256 * 1024 for v in versions) or any(len(v) > 1000 for v in lines):
                raise ValueError("oversized text diff")
            added = removed = 0
            for line in difflib.ndiff(*lines):
                added += line.startswith("+ ")
                removed += line.startswith("- ")
            stat.append({"file": name, "added": added, "removed": removed})
    return {"base": base, "head": head, "diff_stat": stat, "known_consumers": known_consumers,
            "acceptance_criteria": criteria, "decisions": decisions}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--kind", choices=("code", "security", "both"), default="both")
    parser.add_argument("--base", help="reviewed base ref; missing base cannot route")
    parser.add_argument("--lane", action="store_true", help="coordinator must first pass merge_check.py --lane")
    parser.add_argument("--security-trigger", action="store_true")
    args = parser.parse_args(argv)
    if args.lane and args.security_trigger:
        return 2
    try:
        rows = route(author_family(Path.cwd(), base=args.base), config.host_text(), quota_probe.status_lines(),
                     lane=args.lane, kinds=("code", "security") if args.kind == "both" else (args.kind,))
        for row in rows:
            print(" ".join(row))
        return 1 if args.security_trigger and any("same-family" in row[2] for row in rows) else 0
    except (OSError, ValueError, KeyError, IndexError, UnicodeError, struct.error, zlib.error):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
