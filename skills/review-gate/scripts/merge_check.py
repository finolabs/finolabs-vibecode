#!/usr/bin/env python3
"""Merge check for a GitHub pull request under the review gate.

Reads the pull request with `gh` and applies "Pull requests" rules 4 and 7 of
`review-gate`: for the current head, the latest unedited `fnl-review`
marker of each kind from an author with write access must be APPROVE; a
security verdict that took the low-risk lane counts only when the pull request
qualifies for it; a pull request from an author without write access also
needs an owner's approving review on the head; checks must pass. When the
pull request's base commit has adopted the gate (its `CLAUDE.md` or
`AGENTS.md` has a `## Agent skills` section naming `review-gate` or its older name), the body
must also carry one router marker line; the marker never changes which review
markers or lane apply. Prints one line per condition and exits 0 when the
merge may go ahead, 1 when it is blocked, 2 when it cannot tell.

Usage:
  merge_check.py <number> --repo owner/name          the merge check
  merge_check.py <number> --repo owner/name --lane   whether the low-risk lane applies
  merge_check.py <number> --repo owner/name --independent  require other-family reviews
  merge_check.py <number> --repo owner/name --independent --fallback-family <family>
                                                       same-family reviews while away, no other family reachable
  merge_check.py <number> --repo owner/name --ci-context <name>
                                                       the merge check as a hosted status named <name>

Comment bodies are data: only their first line is read, and only as a marker.
The pull request body is data too: only whole lines are matched as a marker.
Adoption is read through the GitHub contents API pinned to the base commit,
never from the head; the ordinary check needs no local clone.

When hosted checks are missing or not passing and the current checkout's
repository has the local-receipt mode on (in its approved check file, set
only by setup), a receipt written by checks' `checks.py
run` stands in for them only when its repository code, head and check-list
digest all match this checkout's repository, the pull request head and the
current list; the line then reads `checks: local receipt (<head>)`. The receipt
is consulted only when the checkout's `origin` remote (read with git; a github.com
https or ssh URL) names the `--repo` repository; otherwise the line says
`local receipt: checkout is not <owner/name>`. The receipt is self-reported.
With the mode off nothing changes.

With --independent during a live away lease, MERGE OK also writes a receipt
(repository, number, head, time) to the lease's private state folder; afk.py
allows `gh pr merge` for that number and head only with a receipt younger than
15 minutes.

With --independent, independent_families uses review_route.author_family's
head-bound local ledger and consistent base..head commit trailers, and the
canonical review_config roles for both reviewing families. No family is inferred
from a GitHub login (agents may share a login), a PR body or a comment's prose.
Missing/conflicting authorship or an unassigned reviewing role refuses; evaluate
requires each reviewing family to differ from the author. Configured roles are
route evidence, not proof that the assigned agent actually posted: following the
route and associating each posted marker with that run remain agent judgment,
advisory. This flag does not establish trusted authors, local test results or
Tier 3 path eligibility; those are the afk caller's separate gates.

With --fallback-family <family> as well, current-head markers from the author's
own family count only when all of these hold (docs/specs/afk-per-project.md D):
a live away lease; <family> is the author's family; every other present family
has positive evidence of being out (a reading under 8 hours old for every
configured install, with every pool below the routing floor, or a live rate-limit
marker; no reading or a partial one is no evidence);
the router trigger is not security, permission or privacy; and each counted
marker's second line starts with the exact fallback reviewer line. When an
enforcer script or instruction file changed, each kind also needs approvals at
the head from two different models, each named as ` model=<name>` right after
the fallback reviewer line; every counted marker of that kind must name its
model, and the latest marker of each model must be APPROVE. The flag runs these checks on both reviews
whatever routing would pick now. Without the flag, a counted marker carrying a
fallback reviewer line blocks. Anything unknown refuses.

Under a lease whose effective mode for --repo is `open` (docs/specs/afk-autonomy.md D), the fallback needs only the
live lease, <family> as the author's family, and for each kind either a counted marker whose second line starts with
the exact fallback reviewer line or, inside this branch only, a marker without any fallback line whose kind's
configured review role names a family other than <family>; no quota evidence, router trigger or two-model condition
applies. The mode is the `## afk` `Mode` line of the canonical host config (a missing line is `open`), replaced by the
approved `mode` of the checkout in the working folder whose origin is --repo, read through this skill's copy of
`project_store.py`; any doubt counts as `strict`, which keeps the conditions above. Outside a lease nothing changes.

With --ci-context <name> (the repository's merge-check workflow, which posts
the result as the commit status <name>), the status named <name> is left out of
the checks, so the check never waits on itself; merge state BLOCKED is accepted,
because a required status that has not passed yet makes GitHub report it, and
GitHub keeps enforcing its own rules; no local receipt is consulted; and while
another hosted check is still running it prints MERGE PENDING and exits 3.
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone

MARKER = re.compile(
    r"<!-- fnl-review kind=(code|security) head=([0-9a-f]{40}) verdict=(APPROVE|REWORK)( lane=yes)? -->"
)
WRITE = {"admin", "maintain", "write"}
REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
CHECK_OK = {"SUCCESS", "NEUTRAL", "SKIPPED"}
MERGEABLE = {"CLEAN", "HAS_HOOKS", "UNSTABLE"}
PAGE = 100  # `gh pr view` returns at most this many comments or reviews
FIELDS = "author,headRefOid,comments,reviews,statusCheckRollup,mergeStateStatus,state,body"

# The router marker: the values `delegate`'s `record.py router` accepts.
DEPTHS = ("MIN", "NORMAL", "DEEP")
TRIGGERS = ("none", "contract", "security", "privacy", "permission", "migration", "dependency",
            "uncertainty", "consumers", "irreversible", "calculation", "prediction", "input")
ROUTER = re.compile(r"<!-- fnl-router depth=(%s) trigger=(%s) -->" % ("|".join(DEPTHS), "|".join(TRIGGERS)))
ADOPTION_FILES = ("CLAUDE.md", "AGENTS.md")
ADOPTION_TOKEN = re.compile(r"(?<![\w-])(?:fnl-)?review-gate(?![\w-])")  # the older fnl- name still adopts
ADOPTION_CAP = 256 * 1024  # maximum size in bytes of one adoption file
SHA = re.compile(r"[0-9a-f]{40}")

# Same-family fallback (docs/specs/afk-per-project.md D). ENFORCERS is the list of `afk.py` in `delegate`; a test
# keeps the two equal, since each skill folder stands alone.
FALLBACK_TRIGGERS = ("security", "permission", "privacy")
ENFORCERS = {'afk.py', 'data_root.py', 'parallel_slots.py', 'secret_patterns.py', 'merge_check.py',
             'review_config.py', 'review_route.py', 'post_review.py', 'heavy_gate.py', 'run_env.py', 'ledger.py',
             'record.py', 'verify_claim.py', 'git_metadata.py', 'quota_probe.py', 'heavy_run.py', 'delegate_env.py',
             'auto_gate.py', 'mode.py', 'judge.py', 'log_scan.py', 'route_task.py', 'brief_check.py', 'assignments.py',
             'away_lease.py', 'away_gate_hook.py', 'project_store.py', 'project_progress.py', 'afk_overlay.py'}
INSTRUCTION_FILES = {'claude.md', 'agents.md', 'skill.md'}
FLOOR = 10  # percent remaining below which a pool is out, as review_route.blocked_families reads it
FRESH = 8 * 3600


def fallback_line(family):
    return f"Reviewer: {family} (same family as the author; no other family reachable)"


# The model a fallback marker names: ` model=<name>` right after the exact fallback line (owner decision 15/11/2026).
FALLBACK_MODEL = re.compile(r" model=([A-Za-z0-9][A-Za-z0-9._:-]{0,79})(?: |$)")


def fallback_model(second, family):
    """The model named on a fallback reviewer line, in lower case, or None when the line or the model is missing."""
    expected = fallback_line(family)
    if not isinstance(second, str) or not second.startswith(expected):
        return None
    match = FALLBACK_MODEL.match(second, len(expected))
    return match[1].casefold() if match else None


def head_markers(pr, can_write):
    """Every counted marker for the head, by kind: [(verdict, createdAt, second line)], read like `verdicts`."""
    found = {"code": [], "security": []}
    for comment in pr["comments"]:
        first = (comment.get("body") or "").split("\n", 1)[0].strip()
        match = MARKER.fullmatch(first)
        if not match or comment.get("includesCreatedEdit") is not False:
            continue
        kind, sha, verdict, _ = match.groups()
        if sha != pr["headRefOid"] or not can_write(login(comment)):
            continue
        second = ((comment.get("body") or "").split("\n") + ["", ""])[1].rstrip("\r")
        found[kind].append((verdict, comment.get("createdAt") or "", second))
    return found


def two_models(markers, family):
    """(granted, detail): each kind has head approvals from two different models, every counted marker of the kind
    names its model on the fallback line, and the latest marker of each model is APPROVE (on a tie, REWORK wins)."""
    for kind in ("code", "security"):
        latest = {}
        for verdict, created, second in markers.get(kind, []):
            model = fallback_model(second, family)
            if model is None:
                return False, f"a {kind} fallback marker names no model"
            current = latest.get(model)
            if current is None or created > current[1] or (created == current[1] and verdict == "REWORK"):
                latest[model] = (verdict, created)
        if any(verdict != "APPROVE" for verdict, _ in latest.values()):
            return False, f"a {kind} model's latest verdict is not APPROVE"
        if len(latest) < 2:
            return False, f"an enforcer script or instruction file changed; {kind} needs approvals from two models"
    return True, "two models approved each kind"

TIMEOUT = 60  # seconds for each gh call

# The low-risk lane: files a pull request may change and still take one review
# pass. The changelog and the root documents written for people may change
# freely; a plugin manifest only in its top-level "version"; a release record
# and the spec index only as RELEASE_RECORD below says. Agent context
# files (CLAUDE.md, AGENTS.md), skills, agents and rules never qualify.
LANE_FREE = {"CHANGELOG.md", "README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
             "SECURITY.md", "PRIVACY.md", "TERMS.md"}
LANE_VERSION_ONLY = {".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".antigravity-plugin/plugin.json"}
# A post-release record (owner decision, 15/11/2026): a release record may change
# only its one `Status:` line, from a prepared form to the released form, and the
# spec index only that release's row, in the same pull request.
RELEASE_RECORD = re.compile(r"docs/specs/release-(\d+\.\d+\.\d+)\.md")
SPEC_INDEX = "docs/specs/index.md"
RELEASED = r"released; tagged v{version} on (\d{{4}}-\d{{2}}-\d{{2}})(?:; .+|\.)?"


class Unknown(Exception):
    """The check cannot be decided from what GitHub returned."""


def login(node):
    return ((node or {}).get("author") or {}).get("login")


def verdicts(pr, can_write):
    """Latest counted verdict per kind for the head: {kind: (verdict, createdAt, lane, second line)}."""
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
            second = ((comment.get("body") or "").split("\n") + ["", ""])[1].rstrip("\r")
            latest[kind] = (verdict, created, bool(lane), second)
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


PENDING = {"QUEUED", "IN_PROGRESS", "PENDING", "WAITING", "REQUESTED", "EXPECTED"}


def checks_pending(pr):
    """True when any hosted check has not finished: a run that is queued or in progress, or a status still pending."""
    for check in pr.get("statusCheckRollup") or []:
        if check.get("conclusion"):
            continue
        if (check.get("status") or check.get("state") or "").upper() in PENDING:
            return True
    return False


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


def one_changed_line(base_text, head_text):
    """(index, base line, head line) when the texts differ in exactly one line, else None."""
    if base_text is None or head_text is None:
        return None
    base, head = base_text.split("\n"), head_text.split("\n")
    if len(base) != len(head):
        return None
    changed = [i for i, (old, new) in enumerate(zip(base, head)) if old != new]
    return (changed[0], base[changed[0]], head[changed[0]]) if len(changed) == 1 else None


def released_status(text, version):
    """True when `text` is the released form for `version` with a real date."""
    match = re.fullmatch(RELEASED.format(version=re.escape(version)), text)
    if not match:
        return False
    try:
        datetime.strptime(match.group(1), "%Y-%m-%d")
    except ValueError:
        return False
    return True


def release_record_only(version, base_text, head_text):
    """True when a release record changes only its `Status:` line, from a prepared form to the released form."""
    change = one_changed_line(base_text, head_text)
    if change is None:
        return False
    _, old, new = change
    if not old.startswith("Status: ") or old.startswith("Status: released") or not new.startswith("Status: "):
        return False
    return released_status(new[len("Status: "):], version)


INDEX_ROW = re.compile(r"\| (\[Release (\d+\.\d+\.\d+)[^\]]*\]\(release-\2\.md\)) \| (.+) \|")


def index_row_only(base_text, head_text, versions):
    """The release version when the spec index changes only that release's row,
    from a prepared status to the released form, and the version is in `versions`; else None."""
    change = one_changed_line(base_text, head_text)
    if change is None:
        return None
    _, old, new = change
    old_row, new_row = INDEX_ROW.fullmatch(old), INDEX_ROW.fullmatch(new)
    if not old_row or not new_row or old_row.group(1) != new_row.group(1):
        return None
    version = new_row.group(2)
    if version not in versions or old_row.group(3).startswith("released"):
        return None
    return version if released_status(new_row.group(3), version) else None


def lane_files(files, read):
    """(eligible, reasons) for the low-risk lane. `read(path, side)` returns the
    file's text at "base" or "head"."""
    reasons = []
    if not files:
        reasons.append("no files listed")
    records = {}
    for entry in files:
        match = RELEASE_RECORD.fullmatch(entry.get("filename") or "")
        if match and entry.get("status") == "modified":
            records[match.group(1)] = entry["filename"]
    index_version = None
    if any(entry.get("filename") == SPEC_INDEX and entry.get("status") == "modified" for entry in files):
        index_version = index_row_only(read(SPEC_INDEX, "base"), read(SPEC_INDEX, "head"), records)
    for entry in files:
        name, status = entry.get("filename"), entry.get("status")
        if status != "modified":
            reasons.append(f"{name}: {status} (only modified files qualify)")
        elif name in LANE_FREE:
            continue
        elif name in LANE_VERSION_ONLY:
            if not version_only(read(name, "base"), read(name, "head")):
                reasons.append(f"{name}: changes more than the top-level version")
        elif RELEASE_RECORD.fullmatch(name or ""):
            version = RELEASE_RECORD.fullmatch(name).group(1)
            if not release_record_only(version, read(name, "base"), read(name, "head")):
                reasons.append(f"{name}: changes more than its Status line to the released form")
            elif index_version != version:
                reasons.append(f"{name}: its row in {SPEC_INDEX} is not changed with it")
        elif name == SPEC_INDEX:
            if index_version is None:
                reasons.append(f"{name}: changes more than one changed release's row to the released form")
        else:
            reasons.append(f"{name}: outside the lane")
    return not reasons, reasons


