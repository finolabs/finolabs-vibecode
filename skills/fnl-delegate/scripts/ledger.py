#!/usr/bin/env python3
"""Append-only dispatch ledger for the delegation skills.

Each dispatch writes a `start` line and later a `finish` line to a JSONL file
in the resolved data root. Environment variables cannot redirect the ledger.
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import statistics
import subprocess
import sys
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
# Keys open and summary read from each kind of line.
REQUIRED = {
    "start": {"id", "ts", "project", "task", "kind", "grade", "agent", "model", "reason"},
    "finish": {"id", "ts", "outcome", "rework_rounds"},
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


def load():
    try:
        text = dr.read_data("ledger.jsonl", 16 * 1024 * 1024).decode("utf-8")
    except FileNotFoundError:
        return {}, {}
    starts, finishes = {}, {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            rec = None
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
    append({
        "checkout_id": checkout_id,
        "coord_session": coord_session,
        "event": "start", "id": dispatch_id, "ts": now(),
        "project": args.project, "task": args.task, "kind": args.kind,
        "grade": args.grade, "coordinator": args.coordinator, "agent": args.agent,
        "model": args.model, "reason": args.reason, "route_by": args.route_by,
        "budget_min": args.budget,
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
    print("label: " + run_label(args.agent, args.model, args.project, args.task), file=sys.stderr)


def cmd_finish(args):
    # Scan before ledger reads can warn or anything about the run is stored.
    status = "not_scanned"
    if args.log_path is not None:
        try:
            import log_scan
            status = log_scan.scan(args.log_path)["status"]
        except (ImportError, OSError, ValueError):
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


def cmd_summary(args):
    rows = summary_rows(since=args.since, project=args.project)
    if args.json:
        print(json.dumps(rows))
        return
    if not rows:
        print("ledger: no finished dispatches match")
        return
    header = f"{'agent':<16}{'model':<24}{'kind':<10}{'grade':<10}{'n':>4}{'1st-pass':>10}{'accepted':>10}{'timeout':>9}{'fallback':>10}{'median min':>12}{'unverified':>12}"
    print(header)
    for r in rows:
        print(f"{r['agent']:<16}{r['model']:<24}{r['kind']:<10}{r['grade']:<10}{r['n']:>4}{r['first_pass']:>10.0%}{r['accepted']:>10.0%}"
              f"{r['timeout']:>9}{r['fallback']:>10}{r['median_min']:>12.0f}{r['accepted_unverified']:>12}")


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

    m = sub.add_parser("summary", help="acceptance and timing per agent, model, kind and grade")
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
