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


FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[0] == 'pr':
    data = json.loads(@PR@)
    data['baseRefOid'] = 'd' * 40
    print(json.dumps(data))
elif args[0] == 'api' and '/compare/' in args[1]:
    files = [{'filename': name, 'status': 'modified'} for name in os.environ['FAKE_FILES'].split(',')]
    print(json.dumps({'merge_base_commit': {'sha': 'c' * 40}, 'files': files}))
elif args[0] == 'api' and '/contents/' in args[-1]:
    print(json.dumps({'name': 'demo', 'version': '1' if 'c' * 40 in args[-1] else '2'}))
elif args[0] == 'api':
    who = args[1].split('/')[4]
    if who == 'owner':
        print('admin')
    elif who == 'broken':
        sys.stderr.write('HTTP 502: Bad Gateway'); sys.exit(1)
    else:
        sys.stderr.write('gh: Not Found (HTTP 404)'); sys.exit(1)
else:
    sys.exit(1)
"""


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
        base = '{"name": "demo", "version": "0.1.2", "author": {"name": "x"}}'
        texts = {"base": base, "head": base.replace("0.1.2", "0.1.3-dev")}
        read = lambda path, side: texts[side]
        ok = [{"filename": "CHANGELOG.md", "status": "modified"},
              {"filename": ".claude-plugin/plugin.json", "status": "modified"}]
        self.assertTrue(mc.lane_files(ok, read)[0])
        self.assertTrue(mc.lane_files(ok + [{"filename": "README.md", "status": "modified"}], read)[0])
        for bad in (
            {"filename": "CLAUDE.md", "status": "modified"},
            {"filename": "skills/x/SKILL.md", "status": "modified"},
            {"filename": "README.md", "status": "renamed", "previous_filename": "skills/x/SKILL.md"},
            {"filename": "CHANGELOG.md", "status": "renamed", "previous_filename": "skills/x/SKILL.md"},
            {"filename": "CHANGELOG.md", "status": "changed"},
            {"filename": "CHANGELOG.md", "status": "added"},
        ):
            self.assertFalse(mc.lane_files(ok + [bad], read)[0], bad)
        self.assertFalse(mc.lane_files([], read)[0])

    def test_a_manifest_qualifies_only_for_its_top_level_version(self):
        base = '{"name": "demo", "version": "0.1.2", "author": {"name": "x"}}'
        self.assertTrue(mc.version_only(base, base.replace("0.1.2", "0.1.3")))
        for head in (
            base.replace('"name": "x"', '"name": "x", "version": "9"'),   # nested version added
            base.replace('"name": "demo"', '"name": "demo", "hooks": "./h.json"'),
            base.replace('"version": "0.1.2", ', ''),                       # version removed
            base.replace('"version": "0.1.2"', '"version": "0.1.2", "version": "0.1.3"'),  # duplicate key
            "not json",
        ):
            self.assertFalse(mc.version_only(base, head), head)

    def test_cli_reads_gh_and_exits_by_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "gh"
            fake.write_text(FAKE_GH.replace("@PR@", json.dumps(json.dumps(pr()))))
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = {**os.environ, "PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}", "FAKE_FILES": "CHANGELOG.md"}
            result = subprocess.run([sys.executable, "-I", str(SCRIPT), "7", "--repo", "acme/demo"],
                                    capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MERGE OK", result.stdout)
        self.assertIn("repo acme/demo", result.stdout)

    def cli(self, data, *extra, files="CHANGELOG.md"):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "gh"
            fake.write_text(FAKE_GH.replace("@PR@", json.dumps(json.dumps(data))))
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = {**os.environ, "PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}", "FAKE_FILES": files}
            return subprocess.run([sys.executable, "-I", str(SCRIPT), "7", "--repo", "acme/demo", *extra],
                                  capture_output=True, text=True, env=env)

    def test_cli_lane_check(self):
        result = self.cli(pr(), "--lane", files="CHANGELOG.md,.claude-plugin/plugin.json")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"head {HEAD}", result.stdout)
        result = self.cli(pr(), "--lane", files="CHANGELOG.md,CLAUDE.md")
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_cli_permission_404_means_no_access_and_other_errors_are_unknown(self):
        stranger = pr(comments=[comment(marker("code", "APPROVE"), who="stranger"),
                                comment(marker("security", "APPROVE"))])
        self.assertEqual(self.cli(stranger).returncode, 1)
        broken = pr(comments=[comment(marker("code", "APPROVE"), who="broken"),
                              comment(marker("security", "APPROVE"))])
        result = self.cli(broken)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("permission lookup for broken failed", result.stdout)

    def test_compare_fails_closed(self):
        def fake(payload):
            mc.gh = lambda *args: json.dumps(payload)
        real = mc.gh
        try:
            for payload in ({"merge_base_commit": {"sha": "c" * 40}},
                            {"merge_base_commit": {"sha": "c" * 40},
                             "files": [{"filename": f"f{i}", "status": "modified"} for i in range(mc.COMPARE_CAP)]}):
                fake(payload)
                with self.assertRaises(mc.Unknown):
                    mc.compare("acme/demo", "b" * 40, HEAD)
            for payload in ({"files": []}, {"merge_base_commit": None, "files": []},
                            {"merge_base_commit": {"sha": "main"}, "files": []},
                            {"merge_base_commit": {"sha": "c" * 40}, "files": {}}):
                fake(payload)
                with self.assertRaises(mc.Unknown):
                    mc.compare("acme/demo", "b" * 40, HEAD)
            below = [{"filename": f"f{i}", "status": "modified"} for i in range(mc.COMPARE_CAP - 1)]
            fake({"merge_base_commit": {"sha": "c" * 40}, "files": below})
            self.assertEqual(mc.compare("acme/demo", "b" * 40, HEAD), (below, "c" * 40))
        finally:
            mc.gh = real

    def test_cli_requires_the_repository(self):
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "7"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "main", "--repo", "acme/demo"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
