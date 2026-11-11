"""Tests for skills/fnl-review-gate/scripts/merge_check.py."""

import base64
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


def pr(comments=None, reviews=None, author="owner", checks=None, merge_state="CLEAN", body=""):
    if comments is None:
        comments = [comment(marker("code", "APPROVE") + "\nreport"),
                    comment(marker("security", "APPROVE") + "\nreport")]
    return {
        "state": "OPEN", "headRefOid": HEAD, "author": {"login": author},
        "comments": comments, "reviews": reviews or [],
        "statusCheckRollup": checks if checks is not None else [{"name": "validate", "conclusion": "SUCCESS"}],
        "mergeStateStatus": merge_state, "body": body,
    }


def run(data):
    return mc.evaluate(data, lambda who: who in WRITERS, adopted=False)


BASE = "d" * 40
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[0] == 'pr':
    data = json.loads(@PR@)
    data['baseRefOid'] = os.environ.get('FAKE_BASE', 'd' * 40)
    print(json.dumps(data))
elif args[0] == 'api' and '/compare/' in args[1]:
    files = [{'filename': name, 'status': 'modified'} for name in os.environ['FAKE_FILES'].split(',')]
    print(json.dumps({'merge_base_commit': {'sha': 'c' * 40}, 'files': files}))
elif args[0] == 'api' and '/contents/' in args[-1]:
    endpoint = args[-1]
    if len(args) > 2:  # the low-risk lane reads raw manifest content
        print(json.dumps({'name': 'demo', 'version': '1' if 'c' * 40 in endpoint else '2'}))
    else:
        entries = json.loads(@CONTENTS@)
        entry = entries.get(endpoint, {'error': 'gh: Not Found (HTTP 404)'})
        if isinstance(entry, dict) and 'error' in entry:
            sys.stderr.write(entry['error']); sys.exit(1)
        print(json.dumps(entry))
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


ADOPTED = "# Demo\n\n## Agent skills\n\nPull requests follow `fnl-review-gate`.\n"
ROUTED = "Summary\n<!-- fnl-router depth=NORMAL trigger=none -->\n"


def contents_file(content):
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    return {"type": "file", "size": len(raw), "encoding": "base64",
            "content": base64.encodebytes(raw).decode("ascii")}


def run_cli(data, *extra, files="CHANGELOG.md", base_files=None, base=None, head_files=None, cwd=None):
    """Serve base/head contents through fake gh; run without creating any git repository.

    Strings/bytes become file responses, dictionaries model API responses or errors,
    and an absent key (or None) serves a clean 404.
    """
    contents = {}
    for ref, entries in ((BASE, base_files or {}), (HEAD, head_files or {})):
        for path, content in entries.items():
            if content is not None:
                contents[f"repos/acme/demo/contents/{path}?ref={ref}"] = (
                    contents_file(content) if isinstance(content, (str, bytes)) else content)
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text(FAKE_GH.replace("#!/usr/bin/env python3", "#!" + sys.executable).replace("@PR@", json.dumps(json.dumps(data)))
                        .replace("@CONTENTS@", json.dumps(json.dumps(contents))))
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        env = {"PATH": f"{bin_dir}{os.pathsep}{os.defpath}", "FAKE_FILES": files,
               "FAKE_BASE": BASE if base is None else base, "GIT_CEILING_DIRECTORIES": tmp}
        return subprocess.run([sys.executable, "-I", str(SCRIPT), "7", "--repo", "acme/demo", *extra],
                              capture_output=True, text=True, env=env, cwd=cwd or tmp)


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
            mc.evaluate(pr(), can_write, adopted=False)

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
        self.assertTrue(mc.evaluate(data, lambda who: who in WRITERS, lambda: (True, []), adopted=False)[0])
        ok, lines = mc.evaluate(data, lambda who: who in WRITERS, lambda: (False, ["README.md: outside the lane"]), adopted=False)
        self.assertFalse(ok)
        self.assertTrue(any("took the low-risk lane" in line for line in lines), lines)
        self.assertFalse(mc.evaluate(data, lambda who: who in WRITERS, adopted=False)[0])

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
            {"filename": "docs/README.md", "status": "modified"},
            {"filename": "readme.md", "status": "modified"},
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
        result = self.cli(pr())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MERGE OK", result.stdout)
        self.assertIn("repo acme/demo", result.stdout)

    def cli(self, data, *extra, **kwargs):
        """Run the CLI with fake gh contents, without a local clone."""
        return run_cli(data, *extra, **kwargs)

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


