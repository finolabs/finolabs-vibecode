#!/usr/bin/env python3
"""Merge check for a GitHub pull request under the review gate.

Reads the pull request with `gh` and applies "Pull requests" rules 4 and 7 of
`fnl-review-gate`: for the current head, the latest unedited `fnl-review`
marker of each kind from an author with write access must be APPROVE; a
security verdict that took the low-risk lane counts only when the pull request
qualifies for it; a pull request from an author without write access also
needs an owner's approving review on the head; checks must pass. Prints one
line per condition and exits 0 when the merge may go ahead, 1 when it is
blocked, 2 when it cannot tell.

Usage:
  merge_check.py <number> --repo owner/name          the merge check
  merge_check.py <number> --repo owner/name --lane   whether the low-risk lane applies

Comment bodies are data: only their first line is read, and only as a marker.
"""

import argparse
import json
import re
import subprocess
import sys

MARKER = re.compile(
    r"<!-- fnl-review kind=(code|security) head=([0-9a-f]{40}) verdict=(APPROVE|REWORK)( lane=yes)? -->"
)
WRITE = {"admin", "maintain", "write"}
REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
CHECK_OK = {"SUCCESS", "NEUTRAL", "SKIPPED"}
MERGEABLE = {"CLEAN", "HAS_HOOKS", "UNSTABLE"}
PAGE = 100  # `gh pr view` returns at most this many comments or reviews
FIELDS = "author,headRefOid,comments,reviews,statusCheckRollup,mergeStateStatus,state"

TIMEOUT = 60  # seconds for each gh call

