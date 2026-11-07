#!/usr/bin/env python3
"""Verify an authorized JSON brief against a checkout; never accept work itself.

Brief: {"scope": ["relative/file"], "tests": [["executable", "arg"]],
"criteria": [{"id": "C1", "question": "English statement"}]}.
For document comparisons replace question with documents: two objects containing
path and question; compare their independently judged answers in code.
"""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge
import record

LIMIT = 65536


def relative(value):
    return (isinstance(value, str) and bool(value) and not Path(value).is_absolute()
            and ".." not in Path(value).parts and not value.startswith("-") and "\x00" not in value)


def full_suite(argv):
    """Recognize direct and Python module runners; require explicit test selectors."""
    runner, args = Path(argv[0]).name, argv[1:]
    if re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?t?", runner):
        for index, arg in enumerate(args):
            if arg == "-m":
                runner, args = (args[index + 1], args[index + 2:]) if index + 1 < len(args) else ("", [])
                break
            module_flag = re.fullmatch(r"-[IBEOqsuUvVbPdiR]*m(.*)", arg)
            if module_flag:
                module = module_flag[1]
                runner, args = ((module, args[index + 1:]) if module else
                                ((args[index + 1], args[index + 2:]) if index + 1 < len(args) else ("", [])))
                break
            if arg in ("-c", "--"):
                return False  # custom commands remain the coordinator's coverage responsibility
    if runner not in ("pytest", "py.test", "unittest") and not runner.startswith("unittest."):
        return False
    if runner.startswith("unittest.") or "discover" in args:
        return True
    targets, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg in ("-k", "-m", "--maxfail", "--tb", "--durations", "-p"):
            skip = True
        elif not arg.startswith("-"):
            targets.append(arg)
    return not targets or any(not re.search(r"(?:^|[/.])test_[A-Za-z0-9_]", arg) for arg in targets)


def load_brief(path):
    brief = json.loads(judge.read_text(path))
    if not isinstance(brief, dict) or set(brief) != {"scope", "tests", "criteria"}:
        raise ValueError("brief needs scope, tests and criteria")
    if not isinstance(brief["scope"], list) or not brief["scope"] or not all(relative(p) for p in brief["scope"]):
        raise ValueError("invalid scope")
    if not isinstance(brief["tests"], list) or not brief["tests"] or len(brief["tests"]) > 50:
        raise ValueError("list the targeted tests explicitly")
    for argv in brief["tests"]:
        if (not isinstance(argv, list) or not argv or
                not all(isinstance(a, str) and a and "\x00" not in a for a in argv)):
            raise ValueError("tests must be argv arrays")
        words = [Path(a).name for a in argv]
        if (words[0] in ("sh", "bash", "zsh", "fish", "cmd", "powershell")
                or full_suite(argv)):
            raise ValueError("shells and full-suite discovery are refused")
    if not isinstance(brief["criteria"], list) or len(brief["criteria"]) > 50:
        raise ValueError("invalid criteria")
    seen = set()
    for criterion in brief["criteria"]:
        if (not isinstance(criterion, dict) or not isinstance(criterion.get("id"), str)
                or not re.fullmatch(r"C[0-9]{1,4}", criterion["id"]) or criterion["id"] in seen):
            raise ValueError("invalid or duplicate criterion id")
        seen.add(criterion["id"])
        if set(criterion) == {"id", "question"}:
            judge.payload(criterion["question"], "")
        elif set(criterion) == {"id", "documents"}:
            docs = criterion["documents"]
            if not isinstance(docs, list) or len(docs) != 2:
                raise ValueError("a comparison needs two documents")
            for doc in docs:
                if not isinstance(doc, dict) or set(doc) != {"path", "question"} or not relative(doc["path"]):
                    raise ValueError("invalid document")
                judge.payload(doc["question"], "")
        else:
            raise ValueError("invalid criterion")
    return brief


