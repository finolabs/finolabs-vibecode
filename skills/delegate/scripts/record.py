#!/usr/bin/env python3
"""Print a metadata receipt or persist delegated verification.

When the user has turned usage metrics on, the plugin's hook reads this command
after it runs and records only the receipt's metadata with the session.

The verify command writes private local metadata, never a usage event.
For keep, when the auto gate is enabled, this command also writes its local repository
decision file. A failed decision write never changes the receipt or exit code.
"""

import argparse
import hashlib
import json
import subprocess
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # receipts never write import caches
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I

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



def dispatch_id(value):
    if re.fullmatch(r"d[0-9]{8}-[0-9]{6}-[0-9a-f]{4}", value) is None:
        raise ValueError("invalid dispatch id")
    return value


def child_environment():
    """Keep coordinator credentials and home/config overrides out of children."""
    env = {k: os.environ[k] for k in ("PATH", "LANG", "TMPDIR") if k in os.environ}
    env.setdefault("PATH", os.defpath)
    return env


def git(checkout, *args):
    done = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                           "-c", "core.untrackedCache=false", "-C", str(checkout), *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=15,
                          check=True, env=child_environment())
    return done.stdout.strip()


def checkout_identity(checkout):
    root = git(checkout, "rev-parse", "--show-toplevel")
    return hashlib.sha256(os.fsencode(Path(root).resolve())).hexdigest()


def current_head(checkout):
    return git(checkout, "rev-parse", "--verify", "HEAD^{commit}")


def validate_verification(rec):
    if (not isinstance(rec, dict) or set(rec) !=
            {"kind", "id", "head", "checkout_id", "tests", "mechanical", "criteria", "evidence_id"}
            or rec["kind"] != "verify" or dispatch_id(rec["id"]) != rec["id"]
            or not isinstance(rec["head"], str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", rec["head"])
            or not isinstance(rec["checkout_id"], str) or not re.fullmatch(r"[0-9a-f]{64}", rec["checkout_id"])
            or (rec["evidence_id"] is not None and (not isinstance(rec["evidence_id"], str) or not re.fullmatch(r"[0-9a-f]{64}", rec["evidence_id"])))
            or rec["tests"] not in ("passed", "failed", "not-run")
            or rec["mechanical"] not in ("passed", "failed")
            or not isinstance(rec["criteria"], list) or len(rec["criteria"]) > 150):
        raise ValueError("invalid verification receipt")
    seen = set()
    for item in rec["criteria"]:
        if (not isinstance(item, dict) or set(item) != {"id", "answer", "source", "fallback"}
                or not isinstance(item["id"], str) or not re.fullmatch(r"C[0-9]{1,4}(?:\.[12])?", item["id"])
                or item["id"] in seen or item["answer"] not in ("yes", "no", "insufficient")
                or item["source"] not in ("jev", "host") or type(item["fallback"]) is not bool
                or (item["fallback"] and item["source"] != "host")):
            raise ValueError("invalid criterion metadata")
        seen.add(item["id"])
    return rec


def write_verification(dispatch, head, tests, mechanical, criteria, checkout, evidence_id=None):
    import data_root as dr
    rec = validate_verification(dict(kind="verify", id=dispatch, head=head, tests=tests,
                                    mechanical=mechanical, criteria=criteria, evidence_id=evidence_id,
                                    checkout_id=checkout_identity(checkout)))
    if current_head(checkout) != head:
        raise ValueError("checkout head changed")
    with dr.data_folder("state/verification", create=True, private=True) as folder:
        dr.atomic_write(folder, dispatch + ".json", json.dumps(rec).encode())
    return rec


def read_verification(dispatch):
    import data_root as dr
    dispatch_id(dispatch)
    with dr.data_folder("state/verification", private=True) as folder:
        rec = json.loads(dr.read_file(folder, dispatch + ".json", 65536))
    rec = validate_verification(rec)
    if rec["id"] != dispatch:
        raise ValueError("receipt belongs to another dispatch")
    return rec

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
    verify = sub.add_parser("verify", help="write a local verification receipt", allow_abbrev=False)
    verify.add_argument("--id", required=True)
    verify.add_argument("--head", required=True)
    verify.add_argument("--tests", required=True, choices=("passed", "failed", "not-run"))
    verify.add_argument("--mechanical", required=True, choices=("passed", "failed"))
    verify.add_argument("--criteria-file", required=True, help="JSON metadata, never criterion text")
    verify.add_argument("--checkout", default=".")
    verify.add_argument("--evidence-id", help="optional SHA-256 of the private host request packet")
    args = parser.parse_args()
    if args.command == "verify":
        try:
            with open(args.criteria_file, "rb") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError("criteria too large")
            write_verification(args.id, args.head, args.tests, args.mechanical,
                               json.loads(raw), args.checkout, args.evidence_id)
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            parser.exit(2, "record: verification refused\n")
        print("verify receipt: recorded")
        return
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
