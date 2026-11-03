#!/usr/bin/env python3
"""Append-only dispatch ledger for the delegation skills.

Each dispatch writes a `start` line and later a `finish` line to a JSONL file
(default $XDG_STATE_HOME/finolabs-vibecode/ledger.jsonl, with XDG_STATE_HOME
defaulting to ~/.local/state; override with ORCHESTRATION_LEDGER).
`summary` joins them to measure routing: first-pass acceptance, timeouts,
fallbacks and duration per agent, model, kind and grade.
"""

import argparse
import json
import os
import secrets
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

KINDS = ["implement", "review", "advise", "committee"]
GRADES = ["easy", "medium", "hard", "very-hard"]
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
    override = os.environ.get("ORCHESTRATION_LEDGER")
    if override:
        return Path(override)
    state = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state"
    return Path(state) / "finolabs-vibecode/ledger.jsonl"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(record):
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load():
    path = ledger_path()
    if not path.exists():
        return {}, {}
    starts, finishes = {}, {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
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


def cmd_start(args):
    dispatch_id = datetime.now().strftime("d%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    append({
        "event": "start", "id": dispatch_id, "ts": now(),
        "project": args.project, "task": args.task, "kind": args.kind,
        "grade": args.grade, "coordinator": args.coordinator, "agent": args.agent,
        "model": args.model, "reason": args.reason, "route_by": args.route_by,
        "budget_min": args.budget,
    })
    print(dispatch_id)


def cmd_finish(args):
    starts, finishes = load()
    if args.id not in starts:
        sys.exit(f"ledger: no start line for {args.id}")
    if args.id in finishes:
        sys.exit(f"ledger: {args.id} already has a finish line")
    append({
        "event": "finish", "id": args.id, "ts": now(), "outcome": args.outcome,
        "rework_rounds": args.rework_rounds, "tests": args.tests, "note": args.note,
    })


def minutes(start, finish):
    delta = datetime.fromisoformat(finish["ts"]) - datetime.fromisoformat(start["ts"])
    return delta.total_seconds() / 60


def cmd_open(args):
    starts, finishes = load()
    current = datetime.now(timezone.utc)
    for dispatch_id, s in starts.items():
        if dispatch_id not in finishes:
            age = (current - datetime.fromisoformat(s["ts"])).total_seconds() / 60
            print(f"{dispatch_id}  {s['ts']}  age {age:.0f}/{s.get('budget_min', '?')} min  "
                  f"{s['agent']}/{s['model']}  {s['project']}: {s['task']}")


SUMMARY_KEYS = ("agent", "model", "kind", "grade")


def summary_rows(keys=SUMMARY_KEYS, since=None, project=None):
    """One dict per group of finished dispatches: the key fields, the counts and the rates."""
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
        groups[tuple(s[k] for k in keys)].append((s, f))
    rows = []
    for key, pairs in sorted(groups.items()):
        n = len(pairs)
        accepted = [f for _, f in pairs if f["outcome"] == "accepted"]
        rows.append({
            **dict(zip(keys, key)), "n": n,
            "first_pass": len([f for f in accepted if f["rework_rounds"] == 0]) / n,
            "accepted": len(accepted) / n,
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
    header = f"{'agent':<16}{'model':<24}{'kind':<10}{'grade':<10}{'n':>4}{'1st-pass':>10}{'accepted':>10}{'timeout':>9}{'fallback':>10}{'median min':>12}"
    print(header)
    for r in rows:
        print(f"{r['agent']:<16}{r['model']:<24}{r['kind']:<10}{r['grade']:<10}{r['n']:>4}{r['first_pass']:>10.0%}{r['accepted']:>10.0%}"
              f"{r['timeout']:>9}{r['fallback']:>10}{r['median_min']:>12.0f}")


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
    s.set_defaults(func=cmd_start)

    f = sub.add_parser("finish", help="record how a dispatch ended")
    f.add_argument("id")
    f.add_argument("--outcome", required=True, choices=OUTCOMES)
    f.add_argument("--rework-rounds", type=int, default=0)
    f.add_argument("--tests", default="not-run", choices=TESTS)
    f.add_argument("--note", default="")
    f.set_defaults(func=cmd_finish)

    o = sub.add_parser("open", help="list dispatches with no finish line")
    o.set_defaults(func=cmd_open)

    m = sub.add_parser("summary", help="acceptance and timing per agent, model, kind and grade")
    m.add_argument("--since", help="YYYY-MM-DD")
    m.add_argument("--project")
    m.add_argument("--json", action="store_true", help="print the rows as JSON")
    m.set_defaults(func=cmd_summary)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
