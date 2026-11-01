#!/usr/bin/env python3
"""Append-only dispatch ledger for the delegation skills.

Each dispatch writes a `start` line and later a `finish` line to a JSONL file
(default ~/.claude/orchestration/ledger.jsonl, override with ORCHESTRATION_LEDGER).
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
AGENTS = ["codex", "antigravity", "claude-session", "claude-subagent"]
REASONS = ["routing", "fallback-quota", "fallback-failure", "user-choice"]
OUTCOMES = [
    "accepted", "rejected", "timeout", "stalled", "error",
    "blocked", "needs-permission", "quota", "cancelled",
]
TESTS = ["passed", "failed", "not-run"]


def ledger_path():
    return Path(os.environ.get("ORCHESTRATION_LEDGER", Path.home() / ".claude/orchestration/ledger.jsonl"))


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
            print(f"ledger: skipping malformed line {n}", file=sys.stderr)
            continue
        target = starts if rec.get("event") == "start" else finishes
        target[rec.get("id")] = rec
    return starts, finishes


def cmd_start(args):
    dispatch_id = datetime.now().strftime("d%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    append({
        "event": "start", "id": dispatch_id, "ts": now(),
        "project": args.project, "task": args.task, "kind": args.kind,
        "grade": args.grade, "agent": args.agent, "model": args.model,
        "reason": args.reason, "budget_min": args.budget,
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
    for dispatch_id, s in starts.items():
        if dispatch_id not in finishes:
            print(f"{dispatch_id}  {s['ts']}  {s['agent']}/{s['model']}  {s['project']}: {s['task']}")


def cmd_summary(args):
    starts, finishes = load()
    groups = defaultdict(list)
    for dispatch_id, s in starts.items():
        if args.since and s["ts"][:10] < args.since:
            continue
        if args.project and s["project"] != args.project:
            continue
        f = finishes.get(dispatch_id)
        if f is None:
            continue
        groups[(s["agent"], s["model"], s["kind"], s["grade"])].append((s, f))
    if not groups:
        print("ledger: no finished dispatches match")
        return
    header = f"{'agent':<16}{'model':<24}{'kind':<10}{'grade':<10}{'n':>4}{'1st-pass':>10}{'accepted':>10}{'timeout':>9}{'fallback':>10}{'median min':>12}"
    print(header)
    for (agent, model, kind, grade), rows in sorted(groups.items()):
        n = len(rows)
        accepted = [f for _, f in rows if f["outcome"] == "accepted"]
        first_pass = [f for f in accepted if f["rework_rounds"] == 0]
        timed_out = [f for _, f in rows if f["outcome"] in ("timeout", "stalled")]
        fallback = [s for s, _ in rows if s["reason"].startswith("fallback")]
        median = statistics.median(minutes(s, f) for s, f in rows)
        print(f"{agent:<16}{model:<24}{kind:<10}{grade:<10}{n:>4}{len(first_pass) / n:>10.0%}{len(accepted) / n:>10.0%}"
              f"{len(timed_out):>9}{len(fallback):>10}{median:>12.0f}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="record a dispatch; prints its id")
    s.add_argument("--project", required=True)
    s.add_argument("--task", required=True, help="short label, no task data or secrets")
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--grade", required=True, choices=GRADES)
    s.add_argument("--agent", required=True, choices=AGENTS)
    s.add_argument("--model", default="default")
    s.add_argument("--reason", default="routing", choices=REASONS)
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
    m.set_defaults(func=cmd_summary)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
