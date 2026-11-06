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
    text = PAGE.read_text(encoding="utf-8") + (PAGE.parent / "dashboard.js").read_text(encoding="utf-8")

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

    def test_local_script_has_no_inline_script_or_handler(self):
        html = PAGE.read_text()
        self.assertEqual(re.findall(r'<script\b[^>]*src="([^"]+)"', html), ['data.js', 'dashboard.js'])
        self.assertNotRegex(html, r'<script\s*>|<link\b|<[^>]+\son[a-z]+\s*=')
        self.assertIn('new Map([', self.text)
        self.assertNotRegex(self.text, r'querySelector(?:All)?\([^"\']')

    def test_narrow_tab_strip_is_bounded_and_scrolls_inside_the_page(self):
        # CSS contract: a shrinkable grid track bounds the flex strip; labels do
        # not shrink, so only the strip scrolls when their total width exceeds it.
        def rule(selector):
            return re.search(re.escape(selector) + r" \{([^}]+)\}", self.text).group(1)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", rule(".screen"))
        for declaration in ("min-width: 0", "max-width: 100%", "overflow-x: auto"):
            self.assertIn(declaration, rule(".tablist"))
        self.assertIn("flex: 0 0 auto", rule(".tablist button"))
        self.assertIn("min-width: 0", rule(".tabpanel"))

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

    def test_rich_fixture_covers_infographic_acceptance(self):
        data = json.loads(FIXTURE.read_text())
        self.assertEqual(len(data['running']['open']), 3)
        self.assertEqual(len(data['running']['quota']), 3)
        self.assertTrue(any(r['no_process_found'] for r in data['running']['open']))
        projects = list(data['progress']['repositories'].values())
        self.assertEqual(sum(not p['done'] for p in projects), 2)
        self.assertTrue(any(f['done'] == f['total'] for p in projects for f in p['features']))
        self.assertIn('</script>', json.dumps(data['running']))
        self.assertIn('</script>', json.dumps(data['progress']))

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

    def test_tabs_map_every_pane_and_share_the_header(self):
        out = self.render(FIXTURE)
        names = ["overview", "agents", "project", "delegation", "reviews"]
        self.assertEqual([t["text"].split()[0] for t in out["tabs"]], [n.title() for n in names])
        expected = [["activity", "router coverage", "skill and agent use", "depth vs outcome", "load cost"],
                    ["running now"], ["project progress"],
                    ["delegation", "Judge"], ["review gate"]]
        for index, (tab, panel, panes) in enumerate(zip(out["tabs"], out["panels"], expected)):
            self.assertEqual(tab["attrs"]["aria-controls"], panel["attrs"]["id"])
            self.assertEqual(panel["attrs"]["id"], "panel-" + names[index])
            self.assertEqual(panel["attrs"]["aria-labelledby"], tab["attrs"]["id"])
            self.assertEqual(panel["hidden"], index != 0)
            self.assertEqual(tab["attrs"]["aria-selected"], str(index == 0).lower())
            self.assertEqual(tab["tabIndex"], 0 if index == 0 else -1)
            for pane in panes:
                self.assertIn(pane, panel["text"])
        self.assertIn("cmd", out["shared"])
        self.assertIn("kpis", out["shared"])
        for panel in out["panels"]:
            self.assertNotIn("Router coverage", panel["text"])
        self.assertIn("veil", self.render()["shared"])

    def test_click_keyboard_and_hash_navigation(self):
        actions = [{"click": "Agents"}, {"tab": "Agents", "key": "ArrowRight"},
                   {"tab": "Project", "key": "Enter"}, {"tab": "Project", "key": "End"},
                   {"tab": "Reviews", "key": " "}, {"tab": "Reviews", "key": "ArrowRight"},
                   {"tab": "Overview", "key": "Home"}, {"tab": "Overview", "key": "ArrowLeft"},
                   {"hash": "#delegation"}]
        out = self.render(FIXTURE, {"actions": actions})
        self.assertEqual([s["selected"] for s in out["states"]],
                         [["Agents"], ["Agents"], ["Project"], ["Project"], ["Reviews"],
                          ["Reviews"], ["Reviews"], ["Reviews"], ["Delegation"]])
        self.assertEqual([s["focused"] for s in out["states"]][1:8],
                         ["Project", "Project", "Reviews", "Reviews", "Overview", "Overview", "Reviews"])
        self.assertEqual(out["stored"]["fnl-tab"], "delegation")

    def test_hash_storage_validation_and_blocked_storage(self):
        for name in ("overview", "agents", "project", "delegation", "reviews"):
            for scenario in ({"hash": "#" + name, "stored": {"fnl-tab": "reviews"}},
                             {"stored": {"fnl-tab": name}}, {"hash": "#" + name, "storageThrows": True}):
                with self.subTest(scenario=scenario):
                    out = self.render(FIXTURE, scenario)
                    self.assertEqual([t["text"].split()[0] for t in out["tabs"] if t["attrs"]["aria-selected"] == "true"], [name.title()])
        for bad in ("unknown", "__proto__", "constructor", "<img src=hash onerror=alert(2)>", "'][role=tab]", "%3Csvg%3E"):
            for scenario in ({"hash": "#" + bad, "stored": {"fnl-tab": "agents"}},
                             {"stored": {"fnl-tab": bad}}, {"actions": [{"hash": "#" + bad}]}):
                with self.subTest(scenario=scenario):
                    out = self.render(FIXTURE, scenario)
                    self.assertEqual([t["text"].split()[0] for t in out["tabs"] if t["attrs"]["aria-selected"] == "true"], ["Overview"])
                    self.assertNotIn(bad, out["text"])
                    self.assertNotIn(bad, json.dumps([t["attrs"] for t in out["tabs"]] + [p["attrs"] for p in out["panels"]]))
        out = self.render(FIXTURE, {"storageThrows": True, "actions": [{"click": "Reviews"}]})
        self.assertFalse(out["panels"][4]["hidden"])

    def test_reload_preserves_tab_panel_scroll_and_each_open_table(self):
        changed = self.sample()
        changed["sessions"]["with_edits"] = 98765
        out = self.render(FIXTURE, {"next": changed, "ticks": 2, "after": [{"click": "Overview"}, {"click": "Delegation"}], "actions": [
            {"panel": "overview", "scrollTop": 160, "open": True}, {"click": "Delegation"},
            {"panel": "delegation", "scrollTop": 240, "scrollLeft": 12, "open": True}]})
        self.assertFalse(out["panels"][3]["hidden"])
        self.assertEqual(out["panels"][0]["scrollTop"], 160)
        self.assertEqual(out["panels"][3]["scrollTop"], 240)
        self.assertEqual(out["panels"][3]["scrollLeft"], 12)
        self.assertEqual(out["panels"][0]["open"], [True])
        self.assertEqual(out["panels"][3]["open"], [True])
        self.assertIn("with edits 98765", out["text"])
        self.assertEqual(out["poll_ms"], [5000])

    def test_reload_keeps_keyboard_focus_independent_of_selection(self):
        changed = self.sample()
        changed["sessions"]["with_edits"] = 98765
        out = self.render(FIXTURE, {"next": changed, "actions": [{"tab": "Overview", "key": "ArrowRight"}]})
        self.assertEqual(out["focused"], "Agents")
        self.assertEqual([tab["tabIndex"] for tab in out["tabs"]], [-1, 0, -1, -1, -1])
        self.assertFalse(out["panels"][0]["hidden"])

    def test_placeholder_counts_only_when_sources_exist(self):
        data = self.sample()
        data.update(running={"processes": [{}, {}], "open": [{}]}, progress={"in_progress": 4})
        out = self.render_freshness(data)
        self.assertEqual([t["text"] for t in out["tabs"]], ["Overview", "Agents 3", "Project 4", "Delegation", "Reviews"])
        data.update(running={"processes": [], "open": []}, progress={"in_progress": 0})
        self.assertEqual([t["text"] for t in self.render_freshness(data)["tabs"]][1:3], ["Agents 0", "Project 0"])
        for source in (None,):
            out = self.render(source)
            self.assertEqual([t["text"] for t in out["tabs"]][1:3], ["Agents", "Project"])
            self.assertIn("no data: not available yet", out["panels"][1]["text"])
            self.assertIn("no data: not available yet", out["panels"][2]["text"])

    @staticmethod
    def marks(out, cls, disclosure=None):
        return [m for m in out['picture'] if cls in m['cls'].split() and m['disclosure'] == disclosure]

    def test_reviews_cap_chains_project_labels_and_live_hash_changes(self):
        out = self.render(FIXTURE, {'hash': '#agents', 'actions': [{'hash': '#reviews'}, {'hash': '#project'}, {'hash': '#__proto__'}, {'hash': '#reviews'}]})
        self.assertEqual([state['selected'] for state in out['states']], [['Reviews'], ['Project'], ['Overview'], ['Reviews']])
        chains = self.marks(out, 'seq')
        self.assertEqual(chains[0]['attrs']['data-dots'], '8')
        self.assertEqual(self.marks(out, 'more-rounds')[0]['text'], '+6')
        labels = self.marks(out, 'review-label')
        self.assertTrue(labels[0]['text'].startswith('Fino tools '))
        self.assertNotIn('aaaaaaaa', labels[0]['text'])
        self.assertIn('white-space: nowrap', re.search(r'\.rv \.review-label \{([^}]+)', PAGE.read_text())[1])
        self.assertIn('14 rounds', chains[0]['attrs']['data-tip'])
        table = self.marks(out, 'tbl', 'show the data as tables')
        self.assertTrue(any('REWORK → REWORK' in row['text'] for row in table))

    def test_agents_infographics_lanes_kpis_quota_and_hostile_values(self):
        out = self.render(FIXTURE, {'hash': '#agents', 'now': '2026-11-06T10:00:00Z'})
        lanes = self.marks(out, 'lane')
        self.assertEqual([m['attrs']['data-run'] for m in lanes],
                         ['</script><img src=x onerror=alert(1)>', 'run2', 'run1'])
        self.assertEqual([m['style']['left'] for m in self.marks(out, 'lane-tick')], ['50%'] * 3)
        self.assertEqual([m['style']['background'] for m in self.marks(out, 'lane-bar')],
                         ['var(--crit)', 'var(--warn)', 'var(--p)'])
        self.assertEqual([m['text'] for m in self.marks(out, 'agent-value')], ['3', '2', '1'])
        self.assertEqual(len(self.marks(out, 'process-dot')), 3)
        self.assertEqual(len(self.marks(out, 'no-process')), 1)
        quota = self.marks(out, 'quota-meter')
        self.assertEqual(len(quota), 3)
        self.assertEqual([m['attrs']['aria-valuenow'] for m in quota], ['68', '8', '42'])
        bars = self.marks(out, 'quota-bar')
        self.assertEqual(bars[1]['style']['background'], 'var(--crit)')
        self.assertIn('hollow', quota[2]['cls'])
        self.assertIn('unverified', quota[2]['attrs']['data-tip'])
        self.assertTrue(any('</script>' in m['attrs'].get('data-tip', '') for m in lanes))
        tables = self.marks(out, 'tbl', 'show the data as tables')
        self.assertTrue(any('agent state' in row['text'] and 'past the check time' in row['text'] for row in tables))
        self.assertTrue(any('process roots' in row['text'] and 'descendants' in row['text'] for row in tables))
        limits = self.marks(out, 'running-limits', 'limits')
        self.assertEqual(len(limits), 1)
        self.assertIn('machine-wide', limits[0]['text'])
        self.assertIn('not started by the coordinator', limits[0]['text'])
        self.assertTrue(any('quota' in m['text'] for m in self.marks(out, 'tbl', 'show the data as tables')))
        self.assertNotIn('img', out['tags'])
        self.assertNotIn('script', out['tags'])

    def test_agents_empty_state_and_omitted_quota(self):
        data = self.sample()
        data['running'] = dict(open=[], processes=[], snapshot=dict(reason='snapshot off'), ledger_note='')
        out = self.render_freshness(data, {'hash': '#agents'})
        self.assertEqual(len(self.marks(out, 'ghost-lane')), 3)
        self.assertIn('No agents running', out['panels'][1]['text'])
        self.assertEqual([m['text'] for m in self.marks(out, 'agent-value')], ['0', '0', '0'])
        self.assertEqual(self.marks(out, 'quota-meter'), [])
        self.assertTrue(all('alert' not in m['text'] for m in self.marks(out, 'agent-value')))

    def test_project_infographics_priority_cells_hidden_work_and_tables(self):
        out = self.render(FIXTURE, {'hash': '#project'})
        projects = self.marks(out, 'proj')
        self.assertEqual([p['attrs']['data-repo'] for p in projects], ['bbbbbbbb', 'aaaaaaaa'])
        self.assertEqual([p['text'] for p in self.marks(out, 'project-percent')], ['33%', '43%'])
        self.assertEqual([p['attrs']['data-story'] for p in self.marks(out, 'story')], ['US1', 'US2', 'US1', 'US3'])
        self.assertEqual([p['text'] for p in self.marks(out, 'story-label')], ['US1 · P1', 'US2 · P3', 'US1 · P2', 'US3'])
        self.assertEqual([p['attrs']['data-task'] for p in self.marks(out, 'cell')],
                         ['T011', 'T012', 'T010', 'T001', 'T003', 'T004', 'T002', 'T006'])
        self.assertEqual([p['text'] for p in self.marks(out, 'finished-projects')], ['2 projects done, hidden'])
        self.assertEqual([p['text'] for p in self.marks(out, 'finished-stories')], ['1 stories done'])
        self.assertEqual(len(self.marks(out, 'unlinked-sessions')), 2)
        self.assertEqual(len(self.marks(out, 'project-segments')), 2)
        tips = [p['attrs']['data-tip'] for p in self.marks(out, 'cell')]
        self.assertTrue(any(all(t in tip for t in ('T002', 'in progress', 'codex', 'session1', '</script>')) for tip in tips))
        tables = [p for p in out['picture'] if p['disclosure'] == 'show the data as tables']
        self.assertTrue(any('project completion' in p['text'] and '43%' in p['text'] for p in tables))
        self.assertTrue(any('T090' in p['text'] for p in tables), 'finished feature remains in the data equivalent')
        self.assertTrue(any('feature 009' in p['text'] for p in tables))
        self.assertFalse(any(p['tag'] == 'table' and p['disclosure'] is None for p in out['picture']))
        limits = self.marks(out, 'project-limits', 'limits')
        self.assertEqual(len(limits), 1)
        self.assertIn('nothing leaves your machine', limits[0]['text'])
        self.assertNotIn('img', out['tags'])
        self.assertNotIn('script', out['tags'])

    def test_project_empty_no_ghost_and_priority_tie_uses_latest_activity(self):
        data = self.sample()
        repos = data['progress']['repositories']
        repos['aaaaaaaa']['features'][0]['stories'][0]['priority'] = 1
        out = self.render_freshness(data, {'hash': '#project'})
        self.assertEqual([p['attrs']['data-repo'] for p in self.marks(out, 'proj')], ['aaaaaaaa', 'bbbbbbbb'])
        # A later local run wins a priority tie even when its snapshot is older.
        repos['bbbbbbbb']['features'][0]['tasks'][1]['runs'][0]['start'] = '2026-11-06T12:00:00Z'
        out = self.render_freshness(data, {'hash': '#project'})
        self.assertEqual([p['attrs']['data-repo'] for p in self.marks(out, 'proj')], ['bbbbbbbb', 'aaaaaaaa'])
        data['progress']['repositories'] = {'aaaaaaaa': dict(features=[], reason='')}
        out = self.render_freshness(data, {'hash': '#project'})
        self.assertIn('No tasks.md found for this repository', out['panels'][2]['text'])
        self.assertEqual(self.marks(out, 'proj'), [])
        self.assertFalse(any('ghost' in p['cls'] for p in out['picture'] if p.get('panel') == 'panel-project'))

    def test_motion_scoped_to_visible_tab_and_once_per_changed_data(self):
        page = PAGE.read_text()
        self.assertRegex(page, r'@media \(prefers-reduced-motion: reduce\)\s*\{\s*\*, \*::before, \*::after \{ animation: none !important; transition: none !important;')
        for selector, body in re.findall(r'([^{}]+)\{([^{}]+)\}', page.split('</style>')[0]):
            if 'animation:' in body and any(name in body for name in ('amount-grow', 'lane-sweep', 'cell-breathe')):
                self.assertTrue(all('.tabpanel:not([hidden])' in part for part in selector.split(',')))
        out = self.render(FIXTURE, {'actions': [{'click': 'Agents'}, {'click': 'Project'}]})
        self.assertTrue(all(p['attrs'].get('data-enter') != 'true' for p in out['panels'] if p['hidden']))
        again = self.render(FIXTURE, {'actions': [{'click': 'Agents'}, {'click': 'Overview'}, {'click': 'Agents'}]})
        self.assertEqual(again['panels'][1]['attrs'].get('data-enter'), 'false')
        self.assertTrue(any('active' in p['cls'].split() for p in self.marks(out, 'cell')))

    def test_running_panel_off_and_failed_snapshots_do_not_claim_zero_processes(self):
        for reason in ('snapshot off', 'ps timed out'):
            data = self.sample()
            data['running'] = dict(processes=[], open=[], snapshot=dict(time='now', reason=reason, apps={}), ledger_note='')
            out = self.render_freshness(data)
            self.assertIn(reason, out['panels'][1]['text'])
            self.assertNotIn('No command-line agent processes found', out['panels'][1]['text'])
            self.assertNotIn('processes named claude: 0', out['panels'][1]['text'])

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