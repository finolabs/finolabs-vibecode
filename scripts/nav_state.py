#!/usr/bin/env python3
"""Collect course-check anchors and evidence, validate payloads, and check navigator reports.

Stdlib only, no model, no network. Reads ledger state through data_root.py.
"""

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import unicodedata

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

MAX_CRITERION_LEN = 300
MAX_SUBJECT_LEN = 120
MAX_ID_LEN = 80
MAX_REF_LEN = 120
MAX_OPTION_LEN = 300
MAX_FILE_BYTES = 512 * 1024
MAX_DOC_BYTES = 64 * 1024
MAX_GIT_BYTES = 256 * 1024
MAX_CRITERIA = 200
MAX_COMMITS = 500
MAX_SPECS = 80
MAX_LEDGER_IDS = 200

NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
NONBLOCK = getattr(os, "O_NONBLOCK", 0)
DIRECTORY = getattr(os, "O_DIRECTORY", 0)

STATUS_WORDS = ("draft", "accepted", "in progress", "implemented", "released", "deferred", "unknown")
LEDGER_STATUS_WORDS = ("present", "absent")
OUTCOME_WORDS = (
    "accepted", "rejected", "timeout", "stalled", "error",
    "blocked", "needs-permission", "quota", "cancelled",
)
ANCHOR_STATUS_WORDS = ("on course", "drifting", "abandoned", "no drift")
JUDGE_ANSWERS = ("yes", "no", "insufficient")
COUNT_KEYS = ("commits", "pull_requests", "specs", "ledger_runs")

COLLECTION_KEYS = {"since", "criteria", "evidence"}
CRITERION_KEYS = {"id", "criterion", "restated_criterion", "question", "evidence", "evidence_refs"}
EVIDENCE_KEYS = {"commits", "pull_requests", "specs", "ledger", "counts", "ids", "status"}
SPEC_ITEM_KEYS = {"id", "status"}
LEDGER_KEYS = {"status", "ids", "counts"}

REPORT_TOP_KEYS = {"anchors", "unmatched_items", "options", "findings", "judge_validated"}
ANCHOR_ENTRY_KEYS = {
    "id", "anchor", "status", "criterion", "restated_criterion", "question",
    "answer", "judge_answer", "judge", "judge_validated", "finding",
    "criteria", "findings", "evidence", "evidence_refs", "options",
}
FINDING_KEYS = {"id", "finding", "drift_kind", "evidence", "evidence_refs"}
OPTION_KEYS = {"option", "action", "cost"}

INSTRUCTION_FILES = (
    "CLAUDE.MD", "CLAUDE.LOCAL.MD", "AGENTS.MD", "AGENTS.OVERRIDE.MD", "GEMINI.MD",
    "COPILOT-INSTRUCTIONS.MD", "CONVENTIONS.MD", ".CURSORRULES", ".WINDSURFRULES", ".CLINERULES",
)
WORK_TRACKING_META = re.compile(
    r"^(?:This repository uses|Specs live in|Tasks are tracked|The ledger project name is)\b",
    re.I,
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T[0-9:.+-]+Z?)?\Z")
SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}\Z")
COMMIT_ID = re.compile(r"^[0-9a-f]{7,40}\Z")
PR_ID = re.compile(r"^(?:#[0-9]{1,8}|PR-[0-9]{1,8})\Z")
DISPATCH_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}\Z")
SAFE_REF = re.compile(r"^[A-Za-z0-9#._:/-]{1,120}\Z")
PR_IN_SUBJECT = re.compile(r"(?:pull request #|PR #|#)(\d{1,8})\b", re.I)
EXPLICIT_CRITERION_ID = re.compile(
    r"^(?:\*\*([A-Za-z]{1,12}-?\d{1,4})\*\*|([A-Za-z]{1,12}-?\d{1,4}))(?:\s*[:.—-]\s*|\s+)(.+)\Z"
)

LEDGER_REQUIRED = {
    "start": {"id", "ts", "project", "task", "kind", "grade", "agent", "model", "reason"},
    "finish": {"id", "ts", "outcome", "rework_rounds"},
}


def has_control_chars(text):
    if not isinstance(text, str):
        return True
    for ch in text:
        code = ord(ch)
        if code < 32 or code == 127 or unicodedata.category(ch).startswith("C"):
            return True
    return False


def sanitize_text(text, max_len=MAX_CRITERION_LEN):
    """Strip ANSI escape sequences and all Unicode control/format chars, normalize spaces, and cap length."""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    cleaned = ANSI_ESCAPE.sub(" ", text)
    chars = []
    for ch in cleaned:
        if ch in ("\t", "\n", "\r"):
            chars.append(" ")
        elif ord(ch) < 32 or ord(ch) == 127 or unicodedata.category(ch).startswith("C"):
            continue
        else:
            chars.append(ch)
    normalized = " ".join("".join(chars).split())
    return normalized[:max_len]


