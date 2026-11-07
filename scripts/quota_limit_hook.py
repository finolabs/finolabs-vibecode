#!/usr/bin/env python3
"""Claude StopFailure metadata marker. Every failure is silent and exits 0."""
import os
import signal
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    try:
        # Never hold a hook open for a missing/partial stdin writer.
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(2)
        import json
        import quota_probe as qp

        raw = sys.stdin.buffer.read(qp.LIMIT + 1)
        if len(raw) > qp.LIMIT:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get("error") != "rate_limit":
            return 0
        # config() uses only the account-anchored, owner-checked no-follow host.
        if not qp.config():
            return 0
        # Missing or unsafe state stays missing/untouched; no repair from a hook.
        with qp.state_folder() as folder:
            qp.limit_markers(folder)
            qp.write_json(folder, "limits.json", {"claude": qp.stamp(qp.now())})
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
