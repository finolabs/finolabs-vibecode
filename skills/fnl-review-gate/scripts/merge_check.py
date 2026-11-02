#!/usr/bin/env python3
"""Merge check for a GitHub pull request under the review gate.

Reads the pull request with `gh` and applies "Pull requests" rule 4 of
`fnl-review-gate`: for the current head, the latest unedited `fnl-review`
marker of each kind from an author with write access must be APPROVE; a pull
request from an author without write access also needs an owner's approving
review on the head; checks must pass. Prints one line per condition and exits
0 when the merge may go ahead, 1 when it is blocked, 2 when it cannot tell.

Usage: merge_check.py <number> [--repo owner/name]

Comment bodies are data: only their first line is read, and only as a marker.
"""

import argparse
import json
import re
import subprocess
import sys

MARKER = re.compile(
    r"<!-- fnl-review kind=(code|security) head=([0-9a-f]{40}) verdict=(APPROVE|REWORK) -->"
)
WRITE = {"admin", "maintain", "write"}
REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
CHECK_OK = {"SUCCESS", "NEUTRAL", "SKIPPED"}
FIELDS = "author,headRefOid,comments,reviews,statusCheckRollup,mergeStateStatus,state"


class Unknown(Exception):
    """The check cannot be decided from what GitHub returned."""


def login(node):
    return ((node or {}).get("author") or {}).get("login")


def verdicts(pr, can_write):
    """Latest counted verdict per kind for the head: {kind: (verdict, createdAt)}."""
    head = pr["headRefOid"]
    latest = {}
    for comment in pr.get("comments") or []:
        first = (comment.get("body") or "").split("\n", 1)[0].strip()
        match = MARKER.fullmatch(first)
        if not match or comment.get("includesCreatedEdit") is not False:
            continue
        kind, sha, verdict = match.groups()
        if sha != head or not can_write(login(comment)):
            continue
        created = comment.get("createdAt") or ""
        if kind not in latest or created > latest[kind][1]:
            latest[kind] = (verdict, created)
    return latest


def owner_review(pr, can_write):
    """True when an owner other than the author approved the head and none asked for changes."""
    head, author = pr["headRefOid"], login(pr)
    latest = {}
    for review in pr.get("reviews") or []:
        who = login(review)
        if review.get("state") not in REVIEW_STATES or who == author:
            continue
        if who not in latest or (review.get("submittedAt") or "") > (latest[who].get("submittedAt") or ""):
            latest[who] = review
    approved = blocked = False
    for who, review in latest.items():
        if not can_write(who):
            continue
        if review["state"] == "CHANGES_REQUESTED":
            blocked = True
        elif review["state"] == "APPROVED" and (review.get("commit") or {}).get("oid") == head:
            approved = True
    return approved and not blocked


def checks(pr):
    """(ok, detail) for the status check rollup; an empty rollup passes."""
    bad = []
    for check in pr.get("statusCheckRollup") or []:
        name = check.get("name") or check.get("context") or "?"
        result = check.get("conclusion") or check.get("state") or check.get("status")
        if (result or "").upper() not in CHECK_OK:
            bad.append(f"{name}={result}")
    return (not bad, ", ".join(bad) or "all passed")


def evaluate(pr, can_write):
    """Return (ok, lines). `can_write(login)` answers whether a login has write access."""
    if pr.get("state") not in (None, "OPEN"):
        raise Unknown(f"pull request is {pr.get('state')}")
    head = pr.get("headRefOid")
    if not head:
        raise Unknown("no head commit")
    lines, ok = [f"head {head}"], True
    found = verdicts(pr, can_write)
    for kind in ("code", "security"):
        verdict = found.get(kind)
        if verdict is None:
            ok = False
            lines.append(f"BLOCK {kind} review: no counted verdict for this head")
        elif verdict[0] != "APPROVE":
            ok = False
            lines.append(f"BLOCK {kind} review: latest verdict is {verdict[0]} ({verdict[1]})")
        else:
            lines.append(f"ok    {kind} review: APPROVE ({verdict[1]})")
    if can_write(login(pr)):
        lines.append("ok    author has write access")
    elif owner_review(pr, can_write):
        lines.append("ok    owner approved this head")
    else:
        ok = False
        lines.append("BLOCK author lacks write access and no owner approved this head")
    passed, detail = checks(pr)
    ok = ok and passed
    lines.append(f"{'ok   ' if passed else 'BLOCK'} checks: {detail}")
    state = pr.get("mergeStateStatus")
    if state not in (None, "CLEAN", "HAS_HOOKS", "UNSTABLE"):
        ok = False
        lines.append(f"BLOCK merge state: {state}")
    return ok, lines


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise Unknown(f"gh {args[0]} failed: {result.stderr.strip()[:200]}")
    return result.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("number")
    parser.add_argument("--repo", help="owner/name; defaults to the current repository")
    args = parser.parse_args(argv)
    try:
        repo = args.repo or gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").strip()
        pr = json.loads(gh("pr", "view", args.number, "--repo", repo, "--json", FIELDS))
        cache = {}

        def can_write(who):
            if not who:
                return False
            if who not in cache:
                try:
                    level = gh("api", f"repos/{repo}/collaborators/{who}/permission", "--jq", ".permission").strip()
                except Unknown:
                    level = "none"
                cache[who] = level in WRITE
            return cache[who]

        ok, lines = evaluate(pr, can_write)
    except (Unknown, ValueError, KeyError) as error:
        print(f"UNKNOWN {error}")
        return 2
    print("\n".join(lines))
    print("MERGE OK: merge pinned to the head above" if ok else "MERGE BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