def validate_since(since):
    if not isinstance(since, str) or not DATE_PATTERN.match(since):
        raise ValueError("invalid --since date")
    try:
        datetime.fromisoformat(since[:10])
    except ValueError as err:
        raise ValueError("invalid --since date") from err
    return since[:10]


@contextmanager
def open_dir(path):
    """Open a directory without following a symlink at the target path."""
    target = Path(os.path.abspath(path))
    if target.is_symlink():
        raise ValueError("symlink directory refused")
    real = Path(os.path.realpath(target))
    fd = os.open(real, os.O_RDONLY | DIRECTORY | NOFOLLOW | NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("not a directory")
        yield fd
    finally:
        os.close(fd)


def read_safe_file(path, limit=MAX_FILE_BYTES):
    """Read a regular user-owned file without following symlinks."""
    raw_path = Path(path)
    expanded = Path(os.path.abspath(raw_path))
    if raw_path.is_symlink() or expanded.is_symlink() or expanded.parent.is_symlink():
        raise ValueError("symlink file refused")
    with open_dir(expanded.parent) as parent_fd:
        fd = os.open(expanded.name, os.O_RDONLY | NOFOLLOW | NONBLOCK, dir_fd=parent_fd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
                raise ValueError("unsafe or oversized file")
            chunks, size = [], 0
            while size <= limit:
                chunk = os.read(fd, min(65536, limit + 1 - size))
                if not chunk:
                    return b"".join(chunks).decode("utf-8", "replace")
                chunks.append(chunk)
                size += len(chunk)
            raise ValueError("file exceeds size limit")
        finally:
            os.close(fd)


def find_repo_root(start_path):
    start = Path(os.path.abspath(start_path))
    if start.is_file():
        start = start.parent
    for depth, folder in enumerate((start, *start.parents)):
        if depth >= 20:
            break
        try:
            with open_dir(folder) as fd:
                try:
                    info = os.stat(".git", dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode):
                    return folder
        except OSError:
            return None
    return None


def reader_lines(text):
    """Yield (line_number, line) outside fenced code blocks, skipping oversized lines."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > 4096:
            continue
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            token, tail = match.groups()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not tail.strip():
                fence = None
            continue
        if fence is None:
            yield number, line


def placeholder_only(text):
    return re.fullmatch(r"\s*(?:(?:AC|SC|C|T)-?[0-9]+\s+)?<[^<>]*>\s*", text) is not None


def negated_completion(text):
    return re.search(r"\bnot(?:\s+yet)?\s+(?:released|done|merged|implemented)\b", text, re.I) is not None


def status_word(text):
    if not isinstance(text, str) or negated_completion(text):
        return "unknown"
    match = re.fullmatch(
        r"(draft|accepted|in progress|implemented|released|deferred)(?:\s*;.*)?",
        text.strip(),
        re.I,
    )
    return match.group(1).lower() if match else "unknown"


def extract_status_line(text):
    for number, line in reader_lines(text):
        if number > 40:
            break
        match = re.match(r"^\s*(?:\*\*)?Status(?:\*\*)?:(?:\*\*)?\s*(.*)$", line, re.I)
        if match:
            return status_word(match.group(1))
    return "unknown"


def _make_criterion(raw_text, default_prefix, counter, checkbox=None, spec_ref=None):
    cleaned = sanitize_text(raw_text, max_len=MAX_CRITERION_LEN * 2)
    if not cleaned or placeholder_only(cleaned):
        return None
    match = EXPLICIT_CRITERION_ID.match(cleaned)
    if match:
        cid = sanitize_text(match.group(1) or match.group(2), MAX_ID_LEN)
        wording = sanitize_text(match.group(3), MAX_CRITERION_LEN)
    else:
        cid = f"{default_prefix}-{counter}"
        wording = sanitize_text(cleaned, MAX_CRITERION_LEN)
    if not wording or not SAFE_ID.match(cid):
        return None
    refs = []
    if spec_ref and SAFE_REF.match(spec_ref):
        refs.append(spec_ref)
    if checkbox in ("done", "todo"):
        refs.append(f"checkbox:{checkbox}")
    return {"id": cid, "criterion": wording, "evidence_refs": refs}


def parse_criteria_from_markdown(text, prefix="C", spec_ref=None, allow_top_level=False):
    """Extract criteria from Work tracking Outcome lines and acceptance/criteria sections."""
    criteria = []
    section = None
    in_outcome = False
    outcome_counter = 1
    counter = 1

    for _, raw_line in reader_lines(text):
        stripped = raw_line.strip()
        heading = re.match(r"^(#{1,4})\s+(.+?)\s*$", stripped)
        if heading:
            in_outcome = False
            title = heading.group(2).strip().lower()
            if title == "work tracking":
                section = "work_tracking"
            elif title in (
                "goal and acceptance", "success criteria", "measurable outcomes",
                "acceptance criteria", "acceptance",
            ):
                section = "criteria"
            else:
                section = "other"
            continue

        if section == "work_tracking" or (section is None and allow_top_level):
            outcome_match = re.match(
                r"^(?:[-*]\s*)?(?:\*\*)?Outcome(?:\*\*)?(?:\s*\([^)]*\))?\s*:\s*(.*)$",
                stripped,
                re.I,
            )
            if outcome_match:
                in_outcome = True
                outcome_text = outcome_match.group(1).strip()
                if outcome_text:
                    item = _make_criterion(outcome_text, "OUTCOME", outcome_counter, spec_ref=spec_ref)
                    if item:
                        criteria.append(item)
                        outcome_counter += 1
                continue

            if in_outcome:
                box = re.match(r"^\s*[-*]\s*\[([ xX])\]\s+(.*)$", raw_line)
                bullet = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$", raw_line)
                if box:
                    state = "done" if box.group(1).lower() == "x" else "todo"
                    item = _make_criterion(box.group(2), prefix, counter, checkbox=state, spec_ref=spec_ref)
                    if item:
                        criteria.append(item)
                        counter += 1
                    continue
                if bullet and not WORK_TRACKING_META.match(bullet.group(1).strip()):
                    item = _make_criterion(bullet.group(1), prefix, counter, spec_ref=spec_ref)
                    if item:
                        criteria.append(item)
                        counter += 1
                    continue
                if stripped and WORK_TRACKING_META.match(stripped):
                    in_outcome = False
                    continue

        if section == "criteria" or (section is None and allow_top_level and not in_outcome):
            box = re.match(r"^\s*[-*]\s*\[([ xX])\]\s+(.*)$", raw_line)
            bullet = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$", raw_line)
            if box:
                state = "done" if box.group(1).lower() == "x" else "todo"
                item = _make_criterion(box.group(2), prefix, counter, checkbox=state, spec_ref=spec_ref)
                if item:
                    criteria.append(item)
                    counter += 1
            elif bullet and not WORK_TRACKING_META.match(bullet.group(1).strip()):
                item = _make_criterion(bullet.group(1), prefix, counter, spec_ref=spec_ref)
                if item:
                    criteria.append(item)
                    counter += 1

    return criteria[:MAX_CRITERIA]


def is_work_record(text):
    """True when text has a Status line within 40 lines and at least two work-record headings."""
    has_status = False
    for number, line in reader_lines(text):
        if number <= 40 and re.match(r"^\s*(?:\*\*)?Status(?:\*\*)?:(?:\*\*)?\s*", line, re.I):
            has_status = True
            break
    if not has_status:
        return False
    headings = set()
    for _, line in reader_lines(text):
        match = re.fullmatch(r"## (Goal and acceptance|Plan|Tasks|Evidence)\s*", line)
        if match:
            headings.add(match.group(1))
    return len(headings) >= 2


def list_safe_dir(root_fd, relative, cap=200):
    parts = [p for p in Path(relative).parts if p not in ("", ".")]
    if ".." in parts:
        return []
    fd = os.dup(root_fd)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | DIRECTORY | NOFOLLOW | NONBLOCK, dir_fd=fd)
            os.close(fd)
            fd = child
        entries = []
        with os.scandir(fd) as it:
            for entry in it:
                if len(entries) >= cap:
                    break
                entries.append((
                    entry.name,
                    entry.is_dir(follow_symlinks=False),
                    entry.is_file(follow_symlinks=False),
                ))
        return sorted(entries)
    except OSError:
        return []
    finally:
        os.close(fd)


def read_rel_file(root_fd, relative, limit=MAX_DOC_BYTES):
    parts = [p for p in Path(relative).parts if p not in ("", ".")]
    if not parts or ".." in parts or parts[-1].upper() in INSTRUCTION_FILES:
        raise ValueError("unsafe relative path")
    fd = os.dup(root_fd)
    try:
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | NOFOLLOW | NONBLOCK
            if index < len(parts) - 1:
                flags |= DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
            raise ValueError("unsafe spec file")
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - size))
            if not chunk:
                return b"".join(chunks).decode("utf-8", "replace")
            chunks.append(chunk)
            size += len(chunk)
        raise ValueError("spec file too large")
    finally:
        os.close(fd)


def collect_repo_specs_and_criteria(repo_root, anchors_resolved=None):
    """Scan repository specs/*/spec.md and work records for statuses and criteria."""
    specs = []
    extra_criteria = []
    seen_specs = set()
    if repo_root is None:
        return specs, extra_criteria

    try:
        with open_dir(repo_root) as root_fd:
            # 1. Spec Kit: specs/<feature>/spec.md (excluding archive)
            spec_entries = list_safe_dir(root_fd, "specs")
            has_numbered = False
            for name, is_dir, _ in spec_entries:
                if not is_dir or name == "archive":
                    continue
                if re.fullmatch(r"[0-9]{3}-.+", name):
                    has_numbered = True
                rel = f"specs/{name}/spec.md"
                candidate_path = (repo_root / rel).resolve()
                try:
                    text = read_rel_file(root_fd, rel, MAX_DOC_BYTES)
                except (OSError, ValueError):
                    continue
                spec_id = sanitize_text(name, MAX_ID_LEN)
                if not SAFE_ID.match(spec_id):
                    continue
                st = extract_status_line(text)
                if spec_id not in seen_specs and len(specs) < MAX_SPECS:
                    specs.append({"id": spec_id, "status": st})
                    seen_specs.add(spec_id)
                if anchors_resolved is None or candidate_path != anchors_resolved:
                    prefix = re.sub(r"[^A-Za-z0-9_.-]", "-", spec_id)[:24]
                    extra_criteria.extend(
                        parse_criteria_from_markdown(text, prefix=prefix, spec_ref=f"{spec_id}:{st}")
                    )

            # 2. docs/specs, docs/spec, and flat specs/*.md
            for folder in ("docs/specs", "docs/spec", "specs"):
                if folder == "specs" and has_numbered:
                    continue
                entries = list_safe_dir(root_fd, folder)
                for name, _, is_reg in entries:
                    if not is_reg or not name.lower().endswith(".md") or name == "index.md":
                        continue
                    if name.upper() in INSTRUCTION_FILES:
                        continue
                    rel = f"{folder}/{name}"
                    candidate_path = (repo_root / rel).resolve()
                    try:
                        text = read_rel_file(root_fd, rel, MAX_DOC_BYTES)
                    except (OSError, ValueError):
                        continue
                    stem = sanitize_text(Path(name).stem, MAX_ID_LEN)
                    if not SAFE_ID.match(stem):
                        continue
                    st = extract_status_line(text)
                    if stem not in seen_specs and len(specs) < MAX_SPECS:
                        specs.append({"id": stem, "status": st})
                        seen_specs.add(stem)
                    if (anchors_resolved is None or candidate_path != anchors_resolved) and is_work_record(text):
                        prefix = re.sub(r"[^A-Za-z0-9_.-]", "-", stem)[:24]
                        extra_criteria.extend(
                            parse_criteria_from_markdown(text, prefix=prefix, spec_ref=f"{stem}:{st}")
                        )
    except OSError:
        pass

    return specs, extra_criteria


def collect_git_evidence(repo_root, since):
    """Read commit and pull-request identifiers from git log since date; never read bodies."""
    if repo_root is None:
        return [], [], []
    env = {
        "PATH": "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin",
        "LC_ALL": "C",
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        proc = subprocess.run(
            [
                "git", "-C", str(repo_root), "log",
                f"--since={since}", f"-n{MAX_COMMITS}", "--format=%H%x09%s",
            ],
            capture_output=True,
            env=env,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return [], [], []
    if proc.returncode != 0:
        return [], [], []

    raw = proc.stdout[:MAX_GIT_BYTES].decode("utf-8", "replace")
    commits = []
    prs = []
    commit_subjects = []
    seen_commits = set()
    seen_prs = set()

    for line in raw.splitlines():
        if "\t" not in line:
            continue
        sha_part, subj_part = line.split("\t", 1)
        sha = sha_part.strip().lower()
        if not COMMIT_ID.match(sha):
            continue
        short_sha = sha[:12]
        capped_subject = sanitize_text(subj_part, MAX_SUBJECT_LEN)
        if short_sha not in seen_commits:
            commits.append(short_sha)
            seen_commits.add(short_sha)
        commit_subjects.append((short_sha, capped_subject))
        for pr_match in PR_IN_SUBJECT.finditer(capped_subject):
            pr_id = f"#{pr_match.group(1)}"
            if PR_ID.match(pr_id) and pr_id not in seen_prs:
                prs.append(pr_id)
                seen_prs.add(pr_id)

    return commits, prs, commit_subjects


def collect_ledger_evidence(since, project=None):
    """Read ledger outcomes through data_root.py using ledger.py's format; tolerate missing ledger."""
    try:
        if dr.consent_root() is None:
            return {"status": "absent", "ids": [], "counts": {}}
        raw = dr.read_data("ledger.jsonl", 16 * 1024 * 1024).decode("utf-8")
    except (FileNotFoundError, OSError, ValueError, UnicodeError):
        return {"status": "absent", "ids": [], "counts": {}}

    starts, finishes = {}, {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        event = rec.get("event")
        required = LEDGER_REQUIRED.get(event)
        if not required or not required <= rec.keys():
            continue
        rid = rec.get("id")
        if not isinstance(rid, str) or not DISPATCH_ID.match(rid) or has_control_chars(rid):
            continue
        if event == "start":
            starts[rid] = rec
        elif event == "finish":
            finishes[rid] = rec

    counts = Counter()
    ids = []
    for rid, start in starts.items():
        if project and start.get("project") != project:
            continue
        finish = finishes.get(rid)
        ts = str((finish or start).get("ts", ""))
        if ts[:10] < since:
            continue
        if len(ids) < MAX_LEDGER_IDS:
            ids.append(rid)
        if finish is not None:
            outcome = finish.get("outcome")
            if outcome in OUTCOME_WORDS:
                counts[outcome] += 1

    return {
        "status": "present",
        "ids": ids,
        "counts": {k: counts[k] for k in OUTCOME_WORDS if counts[k] > 0},
    }


def collect(anchors_path, since, repo=None, project=None):
    """Collect anchors and repository evidence since `since` with only allowed fields."""
    since_date = validate_since(since)
    anchors_file = Path(os.path.abspath(anchors_path))
    anchors_text = read_safe_file(anchors_file, MAX_FILE_BYTES)
    repo_root = Path(os.path.abspath(repo)) if repo else find_repo_root(anchors_file)

    primary_criteria = parse_criteria_from_markdown(anchors_text, prefix="C", allow_top_level=True)
    specs, repo_criteria = collect_repo_specs_and_criteria(repo_root, anchors_resolved=anchors_file.resolve())

    criteria = []
    seen = set()
    for item in (*primary_criteria, *repo_criteria):
        key = (item["id"], item["criterion"])
        if key in seen:
            continue
        seen.add(key)
        criteria.append(item)
        if len(criteria) >= MAX_CRITERIA:
            break

    commits, prs, commit_subjects = collect_git_evidence(repo_root, since_date)
    ledger = collect_ledger_evidence(since_date, project=project)

    # Link commit and PR identifiers to criteria that are named in capped subjects.
    for item in criteria:
        refs = list(item["evidence_refs"])
        cid_pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(item["id"]) + r"(?![A-Za-z0-9])", re.I)
        for short_sha, subj in commit_subjects:
            if cid_pattern.search(subj):
                if short_sha not in refs:
                    refs.append(short_sha)
                for pr_match in PR_IN_SUBJECT.finditer(subj):
                    pr_id = f"#{pr_match.group(1)}"
                    if pr_id not in refs:
                        refs.append(pr_id)
        item["evidence_refs"] = refs[:50]

    payload = {
        "since": since_date,
        "criteria": criteria,
        "evidence": {
            "commits": commits,
            "pull_requests": prs,
            "specs": specs,
            "ledger": ledger,
            "counts": {
                "commits": len(commits),
                "pull_requests": len(prs),
                "specs": len(specs),
                "ledger_runs": len(ledger["ids"]),
            },
        },
    }
    validate_payload(payload)
    return payload


def strict_json_loads(raw):
    """Parse JSON while rejecting duplicate keys anywhere in the object tree."""
    def no_dups(pairs):
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate JSON key")
        return dict(pairs)

    if not isinstance(raw, str):
        raise ValueError("JSON input must be text")
    try:
        return json.loads(raw, object_pairs_hook=no_dups)
    except ValueError as err:
        raise ValueError("invalid JSON") from err


def _is_nonneg_int(value):
    return type(value) is int and 0 <= value <= 10**7


def _validate_refs_list(refs):
    if not isinstance(refs, list) or len(refs) > 200:
        raise ValueError("invalid evidence_refs list")
    for ref in refs:
        if not isinstance(ref, str) or not ref or len(ref) > MAX_REF_LEN:
            raise ValueError("invalid evidence reference")
        if has_control_chars(ref) or not SAFE_REF.match(ref):
            raise ValueError("invalid evidence reference")


def _validate_evidence_block(ev):
    if isinstance(ev, list):
        _validate_refs_list(ev)
        return
    if not isinstance(ev, dict) or not ev:
        raise ValueError("evidence must be a non-empty object or reference list")
    extra = set(ev) - EVIDENCE_KEYS
    if extra:
        raise ValueError("disallowed evidence field")

    if "commits" in ev:
        if not isinstance(ev["commits"], list) or len(ev["commits"]) > MAX_COMMITS:
            raise ValueError("invalid commits list")
        for cid in ev["commits"]:
            if not isinstance(cid, str) or has_control_chars(cid) or not COMMIT_ID.match(cid):
                raise ValueError("invalid commit id")

    if "pull_requests" in ev:
        if not isinstance(ev["pull_requests"], list) or len(ev["pull_requests"]) > MAX_COMMITS:
            raise ValueError("invalid pull_requests list")
        for pr in ev["pull_requests"]:
            if not isinstance(pr, str) or has_control_chars(pr) or not PR_ID.match(pr):
                raise ValueError("invalid pull request id")

    if "specs" in ev:
        specs = ev["specs"]
        if isinstance(specs, dict):
            if len(specs) > MAX_SPECS:
                raise ValueError("too many specs")
            for sid, st in specs.items():
                if (not isinstance(sid, str) or has_control_chars(sid) or not SAFE_ID.match(sid)
                        or st not in STATUS_WORDS):
                    raise ValueError("invalid spec status entry")
        elif isinstance(specs, list):
            if len(specs) > MAX_SPECS:
                raise ValueError("too many specs")
            for item in specs:
                if not isinstance(item, dict) or set(item) != SPEC_ITEM_KEYS:
                    raise ValueError("invalid spec status entry")
                if (not isinstance(item["id"], str) or has_control_chars(item["id"])
                        or not SAFE_ID.match(item["id"]) or item["status"] not in STATUS_WORDS):
                    raise ValueError("invalid spec status entry")
        else:
            raise ValueError("invalid specs field")

    if "ledger" in ev:
        ledger = ev["ledger"]
        if not isinstance(ledger, dict) or set(ledger) != LEDGER_KEYS:
            raise ValueError("invalid ledger block")
        if ledger["status"] not in LEDGER_STATUS_WORDS:
            raise ValueError("invalid ledger status")
        if not isinstance(ledger["ids"], list) or len(ledger["ids"]) > MAX_LEDGER_IDS:
            raise ValueError("invalid ledger ids")
        for lid in ledger["ids"]:
            if not isinstance(lid, str) or has_control_chars(lid) or not DISPATCH_ID.match(lid):
                raise ValueError("invalid ledger dispatch id")
        counts = ledger["counts"]
        if not isinstance(counts, dict):
            raise ValueError("invalid ledger counts")
        for outcome, num in counts.items():
            if outcome not in OUTCOME_WORDS or not _is_nonneg_int(num):
                raise ValueError("invalid ledger outcome count")
        if ledger["status"] == "absent" and (ledger["ids"] or ledger["counts"]):
            raise ValueError("absent ledger cannot carry ids or counts")

    if "counts" in ev:
        counts = ev["counts"]
        if not isinstance(counts, dict) or not counts or set(counts) - set(COUNT_KEYS):
            raise ValueError("invalid counts block")
        for key, num in counts.items():
            if not _is_nonneg_int(num):
                raise ValueError(f"invalid count for {key}")

    if "ids" in ev:
        _validate_refs_list(ev["ids"])

    if "status" in ev:
        if ev["status"] not in STATUS_WORDS and ev["status"] not in LEDGER_STATUS_WORDS:
            raise ValueError("invalid status word")


def _validate_criterion_item(item, require_evidence=False):
    if not isinstance(item, dict):
        raise ValueError("criterion entry must be an object")
    extra = set(item) - CRITERION_KEYS
    if extra:
        raise ValueError("disallowed field in criterion payload")
    if "id" not in item or "criterion" not in item:
        raise ValueError("criterion payload requires id and criterion")
    cid = item["id"]
    if not isinstance(cid, str) or has_control_chars(cid) or not SAFE_ID.match(cid):
        raise ValueError("invalid criterion id")
    for text_key in ("criterion", "restated_criterion", "question"):
        if text_key in item:
            val = item[text_key]
            if (not isinstance(val, str) or not val.strip()
                    or len(val) > MAX_CRITERION_LEN or has_control_chars(val)):
                raise ValueError(f"invalid {text_key}")
    if require_evidence and "evidence" not in item and "evidence_refs" not in item:
        raise ValueError("criterion payload requires evidence or evidence_refs")
    if "evidence_refs" in item:
        _validate_refs_list(item["evidence_refs"])
    if "evidence" in item:
        _validate_evidence_block(item["evidence"])


def validate_payload(payload):
    """Enforce that a collection or judge payload contains only allowed fields and valid values."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload must be a non-empty JSON object")

    if "criteria" in payload or "since" in payload:
        extra = set(payload) - COLLECTION_KEYS
        if extra:
            raise ValueError("disallowed top-level field in payload")
        if "criteria" not in payload or "evidence" not in payload:
            raise ValueError("collection payload requires criteria and evidence")
        if "since" in payload:
            validate_since(payload["since"])
        if not isinstance(payload["criteria"], list) or len(payload["criteria"]) > MAX_CRITERIA:
            raise ValueError("invalid criteria list")
        for item in payload["criteria"]:
            _validate_criterion_item(item, require_evidence=False)
        _validate_evidence_block(payload["evidence"])
        return True

    if "id" in payload or "criterion" in payload:
        _validate_criterion_item(payload, require_evidence=True)
        return True

    raise ValueError("unrecognized payload shape")


def _require_nonempty_evidence(entry):
    """Every report entry or finding must reference concrete evidence."""
    has_refs = False
    if "evidence_refs" in entry:
        refs = entry["evidence_refs"]
        _validate_refs_list(refs)
        if refs:
            has_refs = True
    if "evidence" in entry:
        ev = entry["evidence"]
        if isinstance(ev, str):
            if not ev.strip() or len(ev) > MAX_REF_LEN or has_control_chars(ev) or not SAFE_REF.match(ev.strip()):
                raise ValueError("invalid evidence reference")
            has_refs = True
        elif isinstance(ev, list):
            _validate_refs_list(ev)
            if ev:
                has_refs = True
        elif isinstance(ev, dict):
            _validate_evidence_block(ev)
            if (ev.get("commits") or ev.get("pull_requests") or ev.get("specs")
                    or ev.get("ids") or (ev.get("ledger") and ev["ledger"].get("ids"))):
                has_refs = True
        else:
            raise ValueError("invalid evidence field")
    if not has_refs:
        raise ValueError("report entry missing evidence reference")


def _check_finding(finding):
    if not isinstance(finding, dict):
        raise ValueError("finding must be an object")
    extra = set(finding) - FINDING_KEYS
    if extra:
        raise ValueError("disallowed field in finding")
    text = finding.get("finding")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CRITERION_LEN or has_control_chars(text):
        raise ValueError("invalid finding text")
    if "id" in finding:
        if not isinstance(finding["id"], str) or has_control_chars(finding["id"]) or not SAFE_ID.match(finding["id"]):
            raise ValueError("invalid finding id")
    if "drift_kind" in finding:
        dk = finding["drift_kind"]
        if not isinstance(dk, str) or not dk.strip() or len(dk) > MAX_ID_LEN or has_control_chars(dk):
            raise ValueError("invalid drift_kind")
    _require_nonempty_evidence(finding)


def _check_options(options):
    if not isinstance(options, list) or len(options) > 3:
        raise ValueError("at most three options to steer back are allowed")
    for opt in options:
        if not isinstance(opt, dict):
            raise ValueError("option must be an object")
        extra = set(opt) - OPTION_KEYS
        if extra:
            raise ValueError("disallowed field in option")
        label = opt.get("option") if "option" in opt else opt.get("action")
        cost = opt.get("cost")
        if (not isinstance(label, str) or not label.strip() or len(label) > MAX_OPTION_LEN or has_control_chars(label)
                or not isinstance(cost, str) or not cost.strip() or len(cost) > MAX_OPTION_LEN or has_control_chars(cost)):
            raise ValueError("each option requires non-empty option and cost")


def _check_anchor_or_entry(entry):
    if not isinstance(entry, dict) or not entry:
        raise ValueError("report entry must be a non-empty object")
    extra = set(entry) - ANCHOR_ENTRY_KEYS
    if extra:
        raise ValueError("disallowed field in report entry")

    for id_key in ("id", "anchor"):
        if id_key in entry:
            val = entry[id_key]
            if not isinstance(val, str) or has_control_chars(val) or not SAFE_ID.match(val):
                raise ValueError(f"invalid {id_key}")

    if "status" in entry:
        st = entry["status"]
        if not isinstance(st, str) or has_control_chars(st) or st.lower() not in ANCHOR_STATUS_WORDS:
            raise ValueError("invalid anchor status")

    for ans_key in ("answer", "judge_answer"):
        if ans_key in entry:
            if entry[ans_key] not in JUDGE_ANSWERS:
                raise ValueError("invalid judge answer")

    if "judge" in entry and entry["judge"] not in ("jev", "host"):
        raise ValueError("invalid judge name")
    if "judge_validated" in entry and type(entry["judge_validated"]) is not bool:
        raise ValueError("judge_validated must be a boolean")

    if "restated_criterion" in entry and "criterion" not in entry:
        raise ValueError("restated_criterion requires original criterion")
    for text_key in ("criterion", "restated_criterion", "question", "finding"):
        if text_key in entry:
            val = entry[text_key]
            if not isinstance(val, str) or not val.strip() or len(val) > MAX_CRITERION_LEN or has_control_chars(val):
                raise ValueError(f"invalid {text_key}")

    if "findings" in entry:
        if not isinstance(entry["findings"], list):
            raise ValueError("findings must be a list")
        for f in entry["findings"]:
            _check_finding(f)

    if "options" in entry:
        _check_options(entry["options"])

    if "criteria" in entry:
        if not isinstance(entry["criteria"], list) or not entry["criteria"]:
            raise ValueError("criteria in report anchor must be a non-empty list")
        for c in entry["criteria"]:
            _check_anchor_or_entry(c)
        if "evidence" in entry or "evidence_refs" in entry:
            _require_nonempty_evidence(entry)
    else:
        _require_nonempty_evidence(entry)


def check_report(report):
    """Validate a navigator report or report entry; reject any entry or finding without evidence."""
    if isinstance(report, list):
        if not report:
            raise ValueError("empty report list")
        for entry in report:
            _check_anchor_or_entry(entry)
        return True

    if not isinstance(report, dict) or not report:
        raise ValueError("report must be a non-empty JSON object or list")

    if "anchors" in report:
        extra = set(report) - REPORT_TOP_KEYS
        if extra:
            raise ValueError("disallowed top-level field in report")
        if not isinstance(report["anchors"], list) or not report["anchors"]:
            raise ValueError("report requires a non-empty anchors list")
        for anchor in report["anchors"]:
            _check_anchor_or_entry(anchor)
        if "findings" in report:
            if not isinstance(report["findings"], list):
                raise ValueError("findings must be a list")
            for f in report["findings"]:
                _check_finding(f)
        if "unmatched_items" in report:
            _validate_refs_list(report["unmatched_items"])
        if "options" in report:
            _check_options(report["options"])
        if "judge_validated" in report and type(report["judge_validated"]) is not bool:
            raise ValueError("judge_validated must be a boolean")
        return True

    _check_anchor_or_entry(report)
    return True


def _read_json_arg(file_arg):
    if file_arg in (None, "-"):
        raw = sys.stdin.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("input too large")
        return strict_json_loads(raw)
    text = read_safe_file(file_arg, MAX_FILE_BYTES)
    return strict_json_loads(text)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid arguments")


def build_parser():
    parser = Parser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="collect anchors and evidence since a date")
    c.add_argument("--anchors", required=True, help="path to the anchors or agent-context file")
    c.add_argument("--since", required=True, help="ISO date YYYY-MM-DD of the last course check")
    c.add_argument("--repo", help="optional repository root path")
    c.add_argument("--project", help="optional ledger project filter")

    v = sub.add_parser("validate-payload", help="validate that a payload contains only allowed fields")
    v.add_argument("path", nargs="?", help="JSON file path, or '-' / omit for stdin")
    v.add_argument("--file", dest="file_opt", help="JSON file path")

    r = sub.add_parser("check-report", help="reject any report entry or finding without an evidence reference")
    r.add_argument("path", nargs="?", help="JSON file path, or '-' / omit for stdin")
    r.add_argument("--file", dest="file_opt", help="JSON file path")

    return parser


def main(argv=None):
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        if args.cmd == "collect":
            result = collect(args.anchors, args.since, repo=args.repo, project=args.project)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.cmd == "validate-payload":
            target = args.file_opt if args.file_opt is not None else args.path
            data = _read_json_arg(target)
            validate_payload(data)
            print(json.dumps({"ok": True}))
            return 0
        if args.cmd == "check-report":
            target = args.file_opt if args.file_opt is not None else args.path
            data = _read_json_arg(target)
            check_report(data)
            print(json.dumps({"ok": True}))
            return 0
    except (ValueError, OSError, OverflowError) as err:
        msg = sanitize_text(str(err).splitlines()[0] if str(err) else "invalid input", 120)
        print(f"Navigator state refused: {msg}.", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