def adopts(text):
    """True when a `## Agent skills` section of an agent context file names `review-gate`."""
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


def out_families(lines, current=None, configured=None):
    """Families with positive evidence of being out: a live rate-limit marker, or a fresh reading for every
    configured install (`configured`: {agent: labels}, from the canonical quota config) with every pool below the
    floor and a reset ahead. A missing, stale, partial or unreadable reading is no evidence."""
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import quota_probe
    current = current or datetime.now(timezone.utc)
    if configured is None:
        configured = {agent: set(entry["configs"]) for agent, entry in quota_probe.canonical_config().items()}
    out, installs = set(), {}
    for line in lines:
        marker = re.fullmatch(r"Quota (claude|codex|agy): rate-limit marker ([^;]+); out of quota until ([^ ]+) \(advisory\)", line)
        if marker:
            if quota_probe.timestamp(marker[2]) <= current < quota_probe.timestamp(marker[3]):
                out.add("antigravity" if marker[1] == "agy" else marker[1])
            continue
        match = re.fullmatch(r"Quota (claude|codex|agy)/([^:]+): measured ([^;]+); (.+)", line)
        if not match:
            continue
        age = (current - quota_probe.timestamp(match[3])).total_seconds()
        pools = [re.fullmatch(r"([a-zA-Z0-9_-]+) ([^:;]+): (\d+)% remaining, resets ([^ ;]+)", part)
                 for part in match[4].split("; ")]
        depleted = (0 <= age <= FRESH and all(pools)
                    and all(int(p[3]) < FLOOR and quota_probe.timestamp(p[4]) > current for p in pools))
        installs.setdefault(match[1], {})[match[2]] = installs.get(match[1], {}).get(match[2], True) and depleted
    for agent, labels in installs.items():
        expected = configured.get(agent)
        if expected and set(labels) >= set(expected) and all(labels[label] for label in expected):
            out.add("antigravity" if agent == "agy" else agent)
    return out


