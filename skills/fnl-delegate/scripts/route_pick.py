#!/usr/bin/env python3
"""Answer the routing query from the assignment matrix and local state only.

`pick --type <type> --level <1-5> [--author <family>]` prints at most five lines: each surviving agent as
`<agent> <model or default>` in preference order, then one `drop <agent>: <reason>` line per dropped agent.
With no survivor, or no usable matrix, the first line is `no preference: use the strength table`.
It reads the canonical host config and the cached quota status, runs no program, reads no repository,
makes no network call and prints no path. A preference never blocks and never grants anything.
"""
import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assignments as am
import review_config as config

NO_PREFERENCE = "no preference: use the strength table"
MAX_LINES = 5
DISPLAY = {"Claude Code": "claude", "Codex": "codex", "Antigravity": "antigravity"}


class Pick:
    def __init__(self, state, work_type, level):
        self.state = state
        self.work_type = work_type
        self.level = level
        self.listed = []
        self.survivors = []
        self.drops = []


def family(agent):
    """An extra Claude Code command (`claude<suffix>`) belongs to the claude family."""
    return agent if agent in config.FAMILIES else "claude"


def coordinator(text):
    lines = config.section(text, "Agents on this machine", 30) or []
    for line in lines:
        match = re.fullmatch(r"Coordinator: (.+?)\s*", line)
        if match:
            name = match[1]
            return DISPLAY.get(name, name if name in config.FAMILIES else None)
    return None


def unreachable(text):
    """Families the `## Coordinators and reach` row of this coordinator marks `no`; anything else excludes nothing."""
    own = coordinator(text)
    lines = config.section(text, "Coordinators and reach", 30)
    if own is None or lines is None:
        return own, set()
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines if line.strip().startswith("|")]
    if not rows or rows[0][:1] != ["Coordinator"]:
        return own, set()
    columns = [DISPLAY.get(c) for c in rows[0]]
    blocked = set()
    for cells in rows[1:]:
        if DISPLAY.get(cells[0]) != own or len(cells) != len(columns):
            continue
        for name, cell in zip(columns[1:], cells[1:]):
            if name and re.match(r"no\b", cell.lower()):
                blocked.add(name)
    return own, blocked


def out_of_quota(lines):
    """Reuse review routing's reading of the cached status; an unreadable status excludes nothing."""
    import review_route
    try:
        return review_route.blocked_families(lines)
    except (ValueError, TypeError):
        return set()


def pick(text, work_type, level, author=None, quota_lines=()):
    matrix = am.parse(text)
    state = "absent" if matrix.state == "absent" else "valid" if config.usable(matrix) else "invalid"
    result = Pick(state, work_type, level)
    if state != "valid":
        return result
    own, unreached = unreachable(text)
    quota = out_of_quota(quota_lines)
    for agent, entry in matrix.agents.items():
        if work_type not in entry["works"]:
            continue
        result.listed.append(agent)
        low, high = entry["levels"]
        if not low <= level <= high:
            reason = f"level {level} outside {low}-{high}"
        elif family(agent) in unreached:
            reason = f"unreachable from {own}"
        elif family(agent) in quota:
            reason = "out of quota"
        elif author is not None and family(agent) == author:
            reason = "author family"
        else:
            result.survivors.append((agent, entry["model"]))
            continue
        result.drops.append((agent, reason))
    return result


def lines(result):
    answer = [f"{agent} {model or 'default'}" for agent, model in result.survivors] or [NO_PREFERENCE]
    if result.state == "invalid":
        answer.append("matrix invalid")
    answer += [f"drop {agent}: {reason}" for agent, reason in result.drops]
    return answer[:MAX_LINES]


def rank(result, name, model):
    """(1-based rank, None) for a survivor, (0, reason) outside the set, None when there is no preference."""
    if not result.survivors:
        return None
    for position, (agent, listed) in enumerate(result.survivors, 1):
        if agent == name:
            if listed is None or listed == model:
                return position, None
            return 0, f"model not listed for {name}"
    for agent, reason in result.drops:
        if agent == name:
            return 0, f"{name}: {reason}"
    return 0, f"{name} not listed for {result.work_type}"


def host_text():
    return config.host_text()


def quota_lines():
    import quota_probe
    return quota_probe.status_lines()


def answer(work_type, level, author=None):
    return pick(host_text(), work_type, level, author=author, quota_lines=quota_lines())


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick", help="ordered candidates for one task", allow_abbrev=False)
    p.add_argument("--type", required=True, choices=am.TYPES)
    p.add_argument("--level", required=True, type=int, choices=range(1, 6))
    p.add_argument("--author", choices=config.FAMILIES)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    for line in lines(answer(args.type, args.level, args.author)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
