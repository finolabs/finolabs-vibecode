#!/usr/bin/env python3
"""Read-only upgrade-note checks and the legacy host settings Check reports.

`upgrade_state.py <state>` exits 0 when done, 1 when open, 3 when not applicable and 2 when unknown.
It reads the canonical host config (and, for `repo-checks`, the current repository's approved check
list), prints nothing, writes nothing, runs nothing and makes no network call.
"""

import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr  # noqa: E402

DONE, OPEN, UNKNOWN, NOT_APPLICABLE = 0, 1, 2, 3
LIMIT = 262144
GLOBAL_LINE = re.compile(r"(?:- )?(?:Ledger project|Task file):")
PARALLEL_LINE = re.compile(r"- Parallel (?:dispatches|per family):")
# Fixed names only; Check never prints a value from these sections or lines.
LEGACY = (("## Checks", "heading", "Checks"),
          ("## Project settings", "heading", "Project settings"),
          ("## Project labels", "heading", "Project labels"),
          ("Ledger project:/Task file: lines", "line", GLOBAL_LINE),
          ("Parallel lines in ## Limits", "line", PARALLEL_LINE))


def unfenced(text):
    """Lines outside fenced examples, which can neither opt in nor count as legacy."""
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield line


def headings(text):
    return {line[3:].strip() for line in unfenced(text) if line.startswith("## ")}


def legacy(text):
    """Fixed names of the retired host.md sections and lines still present."""
    found, titles = [], headings(text)
    lines = list(unfenced(text))
    for name, kind, pattern in LEGACY:
        if (pattern in titles) if kind == "heading" else any(pattern.match(line) for line in lines):
            found.append(name)
    return found


def host_text():
    try:
        return dr.read_data("host.md", LIMIT).decode("utf-8")
    except FileNotFoundError:
        return ""


def repo_checks():
    import checks_list as cl
    import project_progress as pp
    found = pp.find_root(os.getcwd())
    if found is None:
        return NOT_APPLICABLE
    checks, reason = cl.checks_for(pp.repository_code(found), root=found)
    return DONE if checks and not reason else OPEN


def state(name):
    if name == "repo-checks":
        return repo_checks()
    if dr.consent_root() is None:
        return UNKNOWN
    text = host_text()
    titles = headings(text)
    absent = dict(zip(("no-checks-section", "no-project-settings", "no-project-labels",
                       "no-global-lines", "no-parallel-lines"), (key for key, _, _ in LEGACY)))
    if name in absent:
        return OPEN if absent[name] in legacy(text) else DONE
    if name == "matrix":
        old = {"Agent roles", "Agent levels"} & titles
        if old:
            return OPEN
        return DONE if "Assignment matrix" in titles else NOT_APPLICABLE
    if name == "roles-retired":
        # Since 0.2.6 only the assignment matrix sets roles and the judge; `## Agent roles` is never read.
        if "Agent roles" not in titles:
            return DONE
        import assignments
        matrix = assignments.parse(text)
        return DONE if matrix.state == "valid" and matrix.consent == "yes" else OPEN
    if name == "levels":
        return DONE if {"Agent levels", "Assignment matrix"} & titles else OPEN
    # Since 0.2.5 the away settings live in `## afk`; an older `## Autopilot` section is no longer read.
    if name == "afk":
        return DONE if "afk" in titles else OPEN
    if name == "afk-decisions":
        # 0.2.3 added the stop-or-decide questions, recorded with the separate excerpt answer.
        return DONE if any(line.startswith("- Excerpts leave the machine:") for line in section(text, "afk")) \
            else OPEN
    if name == "afk-section":
        # 0.2.5 renamed the section: open while the old heading remains, done once only `## afk` is there.
        if "Autopilot" in titles:
            return OPEN
        return DONE if "afk" in titles else NOT_APPLICABLE
    return UNKNOWN


def section(text, title):
    lines, inside = [], False
    for line in unfenced(text):
        if re.match(r"^#{1,2} ", line):
            inside = line.strip() == "## " + title
        elif inside:
            lines.append(line)
    return lines


def main(argv=None):
    """Several states combine: unknown wins, then open; done unless every one is not applicable."""
    argv = sys.argv[1:] if argv is None else argv
    try:
        if not 1 <= len(argv) <= 8:
            return UNKNOWN
        states = [state(name) for name in argv]
    except Exception:
        return UNKNOWN
    for code in (UNKNOWN, OPEN):
        if code in states:
            return code
    return NOT_APPLICABLE if set(states) == {NOT_APPLICABLE} else DONE


if __name__ == "__main__":
    sys.exit(main())
