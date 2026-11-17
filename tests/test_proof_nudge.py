"""The proof nudge hook: synthetic home, data root, git repositories and hook input only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/proof_nudge.py"
SESSION = "synthetic-session-0001"
LINE = ("This session committed the current head and no checks or verify_claim receipt names it. Before reporting "
        "the work as done, run the targeted tests for the change and read their output.")


class ProofNudgeTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        base = Path(folder.name).resolve()
        self.home = account(self, base / "home")
        self.data = self.home / ".finolabs/vibecode"
        self.data.mkdir(parents=True, mode=0o700)
        self.home.joinpath(".finolabs").chmod(0o700)
        self.marks = self.data / "state/proof-nudge"
        self.mark = self.marks / hashlib.sha256(SESSION.encode()).hexdigest()[:16]
        self.repo = base / "repo"
        self.repo.mkdir(mode=0o700)
        self.git("init", "-q", "-b", "main")
        self.commit("first", old=True)  # an hour before any session in these tests

    def git(self, *args, cwd=None, old=False):
        env = {"PATH": os.defpath + ":/usr/local/bin:/opt/homebrew/bin", "HOME": str(self.home),
               "GIT_CONFIG_NOSYSTEM": "1"}
        if old:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = f"{int(time.time()) - 3600} +0000"
        done = subprocess.run(["git", "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.com",
                               "-c", "commit.gpgsign=false", *args], cwd=cwd or self.repo, env=env,
                              capture_output=True, text=True, check=True)
        return done.stdout.strip()

    def commit(self, message, cwd=None, old=False):
        self.git("commit", "-q", "--allow-empty", "-m", message, cwd=cwd, old=old)
        return self.git("rev-parse", "HEAD", cwd=cwd)

    def run_hook(self, *args, cwd=None, env=None, **fields):
        payload = {"hook_event_name": "Stop", "session_id": SESSION, "cwd": str(cwd or self.repo), **fields}
        result = subprocess.run([sys.executable, "-I", str(HOOK), *args], input=json.dumps(payload).encode(),
                                capture_output=True, timeout=10, env={"PATH": os.defpath, **(env or {})})
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        return result.stdout.decode()

    def start_session(self, at=None):
        self.assertEqual(self.run_hook("start"), "")
        if at is not None:
            self.mark.write_text(str(at))

    def assert_nudged(self, out):
        self.assertEqual(json.loads(out), {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": LINE}})
        self.assertNotIn("decision", out)

    def private(self, relative):
        folder = self.data / relative
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data.joinpath("state").chmod(0o700)
        folder.chmod(0o700)
        return folder

    def test_a_commit_made_this_session_nudges_once_per_head(self):
        self.start_session(at=int(time.time()) - 5)
        self.assertRegex(self.mark.read_text(), r"\A[0-9]{1,12}\Z")
        self.assertEqual(self.mark.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.run_hook(), "")  # the head predates the session
        head = self.commit("second")
        self.assert_nudged(self.run_hook())
        self.assertRegex(self.mark.read_text(), r"\A[0-9]{1,12} [0-9a-f]{16}\Z")
        self.assertIn(hashlib.sha256(head.encode()).hexdigest()[:16], self.mark.read_text())
        self.assertNotIn(head, self.mark.read_text())
        self.assertEqual(self.run_hook(), "")  # same head: once
        self.commit("third")
        self.assert_nudged(self.run_hook())
        self.assertEqual(os.listdir(self.marks), [self.mark.name])  # one mark, no raw session id

    def test_a_commit_before_the_session_started_prints_nothing(self):
        self.commit("second")
        self.start_session(at=int(time.time()) + 60)
        self.assertEqual(self.run_hook(), "")

    def test_no_mark_at_stop_records_the_start_and_prints_nothing(self):
        self.commit("second")
        self.assertEqual(self.run_hook(), "")
        self.assertRegex(self.mark.read_text(), r"\A[0-9]{1,12}\Z")

    def test_a_head_moved_without_a_commit_prints_nothing(self):
        self.start_session(at=int(time.time()) - 5)
        self.commit("second")
        self.git("checkout", "-q", "--detach", "HEAD~1")
        self.assertEqual(self.run_hook(), "")

    def test_a_checks_receipt_for_the_head_prevents_the_nudge(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import project_store
        self.start_session(at=int(time.time()) - 5)
        head = self.commit("second")
        receipt = self.private("state/checks-receipts") / (project_store.repository_code(self.repo) + ".json")
        receipt.write_text(json.dumps({"kind": "checks", "code": receipt.stem, "head": head, "digest": "0" * 64,
                                       "created": 1}))
        receipt.chmod(0o600)
        self.assertEqual(self.run_hook(), "")
        receipt.write_text(json.dumps({"kind": "checks", "code": receipt.stem, "head": "f" * 40, "digest": "0" * 64,
                                       "created": 1}))
        self.assert_nudged(self.run_hook())  # a receipt for another head is no proof

    def test_a_verification_receipt_for_the_head_prevents_the_nudge(self):
        self.start_session(at=int(time.time()) - 5)
        head = self.commit("second")
        receipt = self.private("state/verification") / "d20261117-100000-abcd.json"
        receipt.write_text(json.dumps({"kind": "verify", "id": "d20261117-100000-abcd", "head": head, "tests": "passed"}))
        receipt.chmod(0o600)
        self.assertEqual(self.run_hook(), "")

    def test_a_failed_or_unrun_verification_receipt_is_no_proof(self):
        for tests in ("failed", "not-run"):
            with self.subTest(tests=tests):
                self.start_session(at=int(time.time()) - 5)
                head = self.commit("change " + tests)
                receipt = self.private("state/verification") / "d20261117-100000-abcd.json"
                receipt.write_text(json.dumps({"kind": "verify", "id": "d20261117-100000-abcd", "head": head,
                                               "tests": tests}))
                receipt.chmod(0o600)
                self.assert_nudged(self.run_hook())

    def test_a_linked_worktree_and_packed_refs_are_read(self):
        self.start_session(at=int(time.time()) - 5)
        linked = self.repo.parent / "linked"
        self.git("worktree", "add", "-q", "-b", "side", str(linked))
        self.commit("side work", cwd=linked)
        self.git("pack-refs", "--all")
        self.assertFalse((self.repo / ".git/refs/heads/side").exists())
        self.assert_nudged(self.run_hook(cwd=linked))
        self.assertEqual(self.run_hook(), "")  # the main checkout's head was not committed this session

    def test_a_continued_stop_and_the_switch_print_nothing(self):
        self.start_session(at=int(time.time()) - 5)
        self.commit("second")
        self.assertEqual(self.run_hook(stop_hook_active=True), "")
        self.assertEqual(self.run_hook(env={"FNL_PROOF_NUDGE": "off"}), "")
        self.assert_nudged(self.run_hook())

    def test_the_switch_writes_no_mark_and_start_never_prints(self):
        self.assertEqual(self.run_hook("start", env={"FNL_PROOF_NUDGE": "off"}), "")
        self.assertFalse(self.marks.exists())
        self.assertEqual(self.run_hook("start"), "")
        first = self.mark.read_text()
        self.assertEqual(self.run_hook("start"), "")
        self.assertEqual(self.mark.read_text(), first)  # resume and compact keep the first start

    def test_an_unwritable_mark_prints_nothing(self):
        self.start_session(at=int(time.time()) - 5)
        self.commit("second")
        self.marks.chmod(0o500)
        try:
            self.assertEqual(self.run_hook(), "")
        finally:
            self.marks.chmod(0o700)
        self.assertRegex(self.mark.read_text(), r"\A[0-9]{1,12}\Z")

    def test_outside_a_repository_and_bad_input_print_nothing(self):
        self.start_session(at=int(time.time()) - 5)
        outside = self.repo.parent / "plain"
        outside.mkdir(mode=0o700)
        self.assertEqual(self.run_hook(cwd=outside), "")
        self.assertEqual(self.run_hook(session_id="../bad"), "")
        self.assertEqual(self.run_hook(cwd="relative/path"), "")
        result = subprocess.run([sys.executable, "-I", str(HOOK)], input=b"not json", capture_output=True,
                                timeout=10, env={"PATH": os.defpath})
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))

    def test_marks_stay_at_two_hundred_files_oldest_removed(self):
        self.private("state/proof-nudge")
        names = [hashlib.sha256(str(n).encode()).hexdigest()[:16] for n in range(200)]
        for age, name in enumerate(names):
            path = self.marks / name
            path.write_text("1")
            path.chmod(0o600)
            os.utime(path, (1_000_000 + age, 1_000_000 + age))
        self.start_session()
        left = set(os.listdir(self.marks))
        self.assertEqual(len(left), 200)
        self.assertIn(self.mark.name, left)
        self.assertNotIn(names[0], left)


if __name__ == "__main__":
    unittest.main()