def fallback(pr, family, families, files, verdicts_found, markers=None, repo=None):
    """(granted, detail) for the same-family fallback; every unknown refuses and the detail never echoes text.
    `markers` is `head_markers` of the pull request; without it a changed enforcer or instruction file refuses.
    Under a lease whose effective mode for `repo` is `open` (`lease_mode`), only `open_fallback` applies."""
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import away_lease
        import quota_probe
        import review_config
        if away_lease.live_lease(time.time()) is None:
            return False, "no live away lease"
        if not isinstance(families, dict) or families.get("author") != family:
            return False, f"{family} is not the pull request author's family"
        if lease_mode(repo) == "open":
            return open_fallback(family, verdicts_found)
        present = set(review_config.present_families(review_config.host_text()))
        if family not in present:
            return False, f"{family} is not a present family"
        others = present - {family}
        reachable = sorted(others - out_families(quota_probe.status_lines()))
        if reachable:
            return False, f"no evidence that {', '.join(reachable)} is out"
        marked, detail = router_marker(pr.get("body"))
        trigger = detail.rsplit("trigger=", 1)[-1] if marked else None
        if trigger is None or trigger in FALLBACK_TRIGGERS:
            return False, "router trigger is missing or needs the user"
        listed = files()
        if not isinstance(listed, list) or not listed or any(
                not isinstance(entry, dict) or not isinstance(entry.get("filename"), str) or not entry["filename"]
                for entry in listed):
            return False, "changed files could not be read"
        names = [entry["filename"] for entry in listed] + [str(entry.get("previous_filename") or "") for entry in listed]
        sensitive = any(name.rsplit("/", 1)[-1].casefold() in ENFORCERS | INSTRUCTION_FILES for name in names)
        expected = fallback_line(family)
        for kind in ("code", "security"):
            found = verdicts_found.get(kind)
            second = found[3] if found and len(found) > 3 else ""
            if not (second == expected or second.startswith(expected + " ")):
                return False, f"{kind} marker lacks the fallback reviewer line"
        reachable = f"no other family reachable ({', '.join(sorted(others)) or 'none present'})"
        if sensitive:
            # An enforcer script or instruction file changed: two different models of the family must approve each
            # kind at the head (owner decision 15/11/2026, docs/specs/afk-per-project.md D).
            if markers is None:
                return False, "an enforcer script or instruction file changed"
            granted, detail = two_models(markers, family)
            return (True, f"{reachable}; {detail}") if granted else (False, detail)
        return True, reachable
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError, Unknown):
        return False, "fallback evidence cannot be read"