class RouterMarkerTest(unittest.TestCase):
    """Part K3: the router marker, required only when the base commit adopted the gate."""

    def adopted(self, data, lane_ok=None):
        return mc.evaluate(data, lambda who: who in WRITERS, lane_ok, adopted=True)

    def assertMarkerBlocks(self, result):
        ok, lines = result
        self.assertFalse(ok, lines)
        self.assertTrue(any(line.startswith("BLOCK router marker") for line in lines), lines)

    def test_adopts_reads_only_the_agent_skills_section(self):
        self.assertTrue(mc.adopts(ADOPTED))
        self.assertTrue(mc.adopts("## Agent skills\n- fnl-review-gate\n## Other\n"))
        self.assertTrue(mc.adopts("## Agent skills\n```sh\n# a shell comment\n```\nfnl-review-gate\n"))
        for text in ("", "fnl-review-gate\n", "## Reviews\nfnl-review-gate\n",
                     "## Agent skills\n## Reviews\nfnl-review-gate\n",
                     "## Agent skills\n# Other\nfnl-review-gate\n",
                     "## Agent skills\nfnl-review-gates\n", "## Agent skills\nmy-fnl-review-gate\n",
                     "### Agent skills\nfnl-review-gate\n", "## Agent skills extra\nfnl-review-gate\n"):
            self.assertFalse(mc.adopts(text), text)

    def test_a_valid_marker_passes_when_adopted(self):
        for depth in mc.DEPTHS:
            for trigger in mc.TRIGGERS:
                body = f"text\r\n<!-- fnl-router depth={depth} trigger={trigger} -->\r\n"
                ok, lines = self.adopted(pr(body=body))
                self.assertTrue(ok, lines)
                self.assertIn(f"ok    router marker: depth={depth} trigger={trigger}", lines)

    def test_the_values_match_the_router_receipt(self):
        path = SCRIPT.parents[2] / "fnl-delegate/scripts/record.py"
        record_spec = importlib.util.spec_from_file_location("record_for_merge_check", path)
        record = importlib.util.module_from_spec(record_spec)
        record_spec.loader.exec_module(record)
        self.assertEqual(mc.DEPTHS, record.DEPTHS)
        self.assertEqual(mc.TRIGGERS, record.TRIGGERS)

    def test_a_missing_or_malformed_marker_blocks_when_adopted(self):
        for body in ("", "no marker here",
                     " <!-- fnl-router depth=MIN trigger=none -->",
                     "<!-- fnl-router depth=MIN trigger=none --> trailing",
                     "> <!-- fnl-router depth=MIN trigger=none -->",
                     "<!-- fnl-router depth=min trigger=none -->",
                     "<!-- fnl-router depth=SHALLOW trigger=none -->",
                     "<!-- fnl-router depth=MIN trigger=other -->",
                     "<!-- fnl-router depth=MIN -->",
                     "<!-- fnl-router  depth=MIN trigger=none -->",
                     "<!-- fnl-router depth=MIN trigger=none -->\n<!-- fnl-router depth=MIN trigger=nonee -->",
                     "<!-- fnl-router depth=MIN trigger=none -->\n<!-- fnl-router depth=DEEP trigger=security -->"):
            with self.subTest(body=body):
                self.assertMarkerBlocks(self.adopted(pr(body=body)))

    def test_prose_mentioning_the_marker_name_is_not_malformed(self):
        ok, lines = self.adopted(pr(body="About the fnl-router marker.\n" + ROUTED))
        self.assertTrue(ok, lines)

    def test_block_lines_never_echo_the_body(self):
        body = "<!-- fnl-router depth=MIN trigger=SECRET-TEXT -->"
        ok, lines = self.adopted(pr(body=body))
        self.assertFalse(ok)
        self.assertFalse(any("SECRET-TEXT" in line for line in lines), lines)

    def test_the_marker_is_not_required_without_adoption(self):
        ok, lines = run(pr(body=""))
        self.assertTrue(ok, lines)
        self.assertFalse(any("router marker" in line for line in lines), lines)

    def test_an_unreadable_body_is_unknown_when_adopted(self):
        data = pr()
        for body in (None, 7, ["x"]):
            data["body"] = body
            with self.assertRaises(mc.Unknown):
                self.adopted(data)
        del data["body"]
        with self.assertRaises(mc.Unknown):
            self.adopted(data)

    def test_the_marker_never_relaxes_the_review_markers(self):
        # depth=MIN on a change that hits a security trigger still needs the security marker.
        only_code = [comment(marker("code", "APPROVE"))]
        for body in ("<!-- fnl-router depth=MIN trigger=security -->", "<!-- fnl-router depth=MIN trigger=none -->"):
            ok, lines = self.adopted(pr(comments=only_code, body=body))
            self.assertFalse(ok)
            self.assertIn("BLOCK security review: no counted verdict for this head", lines)
        # Nor the lane: a lane verdict on a pull request outside the lane still blocks.
        lane = [comment(marker("code", "APPROVE")),
                comment(marker("security", "APPROVE").replace(" -->", " lane=yes -->"))]
        ok, lines = self.adopted(pr(comments=lane, body="<!-- fnl-router depth=MIN trigger=none -->"),
                                 lambda: (False, ["skills/x/SKILL.md: outside the lane"]))
        self.assertFalse(ok)
        self.assertTrue(any("took the low-risk lane" in line for line in lines), lines)
        # Nor an outside author's need for an owner approval.
        self.assertFalse(self.adopted(pr(author="stranger", body=ROUTED))[0])

    def test_a_lane_or_bot_pull_request_still_needs_the_marker(self):
        lane = [comment(marker("code", "APPROVE")),
                comment(marker("security", "APPROVE").replace(" -->", " lane=yes -->"))]
        self.assertMarkerBlocks(self.adopted(pr(comments=lane), lambda: (True, [])))
        self.assertTrue(self.adopted(pr(comments=lane, body=ROUTED), lambda: (True, []))[0])
        bot = pr(author="dependabot[bot]", reviews=[review("APPROVED")])
        self.assertMarkerBlocks(self.adopted(bot))
        bot["body"] = ROUTED
        self.assertTrue(self.adopted(bot)[0])

    # The command line: adoption read from the base commit through the contents API.

    def test_cli_adopted_base_blocks_a_missing_marker(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            with self.subTest(name=name):
                result = run_cli(pr(), base_files={name: ADOPTED})
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("BLOCK router marker: missing", result.stdout)
                result = run_cli(pr(body=ROUTED), base_files={name: ADOPTED})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("ok    router marker: depth=NORMAL trigger=none", result.stdout)

    def test_cli_missing_files_mean_not_adopted(self):
        for files in ({"README.md": "x\n"}, {"CLAUDE.md": "# Demo\n## Reviews\nfnl-review-gate\n"}):
            result = run_cli(pr(), base_files=files)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("router marker", result.stdout)

    def test_cli_a_head_that_adds_or_removes_adoption_does_not_count(self):
        result = run_cli(pr(), base_files={"README.md": "x\n"}, head_files={"CLAUDE.md": ADOPTED})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("router marker", result.stdout)
        for head in ({"CLAUDE.md": None}, {"CLAUDE.md": "# Demo\n"}):
            result = run_cli(pr(), base_files={"CLAUDE.md": ADOPTED}, head_files=head)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("BLOCK router marker: missing", result.stdout)

    def test_cli_unreadable_adoption_or_body_is_unknown(self):
        for base in ("main", "", "d" * 39, "d" * 41, "d" * 39 + "g"):
            with self.subTest(base=base):
                result = run_cli(pr(body=ROUTED), base=base)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("UNKNOWN the pull request has no base commit", result.stdout)
        for entry in ({"type": "dir"}, {"type": "submodule"}, {"type": "other"}, []):
            with self.subTest(entry=entry):
                result = run_cli(pr(body=ROUTED), base_files={"CLAUDE.md": entry})
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("CLAUDE.md at the base commit is not a regular file", result.stdout)
        result = run_cli(pr(body=ROUTED), base_files={"AGENTS.md": b"## Agent skills\n\xff\n"})
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("AGENTS.md at the base commit is not UTF-8", result.stdout)
        for body in (None, 7, ["x"]):
            result = run_cli(pr(body=body))  # unreadable even without adoption
            self.assertEqual(result.returncode, 2, result.stdout)
        data = pr(body=ROUTED)
        del data["body"]
        result = run_cli(data)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("UNKNOWN the pull request body could not be read", result.stdout)

    def test_cli_clean_404_is_absent_but_other_errors_are_unknown(self):
        result = run_cli(pr(), base_files={"CLAUDE.md": {"error": "gh: Not Found (HTTP 404)"}})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("router marker", result.stdout)
        for error in ("gh: Forbidden (HTTP 403)", "gh: Bad Gateway (HTTP 502)", "404 without HTTP status"):
            with self.subTest(error=error):
                # Read both files even when the first already adopts the gate.
                result = run_cli(pr(body=ROUTED), base_files={
                    "CLAUDE.md": ADOPTED, "AGENTS.md": {"error": error}})
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("UNKNOWN AGENTS.md at the base commit could not be read", result.stdout)

    def test_cli_invalid_file_content_is_unknown(self):
        valid = contents_file(ADOPTED)
        for changes in ({"size": 256 * 1024 + 1}, {"size": -1}, {"size": True},
                        {"size": "10"}, {"encoding": "none"}, {"content": "!!!"},
                        {"content": None}, {"size": 0}):
            with self.subTest(changes=changes):
                result = run_cli(pr(body=ROUTED), base_files={"CLAUDE.md": {**valid, **changes}})
                self.assertEqual(result.returncode, 2, result.stdout)
        result = run_cli(pr(body=ROUTED), base_files={"CLAUDE.md": "x" * (256 * 1024)})
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_size_cap_is_checked_before_decoding(self):
        payload = {"type": "file", "size": 256 * 1024 + 1, "encoding": "base64", "content": ""}
        response = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        with patch.object(mc, "run_gh", return_value=response), patch.object(mc.base64, "b64decode") as decode:
            with self.assertRaises(mc.Unknown):
                mc.adopted_at("acme/demo", BASE)
            decode.assert_not_called()

    def test_cli_a_link_to_the_other_adoption_file_counts_through_its_target(self):
        for name, target in (("CLAUDE.md", "AGENTS.md"), ("AGENTS.md", "CLAUDE.md")):
            with self.subTest(name=name):
                files = {name: {"type": "symlink", "target": target}, target: ADOPTED}
                result = run_cli(pr(body=ROUTED), base_files=files)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = run_cli(pr(), base_files=files)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("BLOCK router marker: missing", result.stdout)

    def test_cli_a_link_to_anything_else_is_unknown(self):
        for target in ("docs/NOTES.md", "./AGENTS.md", "AGENTS.md\n", "CLAUDE.md", None):
            with self.subTest(target=target):
                result = run_cli(pr(body=ROUTED), base_files={
                    "CLAUDE.md": {"type": "symlink", "target": target}, "AGENTS.md": ADOPTED})
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("CLAUDE.md at the base commit is not a regular file", result.stdout)

    def test_cli_runs_from_an_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as unrelated:
            for files in ({}, {"CLAUDE.md": ADOPTED}):
                result = run_cli(pr(body=ROUTED), base_files=files, cwd=unrelated)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_unadopted_output_is_byte_identical(self):
        result = run_cli(pr())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.encode(), (
            "repo acme/demo pull request #7\n"
            f"head {HEAD}\n"
            "ok    code review: APPROVE (2026-11-02T01:00:00Z)\n"
            "ok    security review: APPROVE (2026-11-02T01:00:00Z)\n"
            "ok    author has write access\n"
            "ok    checks: all passed\n"
            "MERGE OK: merge pinned to the head above\n").encode())
        self.assertEqual(result.stderr, "")

    def test_two_identical_marker_lines_block(self):
        body = ROUTED + ROUTED
        self.assertMarkerBlocks(self.adopted(pr(body=body)))
        result = run_cli(pr(body=body), base_files={"CLAUDE.md": ADOPTED})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("BLOCK router marker", result.stdout)

    def test_evaluate_requires_an_explicit_adoption_decision(self):
        with self.assertRaises(TypeError):
            mc.evaluate(pr(), lambda who: True)

    def test_the_lane_check_does_not_read_adoption(self):
        result = run_cli(pr(), "--lane", base_files={"CLAUDE.md": {"error": "gh: Forbidden (HTTP 403)"}})
        self.assertEqual(result.returncode, 0, result.stdout)


