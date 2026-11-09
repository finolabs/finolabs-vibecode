#!/usr/bin/env python3
"""Check that cross-references in the skills, agents and docs still resolve.

- README and the help map list exactly the skill folders (tests/test_manifests.py checks the count).
- Retired names occur only in dated releases, Unreleased migration mappings or
  the explicitly listed historical setup specs.
- Every `fnl-<name>` in backticks names a skill, an agent or the review marker,
  except explicitly retired setup names in the historical specs listed below.
- Every `fnl-<name>` "Heading" names a heading in that skill or agent.
- Every `file.md` "Heading" or [file.md](file.md) "Heading" names a heading in that file, in the same skill.
- Every relative Markdown link points to an existing file.
- Every ledger subcommand a skill cites exists in ledger.py, with its own flags and allowed values.
- Every flag in a host config command is described in agents.md for that agent.

Usage: scripts/check-references.py [repository root]
Prints one line per broken reference and exits 1 when there are any.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

# Names in backticks that are neither skills nor agents.
OTHER_NAMES = {"fnl-review"}  # the review marker in pull request comments
# Spell retired names only in the changelog, not in this source.
RETIRED = {"fnl-" + old: "fnl-" + new for old, new in (
    ("committee", "advisor"), ("coordinator-sessions", "delegate"),
    ("knowledge", "session-hygiene"))}
# Historical specs and released entries retain these names; current callers use the replacements.
RETIRED_AGENTS = {"fnl-" + old: "fnl-" + new for old, new in (
    ("verifier", "verification"), ("steward", "session-hygiene"))}
# Setup commands were folded into one skill in 0.2.0. Keep the original
# decisions in these specs; current surfaces must use the replacement commands.
SETUP_RETIRED = {"fnl-" + old: "/fnl-setup " + new for old, new in (
    ("setup-instructions", "instructions"), ("scan-agents", "scan"), ("set-mode", "mode"))}
SETUP_HISTORY = {
    "docs/specs/agent-roles.md", "docs/specs/agent-scan-and-consolidation.md",
    "docs/specs/release-0.1.8.md", "docs/specs/setup-restructure.md",
    "docs/specs/work-tracking.md",
}
RELEASED = re.compile(r"^## \[\d[^\]]*\] - \d{4}-\d{2}-\d{2}$")
# Agent CLI flags that fnl-delegate cites beside the ledger's.
AGENT_FLAGS = {"print-timeout", "timeout", "max-turns"}
# Files whose inline `--flag` spans are ledger flags.
LEDGER_PROSE = ["skills/fnl-delegate/SKILL.md", "skills/fnl-delegate/references/dispatch.md",
                "skills/fnl-delegate/references/ledger.md", "skills/fnl-delegate/references/route-judgment.md",
                "skills/fnl-status/SKILL.md", "skills/fnl-advisor/SKILL.md", "skills/fnl-advisor/references/committee.md"]

NAME = re.compile(r"`(fnl-[a-z-]+)`")
SECTION = re.compile(r"`(fnl-[a-z-]+)`(?:'s)? \(?\"([^\"]+)\"")
FILE_SECTION = re.compile(r"(?:`([A-Za-z0-9_-][A-Za-z0-9_/-]*\.md)`|\[[^\]]+\]\(([A-Za-z0-9_/.-]+\.md)\))(?:'s)? \(?\"([^\"]+)\"")
REVIEW_BY = re.compile(r"^Checked \d{4}-\d{2}-\d{2}\. Review by \d{4}-\d{2}-\d{2}\.$", re.M)
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
SPAN = re.compile(r"`([^`\n]+)`")
FLAG = re.compile(r"(?<![\w-])--([a-zA-Z][\w-]*)(?:[ =]([A-Za-z0-9][\w.-]*))?")
SUBCOMMAND = re.compile(r'(?:ledger\.py|\$\{?L\}?)[">]?\s+([a-z][\w-]*)')
SHORT_FLAG = re.compile(r"(?<![\w-])(-[a-zA-Z])\b")


def headings(path):
    text = re.sub(r"^```.*?^```", "", path.read_text(), flags=re.M | re.S)  # headings inside code fences are not sections
    return {h.strip("`* ") for h in HEADING.findall(text)}


def documents(root):
    result = subprocess.run(["git", "ls-files", "--cached", "-z", "--",
                             ":(glob)skills/*/**/*.md", ":(glob)agents/*.md", ":(glob)rules/*.md",
                             ":(glob)*.md", ":(glob)docs/**/*.md"], cwd=root,
                            capture_output=True, check=True)
    return sorted(root / name for name in result.stdout.decode().split("\0")
                  if name and (root / name).is_file())


def strip_frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return "\n" * text[:end + 5].count("\n") + text[end + 5:]
    return text


def lines(path):
    text = strip_frontmatter(path.read_text())
    if path.name == "CHANGELOG.md":
        # Released entries name skills and sections as they were; check only Unreleased.
        released = re.search(r"^## \[\d", text, re.M)
        text = text[:released.start()] if released else text
    return enumerate(text.splitlines(), 1)


def targets(root):
    """Skill and agent names mapped to the files that hold their headings."""
    found = {}
    for skill in root.glob("skills/fnl-*/SKILL.md"):
        found[skill.parent.name] = skill
    for agent in root.glob("agents/fnl-*.md"):
        found[agent.stem] = agent
    return found


def check_names_and_sections(root, docs, problems):
    known = targets(root)
    for path in docs:
        rel = path.relative_to(root)
        for n, line in lines(path):
            for name in NAME.findall(line):
                if name not in known and name not in OTHER_NAMES:
                    if name in RETIRED_AGENTS:
                        if rel.parts[:2] == ("docs", "specs"):
                            continue  # preserve design history, including the retirement decision
                        if (path == root / "CHANGELOG.md"
                                and f"`{name}` → `{RETIRED_AGENTS[name]}`" in line):
                            continue  # explicit migration mapping in Unreleased
                    if (path == root / "CHANGELOG.md" and name in RETIRED
                            and f"`{name}` → `{RETIRED[name]}`" in line):
                        continue  # the inventory check enforces the mapping's section
                    if name in SETUP_RETIRED:
                        if rel.as_posix() in SETUP_HISTORY:
                            continue
                        if (path == root / "CHANGELOG.md"
                                and f"`{name}` → `{SETUP_RETIRED[name]}`" in line):
                            continue
                    problems.append(f"{rel}:{n}: unknown skill or agent `{name}`")
            for name, title in SECTION.findall(line):
                if name in known and title not in headings(known[name]):
                    problems.append(f"{rel}:{n}: `{name}` has no section \"{title}\"")
            for quoted, linked, title in FILE_SECTION.findall(line):
                fname = quoted or linked
                skill_dir = next((p for p in path.parents if p.parent.name == "skills"), None)
                base = skill_dir or path.parent
                matches = ([path.parent / linked] if linked and (path.parent / linked).exists()
                           else [p for p in base.glob(f"**/{fname}")])
                if not matches:
                    problems.append(f"{rel}:{n}: `{fname}` not found beside this file")
                elif not any(title in headings(p) for p in matches):
                    problems.append(f"{rel}:{n}: `{fname}` has no section \"{title}\"")


def check_links(root, docs, problems):
    for path in docs:
        rel = path.relative_to(root)
        for n, line in lines(path):
            for target in LINK.findall(SPAN.sub("", line)):
                if re.match(r"^[a-z]+:|^#|^<", target):
                    continue
                file_part = target.split("#", 1)[0]
                if file_part and not (path.parent / file_part).exists():
                    problems.append(f"{rel}:{n}: link target {file_part} does not exist")


def ledger_options(root):
    sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
    spec = importlib.util.spec_from_file_location("ledger", root / "skills/fnl-delegate/scripts/ledger.py")
    ledger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger)
    parser = ledger.build_parser()
    options = {}  # {subcommand: {flag: choices}}
    subparsers = next(a for a in parser._actions if a.choices and isinstance(a.choices, dict))
    for name, sub in subparsers.choices.items():
        for action in sub._actions:
            for opt in action.option_strings:
                if opt.startswith("--") and opt != "--help":
                    options.setdefault(name, {})[opt[2:]] = set(action.choices or [])
        options.setdefault(name, {})
    return options


def check_flag(options, sub, flag, value, where, problems, extra=()):
    """Check one flag against its subcommand, or against every subcommand when none is named."""
    if flag in extra:
        return
    merged = {}
    for flags in options.values():
        for f, choices in flags.items():
            merged.setdefault(f, set()).update(choices)
    if flag not in merged:
        problems.append(f"{where}: ledger.py has no option --{flag}")
        return
    if sub and flag not in options[sub]:
        problems.append(f"{where}: ledger.py {sub} takes no option --{flag}")
        return
    choices = options[sub][flag] if sub else merged[flag]
    if value and choices and value not in choices:
        problems.append(f"{where}: --{flag} {value} is not one of {sorted(choices)}")


def check_command(options, sub, code, where, problems):
    if sub and sub not in options:
        problems.append(f"{where}: ledger.py has no subcommand {sub}")
        return
    for flag, value in FLAG.findall(code):
        check_flag(options, sub, flag, value, where, problems)


def check_ledger_flags(root, docs, problems):
    options = ledger_options(root)
    for path in docs:
        rel = path.relative_to(root)
        in_fence = continued = False
        sub = None
        for n, line in lines(path):
            if line.lstrip().startswith("```"):
                in_fence, continued, sub = not in_fence, False, None
                continue
            if in_fence:
                # A ledger command, or the continuation line of one, which keeps its subcommand.
                code = line.split(" #", 1)[0]
                was_continued = continued
                calls_ledger = was_continued or ("ledger.py" in code and not code.startswith("L=")) or bool(re.search(r'"?\$\{?L\}?"?(\s|$)', code))
                continued = calls_ledger and code.rstrip().endswith("\\")
                if calls_ledger:
                    named = SUBCOMMAND.search(code)
                    sub = named.group(1) if named else (sub if was_continued else None)
                    check_command(options, sub, code, f"{rel}:{n}", problems)
            else:
                # Each inline span is its own command.
                for span in SPAN.findall(line):
                    if "ledger.py" in span:
                        named = SUBCOMMAND.search(span)
                        check_command(options, named.group(1) if named else None, span, f"{rel}:{n}", problems)
    for name in LEDGER_PROSE:
        path = root / name
        for n, line in lines(path):
            for span in SPAN.findall(line):
                if span.startswith("--"):
                    for flag, value in FLAG.findall(span):
                        check_flag(options, None, flag, value, f"{name}:{n}", problems, AGENT_FLAGS)


def sections(path):
    """Second-level sections of a file, as {title: text}."""
    parts = re.split(r"^## (.+)$", path.read_text(), flags=re.M)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts), 2)}


def cli_flags(text):
    text = re.sub(r"<[^>]*>", " ", text)  # placeholders such as <full model id>
    return {f"--{f}" for f, _ in FLAG.findall(text)} | set(SHORT_FLAG.findall(text))


def check_host_template(root, problems):
    base = root / "skills/fnl-delegate/references"
    template, contracts = sections(base / "host-template.md"), sections(base / "agents.md")
    for agent in ("Claude Code", "Codex", "Antigravity"):
        if agent not in template or agent not in contracts:
            problems.append(f"host-template.md and agents.md both need a \"{agent}\" section")
            continue
        described = cli_flags(contracts[agent])
        for flag in sorted(cli_flags(template[agent]) - described):
            problems.append(f"host-template.md \"{agent}\": {flag} is not described in agents.md")


def check_review_by(root, problems):
    models = root / "skills/fnl-delegate/references/models.md"
    if not REVIEW_BY.search(models.read_text()):
        problems.append(f"{models.relative_to(root)}: needs a line \"Checked YYYY-MM-DD. Review by YYYY-MM-DD.\"")


def check_mode_copies(root, problems):
    source = root / "skills/fnl-delegate/scripts/mode.py"
    for relative in ("scripts/mode.py", "skills/fnl-setup/scripts/mode.py"):
        copy = root / relative
        if not source.is_file() or not copy.is_file() or source.read_bytes() != copy.read_bytes():
            problems.append(f"{relative}: mode.py copies differ or are missing")


def check_skill_inventory(root, problems):
    folders = {p.name for p in (root / "skills").iterdir() if p.is_dir()}
    for relative in ("README.md", "skills/fnl-help/references/map.md"):
        path = root / relative
        # The canonical skill table lives under Skills, before the next heading.
        section = sections(path).get("Skills", "")
        section = re.split(r"^#{1,6} ", section, maxsplit=1, flags=re.M)[0]
        listed = set(re.findall(r"^\| `(fnl-[a-z-]+)` \|", section, re.M))
        for name in sorted(folders - listed):
            problems.append(f"{relative}: skill folder {name} missing from skill list")
        for name in sorted(listed - folders):
            problems.append(f"{relative}: listed skill {name} has no folder")

    result = subprocess.run(["git", "ls-files", "--cached", "-z"], cwd=root,
                            capture_output=True, check=False)
    if result.returncode:
        problems.append("cannot list tracked files for retired skill check")
        return
    for relative in result.stdout.decode().split("\0"):
        path = root / relative
        if not relative or not path.is_file():
            continue  # a tracked deletion in the working tree
        version = heading = ""
        for n, line in enumerate(path.read_bytes().decode("utf-8", errors="replace").splitlines(), 1):
            if line.startswith("## "):
                version, heading = line, ""
            elif line.startswith("### "):
                heading = line
            # Check every tracked consumer, including manifests and HTML labels.
            # Test fixtures may define retired names as input data.
            if not relative.startswith("tests/"):
                for old, new in SETUP_RETIRED.items():
                    if not re.search(r"(?<![\w-])" + re.escape(old) + r"(?![\w-])", line):
                        continue
                    released = relative == "CHANGELOG.md" and RELEASED.fullmatch(version)
                    mapping = (relative == "CHANGELOG.md" and version == "## [Unreleased]"
                               and heading == "### Removed" and f"`{old}` → `{new}`" in line)
                    if relative not in SETUP_HISTORY and not released and not mapping:
                        problems.append(f"{relative}:{n}: retired skill name {old}")
            for old, new in RETIRED.items():
                if old not in line:
                    continue
                released = relative == "CHANGELOG.md" and RELEASED.fullmatch(version)
                mapping = (relative == "CHANGELOG.md" and version == "## [Unreleased]"
                           and heading == "### Changed" and f"`{old}` → `{new}`" in line)
                if not released and not mapping:
                    problems.append(f"{relative}:{n}: retired skill name {old}")


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
    docs = documents(root)
    problems = []
    check_names_and_sections(root, docs, problems)
    check_links(root, docs, problems)
    check_ledger_flags(root, docs, problems)
    check_host_template(root, problems)
    check_review_by(root, problems)
    check_mode_copies(root, problems)
    check_skill_inventory(root, problems)
    print("\n".join(problems) or f"references ok ({len(docs)} files)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
