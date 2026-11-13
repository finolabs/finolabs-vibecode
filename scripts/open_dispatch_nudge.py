#!/usr/bin/env python3
"""Claude Code UserPromptSubmit reminder: delegated runs this session started that have no ledger outcome.

It reads the hook input's `session_id`, hashes it as `ledger.py start` computes `coord_session`, and reads the
dispatch ledger with a bounded read. It counts this session's records with no `finish` line that have an `ended`
line or are past their budget (60 minutes when absent), and prints one fixed line with the count and up to five ids,
at most once per 30 minutes per session. The throttle mark, one integer timestamp, is written atomically (mode 0600)
under `<data root>/state/dispatch-nudge/` before printing; when it cannot be written nothing is printed.

It reads only the ledger and its own mark, never denies anything, records no metrics event, sends nothing anywhere,
prints nothing on any error and always exits 0. `FNL_DISPATCH_NUDGE=off` disables it.
"""

import os
import signal
import sys

INPUT_LIMIT = 64 * 1024
LEDGER_LIMIT = 4 * 1024 * 1024  # the session-start hook's bound; a larger ledger prints nothing
DEFAULT_BUDGET = 60  # minutes, for a start line without a usable budget
THROTTLE = 30 * 60  # seconds between two reminders in one session
MARKS = "state/dispatch-nudge"
MAX_MARKS = 200
SHOWN = 5
LINE = ("Delegated runs this session started have no ledger outcome: {count} ({ids}). Record each with ledger.py "
        "finish (delegate \"Record\"); a run still working stays open.\n")


def due_ids(raw, coord_session, current):
    """Ids of this session's open records that ended or are past their budget, in ledger order."""
    import json
    import re
    from datetime import datetime
    dispatch = re.compile(r"d[0-9]{8}-[0-9]{6}-[0-9a-f]{4}")
    starts, finished, ended = {}, set(), set()
    for line in raw.decode("utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
            continue
        event = rec.get("event")
        if event == "start":
            if rec.get("coord_session") == coord_session and dispatch.fullmatch(rec["id"]):
                starts[rec["id"]] = rec
        elif event == "finish":
            finished.add(rec["id"])
        elif event == "ended" and type(rec.get("exit")) is int:
            ended.add(rec["id"])
    due = []
    for ident, rec in starts.items():
        if ident in finished:
            continue
        if ident in ended:
            due.append(ident)
            continue
        budget = rec.get("budget_min")
        if type(budget) is not int or budget <= 0:
            budget = DEFAULT_BUDGET
        try:
            started = datetime.fromisoformat(rec["ts"]).timestamp()
        except (KeyError, TypeError, ValueError):
            continue
        if (current - started) / 60 > budget:
            due.append(ident)
    return due


def claim_mark(dr, name, current):
    """True when this session may print now; the new mark is written first. False inside the throttle window."""
    import re
    with dr.data_folder(MARKS, create=True, private=True) as folder:
        try:
            raw = dr.read_file(folder, name, 32)
        except FileNotFoundError:
            raw = None
        if raw is not None and re.fullmatch(rb"[0-9]{1,12}", raw) and 0 <= current - int(raw) < THROTTLE:
            return False
        names = [n for n in os.listdir(folder) if re.fullmatch(r"[0-9a-f]{16}", n) and n != name]
        if len(names) >= MAX_MARKS:
            names.sort(key=lambda n: os.stat(n, dir_fd=folder, follow_symlinks=False).st_mtime)
            for old in names[:len(names) - MAX_MARKS + 1]:
                os.unlink(old, dir_fd=folder)
        dr.atomic_write(folder, name, str(int(current)).encode())
    return True


def main():
    try:
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(3)
        if os.environ.get("FNL_DISPATCH_NUDGE", "").lower() in {"off", "0", "false", "no"}:
            return 0

        import hashlib
        import json
        import re
        import time
        from pathlib import Path

        raw = sys.stdin.buffer.read(INPUT_LIMIT)
        if len(raw) == INPUT_LIMIT:
            return 0
        event = json.loads(raw)
        session = event.get("session_id") if isinstance(event, dict) else None
        # The same validation and hash as `ledger.py start`; the raw id is never stored.
        if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
            return 0
        digest = hashlib.sha256(session.encode("utf-8")).hexdigest()

        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import data_root as dr

        if dr.consent_root() is None:
            return 0
        try:
            ledger = dr.read_data("ledger.jsonl", LEDGER_LIMIT)
        except FileNotFoundError:
            return 0
        current = time.time()
        due = due_ids(ledger, digest[:12], current)
        if not due or not claim_mark(dr, digest[:16], current):
            return 0
        os.write(1, LINE.format(count=len(due), ids=", ".join(due[:SHOWN])).encode())
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