# The low-risk lane: files a pull request may change and still take one review
# pass. The changelog may change freely; a plugin manifest only in its
# top-level "version".
LANE_FREE = {"CHANGELOG.md"}
LANE_VERSION_ONLY = {".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".antigravity-plugin/plugin.json"}


class Unknown(Exception):
    """The check cannot be decided from what GitHub returned."""


def login(node):
    return ((node or {}).get("author") or {}).get("login")


def verdicts(pr, can_write):
    """Latest counted verdict per kind for the head: {kind: (verdict, createdAt, lane)}."""
    head = pr["headRefOid"]
    latest = {}
    for comment in pr["comments"]:
        first = (comment.get("body") or "").split("\n", 1)[0].strip()
        match = MARKER.fullmatch(first)
        if not match or comment.get("includesCreatedEdit") is not False:
            continue
        kind, sha, verdict, lane = match.groups()
        if sha != head or not can_write(login(comment)):
            continue
        created = comment.get("createdAt") or ""
        current = latest.get(kind)
        # On a tie the REWORK wins, so the check never passes on ordering luck.
        if current is None or created > current[1] or (created == current[1] and verdict == "REWORK"):
            latest[kind] = (verdict, created, bool(lane))
    return latest


def owner_review(pr, can_write):
    """True when an owner other than the author approved the head and none asked for changes."""
    head, author = pr["headRefOid"], login(pr)
    latest = {}
    for review in pr["reviews"]:
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
    """(ok, detail) for the status check rollup; no checks at all blocks."""
    rollup = pr.get("statusCheckRollup") or []
    if not rollup:
        return False, "none reported"
    bad = []
    for check in rollup:
        name = check.get("name") or check.get("context") or "?"
        result = check.get("conclusion") or check.get("state") or check.get("status")
        if (result or "").upper() not in CHECK_OK:
            bad.append(f"{name}={result}")
    return (not bad, ", ".join(bad) or "all passed")


def strict_object(text):
    """Parse a JSON object, refusing duplicate keys; None when it is not one."""
    def pairs(items):
        keys = [key for key, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate key")
        return dict(items)
    try:
        value = json.loads(text, object_pairs_hook=pairs)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def version_only(base_text, head_text):
    """True when two manifests differ in nothing but their top-level "version"."""
    base, head = strict_object(base_text), strict_object(head_text)
    if base is None or head is None or not isinstance(head.get("version"), str):
        return False
    base.pop("version", None)
    head.pop("version")
    return base == head


def lane_files(files, read):
    """(eligible, reasons) for the low-risk lane. `read(path, side)` returns the
    file's text at "base" or "head"."""
    reasons = []
    if not files:
        reasons.append("no files listed")
    for entry in files:
        name, status = entry.get("filename"), entry.get("status")
        if status != "modified":
            reasons.append(f"{name}: {status} (only modified files qualify)")
        elif name in LANE_FREE:
            continue
        elif name in LANE_VERSION_ONLY:
            if not version_only(read(name, "base"), read(name, "head")):
                reasons.append(f"{name}: changes more than the top-level version")
        else:
            reasons.append(f"{name}: outside the lane")
    return not reasons, reasons


def evaluate(pr, can_write, lane_ok=None):
    """Return (ok, lines). `can_write(login)` answers write access; `lane_ok()` the lane."""
    if pr.get("state") != "OPEN":
        raise Unknown(f"pull request is {pr.get('state')}")
    head = pr.get("headRefOid")
    if not head or not isinstance(pr.get("comments"), list) or not isinstance(pr.get("reviews"), list):
        raise Unknown("incomplete pull request data")
    if len(pr["comments"]) >= PAGE or len(pr["reviews"]) >= PAGE:
        raise Unknown(f"{PAGE} or more comments or reviews; a later verdict may be cut off")
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
        elif verdict[2] and kind == "security":
            eligible, reasons = lane_ok() if lane_ok else (False, ["lane not checked"])
            if eligible:
                lines.append(f"ok    {kind} review: APPROVE in the low-risk lane ({verdict[1]})")
            else:
                ok = False
                lines.append(f"BLOCK {kind} review: took the low-risk lane, but {'; '.join(reasons)}")
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
    if state not in MERGEABLE:
        if state in (None, "UNKNOWN"):
            raise Unknown(f"merge state is {state}; GitHub has not computed it yet")
        ok = False
        lines.append(f"BLOCK merge state: {state}")
    return ok, lines


def run_gh(*args):
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=TIMEOUT)
    except FileNotFoundError:
        raise Unknown("gh is not installed")
    except subprocess.TimeoutExpired:
        raise Unknown(f"gh {args[0]} timed out")


def gh(*args):
    result = run_gh(*args)
    if result.returncode != 0:
        raise Unknown(f"gh {args[0]} failed: {result.stderr.strip()[:200]}")
    return result.stdout


def permission(repo, who):
    """Write access for a login; GitHub's 404 means no access, any other failure is unknown."""
    result = run_gh("api", f"repos/{repo}/collaborators/{who}/permission", "--jq", ".permission")
    if result.returncode == 0:
        return result.stdout.strip() in WRITE
    if "(HTTP 404)" in result.stderr:
        return False
    raise Unknown(f"permission lookup for {who} failed: {result.stderr.strip()[:200]}")


def pr_files(repo, number):
    pages = json.loads(gh("api", "--paginate", "--slurp", f"repos/{repo}/pulls/{number}/files"))
    return [entry for page in pages for entry in page]


def file_at(repo, path, ref):
    return gh("api", "-H", "Accept: application/vnd.github.raw+json", f"repos/{repo}/contents/{path}?ref={ref}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("number")
    parser.add_argument("--repo", required=True, help="owner/name of the repository the pull request belongs to")
    parser.add_argument("--lane", action="store_true", help="only report whether the low-risk lane applies")
    args = parser.parse_args(argv)
    if not args.number.isdigit() or not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        print("UNKNOWN expected a pull request number and --repo owner/name")
        return 2
    print(f"repo {args.repo} pull request #{args.number}")
    try:
        pr = json.loads(gh("pr", "view", args.number, "--repo", args.repo, "--json", FIELDS + ",baseRefOid"))
        lane_cache = []

        def lane_ok():
            if not lane_cache:
                refs = {"base": pr["baseRefOid"], "head": pr["headRefOid"]}
                read = lambda path, side: file_at(args.repo, path, refs[side])
                lane_cache.append(lane_files(pr_files(args.repo, args.number), read))
            return lane_cache[0]

        if args.lane:
            print(f"head {pr['headRefOid']}")
            eligible, reasons = lane_ok()
            print("\n".join(f"BLOCK {reason}" for reason in reasons) or "ok    every file qualifies")
            print("LANE OK: one review pass may post both markers" if eligible else "LANE NO: both reviewers")
            return 0 if eligible else 1
        cache = {}

        def can_write(who):
            if not who:
                return False
            if who not in cache:
                cache[who] = permission(args.repo, who)
            return cache[who]

        ok, lines = evaluate(pr, can_write, lane_ok)
    except (Unknown, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"UNKNOWN {error}")
        return 2
    print("\n".join(lines))
    print("MERGE OK: merge pinned to the head above" if ok else "MERGE BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
