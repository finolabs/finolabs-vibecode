#!/usr/bin/env python3
"""Decide a context action from supplied token counts; no files or commands."""
import argparse
import json
import sys


def check(used, window, threshold, boundary="unknown"):
    if (any(type(value) is not int for value in (used, window, threshold))
            or window <= 0 or not 0 <= used <= 10 * window
            or not 0 < threshold <= window or boundary not in ("yes", "no", "unknown")):
        raise ValueError("invalid input")
    if used * 5 < threshold * 4:
        return {"action": "ok", "reason": "Context use is below 80% of the chosen threshold."}
    if used < threshold:
        return {"action": "prepare", "reason": "Write the handover now before reaching the chosen threshold."}
    if boundary == "no":
        return {"action": "wait", "reason": "Finish the current unit of work before compacting."}
    return {"action": "compact", "reason": "Ask the user to compact, or start a fresh session with a handover if the story just closed."}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid input")


def main():
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="command", required=True)
        command = commands.add_parser("check")
        for name in ("used", "window", "threshold"):
            command.add_argument("--" + name, type=int, required=True)
        command.add_argument("--boundary", choices=("yes", "no", "unknown"), default="unknown")
        args = parser.parse_args()
        result = check(args.used, args.window, args.threshold, args.boundary)
    except (ValueError, OverflowError):
        print("Context steward refused: invalid input.", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
