"""Tests for skills/fnl-delegate/scripts/route_pick.py: the routing query over the assignment matrix."""

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

SCRIPTS = Path(__file__).resolve().parent.parent / "skills/fnl-delegate/scripts"
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

    def test_claude_quota_drops_extra_claude_commands_too(self):
        lines = [line.replace("5h 5h", "week-all 7d") for line in depleted("claude")]
        result = self.pick(quota=lines)
        self.assertEqual(result.survivors, [("codex", None)])
        self.assertEqual(result.drops, [("claude", "out of quota"), ("claudework", "out of quota")])

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


if __name__ == "__main__":
    unittest.main()