AFK_LINE = re.compile(r"- ([A-Za-z -]+): (.+)")
# The closed key set of `afk.py` `settings()` (a test keeps the two equal, since each skill folder stands alone); a
# section with any other key fails there, so it reads as `strict` here.
AFK_KEYS = {'Hosts', 'Task choice', 'Push and pull requests', 'Trusted authors', 'Lease hours', 'Max runs',
            'Max runtime minutes', 'Max actions per hour', 'Quota floor percent', 'Merge', 'Mode',
            'Third-party instructions', 'Default branch', 'Production', 'Real users and customer data',
            'Unrecoverable deletion', 'Messages outside the repository', 'Tags and releases', 'Publishing',
            'Shared settings', 'Recoverable deletion', 'Repository comments', 'Excerpts leave the machine',
            'Non-production targets', 'Production targets', 'Test commands', 'Top-level files', 'Release targets'}
AFK_CHOICES = {'Mode': ('open', 'strict'), 'Third-party instructions': ('guard', 'open'),
               'Default branch': ('guard', 'open')}


def lease_mode(repo):
    """The away lease's effective mode for `repo` (owner/name), read as `afk.py` reads it
    (docs/specs/afk-autonomy.md A and D): the `## afk` `Mode` line of the canonical host config (a missing line is
    `open`), replaced by the approved `mode` of the checkout in the working folder when its origin is `repo`.
    `strict` on any doubt: no or an unreadable section, a malformed or repeated line, a key `afk.py` does not read,
    an invalid mode or guard value, no validated
    checkout, another origin, an unreadable, invalid or unbound approval, or any error."""
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import project_progress
        import project_store as store
        import review_config
        if not isinstance(repo, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            return "strict"
        text = review_config.host_text()
        start, body, end = project_progress.host_section(text, "afk")
        if start == body == end:
            return "strict"
        user, seen = "open", set()
        for line in text[body:end].splitlines():
            if not line.strip():
                continue
            match = AFK_LINE.fullmatch(line)
            if not match or match[1] in seen or match[1] not in AFK_KEYS:
                return "strict"
            seen.add(match[1])
            if match[1] in AFK_CHOICES and match[2] not in AFK_CHOICES[match[1]]:
                return "strict"
            if match[1] == "Mode":
                user = match[2]
        owner, name = repo.split("/")
        target = store.repository_target("github.com", owner, name)
        found, ident = store.identity(str(Path.cwd()))
        if target is None or found != "found" or store.origin_target(ident) != target:
            return "strict"
        state, values, _, record = store.autopilot_binding(ident)
        if state == "unset" or state == "approved" and "autopilot" not in values:
            return user
        project = values.get("autopilot") if state == "approved" else None
        if (not store.valid_autopilot(project) or not isinstance(record, dict) or record.get("target") != target
                or not store.bound(record, ident)):
            return "strict"
        mode = project.get("mode", user)
        return mode if mode in ("open", "strict") else "strict"
    except Exception:  # any doubt is strict, never a relaxation
        return "strict"


REVIEWER_NAME = re.compile(r"Reviewer:\s*([A-Za-z]+)(?![A-Za-z])")


def open_fallback(family, verdicts_found):
    """(granted, detail) under an `open` lease (docs/specs/afk-autonomy.md D): each kind's counted head marker either
    starts its second line with the exact fallback reviewer line of `family`, or carries no fallback reviewer line
    and the configured review role for its kind (`review_config.read_roles`) names a family other than `family`, so
    it counts as that family's. No quota evidence, router trigger or two-model condition applies."""
    import review_config
    roles = review_config.read_roles(review_config.host_text())
    expected, parts = fallback_line(family), []
    for kind in ("code", "security"):
        found = verdicts_found.get(kind)
        second = found[3] if found and len(found) > 3 else ""
        if not isinstance(second, str):
            return False, f"{kind} marker cannot be read"
        if second == expected or second.startswith(expected + " "):
            parts.append(f"{kind} same family")
            continue
        if any(second.startswith(fallback_line(other)) for other in review_config.FAMILIES):
            return False, f"{kind} marker has a malformed or another family's fallback line"
        role = roles.get(f"{kind} review")
        # Fold case, spacing and compatibility forms first, so `Reviewer:  Claude` cannot slip past as another name.
        named = REVIEWER_NAME.match(unicodedata.normalize("NFKC", second).strip())
        name = named.group(1).casefold() if named else None
        if name in review_config.FAMILIES and name != role:
            return False, f"{kind} marker names the {name} reviewer, not the configured role"
        if role in review_config.FAMILIES and role != family:
            parts.append(f"{kind} by the configured {role} role")
            continue
        return False, f"{kind} marker lacks the fallback reviewer line"
    return True, "open lease: " + "; ".join(parts)


GITHUB_REMOTE = re.compile(
    r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100}?)(?:\.git)?/?", re.IGNORECASE)