class IndependentMergeTest(unittest.TestCase):
    def evaluate(self, families, data=None):
        return mc.evaluate(data or pr(), lambda who: who in WRITERS, adopted=False,
                           independent=True, families=families)

    def test_both_other_family_markers_pass_even_with_shared_login(self):
        for author, reviewer in (("claude", "codex"), ("codex", "antigravity"), ("antigravity", "claude")):
            with self.subTest(author=author, reviewer=reviewer):
                ok, lines = self.evaluate(dict(author=author, code=reviewer, security=reviewer))
                self.assertTrue(ok, lines)

    def test_either_same_family_marker_refuses(self):
        for code, security in (("codex", "codex"), ("codex", "claude"), ("claude", "codex")):
            ok, lines = self.evaluate(dict(author="codex", code=code, security=security))
            self.assertFalse(ok)
            self.assertTrue(any("same family" in line for line in lines), lines)

    def test_unknown_family_refuses_and_normal_gate_is_unchanged(self):
        for families in (None, {}, dict(author="codex", code="claude"),
                         dict(author="unknown", code="claude", security="claude")):
            self.assertFalse(self.evaluate(families)[0])
        self.assertTrue(run(pr())[0])

    def test_independence_never_replaces_current_head_reviews_or_checks(self):
        families = dict(author="codex", code="claude", security="claude")
        self.assertFalse(self.evaluate(families, pr(comments=[]))[0])
        self.assertFalse(self.evaluate(families, pr(checks=[]))[0])
        self.assertFalse(self.evaluate(families, pr(comments=[comment(marker("code", "APPROVE", OLD)),
                                                            comment(marker("security", "APPROVE"))]))[0])

    def test_cli_flag_prints_no_merge_ok_on_same_or_unknown_family(self):
        import contextlib
        import io
        for families, status in ((None, 1), (dict(author="codex", code="codex", security="codex"), 1),
                                 (dict(author="codex", code="claude", security="claude"), 0)):
            output = io.StringIO()
            with patch.object(mc, "gh", return_value=json.dumps(pr())), \
                 patch.object(mc, "adopted_at", return_value=False), \
                 patch.object(mc, "permission", return_value=True), \
                 patch.object(mc, "independent_families", return_value=families), \
                 contextlib.redirect_stdout(output):
                actual = mc.main(["7", "--repo", "acme/demo", "--independent"])
            self.assertEqual(actual, status, output.getvalue())
            self.assertEqual("MERGE OK" in output.getvalue(), status == 0)

    def test_resolver_uses_head_bound_author_and_the_families_routing_would_pick(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import review_route
        import review_config
        import quota_probe
        status = patch.object(quota_probe, "status_lines", return_value=[])  # never the machine's real quota cache
        status.start()
        self.addCleanup(status.stop)
        with patch.object(review_route, "author_family", return_value="codex") as author, \
             patch.object(review_config, "host_text", return_value="synthetic"), \
             patch.object(review_config, "present_families", return_value={"claude", "codex", "antigravity"}), \
             patch.object(review_config, "read_roles", return_value={"code review": "claude", "security review": "antigravity"}), \
             patch.object(review_config, "read_posting", return_value={}):
            data = dict(pr(), baseRefOid=BASE)
            self.assertEqual(mc.independent_families(data), dict(author="codex", code="claude", security="antigravity"))
            self.assertEqual(author.call_args.kwargs, dict(base=BASE, head=HEAD))
        with patch.object(review_route, "author_family", return_value="codex"), \
             patch.object(review_config, "host_text", return_value="synthetic"), \
             patch.object(review_config, "present_families", return_value={"claude", "codex"}), \
             patch.object(review_config, "read_roles", return_value={"code review": "codex", "security review": "codex"}), \
             patch.object(review_config, "read_posting", return_value={}):
            # Roles that name the author's own family fall back to another present family, as routing does.
            self.assertEqual(mc.independent_families(data), dict(author="codex", code="claude", security="claude"))
        with patch.object(review_route, "author_family", return_value="codex"), \
             patch.object(review_config, "host_text", return_value="synthetic"), \
             patch.object(review_config, "present_families", return_value={"codex"}), \
             patch.object(review_config, "read_roles", return_value={}), \
             patch.object(review_config, "read_posting", return_value={}):
            # With no other family present the pick is the author's own, so the independent check refuses it.
            self.assertEqual(mc.independent_families(data), dict(author="codex", code="codex", security="codex"))
        import quota_probe
        with patch.object(review_route, "author_family", return_value="claude"), \
             patch.object(review_config, "host_text", return_value="synthetic"), \
             patch.object(review_config, "present_families", return_value={"claude", "codex"}), \
             patch.object(review_config, "read_roles", return_value={"code review": "codex", "security review": "codex"}), \
             patch.object(review_config, "read_posting", return_value={}), \
             patch.object(quota_probe, "status_lines", return_value=["synthetic"]), \
             patch.object(review_route, "blocked_families", return_value={"codex"}):
            # A rate-limited assigned family changes the route exactly as review_route does: the author's own family.
            self.assertEqual(mc.independent_families(data), dict(author="claude", code="claude", security="claude"))
        with patch.object(review_route, "author_family", side_effect=ValueError("unverified ledger author")):
            self.assertIsNone(mc.independent_families(data))
        with patch.object(review_route, "author_family", return_value="codex"), \
             patch.object(review_config, "host_text", return_value=""):
            self.assertIsNone(mc.independent_families(data))
        for matrix in ("## Assignment matrix\n- Consent: no\n- Judge: host\n- claude: levels 1-5; roles code-review\n",
                       "## Assignment matrix\n- Consent: yes (2026-11-09)\n- Judge: host\n- gemini: levels 1-5\n",
                       "## Assignment matrix\n- Consent: yes (2026-11-09)\n- Judge: host\n- claude: levels 1-5; roles code-review\n"):
            with self.subTest(matrix=matrix[-30:]), patch.object(review_route, "author_family", return_value="codex"), \
                    patch.object(review_config, "host_text", return_value=matrix), \
                    patch.object(review_config, "present_families", return_value={"claude", "codex", "antigravity"}), \
                    patch.object(quota_probe, "status_lines", return_value=[]):
                self.assertIsNone(mc.independent_families(data))


class LocalReceiptTest(unittest.TestCase):
    """The local receipt stands in for hosted checks only when the mode is on and repository, head and digest match."""

    def setUp(self):
        from tests.data_root_fixture import account
        root = Path(__file__).resolve().parent.parent
        scratch = root / ".finolabs/tmp"  # git-ignored; keeps test files inside the checkout
        scratch.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temp.cleanup)
        base = Path(temp.name).resolve()
        self.home = account(self, base / "home")
        env = patch.dict(os.environ, {"HOME": str(self.home)}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.host = self.home / ".finolabs/vibecode/host.md"
        self.host.parent.mkdir(parents=True, exist_ok=True)
        self.base = base
        self.repo = self.init(base / "repo", "https://github.com/acme/demo.git")
        cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, cwd)
        scripts = root / "skills/fnl-review-gate/scripts"
        for name in ("checks_list", "project_progress"):
            loaded = importlib.util.spec_from_file_location(name + "_for_receipt", scripts / (name + ".py"))
            module = importlib.util.module_from_spec(loaded)
            loaded.loader.exec_module(module)
            setattr(self, {"checks_list": "cl", "project_progress": "project"}[name], module)
        self.code = self.project.repository_code(self.repo)
        self.checks = [("lint", ["make", "lint"]), ("test", ["make", "test"])]
        self.store(self.checks, receipt=True)

    def git(self, folder, *argv):
        env = {"HOME": str(self.home), "PATH": os.defpath + ":/usr/local/bin:/opt/homebrew/bin",
               "GIT_CONFIG_NOSYSTEM": "1"}
        return subprocess.run(["git", *argv], cwd=folder, env=env, capture_output=True, text=True,
                              check=True).stdout.strip()

    def init(self, folder, origin=None):
        folder.mkdir(parents=True)
        self.git(folder, "init", "-q", "-b", "main")
        self.git(folder, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.com",
                 "commit", "-q", "--allow-empty", "-m", "Start")
        if origin:
            self.git(folder, "remote", "add", "origin", origin)
        return folder

    def store(self, checks, receipt, code=None):
        code = code or self.code
        lines = "".join("- %s: %s = %s\n" % (code, name, json.dumps(argv, separators=(",", ":")))
                        for name, argv in checks)
        self.host.write_text("# Host\n\n## Checks\n\n" + lines + ("- %s: local-receipt = on\n" % code if receipt else ""))

    def receipt(self, head=HEAD, checks=None, code=None):
        record = self.cl.write_receipt(self.code, head, self.cl.list_digest(checks or self.checks))
        if code:
            path = self.home / ".finolabs/vibecode/state/checks-receipts" / (self.code + ".json")
            path.write_text(json.dumps(dict(record, code=code)))

    def evaluate(self, data, repo="acme/demo"):
        return mc.evaluate(data, lambda who: who in WRITERS, adopted=False, local_receipt=mc.local_receipt, repo=repo)

    def checks_line(self, lines):
        return next(line for line in lines if "checks:" in line)

    def test_a_matching_receipt_stands_in_for_missing_or_failing_hosted_checks(self):
        self.receipt()
        for rollup in ([], [{"name": "validate", "conclusion": "FAILURE"}]):
            with self.subTest(rollup=rollup):
                ok, lines = self.evaluate(pr(checks=rollup))
                self.assertTrue(ok, lines)
                self.assertEqual(self.checks_line(lines), f"ok    checks: local receipt ({HEAD[:12]})")

    def test_each_mismatch_blocks_as_today_and_says_which(self):
        cases = {
            "another head": dict(head=OLD),
            "another check list": dict(checks=[("lint", ["make", "lint"])]),
            "another repository": dict(code="0" * 8 if self.code != "0" * 8 else "1" * 8),
        }
        for reason, args in cases.items():
            with self.subTest(reason):
                self.receipt(**args)
                ok, lines = self.evaluate(pr(checks=[]))
                self.assertFalse(ok)
                self.assertEqual(self.checks_line(lines),
                                 f"BLOCK checks: none reported; local receipt: local receipt is for {reason}")

    def test_no_or_an_invalid_receipt_blocks(self):
        ok, lines = self.evaluate(pr(checks=[]))
        self.assertFalse(ok)
        self.assertEqual(self.checks_line(lines), "BLOCK checks: none reported; local receipt: no local receipt")
        self.receipt()
        path = self.home / ".finolabs/vibecode/state/checks-receipts" / (self.code + ".json")
        path.write_text('{"kind": "checks"}')
        ok, lines = self.evaluate(pr(checks=[]))
        self.assertFalse(ok)
        self.assertIn("local receipt unreadable or invalid", self.checks_line(lines))

    def test_with_the_mode_off_nothing_changes(self):
        self.receipt()
        self.store(self.checks, receipt=False)
        ok, lines = self.evaluate(pr(checks=[]))
        self.assertFalse(ok)
        self.assertEqual(self.checks_line(lines), "BLOCK checks: none reported")
        self.assertEqual(lines, run(pr(checks=[]))[1])

    def test_an_invalid_section_is_mode_off(self):
        self.receipt()
        self.host.write_text(self.host.read_text() + "- %s: test = [\"sh\",\"-c\",\"x\"]\n" % self.code)
        ok, lines = self.evaluate(pr(checks=[]))
        self.assertFalse(ok)
        self.assertEqual(self.checks_line(lines), "BLOCK checks: none reported")

    def store_file(self, checks, receipt, approve=True):
        import hashlib
        raw = self.cl.render_project([[name, argv] for name, argv in checks], receipt)
        folder = self.repo / ".finolabs/vibecode"
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        (folder / "checks.json").write_bytes(raw)
        os.chmod(folder / "checks.json", 0o600)
        if approve:
            self.cl.write_approved(self.code, hashlib.sha256(raw).hexdigest())

    def test_the_receipt_mode_and_list_come_from_the_project_file(self):
        self.store([("other", ["make", "other"])], receipt=False)
        self.store_file(self.checks, receipt=True)
        self.receipt()
        ok, lines = self.evaluate(pr(checks=[]))
        self.assertTrue(ok, lines)
        self.assertEqual(self.checks_line(lines), f"ok    checks: local receipt ({HEAD[:12]})")

    def test_an_unapproved_project_file_is_mode_off(self):
        self.store_file(self.checks, receipt=True, approve=False)
        self.receipt()
        ok, lines = self.evaluate(pr(checks=[]))
        self.assertFalse(ok)
        self.assertEqual(self.checks_line(lines), "BLOCK checks: none reported")

    def test_passing_hosted_checks_ignore_the_receipt(self):
        def never(head, repo):
            raise AssertionError("receipt read while hosted checks pass")
        ok, lines = mc.evaluate(pr(), lambda who: who in WRITERS, adopted=False, local_receipt=never, repo="acme/demo")
        self.assertTrue(ok, lines)
        self.assertEqual(self.checks_line(lines), "ok    checks: all passed")

    def test_running_hosted_checks_are_never_replaced_by_the_receipt(self):
        self.receipt()
        def never(head, repo):
            raise AssertionError("receipt read while hosted checks are running")
        for check in ({"name": "validate", "status": "IN_PROGRESS", "conclusion": None},
                      {"name": "validate", "status": "QUEUED", "conclusion": ""},
                      {"context": "legacy", "state": "PENDING"}):
            with self.subTest(check=check):
                ok, lines = mc.evaluate(pr(checks=[check]), lambda who: who in WRITERS, adopted=False,
                                        local_receipt=never, repo="acme/demo")
                self.assertFalse(ok)
                self.assertTrue(self.checks_line(lines).startswith("BLOCK checks: "), lines)
                self.assertTrue(self.checks_line(lines).endswith(
                    "; local receipt: not used while hosted checks are still running"), lines)

    def test_outside_a_repository_the_mode_is_off(self):
        os.chdir(self.home)
        self.receipt()
        self.assertIsNone(mc.local_receipt(HEAD, "acme/demo"))

    # The receipt is bound to the repository the merge check targets

    def test_another_repository_sharing_the_head_is_not_satisfied_by_this_receipt(self):
        other = self.init(self.base / "other", "https://github.com/acme/other.git")
        self.assertNotEqual(self.project.repository_code(other), self.code)
        self.receipt()  # mode on, list and receipt for repository A (acme/demo) only
        ok, lines = self.evaluate(pr(checks=[]), repo="acme/other")  # run from A against B
        self.assertFalse(ok)
        self.assertEqual(self.checks_line(lines),
                         "BLOCK checks: none reported; local receipt: checkout is not acme/other")

    def test_a_linked_worktree_of_the_same_repository_matches(self):
        linked = self.base / "linked"
        self.git(self.repo, "worktree", "add", "-q", "--detach", str(linked))
        self.assertEqual(self.project.repository_code(linked), self.code)
        self.receipt()
        os.chdir(linked)
        ok, lines = self.evaluate(pr(checks=[]), repo="ACME/Demo")
        self.assertTrue(ok, lines)
        self.assertEqual(self.checks_line(lines), f"ok    checks: local receipt ({HEAD[:12]})")

    def test_each_github_remote_form_is_parsed(self):
        forms = ("https://github.com/acme/demo", "https://github.com/acme/demo.git", "https://github.com/acme/demo/",
                 "git" "@github.com:acme/demo.git", "git" "@github.com:acme/demo", "ssh://git" "@github.com/acme/demo.git",
                 "https://GitHub.com/Acme/Demo.git")
        for url in forms:
            with self.subTest(url):
                self.assertEqual(mc.origin_repository(url), ("acme", "demo"))
        for url in ("https://gitlab.com/acme/demo.git", "https://github.com.evil.example/acme/demo",
                    "https://github.com/acme/demo/extra", "file:///tmp/acme/demo", "git" "@github.com:acme",
                    "https://user" "@github.com/acme/demo", "", "https://github.com/acme/..", "https://github.com/acme/.git"):
            with self.subTest(url):
                self.assertIsNone(mc.origin_repository(url))

    def test_a_missing_odd_or_ambiguous_origin_is_not_consulted(self):
        self.receipt()
        cases = {
            "missing": lambda: self.git(self.repo, "remote", "remove", "origin"),
            "not github": lambda: self.git(self.repo, "remote", "set-url", "origin", "https://gitlab.com/acme/demo.git"),
            "two urls": lambda: self.git(self.repo, "config", "--add", "remote.origin.url", "git" "@github.com:acme/fork.git"),
        }
        for name, change in cases.items():
            with self.subTest(name):
                try:
                    change()
                    ok, lines = self.evaluate(pr(checks=[]))
                    self.assertFalse(ok)
                    self.assertEqual(self.checks_line(lines),
                                     "BLOCK checks: none reported; local receipt: checkout is not acme/demo")
                finally:
                    subprocess.run(["git", "-C", str(self.repo), "remote", "remove", "origin"], capture_output=True)
                    self.git(self.repo, "remote", "add", "origin", "https://github.com/acme/demo.git")

    def test_the_effective_origin_decides_not_the_raw_config_value(self):
        self.receipt()
        fork = "https://github.com/acme/fork.git"
        included = self.base / "included.gitconfig"
        included.write_text('[remote "origin"]\n\turl = ' + fork + "\n")

        def worktree_url():
            linked = self.base / "wt-config"
            self.git(self.repo, "worktree", "add", "-q", "--detach", str(linked))
            self.git(self.repo, "config", "extensions.worktreeConfig", "true")
            self.git(linked, "config", "--worktree", "remote.origin.url", fork)
            os.chdir(linked)
        cases = {
            "insteadOf to a fork": lambda: self.git(self.repo, "config", "url." + fork + ".insteadOf",
                                                    "https://github.com/acme/demo.git"),
            "push url differs": lambda: self.git(self.repo, "config", "remote.origin.pushurl", fork),
            "second url from an include": lambda: self.git(self.repo, "config", "include.path", str(included)),
            "worktree-specific url": worktree_url,
        }
        for name, change in cases.items():
            with self.subTest(name):
                try:
                    change()
                    ok, lines = self.evaluate(pr(checks=[]))
                    self.assertFalse(ok)
                    self.assertEqual(self.checks_line(lines),
                                     "BLOCK checks: none reported; local receipt: checkout is not acme/demo")
                finally:
                    os.chdir(self.repo)
                    for key in ("url." + fork + ".insteadOf", "remote.origin.pushurl", "include.path",
                                "extensions.worktreeConfig"):
                        subprocess.run(["git", "-C", str(self.repo), "config", "--unset-all", key], capture_output=True)
                    subprocess.run(["git", "-C", str(self.repo), "worktree", "remove", "--force",
                                    str(self.base / "wt-config")], capture_output=True)

    def test_matching_fetch_and_push_urls_in_other_forms_match(self):
        self.receipt()
        self.git(self.repo, "remote", "set-url", "origin", "git" "@github.com:Acme/Demo.git")
        self.git(self.repo, "config", "remote.origin.pushurl", "ssh://git" "@github.com/acme/demo.git")
        ok, lines = self.evaluate(pr(checks=[]), repo="acme/DEMO")
        self.assertTrue(ok, lines)

    def test_main_binds_the_receipt_to_the_repo_argument(self):
        seen = []

        def spy(head, repo):
            seen.append((head, repo))
            return False, "spied"
        data = dict(pr(checks=[]), baseRefOid=OLD)
        with patch.object(mc, "gh", return_value=json.dumps(data)), \
                patch.object(mc, "adopted_at", return_value=False), \
                patch.object(mc, "permission", return_value=True), \
                patch.object(mc, "local_receipt", spy), \
                patch("sys.stdout", new_callable=__import__("io").StringIO):
            self.assertEqual(mc.main(["7", "--repo", "acme/other"]), 1)
        self.assertEqual(seen, [(HEAD, "acme/other")])


if __name__ == "__main__":
    unittest.main()
