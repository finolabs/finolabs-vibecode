"""Static checks of skills/fnl-status/assets/dashboard.html and its fit with the data refresh.py writes."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "skills/fnl-status/assets/dashboard.html"
FIXTURE = ROOT / "tests/fixtures/status-sample.json"
REFRESH = ROOT / "skills/fnl-status/scripts/refresh.py"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


class DashboardPageTest(unittest.TestCase):
    text = PAGE.read_text(encoding="utf-8")

    def test_it_is_a_complete_document_that_declares_its_encoding(self):
        head = self.text[:600].lower()
        self.assertTrue(head.startswith("<!doctype html>"))
        self.assertIn('<meta charset="utf-8">', head)
        self.assertIn("viewport", head)
        title = re.search(r"<title>([^<]+)</title>", self.text).group(1)
        self.assertTrue(2 <= len(title.split()) <= 4, title)

    def test_it_reaches_nothing_outside_the_page(self):
        urls = [u for u in re.findall(r"https?://[^\s\"')<>]+", self.text) if u != SVG_NAMESPACE]
        self.assertEqual(urls, [])
        self.assertNotRegex(self.text, r"(?:src|href)=[\"']?(?:https?:)?//")

    def test_a_content_security_policy_forbids_network_requests(self):
        policy = re.search(r'Content-Security-Policy" content="([^"]+)"', self.text).group(1)
        self.assertIn("default-src 'none'", policy)
        self.assertNotIn("connect-src", policy)
        self.assertNotIn("unsafe-eval", policy)

    def test_values_never_become_markup(self):
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            self.assertNotIn(banned, self.text)

    def test_the_empty_state_draws_the_plugin_icon(self):
        icon = (ROOT / "assets/icon.svg").read_text(encoding="utf-8")
        for shape in re.findall(r' d="([^"]+)"', icon) + re.findall(r'<rect ([^/]+)/>', icon)[:1]:
            if shape.startswith("M"):
                self.assertIn(shape, self.text)
        self.assertIn('x: 36, y: 54, width: 20, height: 20, rx: 4', self.text)

    def test_it_reads_only_the_sibling_data_file(self):
        self.assertIn('<script src="data.js"></script>', self.text)
        self.assertIn('"data.js?t="', self.text)
        self.assertIn("window.FNL_DATA", self.text)

    def test_the_sample_data_has_exactly_the_keys_refresh_writes(self):
        spec = importlib.util.spec_from_file_location("fnl_refresh", REFRESH)
        refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(refresh)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"FNL_STATE_DIR": tmp + "/state",
                                                                               "ORCHESTRATION_LEDGER": tmp + "/none.jsonl"}):
            account(self, Path(tmp) / "home")
            built = refresh.build()
        sample = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(set(sample), set(built))
        self.assertEqual(set(sample["kpi"]), set(built["kpi"]))
        self.assertEqual(set(sample["kpi"]["spark"]), set(built["kpi"]["spark"]))
        self.assertEqual(set(sample["delegation"][0]), {"agent", "model", "grade", "runs", "first_pass", "quota", "error", "median_min", "rework"})

    def test_every_key_in_the_data_is_read_by_the_page(self):
        sample = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for key in sample:
            self.assertIn("D." + key, self.text, "the page never reads " + key)


RUNNER = ROOT / "tests/page_runner.js"


@unittest.skipUnless(shutil.which("node") or Path("/opt/homebrew/bin/node").exists(), "node is not installed")
class DashboardScriptTest(unittest.TestCase):
    """Runs the page's own script in node against a small fake DOM."""

    @staticmethod
    def render(data=None, scenario=None):
        node = shutil.which("node") or "/opt/homebrew/bin/node"
        args = [node, str(RUNNER), str(PAGE), str(data) if data else ""]
        if scenario is not None:
            handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            json.dump(scenario, handle)
            handle.close()
            args.append(handle.name)
        done = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if done.returncode:
            raise AssertionError(done.stderr[-800:])
        return json.loads(done.stdout)

    def test_the_sample_data_draws_every_chart_without_an_error(self):
        out = self.render(FIXTURE)
        for expected in ("Router coverage", "events per day", "October 2026", "skill and agent use", "fnl-coding-router",
                         "7 tasks kept by the coordinator in 3 receipts; 14 implementation runs handed off",
                         "claude / needs-context / table"):
            self.assertIn(expected, out["text"])
        self.assertNotIn("No data yet", out["text"])
        self.assertGreaterEqual(out["cells"], 28)
        self.assertGreater(out["svg"], 0)

    def test_without_data_the_page_shows_the_empty_state_and_its_skeleton(self):
        out = self.render()
        self.assertIn("No data yet", out["text"])
        self.assertIn("no data:", out["text"])
        self.assertGreaterEqual(out["cells"], 35)

    def test_a_source_with_no_data_shows_its_reason_and_the_rest_still_draws(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["router"] = None
        data["missing"] = {"router": "no session with an edit in this period"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            out = self.render(path)
        self.assertIn("no data: no session with an edit in this period", out["text"])
        self.assertIn("fnl-coding-router", out["text"])

    def test_kept_work_shows_even_when_no_dispatch_has_finished(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["delegation"] = None
        data["kept"]["handed_off"] = 1
        data["missing"] = {"delegation": "no finished runs in this period"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            out = self.render(path)
        self.assertIn("7 tasks kept", out["text"])
        self.assertIn("1 implementation run handed off", out["text"])
        self.assertIn("no data: no finished runs in this period", out["text"])

    def judge_data(self, receipts=True):
        data = json.loads(FIXTURE.read_text())
        data["delegation"] = None
        data["judge"] = {"receipts": 3 if receipts else 0, "note": "No receipts were recorded.", "outcome_note": "",
                         "outcome_association": [dict(route_by="judge", runs=4, first_pass=.5, small=True),
                                                 dict(route_by="table", runs=5, first_pass=.6, small=False)]}
        if receipts:
            data["judge"].update(use=[dict(site="route", grader="judge", count=2), dict(site="route", grader="agent", count=1)],
                                 usable_answers=dict(validated=1, calls=2, share=.5),
                                 followed=dict(yes=1, validated=1, share=1))
        return data

    def render_judge(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.json"
            path.write_text(json.dumps(data))
            return self.render(path)

    def test_judge_pane_only_with_data_and_small_groups_are_open_rings(self):
        self.assertNotIn("Outcome association", self.render(FIXTURE)["text"])
        self.assertNotIn("Outcome association", self.render()["text"])
        out = self.render_judge(self.judge_data())
        for label in ("Judge", "Use", "Usable answers", "Followed", "Outcome association", "50% (1/2)",
                      "100% (1/1)", "judge · n=4", "table · n=5", "Not measured: cost, latency and accuracy.",
                      "not proof the judge was right", "not judged"):
            self.assertIn(label, out["text"])
        self.assertEqual(out["openRings"], 1)

    def test_judge_without_receipts_shows_only_association_and_escapes_values(self):
        data = self.judge_data(False)
        out = self.render_judge(data)
        self.assertIn("No receipts were recorded.", out["text"])
        self.assertIn("Outcome association", out["text"])
        self.assertNotIn("Usable answers", out["text"])
        self.assertNotIn("Followed", out["text"])
        attack = "<img src=x onerror=alert(1)>"
        for receipts in (False, True):
            data = self.judge_data(receipts)
            data["judge"]["note"] = attack
            data["judge"]["outcome_association"][0]["route_by"] = attack
            if receipts:
                data["judge"]["use"][0]["site"] = attack
                data["judge"]["use"][0]["grader"] = attack
            out = self.render_judge(data)
            self.assertIn(attack, out["text"])
            self.assertNotIn("img", out["tags"])
            self.assertNotIn("script", out["tags"])

    def sample(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    # Acceptance 3: fake clock exercises both warning thresholds without new data.
    def freshness_data(self):
        data = self.sample()
        data["freshness"] = {"built_at": "2026-11-06T10:00:00Z", "latest_event": {
            "codex": "2026-11-06T09:45:00Z", "claude": "2026-11-06T10:00:00Z"},
            "ledger_age_seconds": 120, "quota_age_seconds": 14400}
        return data

    def render_freshness(self, data, scenario=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.json"
            path.write_text(json.dumps(data))
            return self.render(path, scenario)

    def test_freshness_line_and_quiet_warning_advance_with_fake_clock(self):
        data = self.freshness_data()
        initial = self.render_freshness(data, {"now": "2026-11-06T10:00:00Z"})
        for value in ("built 2026-11-06T10:00:00Z", "Codex: last event 2026-11-06T09:45:00Z",
                      "ledger: 2 minutes old", "quota: 240 minutes old"):
            self.assertIn(value, initial["text"])
        self.assertNotIn("hooks may need trust", initial["text"])
        self.assertNotIn("it updates while a session runs tools", initial["text"])
        later = self.render_freshness(data, {"now": "2026-11-06T10:00:00Z", "advance_ms": 65000, "fail": True})
        self.assertIn("Codex: last event 2026-11-06T09:45:00Z; hooks may need trust", later["text"])
        self.assertNotIn("Claude Code: last event 2026-11-06T10:00:00Z; hooks may need trust", later["text"])
        self.assertIn("data is 1 minute old; it updates while a session runs tools", later["text"])
        self.assertIn("ledger: 3 minutes old", later["text"])
        self.assertFalse(later["redrawn"])
        quiet = self.render_freshness(data, {"now": "2026-11-06T10:16:00Z"})
        self.assertNotIn("hooks may need trust", quiet["text"], "no host is active")

    def test_freshness_stale_message_waits_for_visible_tab_and_rechecks_on_return(self):
        data = self.freshness_data()
        hidden = self.render_freshness(data, {"now": "2026-11-06T10:02:00Z", "hidden": True})
        self.assertNotIn("it updates while a session runs tools", hidden["text"])
        visible = self.render_freshness(data, {"now": "2026-11-06T10:02:00Z", "hidden": True, "reveal": True})
        self.assertIn("data is 2 minutes old; it updates while a session runs tools", visible["text"])

    def test_freshness_host_and_value_are_text_and_missing_times_are_named(self):
        data = self.freshness_data()
        attack = "<img src=x onerror=alert(1)>"
        data["freshness"].update(built_at=attack, latest_event={attack: attack},
                                 ledger_age_seconds=attack, quota_age_seconds=None)
        out = self.render_freshness(data)
        self.assertGreaterEqual(out["text"].count(attack), 4)
        self.assertIn("quota: no reading", out["text"])
        self.assertNotIn("img", out["tags"])
        self.assertNotIn("script", out["tags"])

    def test_a_visible_tab_polls_every_five_seconds_and_redraws_new_numbers(self):
        changed = self.sample()
        changed["sessions"]["with_edits"] = 98765
        out = self.render(FIXTURE, {"next": changed})
        self.assertEqual(out["poll_ms"], [5000])
        self.assertEqual(len(out["loads"]), 1)
        self.assertRegex(out["loads"][0], r"^data\.js\?t=\d+$")
        self.assertTrue(out["redrawn"])
        self.assertIn("with edits 98765", out["text"])

    def test_a_new_build_with_the_same_numbers_only_updates_the_generated_time(self):
        same = self.sample()
        same["generated"] = "2099-01-01T00:00:00+07:00"
        same["freshness"].update(built_at=same["generated"], ledger_age_seconds=180,
                                 latest_event={"antigravity": same["generated"]})
        out = self.render(FIXTURE, {"next": same})
        self.assertFalse(out["redrawn"])
        self.assertIn("generated 2099-01-01T00:00:00+07:00", out["text"])
        self.assertIn("built 2099-01-01T00:00:00+07:00", out["text"])
        self.assertIn("Antigravity: last event 2099-01-01T00:00:00+07:00", out["text"])
        self.assertIn("ledger: 3 minutes old", out["text"])

    def test_a_hidden_tab_loads_nothing(self):
        changed = self.sample()
        changed["sessions"]["with_edits"] = 98765
        out = self.render(FIXTURE, {"hidden": True, "next": changed})
        self.assertEqual(out["loads"], [])
        self.assertNotIn("98765", out["text"])

    def test_a_failed_load_keeps_the_page_and_the_next_poll_tries_again(self):
        out = self.render(FIXTURE, {"fail": True, "ticks": 2})
        self.assertEqual(len(out["loads"]), 2)
        self.assertFalse(out["redrawn"])
        self.assertIn("fnl-coding-router", out["text"])

    def test_the_empty_page_draws_the_data_once_it_arrives(self):
        out = self.render(None, {"next": self.sample()})
        self.assertNotIn("No data yet", out["text"])
        self.assertIn("fnl-coding-router", out["text"])


if __name__ == "__main__":
    unittest.main()