def origin_repository(url):
    """(owner, name) in lower case for a github.com https or ssh remote URL; None for any other form."""
    match = GITHUB_REMOTE.fullmatch(url) if isinstance(url, str) else None
    if not match or not match.group(2).strip(".") or match.group(2).lower() == ".git":
        return None
    return match.group(1).lower(), match.group(2).lower()


def checkout_origin(root):
    """(owner, name) of the checkout's effective `origin`, as git resolves it for a fetch and for a push
    (`insteadOf`, includes and worktree config applied). Each must be exactly one URL and both must name the
    same github.com repository; None on any failure, ambiguity or disagreement."""
    import os
    env = {name: os.environ[name] for name in ("PATH", "HOME") if name in os.environ}
    found = set()
    for mode in ([], ["--push"]):
        try:
            done = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(root), "remote", "get-url", *mode,
                                   "--all", "origin"], capture_output=True, text=True, encoding="utf-8",
                                  timeout=TIMEOUT, check=False, env=env, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError, UnicodeError):
            return None
        urls = done.stdout.splitlines()
        if done.returncode != 0 or len(urls) != 1:
            return None
        parsed = origin_repository(urls[0].strip())
        if parsed is None:
            return None
        found.add(parsed)
    return found.pop() if len(found) == 1 else None


