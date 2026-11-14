"""Tests for skills/delegate/scripts/route_pick.py: the routing query over the assignment matrix."""

import contextlib
import importlib.util
import io
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from tests.data_root_fixture import account

SCRIPTS = Path(__file__).resolve().parent.parent / "skills/delegate/scripts"
SCRIPT = SCRIPTS / "route_pick.py"
sys.path.insert(0, str(SCRIPTS))


def load():
    spec = importlib.util.spec_from_file_location("route_pick_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MACHINE = """## Agents on this machine

Coordinator: Claude Code

| Agent | Present | Version | Allowed models (confirmed by user) | Checked |
| --- | --- | --- | --- | --- |
| Claude Code | yes | 1 | m | 2026-11-09 |
| Codex | yes | 1 | m | 2026-11-09 |
| Antigravity | yes | 1 | m | 2026-11-09 |

"""

REACH = """## Coordinators and reach

| Coordinator | Claude Code | Codex | Antigravity |
| --- | --- | --- | --- |
| Claude Code | — | yes | {agy} |
| Codex | yes | — | yes |
| Antigravity | yes | yes | — |

"""

MATRIX = """## Assignment matrix

- Consent: yes (2026-11-09)
- Judge: host
- claude: levels 1-5; works on frontend, design
- claudework: levels 3-5; works on frontend; model claude-opus-5-5
- codex: levels 1-4; works on image-generation, transcription, frontend
- antigravity: levels 1-3; works on image-generation, transcription

"""


def host(matrix=MATRIX, agy="yes"):
    return MACHINE + REACH.format(agy=agy) + matrix


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def depleted(family):
    current = datetime.now(timezone.utc)
    return [f"Quota {family}/default: measured {stamp(current - timedelta(minutes=5))}; "
            f"5h 5h: 3% remaining, resets {stamp(current + timedelta(hours=2))}"]


class PickTest(unittest.TestCase):
    def setUp(self):
        self.rp = load()

    def pick(self, text=None, work_type="frontend", level=3, author=None, quota=()):
        return self.rp.pick(host() if text is None else text, work_type, level, author=author, quota_lines=list(quota))

    def test_ordering_follows_matrix_lines_and_models(self):
        result = self.pick()
        self.assertEqual(result.survivors, [("claude", None), ("claudework", "claude-opus-5-5"), ("codex", None)])
        self.assertEqual(self.rp.lines(result), ["claude default", "claudework claude-opus-5-5", "codex default"])

    def test_only_agents_listing_the_type_are_candidates(self):
        result = self.pick(work_type="image-generation", level=2)
        self.assertEqual([a for a, _ in result.survivors], ["codex", "antigravity"])

    def test_level_outside_range_is_dropped_with_reason(self):
        result = self.pick(level=5)
        self.assertEqual([a for a, _ in result.survivors], ["claude", "claudework"])
        self.assertEqual(result.drops, [("codex", "level 5 outside 1-4")])
        self.assertIn("drop codex: level 5 outside 1-4", self.rp.lines(result))

    def test_unreachable_from_coordinator_is_dropped(self):
        result = self.pick(text=host(agy="no: not signed in"), work_type="transcription", level=2)
        self.assertEqual(result.survivors, [("codex", None)])
        self.assertEqual(result.drops, [("antigravity", "unreachable from claude")])

    def test_out_of_quota_is_dropped(self):
        result = self.pick(quota=depleted("codex"))
        self.assertEqual([a for a, _ in result.survivors], ["claude", "claudework"])
        self.assertEqual(result.drops, [("codex", "out of quota")])

    def week(self, label, percent):
        reset = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        measured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"Quota claude/{label}: measured {measured}; week-all 7d: {percent}% remaining, resets {reset}"

    def test_a_depleted_install_is_dropped_and_the_healthy_one_stays(self):
        result = self.pick(quota=[self.week("default", 3), self.week("work", 80)])
        self.assertEqual([a for a, _ in result.survivors], ["claudework", "codex"])
        self.assertEqual(result.drops, [("claude", "out of quota")])
        self.assertEqual(self.rp.rank(result, "claudework", "claude-opus-5-5"), (1, None))
        self.assertEqual(self.rp.rank(result, "claude", "default"), (0, "claude: out of quota"))

    def test_an_install_with_no_reading_does_not_borrow_another_installs_quota(self):
        result = self.pick(quota=[self.week("work", 3)])
        self.assertEqual([a for a, _ in result.survivors], ["claude", "codex"])
        self.assertEqual(result.drops, [("claudework", "out of quota")])

    def test_a_rate_limit_marker_covers_every_claude_install(self):
        now = datetime.now(timezone.utc)
        marked = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        until = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = self.pick(quota=[f"Quota claude: rate-limit marker {marked}; out of quota until {until} (advisory)"])
        self.assertEqual(result.survivors, [("codex", None)])
        self.assertEqual(result.drops, [("claude", "out of quota"), ("claudework", "out of quota")])

    def test_the_dispatching_coordinator_decides_reachability(self):
        for own, kept in (("codex", True), ("claude", False), (None, False)):
            with self.subTest(own=own):
                result = self.rp.pick(host(agy="no"), "transcription", 2, dispatcher=own)
                self.assertEqual("antigravity" in [a for a, _ in result.survivors], kept)

    def test_author_rule_drops_the_author_family(self):
        result = self.pick(author="claude")
        self.assertEqual(result.survivors, [("codex", None)])
        self.assertEqual(result.drops, [("claude", "author family"), ("claudework", "author family")])

    def test_nothing_survives_means_no_preference(self):
        result = self.pick(level=5, author="claude")
        self.assertEqual(result.survivors, [])
        output = self.rp.lines(result)
        self.assertEqual(output[0], "no preference: use the strength table")
        self.assertIn("drop codex: level 5 outside 1-4", output)

    def test_no_agent_lists_the_type_means_no_preference(self):
        result = self.pick(work_type="video")
        self.assertEqual(self.rp.lines(result), ["no preference: use the strength table"])

    def test_missing_matrix_means_no_preference(self):
        result = self.pick(text=MACHINE)
        self.assertEqual(result.state, "absent")
        self.assertEqual(self.rp.lines(result), ["no preference: use the strength table"])

    def test_invalid_matrix_means_no_preference(self):
        broken = MATRIX.replace("works on frontend, design", "works on frontend, cooking")
        result = self.pick(text=host(matrix=broken))
        self.assertEqual(result.state, "invalid")
        self.assertEqual(result.survivors, [])
        self.assertEqual(self.rp.lines(result), ["no preference: use the strength table", "matrix invalid"])
        unconsented = MATRIX.replace("yes (2026-11-09)", "no").replace("- claude", "- x-claude")
        self.assertEqual(self.pick(text=host(matrix=unconsented)).state, "invalid")

    def test_at_most_five_lines(self):
        many = "\n".join(["## Assignment matrix", "", "- Consent: yes (2026-11-09)", "- Judge: host"]
                         + [f"- {name}: levels 1-2; works on design" for name in
                            ("claude", "claudea", "claudeb", "claudec", "clauded", "claudee", "codex", "antigravity")]) + "\n"
        result = self.pick(text=MACHINE + many, work_type="design", level=4)
        self.assertEqual(len(result.drops), 8)
        self.assertEqual(len(self.rp.lines(result)), 5)

    def test_rank_compares_install_and_model(self):
        result = self.pick()
        self.assertEqual(self.rp.rank(result, "claude", "any"), (1, None))
        self.assertEqual(self.rp.rank(result, "claudework", "claude-opus-5-5"), (2, None))
        self.assertEqual(self.rp.rank(result, "claudework", "other-model"), (0, "model not listed for claudework"))
        self.assertEqual(self.rp.rank(result, "antigravity", "m"), (0, "antigravity not listed for frontend"))
        dropped = self.pick(level=5)
        self.assertEqual(self.rp.rank(dropped, "codex", "m"), (0, "codex: level 5 outside 1-4"))
        self.assertIsNone(self.rp.rank(self.pick(text=MACHINE), "claude", "m"))

    def test_runs_no_program_and_opens_no_socket(self):
        guard = mock.Mock(side_effect=AssertionError("forbidden"))
        with mock.patch.object(subprocess, "run", guard), mock.patch.object(subprocess, "Popen", guard), \
                mock.patch.object(os, "system", guard), mock.patch.object(socket, "socket", guard), \
                mock.patch.object(self.rp, "host_text", return_value=host()), \
                mock.patch.object(self.rp, "quota_lines", return_value=[]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = self.rp.main(["pick", "--type", "frontend", "--level", "3"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "claude default\nclaudework claude-opus-5-5\ncodex default\n")
        self.assertNotIn("subprocess", SCRIPT.read_text())
        self.assertNotIn("socket", SCRIPT.read_text())

    def test_bad_arguments_exit_two(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for argv in (["pick", "--type", "cooking", "--level", "3"], ["pick", "--type", "video", "--level", "6"],
                         ["pick", "--type", "video", "--level", "3", "--author", "someone"]):
                with self.assertRaises(SystemExit) as raised:
                    self.rp.main(argv)
                self.assertEqual(raised.exception.code, 2)


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.home = account(self, Path(self.dir.name) / "home")
        self.root = self.home / ".finolabs/vibecode"
        self.root.mkdir(parents=True)
        self.env = {"HOME": str(self.home)}

    def run_pick(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), "pick", *args],
                              capture_output=True, text=True, env=self.env)

    def test_reads_canonical_host_config_and_prints_no_path(self):
        (self.root / "host.md").write_text(host())
        result = self.run_pick("--type", "frontend", "--level", "5", "--author", "codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "claude default\nclaudework claude-opus-5-5\ndrop codex: level 5 outside 1-4\n")
        self.assertNotIn(self.dir.name, result.stdout + result.stderr)

    def test_without_host_config_no_preference(self):
        result = self.run_pick("--type", "frontend", "--level", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "no preference: use the strength table\n")


OWNER_LINE = ("- antigravity: levels 1-5; works on design, video, image-generation, transcription; models "
              "gemini-4-argon-high then gemini-3.8-flash-high for security-review | gemini-4-hydrogen-high for design, "
              "video, three-d, image-generation, levels 4-5 | gemini-4-argon-high for implement, levels 4-5 | "
              "gemini-3.8-flash-high for code-review | gemini-3.8-flash-high for levels 3-4; roles security-review, "
              "navigator")
OWNER = ("## Assignment matrix\n\n- Consent: yes (2026-11-14)\n- Judge: host\n"
         "- codex: levels 1-5; model gpt-codex-9; roles code-review\n" + OWNER_LINE + "\n\n")


def agy(**pools):
    """One fresh Antigravity reading; each keyword is a pool and its remaining percent."""
    current = datetime.now(timezone.utc)
    reset = stamp(current + timedelta(hours=2))
    body = "; ".join(f"{name.replace('_', '-')} 5h: {percent}% remaining, resets {reset}" for name, percent in pools.items())
    return [f"Quota agy/default: measured {stamp(current - timedelta(minutes=5))}; {body}"]


class ModelsTest(unittest.TestCase):
    """docs/specs/matrix-models.md: `--kind`, optional `--type`, the model per dispatch and the quota fallback."""

    def setUp(self):
        self.rp = load()

    def lines(self, kind="implement", work_type=None, level=3, quota=(), matrix=OWNER):
        return self.rp.lines(self.rp.pick(host(matrix), work_type, level, quota_lines=list(quota), kind=kind))

    def test_security_review_uses_argon_then_flash_when_argon_is_out(self):
        self.assertEqual(self.lines("security-review"), ["codex gpt-codex-9", "antigravity gemini-4-argon-high"])
        self.assertEqual(self.lines("security-review", quota=agy(argon=3, gemini=60)),
                         ["codex gpt-codex-9", "antigravity gemini-3.8-flash-high quota-fallback"])

    def test_model_chosen_per_kind_type_and_level(self):
        self.assertIn("antigravity gemini-4-argon-high", self.lines("implement", level=4))
        self.assertIn("antigravity gemini-3.8-flash-high", self.lines("code-review", level=2))
        self.assertEqual(self.lines("implement", "design", 4), ["antigravity gemini-4-hydrogen-high"])
        self.assertIn("antigravity default", self.lines("implement", level=2))

    def test_kindless_rules_never_pick_for_another_kind(self):
        self.assertIn("antigravity default", self.lines("advisor", level=3))
        self.assertIn("antigravity default", self.lines("navigator", level=4))
        with_model = OWNER.replace("transcription; models", "transcription; model gemini-base; models")
        self.assertIn("antigravity gemini-base", self.lines("advisor", level=3, matrix=with_model))

    def test_kind_never_filters_candidates(self):
        # codex holds code-review, antigravity none: both are printed, in line order.
        self.assertEqual(self.lines("code-review"), ["codex gpt-codex-9", "antigravity gemini-3.8-flash-high"])
        self.assertEqual(self.lines("advisor"), ["codex gpt-codex-9", "antigravity default"])

    def test_pick_without_type_runs_from_the_command_line(self):
        with mock.patch.object(self.rp, "host_text", return_value=host(OWNER)), \
                mock.patch.object(self.rp, "quota_lines", return_value=agy(argon=3, gemini=60)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = self.rp.main(["pick", "--kind", "security-review", "--level", "3"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "codex gpt-codex-9\nantigravity gemini-3.8-flash-high quota-fallback\n")
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.rp.main(["pick", "--kind", "reviewing", "--level", "3"])

    def test_final_model_out_of_quota_drops_the_agent(self):
        self.assertIn("drop antigravity: out of quota", self.lines("security-review", quota=agy(argon=3, gemini=2)))
        self.assertIn("drop antigravity: out of quota", self.lines("code-review", quota=agy(argon=60, gemini=2)))
        self.assertIn("antigravity gemini-3.8-flash-high", self.lines("code-review", quota=agy(argon=3, gemini=60)))
        self.assertIn("antigravity gemini-4-argon-high", self.lines("security-review", quota=agy(argon=60, gemini=2)))
        # A default choice needs every pool.
        self.assertIn("drop antigravity: out of quota", self.lines("advisor", quota=agy(argon=60, claude_gpt=2)))

    def test_rate_limit_marker_drops_whatever_the_pools_say(self):
        now = datetime.now(timezone.utc)
        marker = (f"Quota agy: rate-limit marker {stamp(now - timedelta(minutes=5))}; "
                  f"out of quota until {stamp(now + timedelta(hours=1))} (advisory)")
        self.assertIn("drop antigravity: out of quota", self.lines("security-review", quota=[marker] + agy(argon=60, gemini=60)))

    def test_then_never_applies_to_other_families(self):
        matrix = ("## Assignment matrix\n\n- Consent: yes (2026-11-14)\n- Judge: host\n"
                  "- codex: levels 1-5; models gpt-a then gpt-b for code-review\n\n")
        self.assertEqual(self.lines("code-review", matrix=matrix), ["codex gpt-a"])
        self.assertEqual(self.lines("code-review", quota=depleted("codex"), matrix=matrix),
                         ["no preference: use the strength table", "drop codex: out of quota"])

    def test_without_rules_behavior_is_unchanged(self):
        self.assertEqual(self.rp.lines(self.rp.pick(host(), "frontend", 3, kind="security-review")),
                         ["claude default", "claudework claude-opus-5-5", "codex default"])

    def test_invalid_rule_means_no_route(self):
        broken = OWNER.replace("for code-review", "for reviewing")
        self.assertEqual(self.lines("code-review", matrix=broken), ["no preference: use the strength table", "matrix invalid"])


if __name__ == "__main__":
    unittest.main()
