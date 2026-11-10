#!/usr/bin/env python3
"""Merge check for a GitHub pull request under the review gate.

Reads the pull request with `gh` and applies "Pull requests" rules 4 and 7 of
`fnl-review-gate`: for the current head, the latest unedited `fnl-review`
marker of each kind from an author with write access must be APPROVE; a
security verdict that took the low-risk lane counts only when the pull request
qualifies for it; a pull request from an author without write access also
needs an owner's approving review on the head; checks must pass. When the
pull request's base commit has adopted the gate (its `CLAUDE.md` or
`AGENTS.md` has a `## Agent skills` section naming `fnl-review-gate`), the body
must also carry one router marker line; the marker never changes which review
markers or lane apply. Prints one line per condition and exits 0 when the
merge may go ahead, 1 when it is blocked, 2 when it cannot tell.

Usage:
  merge_check.py <number> --repo owner/name          the merge check
  merge_check.py <number> --repo owner/name --lane   whether the low-risk lane applies
  merge_check.py <number> --repo owner/name --independent  require other-family reviews

Comment bodies are data: only their first line is read, and only as a marker.
The pull request body is data too: only whole lines are matched as a marker.
Adoption is read through the GitHub contents API pinned to the base commit,
never from the head; the ordinary check needs no local clone.

When hosted checks are missing or not passing and the current checkout's
repository has the local-receipt mode on (`## Checks` of the canonical host
config, set only by fnl-setup), a receipt written by fnl-checks' `checks.py
run` stands in for them only when its repository code, head and check-list
digest all match this checkout's repository, the pull request head and the
current list; the line then reads `checks: local receipt (<head>)`. The receipt
is self-reported. With the mode off nothing changes.

With --independent, independent_families uses review_route.author_family's
head-bound local ledger and consistent base..head commit trailers, and the
canonical review_config roles for both reviewing families. No family is inferred
from a GitHub login (agents may share a login), a PR body or a comment's prose.
Missing/conflicting authorship or an unassigned reviewing role refuses; evaluate
requires each reviewing family to differ from the author. Configured roles are
route evidence, not proof that the assigned agent actually posted: following the
route and associating each posted marker with that run remain agent judgment,
advisory. This flag does not establish trusted authors, local test results or
Tier 3 path eligibility; those are the autopilot caller's separate gates.
"""

import argparse
import base64
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
FIELDS = "author,headRefOid,comments,reviews,statusCheckRollup,mergeStateStatus,state,body"

# The router marker: the values `fnl-delegate`'s `record.py router` accepts.
DEPTHS = ("MIN", "NORMAL", "DEEP")
TRIGGERS = ("none", "contract", "security", "privacy", "permission", "migration", "dependency",
            "uncertainty", "consumers", "irreversible", "calculation", "prediction", "input")
ROUTER = re.compile(r"<!-- fnl-router depth=(%s) trigger=(%s) -->" % ("|".join(DEPTHS), "|".join(TRIGGERS)))
ADOPTION_FILES = ("CLAUDE.md", "AGENTS.md")
ADOPTION_TOKEN = re.compile(r"(?<![\w-])fnl-review-gate(?![\w-])")
ADOPTION_CAP = 256 * 1024  # maximum size in bytes of one adoption file
SHA = re.compile(r"[0-9a-f]{40}")

TIMEOUT = 60  # seconds for each gh call

# The low-risk lane: files a pull request may change and still take one review
# pass. The changelog and the root documents written for people may change
# freely; a plugin manifest only in its top-level "version". Agent context
# files (CLAUDE.md, AGENTS.md), skills, agents and rules never qualify.
LANE_FREE = {"CHANGELOG.md", "README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
             "SECURITY.md", "PRIVACY.md", "TERMS.md"}
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


def adopts(text):
    """True when a `## Agent skills` section of an agent context file names `fnl-review-gate`."""
    inside = fenced = False
    for line in text.splitlines():
        if re.match(r" {0,3}(```|~~~)", line):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,2}(\s|$)", line):
            inside = line.rstrip() == "## Agent skills"
            continue
        if inside and ADOPTION_TOKEN.search(line):
            return True
    return False


