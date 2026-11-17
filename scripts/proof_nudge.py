#!/usr/bin/env python3
"""Proof nudge (Claude Code): one fixed line at the end of a turn whose session committed the head unproven.

`proof_nudge.py start` (SessionStart) writes the session's start time into its mark when none exists and prints
nothing. `proof_nudge.py` (Stop) prints one fixed line as the Stop hook's non-blocking
`hookSpecificOutput.additionalContext` only when all hold: the session has a mark; the working folder's checkout
HEAD is the new commit of a `commit`, `cherry-pick` or `revert` entry in that checkout's HEAD reflog written at or
after the session's start; no `checks` receipt (`state/checks-receipts/<code>.json`) and no `verify_claim.py` or
`checks.py --dispatch` receipt (`state/verification/<id>.json`) names that head; the hook input's
`stop_hook_active` is not true; and the mark does not already hold this head. The new mark (start time and a
16-hex hash of the head) is written atomically, mode 0600, under `<data root>/state/proof-nudge/` before printing;
when it cannot be written nothing is printed.

It reads only git refs (HEAD, one ref file or packed-refs), the last 64 KiB of the HEAD reflog, keeping each
entry's new commit id, time and action word and discarding the subject, the two receipt folders' head fields and
its own mark. It never denies or blocks anything (never `decision: block`), records no metrics event, sends nothing
anywhere, prints nothing on any error and always exits 0. `FNL_PROOF_NUDGE=off` disables it.
See docs/specs/proof-nudge.md.
"""

import os
import signal
import sys

INPUT_LIMIT = 64 * 1024
REFLOG_TAIL = 64 * 1024
PACKED_LIMIT = 1024 * 1024
RECEIPT_LIMIT = 65536
MAX_RECEIPTS = 500
MAX_MARKS = 200
MARK_LIMIT = 64
MARKS = "state/proof-nudge"
CHECKS_RECEIPTS = "state/checks-receipts"
VERIFICATION = "state/verification"
ACTIONS = ("commit", "cherry-pick", "revert")
LINE = ("This session committed the current head and no checks or verify_claim receipt names it. Before reporting "
        "the work as done, run the targeted tests for the change and read their output.")


def off():
    return os.environ.get("FNL_PROOF_NUDGE", "").strip().lower() in {"off", "0", "false", "no"}


def session_name(event):
    """The mark name for the hook input's session id, or None; the raw id is never stored."""
    import hashlib
    import re
    session = event.get("session_id") if isinstance(event, dict) else None
    if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
        return None
    return hashlib.sha256(session.encode("utf-8")).hexdigest()[:16]


def read_mark(dr, name):
    """(start, head hash or None); None when there is no mark. Raises on an unsafe or malformed mark."""
    import re
    try:
        with dr.data_folder(MARKS, private=True) as folder:
            raw = dr.read_file(folder, name, MARK_LIMIT)
    except FileNotFoundError:
        return None
    found = re.fullmatch(rb"([0-9]{1,12})(?: ([0-9a-f]{16}))?", raw)
    if not found:
        raise ValueError("invalid mark")
    return int(found[1]), found[2].decode("ascii") if found[2] else None


def write_mark(dr, name, start, head_hash=None):
    import re
    with dr.data_folder(MARKS, create=True, private=True) as folder:
        names = [n for n in os.listdir(folder) if re.fullmatch(r"[0-9a-f]{16}", n) and n != name]
        if len(names) >= MAX_MARKS:
            names.sort(key=lambda n: os.stat(n, dir_fd=folder, follow_symlinks=False).st_mtime_ns)
            for old in names[:len(names) - MAX_MARKS + 1]:
                os.unlink(old, dir_fd=folder)
        body = str(int(start)) + (" " + head_hash if head_hash else "")
        dr.atomic_write(folder, name, body.encode("ascii"))


