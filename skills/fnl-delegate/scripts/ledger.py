#!/usr/bin/env python3
"""Append-only dispatch ledger for the delegation skills.

Each dispatch writes a `start` line and later a `finish` line to a JSONL file
in the resolved data root. Environment variables cannot redirect the ledger.
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

KINDS = ["implement", "review", "advise", "committee"]
GRADES = ["easy", "medium", "hard", "very-hard", "ultra-hard"]
AGENTS = ["claude", "claude-session", "codex", "antigravity", "subagent"]
COORDINATORS = ["claude", "codex", "antigravity"]
ROUTE_BY = ["table", "judge", "user"]
REASONS = ["routing", "fallback-quota", "fallback-failure", "user-choice"]
OUTCOMES = [
    "accepted", "rejected", "timeout", "stalled", "error",
    "blocked", "needs-permission", "quota", "cancelled",
]
TESTS = ["passed", "failed", "not-run"]
# Same closed lists as the assignment matrix (assignments.py); local ledger only.
WORK_TYPES = ["frontend", "design", "video", "three-d", "image-generation", "transcription"]
INSTALL = re.compile(r"claude|codex|antigravity|claude[a-z0-9]{1,24}")
# Keys open and summary read from each kind of line.
REQUIRED = {
    "start": {"id", "ts", "project", "task", "kind", "grade", "agent", "model", "reason"},
    "finish": {"id", "ts", "outcome", "rework_rounds"},
}
# Away-decision lines (docs/specs/away-decisions.md): load() skips them silently, load_away() returns them.
AWAY_EVENTS = {
    "decision": {"id", "ts", "lease_start", "rung", "settled"},
    "question_denied": {"ts", "lease_start"},
    "decision_review": {"id", "ts", "verdict"},
}


def ledger_path():
    root = dr.consent_root()
    if root is None:
        raise ValueError("invalid data root")
    return root / "ledger.jsonl"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(record):
    with dr.data_folder(create=True) as folder:
        fd = os.open("ledger.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                     0o600, dir_fd=folder)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            import stat
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise ValueError("unsafe ledger")
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_lines():
    try:
        return dr.read_data("ledger.jsonl", 16 * 1024 * 1024).decode("utf-8").splitlines()
    except FileNotFoundError:
        return []


def load_away():
    """The decision, question_denied and decision_review lines, in file order; anything else is skipped silently."""
    records = []
    for line in read_lines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        required = AWAY_EVENTS.get(rec.get("event")) if isinstance(rec, dict) else None
        if required and required <= rec.keys():
            records.append(rec)
    return records


def load():
    lines = read_lines()
    starts, finishes = {}, {}
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            rec = None
        if isinstance(rec, dict) and rec.get("event") in AWAY_EVENTS:
            continue  # away lines are read by load_away(), never reported as malformed
        required = REQUIRED.get(rec.get("event")) if isinstance(rec, dict) else None
        if not required or not required <= rec.keys():
            print(f"ledger: skipping malformed line {n}", file=sys.stderr)
            continue
        target = starts if rec["event"] == "start" else finishes
        target[rec.get("id")] = rec
    return starts, finishes


def run_label(agent, model, project, task):
    """`<runner>: <project> <task>` for the host's name field; the runner is the family plus a short model name."""
    family = {"claude-session": "claude", "subagent": "claude", "antigravity": "agy"}.get(agent, agent)
    words = [w for w in (model or "").split("-") if w and not any(c.isdigit() for c in w) and w not in ("claude", "gpt", "gemini", "default", "low", "medium", "high", "xhigh", "max", "ultra")]
    runner = f"{family} {words[-1]}" if words else family
    return " ".join(f"{runner}: {project} {task}".split())


def install_name(value):
    if not INSTALL.fullmatch(value):
        raise argparse.ArgumentTypeError("invalid install name")
    return value