def router_marker(body):
    """(ok, detail) for the router marker in the pull request body; never echoes body text."""
    if not isinstance(body, str):
        raise Unknown("the pull request body could not be read")
    lines = [line[:-1] if line.endswith("\r") else line for line in body.split("\n")]
    found = [line for line in lines if ROUTER.fullmatch(line)]
    malformed = [line for line in lines if "<!-- fnl-router" in line and not ROUTER.fullmatch(line)]
    if malformed:
        return False, f"{len(malformed)} malformed fnl-router line(s); the marker must be one exact line"
    if not found:
        return False, "missing; the body needs one line <!-- fnl-router depth=... trigger=... -->"
    if len(found) > 1:
        return False, "multiple fnl-router lines; keep exactly one"
    depth, trigger = ROUTER.fullmatch(found.pop()).groups()
    return True, f"depth={depth} trigger={trigger}"


def independent_families(pr):
    """Reuse canonical role/route evidence; unknown fails closed, never guess a family."""
    from pathlib import Path
    # Standard-library modules load first, so a new sibling file can never shadow them inside this gate.
    import struct
    import zlib
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import review_route
        import review_config
        author = review_route.author_family(Path.cwd(), base=pr.get("baseRefOid"), head=pr["headRefOid"])
        # The families routing would pick for this author from the same inputs `review_route` uses (assigned role, else
        # the capability fallback, with cached quota readings); a same-family pick means no other family is present. Who posted a marker stays a caller duty.
        import quota_probe
        rows = review_route.route(author, review_config.host_text(), quota_probe.status_lines())
        result = {"author": author, "code": rows[0][0], "security": rows[1][0]}
        if any(value not in review_config.FAMILIES for value in result.values()):
            raise ValueError("unknown family")
        return result
    except (ImportError, OSError, ValueError, KeyError, TypeError, IndexError, struct.error, zlib.error):
        return None