def resolve_head(gm, gitdir, common):
    """The 40- or 64-hex commit id HEAD names, read from HEAD, a loose ref or packed-refs; None when unknown."""
    import re
    sha = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
    line = gm.bounded(gitdir / "HEAD", 4096).decode("ascii").strip()
    if sha.fullmatch(line):
        return line
    if not line.startswith("ref: "):
        return None
    ref = line[5:].strip()
    if not re.fullmatch(r"refs/heads/[A-Za-z0-9._/-]{1,200}", ref) or ".." in ref or "//" in ref:
        return None
    try:
        value = gm.bounded(common / ref, 4096).decode("ascii").strip()
        return value if sha.fullmatch(value) else None
    except FileNotFoundError:
        pass
    try:
        packed = gm.bounded(common / "packed-refs", PACKED_LIMIT).decode("ascii", "replace")
    except FileNotFoundError:
        return None
    for entry in packed.splitlines():
        parts = entry.split(" ")
        if len(parts) == 2 and parts[1] == ref and sha.fullmatch(parts[0]):
            return parts[0]
    return None


def reflog_commits(gm, gitdir):
    """(new commit id, time) of the commit-like entries in the HEAD reflog's last 64 KiB; subjects are discarded."""
    import re
    with gm.opened(gitdir / "logs" / "HEAD") as fd:
        size = os.fstat(fd).st_size
        offset = max(0, size - REFLOG_TAIL)
        os.lseek(fd, offset, os.SEEK_SET)
        chunks, total = [], 0
        while total < REFLOG_TAIL:
            chunk = os.read(fd, REFLOG_TAIL - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    lines = b"".join(chunks).split(b"\n")
    if offset:
        lines = lines[1:]  # the first line may be cut
    found = []
    for line in lines:
        head, tab, message = line.partition(b"\t")
        if not tab:
            continue
        fields = head.split(b" ")
        if len(fields) < 4 or not re.fullmatch(rb"[0-9]{1,12}", fields[-2]):
            continue
        action = message.split(b":", 1)[0].split(b" ", 1)[0].decode("ascii", "replace")
        new = fields[1].decode("ascii", "replace")
        if action in ACTIONS and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", new):
            found.append((new, int(fields[-2])))
    return found


def has_receipt(dr, code, head):
    """True when a checks receipt for this repository, or a verification receipt with passing tests, names this head
    (a checks receipt is only written when the whole list passed)."""
    import json
    import re
    try:
        with dr.data_folder(CHECKS_RECEIPTS, private=True) as folder:
            record = json.loads(dr.read_file(folder, code + ".json", 4096))
        if isinstance(record, dict) and record.get("kind") == "checks" and record.get("head") == head:
            return True
    except (FileNotFoundError, ValueError):
        pass
    try:
        with dr.data_folder(VERIFICATION, private=True) as folder:
            names = sorted((n for n in os.listdir(folder)
                            if re.fullmatch(r"d[0-9]{8}-[0-9]{6}-[0-9a-f]{4}\.json", n)), reverse=True)[:MAX_RECEIPTS]
            for name in names:
                try:
                    record = json.loads(dr.read_file(folder, name, RECEIPT_LIMIT))
                except (FileNotFoundError, ValueError):
                    continue
                if (isinstance(record, dict) and record.get("kind") == "verify" and record.get("head") == head
                        and record.get("tests") == "passed"):
                    return True
    except FileNotFoundError:
        pass
    return False


def main(argv=()):
    try:
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(3)
        argv = list(argv)
        if argv not in ([], ["start"]) or off():
            return 0

        import hashlib
        import json
        import time
        from pathlib import Path

        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            return 0
        event = json.loads(raw)
        name = session_name(event)
        if name is None:
            return 0

        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import data_root as dr

        now = int(time.time())
        mark = read_mark(dr, name)
        if mark is None:
            write_mark(dr, name, now)  # first sight: commits from now on count
            return 0
        if argv or event.get("stop_hook_active") is True:
            return 0
        start, nudged = mark

        import git_metadata as gm
        import project_store as store
        cwd = event.get("cwd")
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            return 0
        root, gitdir, common = gm.checkout_dirs(cwd)
        head = resolve_head(gm, gitdir, common)
        if head is None:
            return 0
        if not any(new == head and when >= start for new, when in reflog_commits(gm, gitdir)):
            return 0
        head_hash = hashlib.sha256(head.encode("ascii")).hexdigest()[:16]
        if head_hash == nudged:
            return 0
        if has_receipt(dr, store.repository_code(root), head):
            return 0
        write_mark(dr, name, start, head_hash)
        os.write(1, json.dumps({"hookSpecificOutput": {"hookEventName": "Stop",
                                                       "additionalContext": LINE}}).encode("ascii") + b"\n")
    except Exception:
        pass
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except BaseException:
        pass
    raise SystemExit(0)
