#!/usr/bin/env python3
"""Claude Code PreToolUse nudge; every failure allows silently with exit 0."""

import os
import signal
import sys


def main():
    try:
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(2)
        if os.environ.get("FNL_AUTO_GATE", "").lower() in {"off", "0", "false", "no"}:
            return 0

        import json
        from pathlib import Path

        raw = sys.stdin.buffer.read(64 * 1024)
        if len(raw) == 64 * 1024:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get("tool_name") not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            return 0
        cwd = event.get("cwd")
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            return 0

        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from mode import effective
        from auto_gate import enabled, repository_key, claim_denial

        if not enabled(effective):
            return 0
        key = repository_key(cwd)
        if key and claim_denial(key):
            # Claude Code's documented PreToolUse JSON decision, with exit 0.
            os.write(1, b'{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
                     b'"permissionDecision":"deny","permissionDecisionReason":'
                     b'"Run the keep-or-hand-off step of fnl-delegate, then retry."}}\n')
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
