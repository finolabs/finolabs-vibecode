#!/usr/bin/env python3
"""Read-only SessionStart reminder for Claude Code and Codex; fail open, exit 0."""

import sys
from pathlib import Path


def main():
    routing = "on"
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
        from mode import effective
        routing = effective()["routing"]
    except Exception:
        pass  # an unavailable reader must keep the default reminder
    try:
        text = (Path(__file__).resolve().parent.parent / "rules/AGENTS.md").read_text(encoding="utf-8")
        if routing == "off":
            text = "\n".join(line for line in text.splitlines() if "fnl-coding-router" not in line) + "\n"
    except (OSError, UnicodeError):
        text = "Invoke fnl-delegate before handing work to another agent.\n"
        if routing == "on":
            text = "Start coding work with fnl-coding-router.\n" + text
    try:
        print(text, end="")
    except (OSError, UnicodeError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
