#!/usr/bin/env python3
"""Print a router, keep, judge or task receipt.

When the user has turned usage metrics on, the plugin's hook reads this command
after it runs and records only the receipt's metadata with the session.

Only for keep, when the auto gate is enabled, this command also writes its local repository
decision file. A failed decision write never changes the receipt or exit code.
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # receipts never write import caches

DEPTHS = ("MIN", "NORMAL", "DEEP")
TRIGGERS = ("none", "contract", "security", "privacy", "permission", "migration", "dependency",
            "uncertainty", "consumers", "irreversible", "calculation", "prediction", "input")
REASONS = ("needs-context", "brief-costs-more", "hard-grade", "no-delegate", "never-delegated", "user-choice")
ROUTE_BY = ("table", "judge", "user")


JUDGE_SITES = ("route", "depth", "activity", "instruction")
JUDGE_GRADERS = ("judge", "agent")
JUDGE_RESULTS = ("validated", "unverified")
JUDGE_FOLLOWED = ("yes", "no", "na")


def task_count(value):
    count = int(value)
    if not 1 <= count <= 999:
        raise argparse.ArgumentTypeError("a keep receipt holds 1 to 999 tasks")
    return count


def task_id(value):
    if re.fullmatch(r"T[0-9]{1,4}", value) is None:
        raise argparse.ArgumentTypeError("task id must match T[0-9]{1,4}")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    router = sub.add_parser("router", help="print the depth receipt")
    router.add_argument("--depth", required=True, choices=DEPTHS)
    router.add_argument("--trigger", required=True, choices=TRIGGERS)
    task = sub.add_parser("task", help="print the task receipt", allow_abbrev=False)
    task.add_argument("--id", required=True, type=task_id)
    keep = sub.add_parser("keep", help="print the keep receipt", allow_abbrev=False)  # the hook reads full flag names
    keep.add_argument("--tasks", required=True, type=task_count, help="how many tasks you kept for this reason")
    keep.add_argument("--reason", required=True, choices=REASONS)
    keep.add_argument("--route-by", default="table", choices=ROUTE_BY)
    judge = sub.add_parser("judge", help="print the judge receipt", allow_abbrev=False)
    judge.add_argument("--site", required=True, choices=JUDGE_SITES)
    judge.add_argument("--grader", required=True, choices=JUDGE_GRADERS)
    judge.add_argument("--result", required=True, choices=JUDGE_RESULTS)
    judge.add_argument("--followed", required=True, choices=JUDGE_FOLLOWED)
    args = parser.parse_args()
    if args.command == "router":
        print("router receipt: depth=%s trigger=%s" % (args.depth, args.trigger))
        return
    if args.command == "task":
        print("task receipt: id=%s" % args.id)
        return
    if args.command == "judge":
        if ((args.grader == "agent" and args.result != "validated")
                or (args.followed != "na" and (args.grader != "judge" or args.result != "validated"))):
            parser.error("invalid judge field pair")
        print("judge receipt: site=%s grader=%s result=%s followed=%s" %
              (args.site, args.grader, args.result, args.followed))
        return
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
        from mode import effective
        from auto_gate import enabled, repository_key, write_decision
        if enabled(effective):
            key = repository_key(os.getcwd())
            if key:
                write_decision(key, "keep")
    except Exception:
        pass  # gate state must never change this command's output or exit code
    print("keep receipt: tasks=%d reason=%s route_by=%s" % (args.tasks, args.reason, args.route_by))


if __name__ == "__main__":
    main()
