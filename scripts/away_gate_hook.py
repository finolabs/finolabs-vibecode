#!/usr/bin/env python3
"""Claude Code PreToolUse question gate for the away mandate; every failure allows silently with exit 0.

It denies only the AskUserQuestion tool, only while a valid, unexpired away lease exists, with one fixed
message. It never reads the question, and it appends one ledger line holding the time and the lease's start.
"""

import os
import signal
import sys

MESSAGE = (b'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",'
           b'"permissionDecisionReason":"The user is away under an active away mandate: do not ask the user; '
           b'follow afk \\"Decide\\"."}}\n')


def main():
    try:
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(2)
        if os.environ.get("FNL_AWAY_GATE", "").lower() in {"off", "0", "false", "no"}:
            return 0

        import json
        import time
        from datetime import datetime, timezone
        from pathlib import Path

        raw = sys.stdin.buffer.read(64 * 1024)
        if len(raw) == 64 * 1024:
            return 0
        event = json.loads(raw)
        # Only the tool name is read; the question itself is never inspected.
        if not isinstance(event, dict) or event.get("tool_name") != "AskUserQuestion":
            return 0

        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import away_lease

        current = time.time()
        lease = away_lease.live_lease(current)
        if lease is None:
            return 0
        away_lease.append_ledger({"event": "question_denied",
                                  "ts": datetime.fromtimestamp(current, timezone.utc).isoformat(timespec="seconds"),
                                  "lease_start": lease["start"]})
        # Claude Code's documented PreToolUse JSON decision, with exit 0.
        os.write(1, MESSAGE)
    except Exception:
        pass
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
