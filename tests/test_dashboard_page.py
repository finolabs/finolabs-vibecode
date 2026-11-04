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

    def sample(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

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
        out = self.render(FIXTURE, {"next": same})
        self.assertFalse(out["redrawn"])
        self.assertIn("generated 2099-01-01T00:00:00+07:00", out["text"])

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