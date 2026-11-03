"""Static checks of skills/fnl-status/assets/dashboard.html and its fit with the data refresh.py writes."""

import importlib.util
import json
import os
import re
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


if __name__ == "__main__":
    unittest.main()
