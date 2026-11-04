"""Tests for skills/fnl-status/scripts/refresh.py: the six metrics from a fixture store and ledger, and the files it writes."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
REFRESH = ROOT / "skills/fnl-status/scripts/refresh.py"
LEDGER = ROOT / "skills/fnl-delegate/scripts/ledger.py"
PAGE = ROOT / "skills/fnl-status/assets/dashboard.html"
X, Y = "aaaaaaaa", "bbbbbbbb"


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "state"
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"
        self.env = {**os.environ, "FNL_STATE_DIR": str(self.dir), "ORCHESTRATION_LEDGER": str(self.ledger)}
        self.env.pop("FNL_METRICS", None)
        self.at = datetime.now(timezone.utc)

    def refresh(self, *args, check=True):
        result = subprocess.run([sys.executable, "-I", str(REFRESH), *args], capture_output=True, text=True, env=self.env)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def consent(self, days="90"):
        self.refresh("consent", "--retention", days)

    def event(self, minutes_ago, sid, repo, event, **fields):
        ts = (self.at - timedelta(minutes=minutes_ago)).isoformat(timespec="milliseconds")
        return {"ts": ts, "sid": sid, "repo": repo, "event": event, **fields}

    def write_events(self, events):
        self.dir.mkdir(parents=True, exist_ok=True)
        by_month = {}
        for e in events:
            by_month.setdefault(e["ts"][:7], []).append(json.dumps(e))
        for month, lines in by_month.items():
            (self.dir / ("events-%s.jsonl" % month)).write_text("\n".join(lines) + "\n")

    def data(self):
        text = (self.dir / "data.js").read_text()
        self.assertTrue(text.startswith("window.FNL_DATA = ") and text.endswith(";\n"))
        return json.loads(text[len("window.FNL_DATA = "):-2])

    def fixture_store(self):
        start = {"host": "claude", "dispatch": None, "source": "startup"}
        self.write_events([
            self.event(120, "a", X, "session_start", **start), self.event(119, "a", X, "skill", name="fnl-coding-router"),
            self.event(118, "a", X, "router", depth="DEEP", trigger="security"), self.event(110, "a", X, "first_edit"),
            self.event(100, "b", X, "session_start", **start), self.event(90, "b", X, "first_edit"),
            self.event(80, "c", X, "session_start", host="claude", dispatch="d20261103-1", source="startup"),
            self.event(70, "c", X, "first_edit"),
            self.event(60, "d", X, "first_edit"),
            self.event(50, "e", Y, "session_start", **start), self.event(49, "e", Y, "router", depth="MIN", trigger="none"),
            self.event(40, "e", Y, "first_edit"),
            self.event(35, "a", X, "agent", name="fnl-reviewer"), self.event(34, "a", X, "agent", name="fnl-reviewer"),
            self.event(30, "a", X, "review", kind="code", verdict="REWORK", pr=5),
            self.event(20, "a", X, "review", kind="security", verdict="APPROVE", pr=5),
            self.event(10, "e", Y, "review", kind="code", verdict="APPROVE", pr=7),
        ])

    def fixture_ledger(self):
        env = self.env
        start = ["start", "--project", "demo", "--task", "t", "--kind", "implement", "--grade", "medium",
                 "--agent", "codex", "--model", "m1", "--budget", "40"]
        ids = [subprocess.run([sys.executable, "-I", str(LEDGER), *start], capture_output=True, text=True, env=env).stdout.strip()
               for _ in range(2)]
        for dispatch_id, outcome in zip(ids, ("accepted", "quota")):
            subprocess.run([sys.executable, "-I", str(LEDGER), "finish", dispatch_id, "--outcome", outcome], check=True, env=env)

    def test_the_metrics_match_a_hand_computation(self):
        self.consent()
        self.fixture_store()
        self.fixture_ledger()
        self.refresh("run")
        d = self.data()
        self.assertEqual(d["sessions"], {"total": 5, "with_edits": 5, "dispatch": 1, "unclassified": 1})
        self.assertEqual(d["router"], {"covered": 2, "missed": 1, "excluded": 1, "unclassified": 1, "eligible": 3})
        self.assertAlmostEqual(d["kpi"]["router_coverage"], 2 / 3)
        self.assertEqual({(u["kind"], u["name"], u["count"]) for u in d["use"]},
                         {("skill", "fnl-coding-router", 1), ("agent", "fnl-reviewer", 2)})
        self.assertEqual(d["kpi"]["calls"], 3)
        self.assertEqual({r["depth"]: (r["receipts"], r["reworked"]) for r in d["depth"]}, {"MIN": (1, 0), "DEEP": (1, 1)})
        self.assertEqual({(r["repo"], r["pr"]): r["verdicts"] for r in d["reviews"]},
                         {("repo-" + X, 5): ["REWORK", "APPROVE"], ("repo-" + Y, 7): ["APPROVE"]})
        [row] = d["delegation"]
        self.assertEqual((row["agent"], row["runs"], row["first_pass"], row["quota"], row["error"]), ("codex", 2, 0.5, 1, 0))
        self.assertAlmostEqual(d["kpi"]["first_pass"], 0.5)
        size = (ROOT / "skills/fnl-coding-router/SKILL.md").stat().st_size // 4
        self.assertEqual(d["load"]["top"], [{"name": "fnl-coding-router", "tokens": size, "loads": 1}])
        self.assertEqual(len(d["activity"]), 84)
        self.assertEqual(sum(a["count"] for a in d["activity"]), 17)
        self.assertEqual(d["errors"], 0)
        self.assertEqual(d["missing"], {})

    def days_ago(self, days, sid, repo, event, **fields):
        return self.event(days * 24 * 60, sid, repo, event, **fields)

    def test_weeks_without_data_are_null_not_zero(self):
        self.consent()
        start = {"host": "claude", "dispatch": None, "source": "startup"}
        self.write_events([
            self.days_ago(20, "a", X, "session_start", **start), self.days_ago(20, "a", X, "router", depth="MIN", trigger="none"),
            self.days_ago(20, "a", X, "first_edit"),
            self.days_ago(12, "b", X, "session_start", **start), self.days_ago(12, "b", X, "first_edit"),
        ])
        self.refresh("run")
        spark = self.data()["kpi"]["spark"]["router_coverage"]
        self.assertEqual(len(spark), 12)
        self.assertEqual((spark[9], spark[10]), (1.0, 0.0))
        self.assertTrue(all(v is None for i, v in enumerate(spark) if i not in (9, 10)))

    def test_with_no_events_the_weekly_charts_are_absent_not_zero(self):
        self.consent()
        self.refresh("run")
        spark = self.data()["kpi"]["spark"]
        self.assertEqual((spark["sessions"], spark["calls"], spark["router_coverage"]), (None, None, None))

    def test_the_rework_share_counts_every_pull_request_not_only_the_newest_eight(self):
        self.consent()
        events = []
        for pr in range(1, 11):
            if pr % 2 == 0:
                events.append(self.event(100 - pr, "a", X, "review", kind="code", verdict="REWORK", pr=pr))
            events.append(self.event(50 - pr, "a", X, "review", kind="code", verdict="APPROVE", pr=pr))
        self.write_events(events)
        self.refresh("run")
        d = self.data()
        self.assertEqual(len(d["reviews"]), 8)
        self.assertEqual(d["review_stats"], {"total": 10, "reworked": 5})

    def test_events_without_skills_say_so_instead_of_blaming_the_hooks(self):
        self.consent()
        self.write_events([self.event(10, "a", X, "first_edit")])
        self.refresh("run")
        self.assertEqual(self.data()["missing"]["use"], "no fnl- skill or agent used in this period")

    def test_a_malformed_ledger_line_does_not_stop_the_refresh(self):
        self.consent()
        start = {"event": "start", "id": "d1", "ts": "garbage", "project": "p", "task": "t", "kind": "implement",
                 "grade": "easy", "agent": "codex", "model": "m", "reason": "routing"}
        finish = {"event": "finish", "id": "d1", "ts": "garbage", "outcome": "accepted", "rework_rounds": 0}
        self.ledger.write_text(json.dumps(start) + "\n" + json.dumps(finish) + "\n")
        self.refresh("run")
        self.assertEqual(self.data()["missing"]["delegation"], "ledger could not be read")

    def test_missing_sources_are_named_not_shown_as_zero(self):
        self.refresh("run")
        d = self.data()
        self.assertIsNone(d["kpi"]["router_coverage"])
        self.assertIsNone(d["kpi"]["sessions"])
        self.assertIn("consent not given", d["missing"]["activity"])
        self.consent()
        self.refresh("run")
        self.assertEqual(self.data()["missing"]["activity"], "no events recorded yet")

    def test_the_written_files_are_ascii_private_and_the_page_is_a_byte_copy(self):
        self.consent()
        self.fixture_store()
        self.refresh("run")
        raw = (self.dir / "data.js").read_bytes()
        self.assertTrue(raw.isascii())
        self.assertEqual(oct((self.dir / "data.js").stat().st_mode & 0o777), "0o600")
        self.assertEqual((self.dir / "dashboard.html").read_bytes(), PAGE.read_bytes())

    def test_a_tampered_store_line_cannot_reach_the_script_file(self):
        self.consent()
        self.fixture_store()
        evil = self.event(5, "z", X, "skill", name="</script><img src=x onerror=alert(1)>")
        with open(next(self.dir.glob("events-*.jsonl")), "a") as handle:
            handle.write(json.dumps(evil) + "\n")
        self.refresh("run")
        text = (self.dir / "data.js").read_text()
        self.assertNotIn("</script", text)
        self.assertNotIn("onerror", text)

    def test_purge_needs_a_yes_and_keeps_consent(self):
        self.consent()
        self.fixture_store()
        self.refresh("run")
        self.assertNotEqual(self.refresh("purge", check=False).returncode, 0)
        self.assertTrue(list(self.dir.glob("events-*")))
        self.refresh("purge", "--yes")
        self.assertEqual([p.name for p in self.dir.iterdir()], ["consent.json"])

    def agy_hook(self, config, *args):
        return self.refresh("antigravity-hook", "--config", str(config), *args, check=False)

    def test_the_antigravity_hook_is_merged_with_a_backup_and_every_other_group_kept(self):
        config = Path(self.tmp.name) / "my config" / "hooks.json"
        config.parent.mkdir()
        others = {"finos": {"Stop": [{"type": "command", "command": "x", "timeout": 5}]}, "hatch": {"PreToolUse": []}}
        config.write_text(json.dumps(others))
        config.chmod(0o640)
        result = self.agy_hook(config, "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(config.read_text())
        self.assertEqual({k: data[k] for k in others}, others)
        group = data["finolabs-vibecode"]
        script = str(ROOT / "scripts/metrics_hook.py")
        self.assertIn(script, group["SessionStart"][0]["command"])
        self.assertIn("--host antigravity --event post_tool_use", group["PostToolUse"][0]["hooks"][0]["command"])
        self.assertEqual(oct(config.stat().st_mode & 0o777), "0o640")
        backups = list(config.parent.glob("hooks.json.finolabs-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), others)
        self.agy_hook(config, "--yes")
        self.assertEqual(len([k for k in json.loads(config.read_text()) if k == "finolabs-vibecode"]), 1)

    def test_the_antigravity_hook_can_be_removed_and_leaves_the_rest(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text(json.dumps({"finos": {"Stop": []}}))
        self.agy_hook(config, "--yes")
        self.assertEqual(self.agy_hook(config, "--remove", "--yes").returncode, 0)
        self.assertEqual(json.loads(config.read_text()), {"finos": {"Stop": []}})

    def test_the_antigravity_hook_is_refused_without_yes_or_for_a_file_that_is_not_a_json_object(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text("{}")
        self.assertNotEqual(self.agy_hook(config).returncode, 0)
        self.assertEqual(config.read_text(), "{}")
        for bad in ("not json", "[1]"):
            config.write_text(bad)
            self.assertNotEqual(self.agy_hook(config, "--yes").returncode, 0)
            self.assertEqual(config.read_text(), bad)
        self.assertEqual(list(config.parent.glob("hooks.json.finolabs-backup-*")), [])

    def test_a_commit_counts_as_a_change_when_files_were_written_through_the_shell(self):
        start = {"host": "claude", "dispatch": None, "source": "startup"}
        self.consent()
        self.write_events([self.event(30, "s", X, "session_start", **start), self.event(29, "s", X, "skill", name="fnl-coding-router"),
                           self.event(20, "s", X, "commit")])
        self.refresh("run")
        self.assertEqual(self.data()["router"]["eligible"], 1)
        self.assertEqual(self.data()["router"]["covered"], 1)

    def test_the_antigravity_hook_is_refused_for_a_skill_outside_the_plugin(self):
        tree = Path(self.tmp.name) / "repo" / ".claude"
        shutil.copytree(ROOT / "skills/fnl-status", tree / "skills/fnl-status")
        (tree / "scripts").mkdir()
        (tree / "scripts/metrics_hook.py").write_text("print('pwned')\n")
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text("{}")
        result = subprocess.run([sys.executable, "-I", str(tree / "skills/fnl-status/scripts/refresh.py"), "antigravity-hook",
                                 "--config", str(config), "--yes"], capture_output=True, text=True, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not inside the finolabs-vibecode plugin", result.stderr)
        self.assertEqual(config.read_text(), "{}")
        self.assertEqual(list(config.parent.glob("hooks.json.finolabs-backup-*")), [])

    def test_a_symlinked_hooks_file_is_edited_in_place_and_stays_a_link(self):
        real = Path(self.tmp.name) / "dotfiles" / "hooks.json"
        real.parent.mkdir()
        real.write_text(json.dumps({"finos": {}}))
        link = Path(self.tmp.name) / "hooks.json"
        link.symlink_to(real)
        self.assertEqual(self.agy_hook(link, "--yes").returncode, 0)
        self.assertTrue(link.is_symlink())
        self.assertIn("finolabs-vibecode", json.loads(real.read_text()))

    def test_a_hooks_file_with_nan_is_refused_and_non_ascii_text_is_kept_readable(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text('{"a": NaN}')
        self.assertNotEqual(self.agy_hook(config, "--yes").returncode, 0)
        self.assertEqual(config.read_text(), '{"a": NaN}')
        config.write_text(json.dumps({"note": "xin chào"}, ensure_ascii=False))
        self.agy_hook(config, "--yes")
        self.assertIn("xin chào", config.read_text())

    def test_a_lone_surrogate_escape_in_the_hooks_file_is_still_written(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text('{"note": "\\ud800"}')
        self.assertEqual(self.agy_hook(config, "--yes").returncode, 0)
        self.assertIn("finolabs-vibecode", json.loads(config.read_text()))

    def test_two_runs_in_one_second_keep_two_backups(self):
        config = Path(self.tmp.name) / "hooks.json"
        config.write_text("{}")
        self.agy_hook(config, "--yes")
        self.agy_hook(config, "--yes")
        self.assertEqual(len(list(config.parent.glob("hooks.json.finolabs-backup-*"))), 2)

    def test_consent_can_be_withdrawn_and_recorded_events_stay_until_purge(self):
        self.consent()
        self.refresh("run")
        self.refresh("consent", "--revoke")
        self.assertFalse((self.dir / "consent.json").exists())
        self.assertNotEqual(self.refresh("consent", check=False).returncode, 0)

    def test_consent_rejects_an_unknown_retention(self):
        self.assertNotEqual(self.refresh("consent", "--retention", "7", check=False).returncode, 0)
        self.assertFalse((self.dir / "consent.json").exists())


class RefreshOverlapTest(unittest.TestCase):
    """Overlapping rebuilds, run in-process with the build replaced so the interleaving is exact."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"FNL_STATE_DIR": str(Path(self.tmp.name) / "state")})
        patcher.start()
        self.addCleanup(patcher.stop)
        spec = importlib.util.spec_from_file_location("fnl_refresh_overlap", REFRESH)
        self.refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.refresh)
        self.state = Path(self.tmp.name) / "state"

    @staticmethod
    def data():
        return {"missing": {}, "period": {"from": "", "to": ""}, "sessions": {"total": 0, "unclassified": 0}, "errors": 0}

    def args(self, throttle=None):
        return mock.Mock(throttle=throttle, open=False)

    def test_a_run_during_a_rebuild_makes_the_holder_rebuild_again_and_the_newest_data_wins(self):
        snapshots = iter(["old", "new"])
        seen = []

        def build():
            value = next(snapshots)
            seen.append(value)
            if value == "old":
                self.refresh.cmd_run(self.args())  # a forced run arrives while the first build is in progress
            return {"snapshot": value, "missing": {}, "period": {"from": "", "to": ""}, "sessions": {"total": 0, "unclassified": 0},
                    "errors": 0}

        with mock.patch.object(self.refresh, "build", build):
            self.refresh.cmd_run(self.args())
        self.assertEqual(seen, ["old", "new"])
        self.assertIn('"snapshot":"new"', (self.state / "data.js").read_text())
        self.assertFalse((self.state / "refresh.dirty").exists())

    def test_a_throttled_run_during_a_rebuild_neither_waits_nor_asks_for_another(self):
        builds = []

        def build():
            builds.append(1)
            if len(builds) == 1:
                self.refresh.cmd_run(self.args(throttle=10))
            return {"missing": {}, "period": {"from": "", "to": ""}, "sessions": {"total": 0, "unclassified": 0}, "errors": 0}

        with mock.patch.object(self.refresh, "build", build):
            self.refresh.cmd_run(self.args())
        self.assertEqual(len(builds), 1)

    def test_a_throttled_run_skips_fresh_data_even_when_it_holds_the_lock(self):
        with mock.patch.object(self.refresh, "build", return_value={"missing": {}, "period": {"from": "", "to": ""},
                                                                       "sessions": {"total": 0, "unclassified": 0}, "errors": 0}) as build:
            self.refresh.cmd_run(self.args())
            self.refresh.cmd_run(self.args(throttle=10))
        self.assertEqual(build.call_count, 1)

    def test_a_lock_file_left_by_a_killed_process_does_not_block(self):
        self.state.mkdir(parents=True)
        (self.state / "refresh.lock").write_text("")  # a file with no live holder holds nothing
        with mock.patch.object(self.refresh, "build", return_value=self.data()) as build:
            self.refresh.cmd_run(self.args())
        self.assertEqual(build.call_count, 1)

    def test_a_forced_run_queued_behind_a_throttled_holder_is_not_throttled_away(self):
        builds = []

        def build():
            builds.append(1)
            if len(builds) == 1:
                self.refresh.cmd_run(self.args())  # forced run arrives while the throttled holder builds
            return self.data()

        with mock.patch.object(self.refresh, "build", build):
            self.refresh.cmd_run(self.args(throttle=10))
        self.assertEqual(len(builds), 2)

    def test_the_dirty_flag_never_follows_a_symlink(self):
        self.state.mkdir(parents=True)
        target = Path(self.tmp.name) / "elsewhere"
        (self.state / "refresh.dirty").symlink_to(target)
        held = self.refresh.take_lock(self.state / "refresh.lock")
        try:
            with mock.patch.object(self.refresh, "build") as build:
                self.refresh.cmd_run(self.args())
        finally:
            os.close(held)
        build.assert_not_called()
        self.assertFalse(target.exists())

    def test_a_symlink_at_the_lock_name_is_refused(self):
        self.state.mkdir(parents=True)
        target = Path(self.tmp.name) / "elsewhere"
        (self.state / "refresh.lock").symlink_to(target)
        self.assertIsNone(self.refresh.take_lock(self.state / "refresh.lock"))
        self.assertFalse(target.exists())

    def test_two_runs_cannot_hold_the_lock_at_once(self):
        self.state.mkdir(parents=True)
        first = self.refresh.take_lock(self.state / "refresh.lock")
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(self.refresh.take_lock(self.state / "refresh.lock"))
        finally:
            os.close(first)
        second = self.refresh.take_lock(self.state / "refresh.lock")
        self.assertIsNotNone(second, "released when the holder closes it")
        os.close(second)

    def test_a_refused_lock_does_not_lose_the_request_to_open_the_page(self):
        self.state.mkdir(parents=True)
        (self.state / "dashboard.html").write_text("<html></html>")
        held = self.refresh.take_lock(self.state / "refresh.lock")
        try:
            with mock.patch.object(self.refresh.webbrowser, "open") as opened, mock.patch.object(self.refresh, "build") as build:
                self.refresh.cmd_run(mock.Mock(throttle=None, open=True))
        finally:
            os.close(held)
        opened.assert_called_once()
        build.assert_not_called()

    def test_a_fresh_lock_held_by_another_process_makes_a_run_return_without_building(self):
        self.state.mkdir(parents=True)
        held = self.refresh.take_lock(self.state / "refresh.lock")
        try:
            with mock.patch.object(self.refresh, "build") as build:
                self.refresh.cmd_run(self.args())
        finally:
            os.close(held)
        build.assert_not_called()
        self.assertTrue((self.state / "refresh.dirty").exists(), "the holder is asked to go round again")


if __name__ == "__main__":
    unittest.main()
