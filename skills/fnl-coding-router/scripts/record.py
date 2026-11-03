#!/usr/bin/env python3
"""Print the coding router's depth receipt.

The command records nothing itself. When the user has turned usage metrics on, the plugin's
hook reads this command after it runs and records the depth and trigger with the session.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import fnl_metrics as fm  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    router = sub.add_parser("router", help="print the depth receipt")
    router.add_argument("--depth", required=True, choices=fm.DEPTHS)
    router.add_argument("--trigger", required=True, choices=fm.TRIGGERS)
    args = parser.parse_args()
    print("router receipt: depth=%s trigger=%s" % (args.depth, args.trigger))


if __name__ == "__main__":
    main()