def run_test(argv, checkout, timeout):
    """No shell; cap combined output and kill descendants on timeout or overflow."""
    process = subprocess.Popen(argv, cwd=checkout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True, env=record.child_environment())
    chunks, total, failed = [], 0, False
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                failed = True
                break
            for key, _ in selector.select(min(.1, max(0, deadline - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                total += len(chunk)
                if total > LIMIT:
                    failed = True
                    break
                chunks.append(chunk)
            if failed:
                break
        # A child can close stdout and keep running: the deadline still applies.
        if not failed:
            try:
                process.wait(timeout=max(.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                failed = True
    finally:
        selector.close()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()
    output = b"".join(chunks).decode("utf-8", errors="replace")
    return process.returncode == 0 and not failed, output, "limit" if failed else str(process.returncode)


def ask(question, evidence, identifier, source, answers):
    fallback = False
    if source == "jev":
        try:
            out = judge.ask_jev(question, evidence)
        except judge.Unavailable:
            fallback = True
            print(f"{identifier}: Jev unavailable; falling back to small host judge", file=sys.stderr)
    if source == "host" or fallback:
        packet = answers.get(identifier)
        # Bind saved host output to this exact question and current evidence.
        if (not isinstance(packet, dict) or "evidence_sha256" not in packet or "question" not in packet):
            out = judge.result()
        else:
            out = judge.check_host(packet, evidence, question)
    if out["source"] == "jev":
        print(f"{identifier}: Jev p={out['p']}", file=sys.stderr)
    return dict(id=identifier, answer=out["answer"], source=out["source"], fallback=fallback)


def verify(brief, base, head, dispatch, checkout, source, answers, timeout=300):
    record.dispatch_id(dispatch)
    for rev in (base, head):
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", rev):
            raise ValueError("base and head must be full commit ids")
    mechanical = True
    def check(label, passed, detail):
        nonlocal mechanical
        mechanical &= passed
        print(f"{'PASS' if passed else 'FAIL'} {label}: {detail}")
    check("head", record.current_head(checkout) == head, head)
    # Only an ancestor base gives the coordinator's intended change range.
    try:
        record.git(checkout, "merge-base", "--is-ancestor", base, head)
        ancestor = True
    except subprocess.CalledProcessError:
        ancestor = False
    check("base", ancestor, base)
    def clean():
        return not record.git(checkout, "status", "--porcelain", "--untracked-files=all")
    check("clean checkout", clean(), "committed bytes only")
    changed = record.git(checkout, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--name-only", "-z", base, head, "--")
    paths = [p for p in changed.split("\x00") if p]
    outside = [p for p in paths if not any(fnmatch.fnmatchcase(p, pattern) for pattern in brief["scope"])]
    check("scope", not outside, json.dumps(outside if outside else paths))
    diff = record.git(checkout, "diff", "--no-ext-diff", "--no-textconv", "--stat", base, head, "--")
    outputs, tests_passed = [], True
    for index, argv in enumerate(brief["tests"], 1):
        try:
            passed, output, code = run_test(argv, checkout, timeout)
        except OSError:
            passed, output, code = False, "Test executable unavailable", "unavailable"
        check(f"test {index}", passed, f"exit={code}")
        print(output, end="" if output.endswith("\n") else "\n")
        outputs.append(f"Test {index}: {'PASS' if passed else 'FAIL'}\n{output}")
        tests_passed &= passed
    check("final head", record.current_head(checkout) == head, head)
    check("final checkout", clean(), "no test-induced changes")
    evidence = json.dumps({"head": head, "diff_summary": diff, "test_results": outputs}, ensure_ascii=False)
    requests, criteria = {}, []
    for criterion in brief["criteria"]:
        cid = criterion["id"]
        pieces = [(cid, criterion["question"], evidence)] if "question" in criterion else []
        if "documents" in criterion:
            for i, doc in enumerate(criterion["documents"], 1):
                # Read each document independently from the named commit, never a working file.
                blob = f"{head}:{doc['path']}"
                size = int(record.git(checkout, "cat-file", "-s", blob))
                try:
                    text = record.git(checkout, "show", blob) if size <= LIMIT else None
                except UnicodeDecodeError:
                    text = None  # Invalid UTF-8 is unavailable evidence, never a partial judgment.
                pieces.append((f"{cid}.{i}", doc["question"], text))
        judged = []
        for identifier, question, supplied in pieces:
            if supplied is None or len(supplied.encode()) > LIMIT:
                # Never judge truncated evidence or lose the run's failure receipt.
                check(f"{identifier} evidence", False, "unavailable or exceeds byte limit; judgment insufficient")
                answer = dict(id=identifier, answer="insufficient", source="host", fallback=False)
            else:
                requests[identifier] = {"question": question, "evidence": supplied,
                                        "evidence_sha256": hashlib.sha256(supplied.encode()).hexdigest()}
                answer = ask(question, supplied, identifier, source, answers)
            judged.append(answer)
            criteria.append(answer)
            print(f"{identifier}: {answer['answer']} source={answer['source']} fallback={str(answer['fallback']).lower()}")
        if len(judged) == 2:
            values = [a["answer"] for a in judged]
            # Two yes answers support alignment; two no answers do not prove agreement.
            combined = "yes" if values == ["yes", "yes"] else "no" if "no" in values else "insufficient"
            criteria.append(dict(id=cid, answer=combined, source="host", fallback=any(a["fallback"] for a in judged)))
            print(f"{cid}: {combined} (document answers compared in code)")
    record.write_verification(dispatch, head, "passed" if tests_passed else "failed",
                              "passed" if mechanical else "failed", criteria, checkout, evidence_id(requests))
    print("judge validation: unvalidated; coordinator reads every no/insufficient", file=sys.stderr)
    print("PASS verification mechanics" if mechanical else "FAIL verification mechanics")
    return mechanical, requests




def write_packet(path, requests):
    """Publish an owner-only local artifact atomically, without replacing a file."""
    path = Path(path)
    folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = ".verify-" + os.urandom(12).hex()
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=folder)
        with os.fdopen(fd, "w") as stream:
            json.dump(requests, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path.name, src_dir_fd=folder, dst_dir_fd=folder, follow_symlinks=False)
        os.fsync(folder)
    finally:
        try:
            os.unlink(temporary, dir_fd=folder)
        except FileNotFoundError:
            pass
        os.close(folder)

def evidence_id(requests):
    return hashlib.sha256(json.dumps(requests, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def complete_host(requests, answers, dispatch, head, checkout):
    """Attach checked host judgments to the exact test run without rerunning tests."""
    receipt = record.read_verification(dispatch)
    if (receipt["head"] != head or record.current_head(checkout) != head
            or receipt["checkout_id"] != record.checkout_identity(checkout)
            or not isinstance(requests, dict) or receipt["evidence_id"] != evidence_id(requests)
            or record.git(checkout, "status", "--porcelain", "--untracked-files=all")):
        raise ValueError("stale host evidence")
    criteria = []
    for item in receipt["criteria"]:
        identifier = item["id"]
        if identifier in requests and item["source"] == "host":
            request = requests[identifier]
            out = ask(request["question"], request["evidence"], identifier, "host", answers)
            out["fallback"] = item["fallback"]
            criteria.append(out)
        else:
            criteria.append(item.copy())
    indexed = {item["id"]: item for item in criteria}
    for item in criteria:
        first, second = indexed.get(item["id"] + ".1"), indexed.get(item["id"] + ".2")
        if first and second:
            values = [first["answer"], second["answer"]]
            item["answer"] = "yes" if values == ["yes", "yes"] else "no" if "no" in values else "insufficient"
        print(f"{item['id']}: {item['answer']} source={item['source']} fallback={str(item['fallback']).lower()}")
    record.write_verification(dispatch, head, receipt["tests"], receipt["mechanical"], criteria,
                              checkout, receipt["evidence_id"])
    print("judge validation: unvalidated; coordinator reads every no/insufficient", file=sys.stderr)
    return receipt["mechanical"] == "passed"

def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--brief")
    parser.add_argument("--base")
    parser.add_argument("--head", required=True)
    parser.add_argument("--ledger-id", required=True)
    parser.add_argument("--checkout", default=".")
    parser.add_argument("--judge", choices=("jev", "host"))
    parser.add_argument("--host-answers", help="JSON object keyed by criterion id")
    parser.add_argument("--requests-out", help="private local host request packet; contains evidence, never a receipt")
    parser.add_argument("--complete-host", help="complete the exact saved request packet without rerunning tests")
    args = parser.parse_args()
    try:
        answers = json.loads(judge.read_text(args.host_answers, 8 * 1024 * 1024)) if args.host_answers else {}
        if not isinstance(answers, dict):
            raise ValueError("invalid answer packet")
        if args.complete_host:
            if not args.host_answers or args.requests_out or args.brief or args.base or args.judge:
                raise ValueError("invalid host completion options")
            requests = json.loads(judge.read_text(args.complete_host, 8 * 1024 * 1024))
            return 0 if complete_host(requests, answers, args.ledger_id, args.head, args.checkout) else 1
        if not args.brief or not args.base:
            raise ValueError("brief and base required")
        brief = load_brief(args.brief)
        passed, requests = verify(brief, args.base, args.head, args.ledger_id, args.checkout,
                                  args.judge or judge.configured_judge(), answers)
        if args.requests_out:
            write_packet(args.requests_out, requests)
        return 0 if passed else 1
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        print("verify_claim: refused; invalid brief, evidence, checkout or receipt storage", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