def local_receipt(head, repo):
    """None when the current checkout's repository has the local-receipt mode off (or it cannot be read);
    else (matched, reason). The receipt is consulted only when the checkout's `origin` is `repo` (owner/name,
    case-insensitive); otherwise (False, 'checkout is not <repo>'). Any error is a non-match, never a pass."""
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import checks_list
        import project_progress
        root = project_progress.find_root(Path.cwd())
        if root is None:
            return None
        code = project_progress.repository_code(root)
        if not checks_list.receipt_mode(code, root=root):
            return None
        target = tuple(repo.lower().split("/")) if isinstance(repo, str) and re.fullmatch(r"[\w.-]+/[\w.-]+", repo) else None
        origin = checkout_origin(root)
        if target is None or origin is None or origin != target:
            return False, f"checkout is not {repo}"
        return checks_list.receipt_status(code, head, root=root)
    except (ImportError, OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return None


def evaluate(pr, can_write, lane_ok=None, *, adopted, independent=False, families=None, local_receipt=None,
             repo=None, fallback_family=None, changed_files=None, blocked_ok=False):
    """Return (ok, lines). `can_write(login)` answers write access; `lane_ok()` the lane;
    `adopted` whether the base commit adopted the gate, which makes the router marker required.
    The marker is checked beside the review markers and never relaxes them.
    `local_receipt(head, repo)` is consulted only when the hosted checks are missing or not passing;
    `repo` is the owner/name the pull request was fetched from."""
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
            granted = False
            if fallback_family is not None:
                # A fallback request treats both reviews as same-family, whatever routing would pick now.
                same = ["code", "security"]
                granted, detail = fallback(pr, fallback_family, families, changed_files or (lambda: []), found,
                                           head_markers(pr, can_write), repo=repo)
                lines.append(f"{'ok   ' if granted else 'BLOCK'} same-family review: {detail}")
                ok = ok and granted
            else:
                same = [kind for kind in ("code", "security") if families[kind] == families["author"]]
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                import review_config
                for kind in ("code", "security"):
                    second = (found.get(kind) or ("", "", None, ""))[3]
                    if any(second == fallback_line(f) or second.startswith(fallback_line(f) + " ")
                           for f in review_config.FAMILIES):
                        ok = False
                        lines.append(f"BLOCK independent {kind} review: a same-family fallback marker needs --fallback-family")
            for kind in ("code", "security"):
                if kind in same and granted:
                    lines.append(f"ok    independent {kind} review: same family, allowed by the fallback")
                elif kind in same:
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
    if not passed and local_receipt is not None and checks_pending(pr):
        detail += "; local receipt: not used while hosted checks are still running"
    elif not passed and local_receipt is not None:
        found = local_receipt(head, repo)  # None: the mode is off, so nothing changes
        if found is not None:
            matched, reason = found
            if matched is True:
                passed, detail = True, f"local receipt ({head[:12]})"
            else:
                detail += f"; local receipt: {reason}"
    ok = ok and passed
    lines.append(f"{'ok   ' if passed else 'BLOCK'} checks: {detail}")
    state = pr.get("mergeStateStatus")
    if blocked_ok and state == "BLOCKED":
        lines.append("ok    merge state: BLOCKED (accepted for the hosted status; GitHub enforces its own rules)")
    elif state not in MERGEABLE:
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
    parser.add_argument("--fallback-family", choices=("claude", "codex", "antigravity"),
                        help="with --independent, during an away lease: accept the author's own family when no other is reachable")
    parser.add_argument("--ci-context", metavar="NAME",
                        help="run as the hosted status NAME: ignore that status, accept merge state BLOCKED, exit 3 while checks run")
    args = parser.parse_args(argv)
    if args.lane and args.independent:
        print("UNKNOWN --lane cannot verify independent merge reviews")
        return 2
    if args.fallback_family and not args.independent:
        print("UNKNOWN --fallback-family needs --independent")
        return 2
    if args.ci_context is not None and (args.lane or args.independent
                                        or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", args.ci_context)):
        print("UNKNOWN --ci-context takes a lowercase status name and no --lane or --independent")
        return 2
    if not args.number.isdigit() or not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        print("UNKNOWN expected a pull request number and --repo owner/name")
        return 2
    print(f"repo {args.repo} pull request #{args.number}")
    try:
        pr = json.loads(gh("pr", "view", args.number, "--repo", args.repo, "--json", FIELDS + ",baseRefOid"))
        if args.ci_context is not None and isinstance(pr.get("statusCheckRollup"), list):
            pr["statusCheckRollup"] = [check for check in pr["statusCheckRollup"] if not isinstance(check, dict)
                                       or (check.get("name") or check.get("context")) != args.ci_context]
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
        files_cache = []

        def changed_files():
            if not files_cache:
                files_cache.append(compare(args.repo, pr["baseRefOid"], pr["headRefOid"])[0])
            return files_cache[0]

        ok, lines = evaluate(pr, can_write, lane_ok, adopted=adopted,
                             independent=args.independent, families=families,
                             local_receipt=None if args.ci_context is not None else local_receipt,
                             repo=args.repo, fallback_family=args.fallback_family, changed_files=changed_files,
                             blocked_ok=args.ci_context is not None)
    except (Unknown, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"UNKNOWN {error}")
        return 2
    print("\n".join(lines))
    if not ok and args.ci_context is not None and checks_pending(pr):
        print("MERGE PENDING: hosted checks are still running")
        return 3
    print("MERGE OK: merge pinned to the head above" if ok else "MERGE BLOCKED")
    if ok and args.independent and away_receipt(args.repo, args.number, pr["headRefOid"]):
        print("receipt: recorded for the away lease (afk.py allows this merge for 15 minutes)")
    return 0 if ok else 1


def away_receipt(repo, number, head):
    """Record MERGE OK for afk.py during a live away lease; False without one or on any error (never a pass)."""
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import away_lease
        owner, name = repo.split("/")
        return away_lease.record_merge_ok("/".join(("github.com", owner.casefold(), name.casefold().removesuffix(".git"))),
                                          int(number), head, time.time())
    except (ImportError, OSError, ValueError, TypeError):
        return False


if __name__ == "__main__":
    sys.exit(main())
