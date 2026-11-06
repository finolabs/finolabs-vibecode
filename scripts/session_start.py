#!/usr/bin/env python3
"""Read-only SessionStart reminder for Claude Code and Codex; fail open, exit 0."""

import json
import sys
from pathlib import Path


def main():
    try:
        import sys
        from pathlib import Path
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from quota_probe import worker_guard
        if worker_guard():
            return 0
    except Exception:
        pass
    try:
        from quota_probe import trigger
        trigger()
    except Exception:
        pass
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
    try:
        raw = sys.stdin.buffer.read(64 * 1024 + 1)
        if len(raw) <= 64 * 1024:
            event = json.loads(raw.decode("utf-8"))
            if (isinstance(event, dict) and event.get("source") == "compact"
                    and isinstance(event.get("session_id"), str) and event["session_id"]):
                from handover_state import read
                handover = read(event["session_id"])
                if handover:
                    print("\nHandover before compaction\n" + handover, end="")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
