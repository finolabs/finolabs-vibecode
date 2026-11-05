#!/usr/bin/env python3
"""Print a coordinator's keep receipt.

When the auto gate is enabled, this command also writes its local repository decision file.
A failed decision write never changes the receipt or exit code. When the user has turned usage metrics on, the plugin's
hook reads this command after it runs and records the count, the reason and who settled it
with the session.
"""

import argparse
import os
import sys
from pathlib import Path

REASONS = ("needs-context", "brief-costs-more", "hard-grade", "no-delegate", "never-delegated", "user-choice")
ROUTE_BY = ("table", "judge", "user")


def task_count(value):
    count = int(value)
    if not 1 <= count <= 999:
        raise argparse.ArgumentTypeError("a keep receipt holds 1 to 999 tasks")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    keep = sub.add_parser("keep", help="print the keep receipt", allow_abbrev=False)  # the hook reads full flag names
    keep.add_argument("--tasks", required=True, type=task_count, help="how many tasks you kept for this reason")
    keep.add_argument("--reason", required=True, choices=REASONS)
    keep.add_argument("--route-by", default="table", choices=ROUTE_BY)
    args = parser.parse_args()
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
