"""Tests for skills/fnl-review-gate/scripts/merge_check.py."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills/fnl-review-gate/scripts/merge_check.py"
spec = importlib.util.spec_from_file_location("merge_check", SCRIPT)
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)

HEAD = "a" * 40
OLD = "b" * 40
WRITERS = {"owner", "bot-reviewer"}


def marker(kind, verdict, head=HEAD):
    return f"<!-- fnl-review kind={kind} head={head} verdict={verdict} -->"


def comment(body, who="owner", at="2026-11-02T01:00:00Z", edited=False):
    return {"author": {"login": who}, "body": body, "createdAt": at, "includesCreatedEdit": edited}


def review(state, who="owner", oid=HEAD, at="2026-11-02T02:00:00Z"):
    return {"author": {"login": who}, "state": state, "commit": {"oid": oid}, "submittedAt": at}


def pr(comments=None, reviews=None, author="owner", checks=None, merge_state="CLEAN"):
    if comments is None:
        comments = [comment(marker("code", "APPROVE") + "\nreport"),
                    comment(marker("security", "APPROVE") + "\nreport")]
    return {
        "state": "OPEN", "headRefOid": HEAD, "author": {"login": author},
        "comments": comments, "reviews": reviews or [],
        "statusCheckRollup": checks if checks is not None else [{"name": "validate", "conclusion": "SUCCESS"}],
        "mergeStateStatus": merge_state,
    }


def run(data):
    return mc.evaluate(data, lambda who: who in WRITERS)


class MergeCheckTest(unittest.TestCase):
    def assertBlocked(self, data, reason):
        ok, lines = run(data)
        self.assertFalse(ok, lines)
        self.assertTrue(any(line.startswith("BLOCK") and reason in line for line in lines), lines)

    def test_two_approvals_on_the_head_pass(self):
        ok, lines = run(pr())
        self.assertTrue(ok, lines)

    def test_a_verdict_for_an_older_head_is_stale(self):
        data = pr(comments=[comment(marker("code", "APPROVE", OLD)), comment(marker("security", "APPROVE"))])
        self.assertBlocked(data, "code review: no counted verdict")

    def test_a_later_rework_blocks(self):
        data = pr()
        data["comments"].append(comment(marker("security", "REWORK"), at="2026-11-02T03:00:00Z"))
        self.assertBlocked(data, "security review: latest verdict is REWORK")

    def test_a_newer_approve_replaces_a_rework(self):
        data = pr(comments=[comment(marker("code", "APPROVE")),
                            comment(marker("security", "REWORK"), at="2026-11-02T01:00:00Z"),
                            comment(marker("security", "APPROVE"), at="2026-11-02T04:00:00Z")])
        self.assertTrue(run(data)[0])

    def test_an_edited_verdict_does_not_count(self):
        data = pr(comments=[comment(marker("code", "APPROVE"), edited=True), comment(marker("security", "APPROVE"))])
        self.assertBlocked(data, "code review: no counted verdict")

    def test_a_marker_without_the_edit_flag_does_not_count(self):
        data = pr()
        del data["comments"][0]["includesCreatedEdit"]
        self.assertBlocked(data, "code review: no counted verdict")

    def test_a_quoted_marker_is_not_a_verdict(self):
        data = pr(comments=[comment("> " + marker("code", "APPROVE")),
                            comment("see\n" + marker("code", "APPROVE")),
                            comment(marker("security", "APPROVE"))])
        self.assertBlocked(data, "code review: no counted verdict")

    def test_a_marker_from_an_author_without_write_access_does_not_count(self):
        data = pr(comments=[comment(marker("code", "APPROVE"), who="stranger"),
                            comment(marker("security", "APPROVE"))])
        self.assertBlocked(data, "code review: no counted verdict")

    def test_an_outside_author_needs_an_owner_approval_on_the_head(self):
        self.assertBlocked(pr(author="stranger"), "no owner approved this head")
        self.assertTrue(run(pr(author="stranger", reviews=[review("APPROVED")]))[0])

    def test_an_owner_approval_of_an_older_commit_does_not_count(self):
        self.assertBlocked(pr(author="stranger", reviews=[review("APPROVED", oid=OLD)]),
                           "no owner approved this head")

    def test_a_comment_review_after_an_approval_keeps_the_approval(self):
        reviews = [review("APPROVED"), review("COMMENTED", at="2026-11-02T05:00:00Z")]
        self.assertTrue(run(pr(author="stranger", reviews=reviews))[0])

    def test_a_dismissed_approval_blocks(self):
        reviews = [review("APPROVED"), review("DISMISSED", at="2026-11-02T05:00:00Z")]
        self.assertBlocked(pr(author="stranger", reviews=reviews), "no owner approved this head")

    def test_changes_requested_by_another_owner_blocks(self):
        reviews = [review("APPROVED"), review("CHANGES_REQUESTED", who="bot-reviewer")]
        self.assertBlocked(pr(author="stranger", reviews=reviews), "no owner approved this head")

    def test_the_authors_own_approval_does_not_count(self):
        data = pr(author="stranger", reviews=[review("APPROVED", who="stranger")])
        self.assertBlocked(data, "no owner approved this head")

    def test_failing_or_pending_checks_block(self):
        self.assertBlocked(pr(checks=[{"name": "validate", "conclusion": "FAILURE"}]), "validate=FAILURE")
        self.assertBlocked(pr(checks=[{"name": "validate", "conclusion": "", "status": "IN_PROGRESS"}]),
                           "validate=IN_PROGRESS")

    def test_a_branch_behind_its_base_blocks(self):
        self.assertBlocked(pr(merge_state="BEHIND"), "merge state: BEHIND")

    def test_a_closed_pull_request_is_unknown(self):
        data = pr()
        data["state"] = "MERGED"
        with self.assertRaises(mc.Unknown):
            run(data)

    def test_on_a_tie_the_rework_wins(self):
        data = pr(comments=[comment(marker("code", "APPROVE")),
                            comment(marker("security", "APPROVE"), at="2026-11-02T01:00:00Z"),
                            comment(marker("security", "REWORK"), at="2026-11-02T01:00:00Z")])
        self.assertBlocked(data, "security review: latest verdict is REWORK")

    def test_a_failed_permission_lookup_is_unknown(self):
        def can_write(who):
            raise mc.Unknown("lookup failed")
        with self.assertRaises(mc.Unknown):
            mc.evaluate(pr(), can_write)

    def test_an_uncomputed_merge_state_is_unknown(self):
        for state in ("UNKNOWN", None):
            with self.assertRaises(mc.Unknown):
                run(pr(merge_state=state))

    def test_no_reported_checks_block(self):
        self.assertBlocked(pr(checks=[]), "checks: none reported")

    def test_a_status_context_counts_by_its_state(self):
        self.assertTrue(run(pr(checks=[{"context": "ci/legacy", "state": "SUCCESS"}]))[0])
        self.assertBlocked(pr(checks=[{"context": "ci/legacy", "state": "PENDING"}]), "ci/legacy=PENDING")

    def test_a_full_page_of_comments_is_unknown(self):
        data = pr()
        data["comments"] += [comment("note")] * mc.PAGE
        with self.assertRaises(mc.Unknown):
            run(data)

    def test_a_lane_verdict_needs_a_lane_pull_request(self):
        data = pr(comments=[comment(marker("code", "APPROVE")),
                            comment(marker("security", "APPROVE").replace(" -->", " lane=yes -->"))])
        self.assertTrue(mc.evaluate(data, lambda who: who in WRITERS, lambda: (True, []))[0])
        ok, lines = mc.evaluate(data, lambda who: who in WRITERS, lambda: (False, ["README.md: outside the lane"]))
        self.assertFalse(ok)
        self.assertTrue(any("took the low-risk lane" in line for line in lines), lines)
        self.assertFalse(mc.evaluate(data, lambda who: who in WRITERS)[0])

    def test_lane_files(self):
        version = '@@ -1 +1 @@\n-  "version": "0.1.2",\n+  "version": "0.1.3-dev",'
        ok = [{"filename": "CHANGELOG.md", "status": "modified", "patch": "@@\n+- x"},
              {"filename": ".claude-plugin/plugin.json", "status": "modified", "patch": version}]
        self.assertTrue(mc.lane_files(ok)[0])
        for bad in (
            {"filename": "README.md", "status": "modified", "patch": "+x"},
            {"filename": "CHANGELOG.md", "status": "renamed", "previous_filename": "skills/x/SKILL.md"},
            {"filename": "CHANGELOG.md", "status": "changed"},
            {"filename": "CHANGELOG.md", "status": "added"},
            {"filename": ".claude-plugin/plugin.json", "status": "modified",
             "patch": version + '\n+  "hooks": "./evil.json",'},
            {"filename": ".claude-plugin/plugin.json", "status": "modified"},
        ):
            self.assertFalse(mc.lane_files(ok + [bad])[0], bad)
        self.assertFalse(mc.lane_files([])[0])

    def test_cli_reads_gh_and_exits_by_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "gh"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "args = sys.argv[1:]\n"
                "if args[0] == 'pr':\n"
                f"    print({json.dumps(json.dumps(pr()))})\n"
                "elif args[0] == 'api':\n"
                "    if '/owner/' not in args[1]:\n"
                "        sys.stderr.write('HTTP 404: Not Found'); sys.exit(1)\n"
                "    print('admin')\n"
                "else:\n"
                "    sys.exit(1)\n"
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = {**os.environ, "PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}"}
            result = subprocess.run([sys.executable, "-I", str(SCRIPT), "7", "--repo", "acme/demo"],
                                    capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MERGE OK", result.stdout)
        self.assertIn("repo acme/demo", result.stdout)

    def test_cli_requires_the_repository(self):
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "7"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "main", "--repo", "acme/demo"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