def pick_fields(args):
    """Record the routing query's rank and its stderr notice; any failure leaves the rank out."""
    fields = {k: v for k, v in (("install", args.install), ("work_type", args.work_type), ("level", args.level))
              if v is not None}
    notice = None
    if args.work_type is not None and args.level is not None:
        try:
            import route_pick
            ranked = route_pick.rank(route_pick.answer(args.work_type, args.level, dispatcher=args.coordinator),
                                     args.install or args.agent, args.model)
            if ranked is not None:
                fields["pick_rank"] = ranked[0]
                if ranked[0] > 1:
                    notice = f"off the preferred order: rank {ranked[0]}"
                elif ranked[0] == 0:
                    notice = f"off the preferred set: {ranked[1]}"
        except Exception:
            fields.pop("pick_rank", None)
            notice = None  # a preference never refuses or changes a dispatch
    return fields, notice


def cmd_start(args):
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
        session = ""  # unknown or unusable ids are recorded as null, never echoed
    coord_session = hashlib.sha256(session.encode("utf-8")).hexdigest()[:12] if session else None
    try:
        from mode import effective
        manual = effective(keys=("delegation_mode",), gate_opt_in=True)["delegation_mode"] == "manual"
    except Exception:
        manual = False
    family = "claude" if args.agent in ("claude", "claude-session", "subagent") else args.agent
    if manual and family != args.coordinator and args.route_by != "user":
        sys.exit("Delegation mode is manual: another agent family needs --route-by user")
    dispatch_id = datetime.now().strftime("d%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    try:
        from record import checkout_identity
        checkout_id = checkout_identity(args.checkout)
    except (ImportError, OSError, ValueError, subprocess.SubprocessError):
        checkout_id = None  # non-code tasks can still end through the explicit escape hatch
    picked, notice = pick_fields(args)
    append({
        "checkout_id": checkout_id,
        "coord_session": coord_session,
        "event": "start", "id": dispatch_id, "ts": now(),
        "project": args.project, "task": args.task, "kind": args.kind,
        "grade": args.grade, "coordinator": args.coordinator, "agent": args.agent,
        "model": args.model, "reason": args.reason, "route_by": args.route_by,
        "budget_min": args.budget, **picked,
    })
    if args.kind == "implement":
        try:
            sys.dont_write_bytecode = True
            sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
            from mode import effective
            from auto_gate import enabled, repository_key, write_decision
            if enabled(effective):
                key = repository_key(os.getcwd())
                if key:
                    write_decision(key, "handoff")
        except Exception:
            pass  # gate state must never change this command's output or exit code
    print(dispatch_id)
    if notice:
        print(notice, file=sys.stderr)
    print("label: " + run_label(args.agent, args.model, args.project, args.task), file=sys.stderr)


def cmd_finish(args):
    # Scan before ledger reads can warn or anything about the run is stored.
    status = "not_scanned"
    if args.log_path is not None:
        try:
            import log_scan
            status = log_scan.scan(args.log_path)["status"]
        except (ImportError, OSError, ValueError) as error:
            # Only the fixed folder message is shown; other refusals stay terse.
            folder = getattr(sys.modules.get("log_scan"), "FolderRefused", None)
            if folder is not None and isinstance(error, folder):
                sys.exit("ledger: log refused; " + str(error))
            sys.exit("ledger: log refused")
    starts, finishes = load()
    if args.id not in starts:
        sys.exit(f"ledger: no start line for {args.id}")
    if args.id in finishes:
        sys.exit(f"ledger: {args.id} already has a finish line")
    if args.head is not None and starts[args.id]["kind"] != "implement":
        sys.exit("ledger: only implementation dispatches can bind a head")
    if args.head is not None and not re.fullmatch(r"[0-9a-f]{40}", args.head):
        sys.exit("ledger: invalid head")
    extra = {}
    if args.accept_unverified and args.outcome != "accepted":
        sys.exit("ledger: --accept-unverified requires accepted")
    if args.reason and not args.accept_unverified:
        sys.exit("ledger: --reason requires --accept-unverified")
    if args.outcome == "accepted":
        if args.accept_unverified:
            if not args.reason or not args.reason.strip() or len(args.reason) > 4096:
                sys.exit("ledger: --accept-unverified requires a bounded nonempty --reason")
            # Free text is never persisted. The digest identifies the coordinator's report.
            extra = {"accept_unverified": True,
                     "reason_id": hashlib.sha256(args.reason.encode()).hexdigest()}
        else:
            try:
                from record import checkout_identity, current_head, read_verification
                receipt = read_verification(args.id)
                identity = checkout_identity(args.checkout)
                if (starts[args.id].get("checkout_id") != identity or receipt["checkout_id"] != identity
                        or receipt["head"] != current_head(args.checkout)
                        or (args.head is not None and receipt["head"] != args.head)
                        or receipt["mechanical"] != "passed" or receipt["tests"] != "passed"):
                    raise ValueError("verification mismatch")
                extra = {"verified_head": receipt["head"], "accept_unverified": False}
            except (ImportError, OSError, ValueError, TypeError, subprocess.SubprocessError):
                sys.exit("ledger: acceptance refused: current checkout head needs a passing verify receipt; "
                         "or use --accept-unverified --reason")
    if status != "no_findings":
        print("ledger: log_scan: " + status, file=sys.stderr)
    append({
        **extra,
        **({"head": args.head, "agent": starts[args.id]["agent"]} if args.head is not None else {}),
        "event": "finish", "id": args.id, "ts": now(), "outcome": args.outcome,
        "rework_rounds": args.rework_rounds, "tests": args.tests, "note": args.note,
        "log_scan": status,
    })


def minutes(start, finish):
    delta = datetime.fromisoformat(finish["ts"]) - datetime.fromisoformat(start["ts"])
    return delta.total_seconds() / 60


def cmd_open(args):
    starts, finishes = load()
    current = datetime.now(timezone.utc)
    for dispatch_id, s in starts.items():
        if args.project is not None and s["project"] != args.project:
            continue
        if dispatch_id not in finishes:
            age = (current - datetime.fromisoformat(s["ts"])).total_seconds() / 60
            print(f"{dispatch_id}  {s['ts']}  age {age:.0f}/{s.get('budget_min', '?')} min  "
                  f"{s['agent']}/{s['model']}  {s['project']}: {s['task']}")


STALE_STATE = "state/ledger-stale"
STALE_EXPIRY = 3600
STALE_OUTCOMES = ("stalled", "error", "cancelled")
LOG_TAIL = 64
SAFE_ID = re.compile(r"[A-Za-z0-9-]{1,40}")  # the ids `start` writes; anything else never names a log file
EXIT_LINE = re.compile(rb"exit=(-?[0-9]{1,3})")


def past_budget(start, current):
    """Age in minutes when the record is past a positive budget, else None (inside it, or no usable budget)."""
    budget = start.get("budget_min")
    if type(budget) is not int or budget <= 0:
        return None
    try:
        age = (current - datetime.fromisoformat(start["ts"])).total_seconds() / 60
    except (TypeError, ValueError):
        return None
    return age if age > budget else None


def log_facts(ident, current):
    """None when no log is named for the id, else (last-write age in minutes, exit code or None).

    Reads only the last 64 bytes; the content never leaves this function."""
    import log_scan
    root = log_scan.run_log_folder()
    try:
        os.lstat(root)
    except FileNotFoundError:
        return None  # a preview never creates the run-log folder
    with log_scan.folder_descriptor(root) as folder:
        try:
            fd = os.open(ident + ".log", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
        except FileNotFoundError:
            return None
        try:
            info = log_scan.check_file(fd)
            offset = max(0, info.st_size - LOG_TAIL)
            os.lseek(fd, offset, os.SEEK_SET)
            tail = os.read(fd, LOG_TAIL)
        finally:
            os.close(fd)
    lines = tail.splitlines()
    if offset and lines:
        lines = lines[1:]  # the first line of a cut tail is partial
    codes = [m for m in (EXIT_LINE.fullmatch(line.strip()) for line in lines) if m]
    return (max(0.0, current.timestamp() - info.st_mtime) / 60, int(codes[-1][1]) if codes else None)


def stale_rows():
    """Open records past their budget: (id, age, budget, log description, outcome or None, note)."""
    import log_scan
    starts, finishes = load()
    current = datetime.now(timezone.utc)
    rows = []
    for ident, start in starts.items():
        if ident in finishes:
            continue
        age = past_budget(start, current)
        if age is None:
            continue
        if not isinstance(ident, str) or not SAFE_ID.fullmatch(ident):
            rows.append(("(invalid id)", age, start["budget_min"], "unchecked", None, ""))
            continue
        try:
            facts = log_facts(ident, current)
        except log_scan.FolderRefused:
            raise
        except (OSError, ValueError):
            rows.append((ident, age, start["budget_min"], "refused", None, ""))
            continue
        if facts is None:
            described, outcome, reason = "none", "cancelled", "no log"
        else:
            log_age, code = facts
            exit_text = "no exit line" if code is None else f"exit={code}"
            described = f"age {log_age:.0f} min, {exit_text}"
            outcome = "error" if code not in (None, 0) else "stalled"
            reason = "log " + exit_text
        rows.append((ident, age, start["budget_min"], described, outcome,
                     f"closed late by ledger stale: past budget, {reason}"))
    return rows


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def stale_preview():
    rows = stale_rows()
    if not rows:
        print("ledger: no open records past their budget")
        return
    root = dr.consent_root()
    if root is None:
        raise ValueError("invalid data root")
    for ident, age, budget, described, outcome, _ in rows:
        print(f"{ident}  age {age:.0f}/{budget} min  log: {described}  -> {outcome or 'left open'}")
    records = [{"id": ident, "outcome": outcome, "note": note} for ident, _, _, _, outcome, note in rows if outcome]
    if not records:
        print("ledger: nothing to close; ledger unchanged")
        return
    plan = {"root": str(root), "created": time.time(), "records": records}
    value = plan_digest(plan)
    with dr.data_folder(STALE_STATE, create=True, private=True) as state:
        fcntl.flock(state, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dr.atomic_write(state, "preview.json", json.dumps({"plan": plan, "digest": value}).encode())
    print(f"Closes {len(records)} of {len(rows)} listed records; none is marked accepted.")
    print("Digest: " + value)
    print("Close with: ledger.py stale --close --digest <at least 12 hex digits of the digest>")
    print("Preview expires in 60 minutes; ledger unchanged.")


def valid_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {"root", "created", "records"}:
        return False
    if type(plan["created"]) not in (int, float) or not isinstance(plan["records"], list):
        return False
    return all(isinstance(r, dict) and set(r) == {"id", "outcome", "note"} and isinstance(r["id"], str)
               and SAFE_ID.fullmatch(r["id"]) and r["outcome"] in STALE_OUTCOMES
               and isinstance(r["note"], str) and len(r["note"]) <= 200 for r in plan["records"])


def stale_close(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{12,64}", value):
        raise ValueError("at least 12 hex digits of the preview digest required")
    root = dr.consent_root()
    if root is None:
        raise ValueError("invalid data root")
    with dr.data_folder(STALE_STATE, private=True) as state:
        fcntl.flock(state, fcntl.LOCK_EX | fcntl.LOCK_NB)
        import stat
        raw = dr.read_file(state, "preview.json", 1024 * 1024)
        if stat.S_IMODE(os.stat("preview.json", dir_fd=state, follow_symlinks=False).st_mode) != 0o600:
            raise ValueError("preview must be private (0600)")
        saved = json.loads(raw)
        if not isinstance(saved, dict) or set(saved) != {"plan", "digest"} or not valid_plan(saved["plan"]):
            raise ValueError("invalid preview; preview again")
        plan = saved["plan"]
        digest = plan_digest(plan)
        if saved["digest"] != digest or not digest.startswith(value):
            raise ValueError("digest mismatch; preview again")
        if plan["root"] != str(root):
            raise ValueError("data root changed; preview again")
        if not 0 <= time.time() - plan["created"] <= STALE_EXPIRY:
            raise ValueError("preview expired; preview again")
        starts, finishes = load()
        current = datetime.now(timezone.utc)
        closed = 0
        for item in plan["records"]:
            start = starts.get(item["id"])
            if start is None or item["id"] in finishes or past_budget(start, current) is None:
                continue  # finished since the preview, or never past its budget: never closed here
            append({"event": "finish", "id": item["id"], "ts": now(), "outcome": item["outcome"],
                    "rework_rounds": 0, "tests": "not-run", "note": item["note"], "log_scan": "not_scanned"})
            closed += 1
        os.unlink("preview.json", dir_fd=state)
        os.fsync(state)
    print(f"ledger: closed {closed} of {len(plan['records'])} previewed records")


def cmd_stale(args):
    import log_scan
    if args.close and args.digest is None:
        sys.exit("ledger: --close needs --digest from the preview")
    if args.digest is not None and not args.close:
        sys.exit("ledger: --digest only goes with --close")
    try:
        if args.close:
            stale_close(args.digest)
        else:
            stale_preview()
    except log_scan.FolderRefused as error:
        sys.exit("ledger: " + str(error))
    except FileNotFoundError:
        sys.exit("ledger: stale refused: no preview; preview again")
    except BlockingIOError:
        sys.exit("ledger: stale refused: another stale command is running")
    except (OSError, json.JSONDecodeError, UnicodeError):
        sys.exit("ledger: stale refused: unsafe or unreadable state; preview again")


SUMMARY_KEYS = ("agent", "model", "kind", "grade")
SUMMARY_GROUP_KEYS = (*SUMMARY_KEYS, "route_by")


def summary_rows(keys=SUMMARY_KEYS, since=None, project=None):
    """One dict per group of finished dispatches: the key fields, the counts and the rates."""
    if not keys or any(k not in SUMMARY_GROUP_KEYS for k in keys):
        raise ValueError("invalid summary key")
    starts, finishes = load()
    groups = defaultdict(list)
    for dispatch_id, s in starts.items():
        if since and s["ts"][:10] < since:
            continue
        if project and s["project"] != project:
            continue
        f = finishes.get(dispatch_id)
        if f is None:
            continue
        if "route_by" in keys and s.get("route_by") not in ROUTE_BY:
            continue  # older or malformed lines have no known routing source
        groups[tuple(s[k] for k in keys)].append((s, f))
    rows = []
    for key, pairs in sorted(groups.items()):
        n = len(pairs)
        accepted = [f for _, f in pairs if f["outcome"] == "accepted"]
        rows.append({
            **dict(zip(keys, key)), "n": n,
            "first_pass": len([f for f in accepted if f["rework_rounds"] == 0]) / n,
            "accepted": len(accepted) / n,
            "accepted_unverified": sum(f.get("accept_unverified") is True for f in accepted),
            "timeout": len([f for _, f in pairs if f["outcome"] in ("timeout", "stalled")]),
            "fallback": len([s for s, _ in pairs if s["reason"].startswith("fallback")]),
            "quota": len([f for _, f in pairs if f["outcome"] == "quota"]),
            "error": len([f for _, f in pairs if f["outcome"] == "error"]),
            "median_min": statistics.median(minutes(s, f) for s, f in pairs),
            "rework": statistics.mean(f["rework_rounds"] for _, f in pairs),
        })
    return rows


def pick_rows(since=None, project=None):
    """Per install (else agent): dispatches with a pick_rank at rank 1, lower and outside, and how many had none."""
    starts, _ = load()
    counts = {}
    for s in starts.values():
        if since and s["ts"][:10] < since:
            continue
        if project and s["project"] != project:
            continue
        name = s.get("install") or s["agent"]
        row = counts.setdefault(name, {"agent": name, "ranked": 0, "first": 0, "lower": 0, "outside": 0, "left_out": 0})
        rank = s.get("pick_rank")
        if type(rank) is not int or rank < 0:
            row["left_out"] += 1  # older or unpicked dispatches never count as outside the set
            continue
        row["ranked"] += 1
        row["first" if rank == 1 else "lower" if rank > 1 else "outside"] += 1
    if not any(row["ranked"] for row in counts.values()):
        return []
    return [counts[name] for name in sorted(counts)]


def print_pick_rows(rows):
    print()
    print("preferred order (shares over dispatches with a pick rank)")
    print(f"{'agent':<16}{'ranked':>8}{'rank 1':>8}{'lower':>8}{'outside':>9}{'left out':>10}")
    for r in rows:
        n = r["ranked"]
        shares = [f"{r[k] / n:.0%}" if n else "-" for k in ("first", "lower", "outside")]
        print(f"{r['agent']:<16}{n:>8}{shares[0]:>8}{shares[1]:>8}{shares[2]:>9}{r['left_out']:>10}")


def away_rows(since=None, project=None):
    """Per lease: decisions by deciding rung, advisor attempts by agent and model, the Jev spread, parked, denied, reversed."""
    leases = defaultdict(lambda: {"attempts": defaultdict(list), "denied": 0})
    reviews, lease_of = {}, {}
    for rec in load_away():
        if since and str(rec["ts"])[:10] < since:
            continue
        if rec["event"] == "decision_review":
            reviews[rec["id"]] = rec["verdict"]  # a later review of the same id replaces the earlier one
            continue
        if not isinstance(rec["lease_start"], (int, float)) or isinstance(rec["lease_start"], bool):
            continue
        if rec["event"] == "question_denied":
            leases[rec["lease_start"]]["denied"] += 1
        elif not project or rec.get("project") == project:
            leases[rec["lease_start"]]["attempts"][rec["id"]].append(rec)
            lease_of[rec["id"]] = rec["lease_start"]
    rows = []
    for start in sorted(leases):
        attempts, by_rung, by_advisor, probabilities = leases[start]["attempts"], defaultdict(int), defaultdict(int), []
        parked = no_precedent = reviewed = reversed_ = 0
        for decision_id, tries in attempts.items():
            settled = [t for t in tries if t["settled"] == "yes"]
            if settled:
                by_rung[settled[-1]["rung"]] += 1
                parked += settled[-1]["rung"] == "park"
            if all(t.get("precedents") == 0 for t in tries):
                no_precedent += 1
            for t in tries:
                if t["rung"] == "advisor" and t.get("by"):
                    by_advisor[f"{t['by']} {t.get('model') or '-'}"] += 1
                if t["rung"] == "jev" and isinstance(t.get("probability"), (int, float)):
                    probabilities.append(float(t["probability"]))
            if decision_id in reviews:
                reviewed += 1
                reversed_ += reviews[decision_id] == "reversed"
        spread = ({"n": len(probabilities), "min": min(probabilities), "median": statistics.median(probabilities),
                   "max": max(probabilities)} if probabilities else {"n": 0})
        rows.append({"lease_start": start, "decisions": len(attempts), "by_rung": dict(sorted(by_rung.items())),
                     "by_advisor": dict(sorted(by_advisor.items())), "jev_p": spread, "parked": parked,
                     "denied": leases[start]["denied"], "no_precedent": no_precedent,
                     "reviewed": reviewed, "reversed": reversed_})
    return rows


def print_away_rows(rows):
    print()
    print("away decisions per lease (no question or option text is kept)")
    for r in rows:
        started = datetime.fromtimestamp(r["lease_start"], timezone.utc).isoformat(timespec="minutes")
        rungs = ", ".join(f"{k} {v}" for k, v in r["by_rung"].items()) or "none settled"
        advisors = ", ".join(f"{k} {v}" for k, v in r["by_advisor"].items()) or "none"
        p = r["jev_p"]
        spread = f"n {p['n']}, min {p['min']:.2f}, median {p['median']:.2f}, max {p['max']:.2f}" if p["n"] else "n 0"
        share = f"reversed {r['reversed']} of {r['reviewed']} reviewed" if r["reviewed"] else "none reviewed yet"
        print(f"lease {started}: {r['decisions']} decisions ({r['no_precedent']} without precedent); by rung: {rungs}; "
              f"advisors: {advisors}; Jev p: {spread}; parked {r['parked']}; denied questions {r['denied']}; {share}")


def cmd_summary(args):
    rows = summary_rows(since=args.since, project=args.project)
    if args.json:
        print(json.dumps(rows))
        return
    picks = pick_rows(since=args.since, project=args.project)
    away = away_rows(since=args.since, project=args.project)
    if not rows:
        print("ledger: no finished dispatches match")
        if picks:
            print_pick_rows(picks)
        if away:
            print_away_rows(away)
        return
    header = f"{'agent':<16}{'model':<24}{'kind':<10}{'grade':<10}{'n':>4}{'1st-pass':>10}{'accepted':>10}{'timeout':>9}{'fallback':>10}{'median min':>12}{'unverified':>12}"
    print(header)
    for r in rows:
        print(f"{r['agent']:<16}{r['model']:<24}{r['kind']:<10}{r['grade']:<10}{r['n']:>4}{r['first_pass']:>10.0%}{r['accepted']:>10.0%}"
              f"{r['timeout']:>9}{r['fallback']:>10}{r['median_min']:>12.0f}{r['accepted_unverified']:>12}")
    if picks:
        print_pick_rows(picks)
    if away:
        print_away_rows(away)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="record a dispatch; prints its id")
    s.add_argument("--project", required=True)
    s.add_argument("--task", required=True, help="short label, no task data or secrets")
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--grade", required=True, choices=GRADES)
    s.add_argument("--coordinator", default="claude", choices=COORDINATORS)
    s.add_argument("--agent", required=True, choices=AGENTS)
    s.add_argument("--model", default="default")
    s.add_argument("--reason", default="routing", choices=REASONS)
    s.add_argument("--route-by", default="table", choices=ROUTE_BY)
    s.add_argument("--budget", type=int, required=True, help="time budget in minutes")
    s.add_argument("--checkout", default=".", help="delegated checkout; only its hash is stored")
    s.add_argument("--install", type=install_name, help="install compared with the matrix in place of --agent")
    s.add_argument("--work-type", choices=WORK_TYPES)
    s.add_argument("--level", type=int, choices=range(1, 6), help="numeric level of the grade, 1 to 5")
    s.set_defaults(func=cmd_start)

    f = sub.add_parser("finish", help="record how a dispatch ended")
    f.add_argument("id")
    f.add_argument("--log-path", help="regular file inside the private run-log folder")
    f.add_argument("--head", help="exact reviewed implementation head for trusted review routing")
    f.add_argument("--outcome", required=True, choices=OUTCOMES)
    f.add_argument("--rework-rounds", type=int, default=0)
    f.add_argument("--tests", default="not-run", choices=TESTS)
    f.add_argument("--note", default="")
    f.add_argument("--checkout", default=".", help="the checkout named at dispatch")
    f.add_argument("--accept-unverified", action="store_true")
    f.add_argument("--reason", help="reason retained only as a digest; keep text in the coordinator report")
    f.set_defaults(func=cmd_finish)

    o = sub.add_parser("open", help="list dispatches with no finish line")
    o.add_argument("--project", help="only dispatches of this exact project name")
    o.set_defaults(func=cmd_open)

    st = sub.add_parser("stale", help="preview open records past their budget; close them with --close --digest")
    st.add_argument("--close", action="store_true", help="close the records the preview listed")
    st.add_argument("--digest", help="at least 12 hex digits of the preview digest")
    st.set_defaults(func=cmd_stale)

    m = sub.add_parser("summary",help="acceptance and timing per agent, model, kind and grade")
    m.add_argument("--since", help="YYYY-MM-DD")
    m.add_argument("--project")
    m.add_argument("--json", action="store_true", help="print the rows as JSON")
    m.set_defaults(func=cmd_summary)
    return p


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except ValueError as error:
        sys.exit("ledger: " + str(error).splitlines()[0])


if __name__ == "__main__":
    main()