def local_receipt(head):
    """None when the current checkout's repository has the local-receipt mode off (or it cannot be read);
    else (matched, reason) from `checks_list.receipt_status`. Any error is a non-match, never a pass."""
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import checks_list
        import project_progress
        root = project_progress.find_root(Path.cwd())
        if root is None:
            return None
        return checks_list.receipt_status(project_progress.repository_code(root), head)
    except (ImportError, OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return None


def evaluate(pr, can_write, lane_ok=None, *, adopted, independent=False, families=None, local_receipt=None):
    """Return (ok, lines). `can_write(login)` answers write access; `lane_ok()` the lane;
    `adopted` whether the base commit adopted the gate, which makes the router marker required.
    The marker is checked beside the review markers and never relaxes them.
    `local_receipt(head)` is consulted only when the hosted checks are missing or not passing."""
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
    if independent:
        known = {"claude", "codex", "antigravity"}
        if (not isinstance(families, dict)
                or any(families.get(key) not in known for key in ("author", "code", "security"))):
            ok = False
            lines.append("BLOCK independent reviews: author or reviewing family cannot be determined")
        else:
            for kind in ("code", "security"):
                if families[kind] == families["author"]:
                    ok = False
                    lines.append(f"BLOCK independent {kind} review: same family as the pull request author")
                else:
                    lines.append(f"ok    independent {kind} review: different family")
    if adopted:
        marked, detail = router_marker(pr.get("body"))
        ok = ok and marked
        lines.append(f"{'ok   ' if marked else 'BLOCK'} router marker: {detail}")
    if can_write(login(pr)):
        lines.append("ok    author has write access")
    elif owner_review(pr, can_write):
        lines.append("ok    owner approved this head")
    else:
        ok = False
        lines.append("BLOCK author lacks write access and no owner approved this head")
    passed, detail = checks(pr)
    if not passed and local_receipt is not None:
        found = local_receipt(head)  # None: the mode is off, so nothing changes
        if found is not None:
            matched, reason = found
            if matched is True:
                passed, detail = True, f"local receipt ({head[:12]})"
            else:
                detail += f"; local receipt: {reason}"
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


COMPARE_CAP = 300  # GitHub's compare API lists at most this many files


def compare(repo, base, head):
    """Files changed from the merge base to `head`, bound to those SHAs, and the merge base."""
    data = json.loads(gh("api", f"repos/{repo}/compare/{base}...{head}"))
    files = data.get("files")
    if not isinstance(files, list) or len(files) >= COMPARE_CAP:
        raise Unknown("the compare API did not list every changed file")
    merge_base = (data.get("merge_base_commit") or {}).get("sha")
    if not isinstance(merge_base, str) or not re.fullmatch(r"[0-9a-f]{40}", merge_base):
        raise Unknown("the compare API gave no merge base")
    return files, merge_base


def file_at(repo, path, ref):
    return gh("api", "-H", "Accept: application/vnd.github.raw+json", f"repos/{repo}/contents/{path}?ref={ref}")


def adopted_at(repo, base):
    """Whether the base commit adopted the gate, read through GitHub (never the head
    or a local branch). A clean 404 means absent; every other read failure is Unknown.
    Only exact links to the other adoption file are allowed; it is read on its own turn.
    """
    if not isinstance(base, str) or not SHA.fullmatch(base):
        raise Unknown("the pull request has no base commit")
    adopted = False
    for path in ADOPTION_FILES:
        result = run_gh("api", f"repos/{repo}/contents/{path}?ref={base}")
        if result.returncode != 0:
            if "(HTTP 404)" in result.stderr:
                continue
            raise Unknown(f"{path} at the base commit could not be read")
        data = strict_object(result.stdout)
        if data is not None and data.get("type") == "symlink":
            if data.get("target") == next(other for other in ADOPTION_FILES if other != path):
                continue
        if data is None or data.get("type") != "file":
            raise Unknown(f"{path} at the base commit is not a regular file")
        size = data.get("size")
        if type(size) is not int or not 0 <= size <= ADOPTION_CAP:
            raise Unknown(f"{path} at the base commit could not be read")
        content = data.get("content")
        if data.get("encoding") != "base64" or not isinstance(content, str):
            raise Unknown(f"{path} at the base commit could not be read")
        try:
            blob = base64.b64decode("".join(content.split()), validate=True)
        except ValueError:
            raise Unknown(f"{path} at the base commit could not be read")
        if len(blob) != size:
            raise Unknown(f"{path} at the base commit could not be read")
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            raise Unknown(f"{path} at the base commit is not UTF-8")
        adopted = adopted or adopts(text)
    return adopted


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("number")
    parser.add_argument("--repo", required=True, help="owner/name of the repository the pull request belongs to")
    parser.add_argument("--lane", action="store_true", help="only report whether the low-risk lane applies")
    parser.add_argument("--independent", action="store_true", help="require both reviewing families to differ from the author")
    args = parser.parse_args(argv)
    if args.lane and args.independent:
        print("UNKNOWN --lane cannot verify independent merge reviews")
        return 2
    if not args.number.isdigit() or not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        print("UNKNOWN expected a pull request number and --repo owner/name")
        return 2
    print(f"repo {args.repo} pull request #{args.number}")
    try:
        pr = json.loads(gh("pr", "view", args.number, "--repo", args.repo, "--json", FIELDS + ",baseRefOid"))
        lane_cache = []

        def lane_ok():
            if not lane_cache:
                files, merge_base = compare(args.repo, pr["baseRefOid"], pr["headRefOid"])
                refs = {"base": merge_base, "head": pr["headRefOid"]}
                read = lambda path, side: file_at(args.repo, path, refs[side])
                lane_cache.append(lane_files(files, read))
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

        if not isinstance(pr.get("body"), str):
            raise Unknown("the pull request body could not be read")
        adopted = adopted_at(args.repo, pr.get("baseRefOid"))
        families = independent_families(pr) if args.independent else None
        ok, lines = evaluate(pr, can_write, lane_ok, adopted=adopted,
                             independent=args.independent, families=families, local_receipt=local_receipt)
    except (Unknown, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"UNKNOWN {error}")
        return 2
    print("\n".join(lines))
    print("MERGE OK: merge pinned to the head above" if ok else "MERGE BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
