"""Review routing uses synthetic account roots and local git fixtures only."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import review_config as config
import review_route as route
import quota_probe as qp
import data_root as dr
from tests.data_root_fixture import account

HEAD = "a" * 40
MATRIX = ("## Assignment matrix\n\n- Consent: yes (2026-11-09)\n- Judge: jev\n"
          "- codex: levels 1-5; roles code-review\n- claudework: levels 3-5; roles navigator\n"
          "- antigravity: levels 1-3; roles advisor\n")


def host(present=("claude", "codex", "antigravity"), roles="", posting=""):
    text = "## Agents on this machine\n\n| Agent | Present | Version | Allowed models (confirmed by user) | Checked |\n| --- | --- | --- | --- | --- |\n"
    for name, family in config.AGENTS.items():
        text += f"| {name} | {'yes' if family in present else 'no'} | fixture | unverified | 2026-11-01 |\n"
    return text + "\n## Agent roles\n" + roles + "\n## Review posting\n" + posting + "\n"


class ReviewConfigTest(unittest.TestCase):
    def test_owned_script_copies_match(self):
        for name in ("review_route.py", "review_config.py", "post_review.py", "git_metadata.py", "data_root.py", "quota_probe.py"):
            expected = (ROOT / "scripts" / name).read_bytes()
            skills = ("fnl-delegate", "fnl-review-gate") if name in {"review_route.py", "review_config.py", "git_metadata.py"} else ("fnl-review-gate",)
            for skill in skills:
                self.assertEqual((ROOT / "skills" / skill / "scripts" / name).read_bytes(), expected)

    def test_review_copy_inventory_is_complete_and_listed_in_ci(self):
        ci = (ROOT / ".github/workflows/validate.yml").read_text()
        for name in ("review_route.py", "review_config.py", "post_review.py", "git_metadata.py"):
            skills = ("fnl-delegate", "fnl-review-gate") if name != "post_review.py" else ("fnl-review-gate",)
            copies = {f"scripts/{name}", *[f"skills/{skill}/scripts/{name}" for skill in skills]}
            actual = {str(p.relative_to(ROOT)) for base in (ROOT / "scripts", ROOT / "skills") for p in base.rglob(name)}
            with self.subTest(script=name):
                self.assertEqual(actual, copies)
                for path in copies:
                    self.assertIn('"' + path + '"', ci)

    def test_review_skill_scripts_run_without_repository(self):
        # Copy only the installed skill, with no repository scripts or test
        # helpers on sys.path. Help exercises CLI imports without posting,
        # quota reads or access to the real account's .finolabs folder.
        boot = (
            "import pwd,runpy,sys; from unittest.mock import patch; "
            "script=sys.argv[1]; sys.argv=[script,'--help']; "
            "guard=patch.object(pwd,'getpwuid',side_effect=AssertionError('account access forbidden')); "
            "guard.start(); runpy.run_path(script,run_name='__main__')"
        )
        with tempfile.TemporaryDirectory() as temp:
            skill = Path(temp) / "fnl-review-gate"
            shutil.copytree(ROOT / "skills/fnl-review-gate", skill)
            scripts = sorted((skill / "scripts").glob("*.py"))
            self.assertTrue(scripts)
            for script in scripts:
                with self.subTest(script=script.name):
                    result = subprocess.run(
                        [sys.executable, "-I", "-c", boot, str(script)],
                        cwd=temp, capture_output=True, text=True, timeout=10,
                    )
                    # Posting intentionally accepts only PR and --body-file,
                    # so --help must stop at its usage parser with exit 2.
                    expected = 2 if script.name == "post_review.py" else 0
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    if expected == 2:
                        self.assertIn("usage: post_review.py", result.stderr)
                        self.assertIn("the following arguments are required: pr", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)

    def test_exact_roles_and_absent_judge(self):
        text = host(roles="- code review: antigravity\n- security review: codex\n- navigator: claude\n- judge: jev")
        self.assertEqual(config.read_roles(text), {"code review": "antigravity", "security review": "codex", "navigator": "claude", "judge": "jev"})
        self.assertEqual(config.read_roles(host(roles="- code review: codex"))["judge"], "host")

    def test_invalid_role_shapes_discard_entire_section(self):
        for body in ("- code review: codex\n- code review: claude", "- code review: missing", "- judge: codex",
                     "- navigator: host", "- Judge: host", "- security review: codex\nextra", "- judge: host\n" * 11,
                     "- code review: codex\n\n- judge: host", "- code review: Codex", "- code review: codex "):
            with self.subTest(body=body):
                # Internal and trailing spaces on a line are rejected. Section
                # trailing whitespace follows mode.py's section-strip behavior.
                if body.endswith(" "):
                    body += "\n- judge: host"
                self.assertEqual(config.read_roles(host(roles=body)), {"judge": "host"})
        self.assertEqual(config.read_roles(host(("claude",), "- navigator: codex")), {"judge": "host", "navigator": "codex"})
        self.assertEqual(config.read_roles("## Agent roles\n- navigator: codex"), {"judge": "host"})

    def test_missing_duplicate_and_fenced_sections(self):
        self.assertEqual(config.read_roles(""), {"judge": "host"})
        self.assertEqual(config.read_roles(host(roles="- code review: codex") + "\n## Agent roles\n- judge: jev"), {"judge": "host"})
        self.assertEqual(config.read_roles("```md\n" + host(roles="- judge: jev") + "```\n"), {"judge": "host"})

    def test_matrix_absent_keeps_the_legacy_roles(self):
        legacy = host(roles="- code review: antigravity\n- judge: jev")
        self.assertEqual(config.read_roles(legacy), {"code review": "antigravity", "judge": "jev"})
        fenced = legacy + "```md\n" + MATRIX + "```\n"
        self.assertEqual(config.read_roles(fenced), {"code review": "antigravity", "judge": "jev"})
        self.assertIsNone(config.matrix_agents(legacy))

    def test_valid_matrix_alone_decides_roles_and_judge(self):
        text = host(roles="- code review: antigravity\n- security review: antigravity\n- judge: host") + MATRIX
        self.assertEqual(config.read_roles(text), {"judge": "jev", "code review": "codex", "navigator": "claude",
                                                   "advisor": "antigravity"})
        self.assertEqual(config.matrix_agents(text), 3)
        # Security review is named by no matrix line: unassigned, and the legacy line never resurrects it.
        self.assertNotIn("security review", config.read_roles(text))
        self.assertEqual(route.route("claude", text, []), [("codex", "headless", "assigned-one-run-two-comments"),
                                                           ("codex", "headless", "capability-one-run-two-comments")])

    def test_invalid_matrix_leaves_roles_and_judge_unset_despite_valid_legacy(self):
        legacy = host(roles="- code review: antigravity\n- judge: jev")
        for broken in (MATRIX + "- gemini: levels 1-2\n", MATRIX + "- codex: levels 1-5; roles navigator\n",
                       MATRIX.replace("- Judge: jev\n", ""), MATRIX + MATRIX, "## Assignment matrix\n```\n"):
            with self.subTest(broken=broken[-30:]):
                self.assertEqual(config.read_roles(legacy + broken), {"judge": "host"})
                self.assertIsNone(config.matrix_agents(legacy + broken))
                if "```" in broken:
                    continue  # an open fence hides every section, so no family is present to route to
                self.assertEqual([row[2] for row in route.route("claude", legacy + broken, [])],
                                 ["capability-one-run-two-comments"] * 2)

    def test_matrix_without_consent_leaves_roles_and_judge_unset(self):
        legacy = host(roles="- code review: antigravity\n- judge: jev")
        for consent in ("- Consent: no\n- Judge: host\n", MATRIX.replace("yes (2026-11-09)", "no")):
            with self.subTest(consent=consent[:40]):
                text = legacy + "## Assignment matrix\n" + consent.split("## Assignment matrix\n")[-1]
                self.assertEqual(config.read_roles(text), {"judge": "host"})
                self.assertIsNone(config.matrix_agents(text))

    def test_posting_grammar_dates_duplicates_and_cap(self):
        valid = "- codex: yes (checked 2026-11-01)\n- claude: no (checked 2026-11-01)\n- antigravity: unverified (checked 2026-11-01)"
        self.assertEqual(config.read_posting(host(posting=valid)), {"codex": "yes", "claude": "no", "antigravity": "unverified"})
        for body in ("- codex: yes", "- codex: YES (checked 2026-11-01)", "- other: yes (checked 2026-11-01)",
                     "- codex: yes (checked 2026-02-30)", "- codex: yes (checked 2999-01-01)",
                     valid + "\n- codex: no (checked 2026-11-01)", "- codex: yes (checked 2026-11-01)\n" * 11,
                     valid + "\nextra", valid + "\n## Review posting\n- codex: yes (checked 2026-11-01)"):
            with self.subTest(body=body):
                self.assertEqual(config.read_posting(host(posting=body)), {})


class RouteTest(unittest.TestCase):
    def pick(self, text=None, **kwargs):
        return route.route("claude", host() if text is None else text, [], **kwargs)

    def test_assigned_family(self):
        rows = self.pick(host(roles="- code review: antigravity\n- security review: codex"))
        self.assertEqual(rows, [("antigravity", "headless", "assigned"), ("codex", "headless", "assigned")])

    def test_same_family_fresh_context_disclosure(self):
        rows = self.pick(host(("claude",)))
        self.assertEqual({r[0] for r in rows}, {"claude"})
        self.assertTrue(all("same-family" in r[2] for r in rows))

    def test_absent_or_stale_assignment_falls_back_to_capability_order(self):
        self.assertEqual(self.pick(host(("claude", "codex"), "- code review: antigravity"))[0][0], "codex")
        self.assertEqual(self.pick(host(roles="- code review: antigravity\n- navigator: missing"))[0][0], "codex")

    def test_both_kinds_one_run_two_comments(self):
        rows = self.pick()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r == ("codex", "headless", "capability-one-run-two-comments") for r in rows))

    def test_lane_uses_code_reviewer_for_both(self):
        rows = self.pick(host(roles="- code review: antigravity\n- security review: codex"), lane=True)
        self.assertTrue(all(r[0] == "antigravity" and "lane-one-run-two-comments" in r[2] for r in rows))

    def test_posting_tie_break_never_overrides_independence_or_assignment(self):
        posting = "- claude: yes (checked 2026-11-01)\n- antigravity: yes (checked 2026-11-01)"
        self.assertEqual(self.pick(host(posting=posting))[0][0], "antigravity")
        self.assertEqual(self.pick(host(roles="- code review: codex", posting=posting))[0][0], "codex")
        self.assertEqual(self.pick(host(("claude", "codex"), posting=posting))[0][0], "codex")

    def test_no_available_family_is_error(self):
        with self.assertRaises(ValueError):
            self.pick(host(()))
        with self.assertRaises(ValueError):
            route.route("unknown", host(), [])
        now = qp.now()
        depleted = [f"Quota claude/default: measured {qp.stamp(now)}; week-all week: 1% remaining, resets {qp.stamp(now + timedelta(hours=1))}"]
        with self.assertRaises(ValueError):
            route.route("claude", host(("claude",)), depleted)

    def test_stale_and_future_quota_excludes_nothing(self):
        now = qp.now()
        for measured in (now - timedelta(hours=9), now + timedelta(hours=1)):
            lines = [f"Quota codex/default: measured {qp.stamp(measured)}; primary hour: 0% remaining, resets {qp.stamp(now + timedelta(hours=2))}"]
            self.assertEqual(route.blocked_families(lines, now), set())

    def test_multiple_claude_installs_week_all_and_threshold(self):
        now = qp.now()
        def line(label, remaining, group="week-all"):
            return f"Quota claude/{label}: measured {qp.stamp(now)}; {group} week: {remaining}% remaining, resets {qp.stamp(now + timedelta(hours=1))}"
        self.assertEqual(route.blocked_families([line("default", 1), line("other", 50)], now), set())
        self.assertEqual(route.blocked_families([line("default", 1), line("other", 0)], now), {"claude"})
        self.assertEqual(route.blocked_families([line("default", 0, "week-model")], now), set())
        self.assertEqual(route.blocked_families([line("default", 10)], now), set())


class LocalEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = account(self, self.base / "account")
        self.checkout = self.base / "checkout"
        self.checkout.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Author")
        self.git("config", "user.email", "author@example.com")
        (self.checkout / "sample.txt").write_text("first\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "Add fixture\n\nCo-Authored-By: Codex <noreply@example.com>")
        self.first = self.git("rev-parse", "HEAD").strip()
        self.git("commit", "--allow-empty", "-qm", "Prepare fixture\n\nCo-Authored-By: Codex <noreply@example.com>")
        self.second = self.git("rev-parse", "HEAD").strip()
        self.bind("codex")

    def bind(self, family):
        head = self.git("rev-parse", "HEAD").strip()
        dr.write_data("ledger.jsonl", json.dumps(dict(head=head, agent=family)).encode())

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.checkout, check=True, capture_output=True, text=True,
                              env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}).stdout

    def test_loose_packed_worktree_and_packet_match_git(self):
        self.assertEqual(route.author_family(self.checkout, base=self.first), "codex")
        (self.checkout / "sample.txt").write_text("first\nsecond\n")
        self.git("commit", "-qam", "Extend fixture\n\nCo-Authored-By: Claude <noreply@example.com>")
        head = self.git("rev-parse", "HEAD").strip()
        packet = route.build_packet(self.checkout, self.first, head, ["criterion"], ["decision"], ["consumer"])
        self.assertEqual(packet["diff_stat"], [{"file": "sample.txt", "added": 1, "removed": 0}])
        self.assertEqual(packet["acceptance_criteria"], ["criterion"])
        self.git("gc", "--prune=now")
        self.bind("claude")
        self.assertEqual(route.author_family(self.checkout, base=self.second), "claude")
        self.assertEqual(packet, route.build_packet(self.checkout, self.first, head, ["criterion"], ["decision"], ["consumer"]))
        linked = self.base / "linked"
        self.git("worktree", "add", "--detach", str(linked), "HEAD")
        self.assertEqual(route.author_family(linked, base=self.second), "claude")

    def test_packet_refuses_control_names_and_excessive_text_diff(self):
        name = self.checkout / "bad\nname.txt"
        name.write_text("unsafe name\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Add control name")
        head = self.git("rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(ValueError, "tree name"):
            route.build_packet(self.checkout, self.first, head, [], [], [])
        self.git("rm", str(name))
        (self.checkout / "sample.txt").write_text("line\n" * 1001)
        self.git("commit", "-qam", "Add excessive text diff")
        head = self.git("rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(ValueError, "text diff"):
            route.build_packet(self.checkout, self.first, head, [], [], [])

    def test_pack_deltas_binary_modes_and_gitlinks(self):
        # Similar large blobs force pack delta objects, not only full objects.
        original = "".join(f"synthetic line {i:04d} repeated content\n" for i in range(700))
        (self.checkout / "large.txt").write_text(original)
        (self.checkout / "binary.bin").write_bytes(b"first\0binary")
        self.git("add", ".")
        self.git("commit", "-qm", "Add synthetic data\n\nCo-Authored-By: Codex <noreply@example.com>")
        base = self.git("rev-parse", "HEAD").strip()
        (self.checkout / "large.txt").write_text(original.replace("line 0350", "line changed"))
        (self.checkout / "binary.bin").write_bytes(b"second\0binary")
        (self.checkout / "sample.txt").chmod(0o755)
        self.git("add", ".")
        self.git("update-index", "--add", "--cacheinfo", "160000," + base + ",dependency")
        self.git("commit", "-qm", "Change synthetic data\n\nCo-Authored-By: Claude <noreply@example.com>")
        head = self.git("rev-parse", "HEAD").strip()
        expected = route.build_packet(self.checkout, base, head, [], [], [])
        self.git("repack", "-adf", "--window=50", "--depth=20")
        self.git("prune-packed")
        actual = route.build_packet(self.checkout, base, head, [], [], [])
        self.assertEqual(actual, expected)
        by_name = {item["file"]: item for item in actual["diff_stat"]}
        self.assertEqual(by_name["large.txt"], dict(file="large.txt", added=1, removed=1))
        self.assertTrue(by_name["binary.bin"]["binary"])
        self.assertEqual(by_name["sample.txt"], dict(file="sample.txt", added=0, removed=0))
        self.assertIn("dependency", by_name)

    def test_no_guess_for_legacy_ledger_and_head_bound_fallback(self):
        self.git("commit", "--allow-empty", "-qm", "A human-authored fixture")
        head = self.git("rev-parse", "HEAD").strip()
        with self.assertRaises(ValueError):
            route.author_family(self.checkout, json.dumps({"agent": "codex", "project": "synthetic"}), base=self.first)
        with self.assertRaisesRegex(ValueError, "trailers"):
            route.author_family(self.checkout, json.dumps({"head": head, "agent": "antigravity"}), base=self.second)

    def test_spoofed_trailer_cannot_override_ledger(self):
        ledger = json.dumps({"head": self.second, "agent": "claude"})
        with self.assertRaises(ValueError):
            route.author_family(self.checkout, ledger, base=self.first)

    def test_indented_and_unclosed_fences_do_not_expose_roles(self):
        for fence in (" ```md", "  ~~~md", "   ````md"):
            with self.subTest(fence=fence):
                text = fence + "\n" + host(roles="- judge: jev") + "   " + fence.strip()[0] * 5 + "\n"
                self.assertEqual(config.read_roles(text), {"judge": "host"})
                self.assertEqual(config.section("```md\n" + host(), "Agents on this machine"), None)

    def test_mixed_range_and_missing_evidence_cannot_pick(self):
        self.git("commit", "--allow-empty", "-qm", "Spoof tip\n\nCo-Authored-By: Claude Opus 4.6 <noreply@example.com>")
        self.bind("claude")
        with self.assertRaisesRegex(ValueError, "trailers"):
            route.author_family(self.checkout, base=self.first)
        self.assertEqual(route.author_family(self.checkout, base=self.second), "claude")
        with self.assertRaises(ValueError):
            route.author_family(self.checkout, "", base=self.second)
        with self.assertRaises(ValueError):
            route.author_family(self.checkout)
        output = io.StringIO()
        dr.write_data("host.md", host(roles="- security review: codex").encode())
        with mock.patch.object(route.Path, "cwd", return_value=self.checkout), contextlib.redirect_stdout(output):
            self.assertEqual(route.main(["--base", self.first, "--security-trigger"]), 2)
        self.assertEqual(output.getvalue(), "")

    def test_crlf_model_trailer_and_conflicting_ledger(self):
        self.git("commit", "--allow-empty", "-qm", "Claude fixture\r\n\r\nCo-Authored-By: Claude Opus 4.6 <noreply@example.com>\r\n")
        self.bind("claude")
        self.assertEqual(route.author_family(self.checkout, base=self.second), "claude")
        ledger = dr.read_data("ledger.jsonl").decode()
        ledger += "\n" + json.dumps(dict(head=self.git("rev-parse", "HEAD").strip(), agent="codex"))
        with self.assertRaises(ValueError):
            route.author_family(self.checkout, ledger, base=self.second)

    def test_metadata_symlink_fifo_owner_and_object_paths_refused(self):
        git = self.checkout / ".git"
        for name in ("HEAD", "objects"):
            path = git / name
            moved = git / (name + "-saved")
            path.rename(moved)
            path.symlink_to(moved, target_is_directory=moved.is_dir())
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                route.author_family(self.checkout, base=self.first)
            path.unlink()
            moved.rename(path)
        path = git / "HEAD"
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(ValueError):
            route.author_family(self.checkout, base=self.first)

    def test_quota_cache_depletion_and_marker_route_away(self):
        now = qp.now()
        cache = {"codex": {"default": {"source": qp.SOURCES["codex"], "measured": qp.stamp(now),
                 "groups": [{"name": "codex", "window": "5h", "remaining_fraction": .01,
                             "reset_time": qp.stamp(now + timedelta(hours=1))}]}}}
        # Fixture uses the probe's own allowed pool name, never provider output.
        cache["codex"]["default"]["groups"][0]["name"] = next(iter(qp.NAMES["codex"]))
        with qp.state_folder(create=True, writer=True) as folder:
            qp.write_json(folder, "quota.json", cache)
        rows = route.route("claude", host(roles="- code review: codex"), qp.status_lines())
        self.assertEqual(rows[0][0], "antigravity")
        with qp.state_folder(create=True, writer=True) as folder:
            qp.write_json(folder, "quota.json", {})
            qp.write_json(folder, "limits.json", {"claude": qp.stamp(now)})
        rows = route.route("codex", host(roles="- code review: claude"), qp.status_lines())
        self.assertEqual(rows[0][0], "antigravity")

    def test_canonical_reader_ignores_override_and_refuses_symlink(self):
        dr.write_data("host.md", host(roles="- judge: jev").encode())
        with mock.patch.dict(os.environ, {"ORCHESTRATION_HOST_CONFIG": str(self.base / "other.md")}):
            self.assertEqual(config.read_roles(config.host_text())["judge"], "jev")
        path = dr.consent_root() / "host.md"
        path.unlink()
        path.symlink_to(self.checkout / "sample.txt")
        self.assertEqual(config.host_text(), "")

    def test_main_no_process_no_socket_no_model_and_exact_lines(self):
        dr.write_data("host.md", host().encode())
        output = io.StringIO()
        with mock.patch.object(route.Path, "cwd", return_value=self.checkout), \
             mock.patch.object(socket, "socket", side_effect=AssertionError("socket forbidden")), \
             mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process forbidden")), \
             mock.patch.object(os, "system", side_effect=AssertionError("shell forbidden")), \
             mock.patch.object(qp, "read_family", side_effect=AssertionError("quota read forbidden")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(route.main(["--base", self.first]), 0)
        self.assertEqual(output.getvalue().splitlines(), ["claude agent capability-one-run-two-comments"] * 2)

    def test_invalid_lane_and_missing_config_fail_without_output(self):
        output = io.StringIO()
        with mock.patch.object(route.Path, "cwd", return_value=self.checkout), contextlib.redirect_stdout(output):
            self.assertEqual(route.main(["--lane", "--security-trigger"]), 2)
            self.assertEqual(route.main(["--base", self.first]), 2)
        self.assertEqual(output.getvalue(), "")

    def test_security_same_family_requires_decision(self):
        dr.write_data("host.md", host(("codex",)).encode())
        output = io.StringIO()
        with mock.patch.object(route.Path, "cwd", return_value=self.checkout), contextlib.redirect_stdout(output):
            self.assertEqual(route.main(["--base", self.first, "--security-trigger"]), 1)
        self.assertEqual(len(output.getvalue().splitlines()), 2)
        self.assertIn("same-family", output.getvalue())


if __name__ == "__main__":
    unittest.main()
