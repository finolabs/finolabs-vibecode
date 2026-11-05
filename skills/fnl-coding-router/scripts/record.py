#!/usr/bin/env python3
"""Print the coding router's depth or judge receipt.

The command records nothing itself. When the user has turned usage metrics on, the plugin's
hook reads this command after it runs and records the depth and trigger with the session.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
sys.dont_write_bytecode = True  # receipts never write, including import caches
import fnl_metrics as fm  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    router = sub.add_parser("router", help="print the depth receipt")
    router.add_argument("--depth", required=True, choices=fm.DEPTHS)
    router.add_argument("--trigger", required=True, choices=fm.TRIGGERS)
    judge = sub.add_parser("judge", help="print the judge receipt", allow_abbrev=False)
    judge.add_argument("--site", required=True, choices=fm.JUDGE_SITES)
    judge.add_argument("--grader", required=True, choices=fm.JUDGE_GRADERS)
    judge.add_argument("--result", required=True, choices=fm.JUDGE_RESULTS)
    judge.add_argument("--followed", required=True, choices=fm.JUDGE_FOLLOWED)
    args = parser.parse_args()
    if args.command == "judge":
        if ((args.grader == "agent" and args.result != "validated")
                or (args.followed != "na" and (args.grader != "judge" or args.result != "validated"))):
            parser.error("invalid judge field pair")
        print("judge receipt: site=%s grader=%s result=%s followed=%s" %
              (args.site, args.grader, args.result, args.followed))
        return
    print("router receipt: depth=%s trigger=%s" % (args.depth, args.trigger))


if __name__ == "__main__":
    main()
