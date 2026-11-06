"""Static checks of skills/fnl-status/assets/dashboard.html and its fit with the data refresh.py writes."""

from collections import Counter
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
        self.assertEqual(sorted(r['age_min'] for r in data['running']['open']), [5, 20, 31, 45])
        self.assertTrue(all(r['budget_min'] == 30 for r in data['running']['open']))
        first, second = [data['progress']['repositories'][key] for key in ('aaaaaaaa', 'bbbbbbbb')]
        self.assertEqual(sum(len(f['stories']) for f in first['features']), 5)
        self.assertEqual(sum(len(f['stories']) for f in second['features']), 2)
        stories = [story for f in first['features'] for story in f['stories']]
        self.assertIn(45, [story['total'] for story in stories])
        self.assertIn(14, [story['total'] for story in stories])
        self.assertIn(3, [story['total'] for story in stories])
        self.assertEqual({t['state'] for t in first['features'][0]['tasks'] if t['story'] == 'US1'}, {'done', 'in progress', 'accepted, not ticked', 'todo'})
        self.assertEqual(len(data['running']['quota']), 3)
        self.assertTrue(any(r['no_process_found'] for r in data['running']['open']))
        projects = list(data['progress']['repositories'].values())
        self.assertEqual(sum(not p['done'] for p in projects), 3)
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
                    self.assertNotIn(bad, " ".join(t["text"] for t in out["tabs"]))
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
        self.assertIn("with edits 98765", self.footer_text(out))
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
        data.update(running={"processes": [{}, {}], "open": [{}]}, progress={"in_progress": 0, "active": [dict(repo="aaaaaaaa", label="Active", hosts=["codex"], sessions=1, last="2026-11-06T10:00:00Z", percent=None)]})
        out = self.render_freshness(data)
        self.assertEqual([t["text"] for t in out["tabs"]], ["Overview", "Agents 1", "Project 1", "Delegation", "Reviews"])
        data.update(running={"processes": [], "open": []}, progress={"in_progress": 0})
        self.assertEqual([t["text"] for t in self.render_freshness(data)["tabs"]][1:3], ["Agents 0", "Project 0"])
        for source in (None,):
            out = self.render(source)
            self.assertEqual([t["text"] for t in out["tabs"]][1:3], ["Agents", "Project"])
            self.assertIn("no data: not available yet", out["panels"][1]["text"])
            self.assertIn("no data: not available yet", out["panels"][2]["text"])

    @staticmethod
    def marks(out, cls, disclosure=None):
        return [m for m in out['picture'] if cls in m['cls'].split() and
                (m['disclosure'] == disclosure if disclosure is not None else
                 m['disclosure'] not in ('show the data as tables', 'limits'))]

    @classmethod
    def info_text(cls, out, tab):
        return next(m['tooltip'] for m in cls.marks(out, 'info-button')
                    if m['panel'] == 'panel-' + tab and not m['tooltip'].startswith('sources '))

    @classmethod
    def footer_text(cls, out):
        return next(m['tooltip'] for m in cls.marks(out, 'info-button')
                    if m['tooltip'].startswith('sources '))

    def test_info_buttons_replace_limits_and_preserve_each_tabs_text(self):
        out = self.render(FIXTURE, {'now': '2026-11-06T10:00:00Z'})
        buttons = self.marks(out, 'info-button')
        self.assertEqual(len(buttons), 3)
        for button in buttons:
            self.assertEqual(button['tag'], 'button')
            self.assertEqual(button['text'], 'ⓘ')
            for key, value in {'type': 'button', 'tabindex': '0',
                               'aria-describedby': 'tip', 'aria-expanded': 'false'}.items():
                self.assertEqual(button['attrs'][key], value)
        self.assertIn('machine-wide, current user only', self.info_text(out, 'agents'))
        self.assertIn('liveness is advisory', self.info_text(out, 'agents'))
        self.assertIn('not accepted remains unfinished', self.info_text(out, 'project'))
        for tab in ('agents', 'project'):
            button = next(m for m in buttons if m['panel'] == 'panel-' + tab)
            self.assertEqual(button['spec']['title'], 'How to read this')
            self.assertLessEqual(len(button['spec']['items']), 5)
            self.assertTrue(all(len(item) < 100 for item in button['spec']['items']))
            self.assertNotIn(button['spec']['items'][0], out['text'])
        self.assertFalse(any(p['tag'] == 'details' and 'limits' in p['cls'].split() for p in out['picture']))
        self.assertNotIn('.limits', PAGE.read_text())
        for text in ('indicative', 'events per day', 'from the dispatch ledger'):
            self.assertIn(text, out['text'])
        css = PAGE.read_text()
        self.assertRegex(css, r'\.info-button \{[^}]*width: 14px; height: 14px;')
        self.assertIn('white-space: pre-line', re.search(r'#tip \{([^}]+)', css)[1])

    def test_info_tooltip_opens_by_keyboard_hover_and_tap_and_dismisses(self):
        for tab in ('agents', 'project', 'footer'):
            with self.subTest(tab=tab):
                actions = [dict(scope=tab, tooltip=event) for event in
                           ('focus', 'escape', 'hover', 'blur', 'hover', 'leave', 'tap', 'tap', 'tap', 'outside')]
                out = self.render(FIXTURE, {'hash': '#' + (tab if tab != 'footer' else 'overview'), 'actions': actions})
                self.assertEqual([state['hidden'] for state in out['tipStates']],
                                 [False, True, True, True, False, True, False, True, False, True])
                text = self.footer_text(out) if tab == 'footer' else self.info_text(out, tab)
                self.assertEqual(' '.join(out['tipStates'][0]['text'].split()), ' '.join(text.split()))
                self.assertEqual(out['tipStates'][0]['attrs']['role'], 'tooltip')
                self.assertEqual(' '.join(out['tipStates'][6]['text'].split()), ' '.join(text.split()))
                self.assertFalse(out['tipStates'][6]['hidden'])
                self.assertTrue(all(button['attrs']['aria-expanded'] == 'false' for button in self.marks(out, 'info-button')))

    def test_info_tooltip_stays_open_when_tapped_or_hovered_to_read_it(self):
        out = self.render(FIXTURE, {'actions': [dict(tooltip='hover'), dict(tooltip='surface'), dict(tooltip='outside')]})
        self.assertEqual([state['hidden'] for state in out['tipStates']], [False, False, True])
        self.assertEqual(out['tipStates'][0]['text'], out['tipStates'][1]['text'])

    def test_capacity_values_have_focusable_exact_text_equivalents(self):
        out = self.render(FIXTURE, {'now': '2026-11-06T10:00:00Z'})
        meters = self.marks(out, 'quota-bricks')
        for meter, value in zip(meters, ('68%', '8%', '42%')):
            self.assertIn('remaining: ' + value, meter['attrs']['aria-label'])
            self.assertEqual(meter['attrs']['role'], 'img')
            self.assertEqual(meter['attrs']['tabindex'], '0')
        self.assertIn('unverified', meters[2]['attrs']['aria-label'])
        slots = self.marks(out, 'slots')[0]
        self.assertEqual(slots['attrs']['aria-label'], '4 of 5 slots lit')
        self.assertEqual(slots['attrs']['tabindex'], '0')
        marker = self.marks(out, 'no-process')[0]
        self.assertEqual(marker['attrs']['aria-label'], 'no process found')
        self.assertEqual(marker['attrs']['aria-hidden'], 'false')
        self.assertEqual(marker['attrs']['role'], 'img')
        self.assertEqual(marker['attrs']['tabindex'], '0')
        out = self.render(FIXTURE, {'actions': [dict(tooltip='focus', target='quota-bricks')]})
        self.assertIn('68%', out['tipStates'][0]['text'])

    def test_budget_studs_are_bounded_and_huge_or_nonfinite_is_unknown(self):
        data = self.sample()
        template = data['running']['open'][0]
        for budget, studs, state in ((5e9, 1, 'unknown'), (1000000, 60, 'within'), (800, 60, 'within'),
                                     (None, 1, 'unknown'), (0, 1, 'unknown')):
            with self.subTest(budget=budget):
                data['running']['open'] = [dict(template, budget_min=budget)]
                out = self.render_freshness(data)
                self.assertEqual(self.marks(out, 'lane-stud'), [])
                self.assertEqual(self.marks(out, 'lane')[0]['attrs']['data-state'], state)
                if state == 'unknown':
                    self.assertEqual(self.marks(out, 'lane-value')[0]['text'], '5/? m')
                    self.assertEqual(self.marks(out, 'lane-tick'), [])
                    self.assertIn('budget: unknown', self.marks(out, 'lane')[0]['tooltip'])
        for value in ('Infinity', '-Infinity', 'NaN'):
            out = self.render(FIXTURE, {'budgetValue': value})
            self.assertEqual(self.marks(out, 'lane-stud'), [])
            self.assertTrue(all(m['attrs']['data-state'] == 'unknown' for m in self.marks(out, 'lane')))

    def test_positive_verified_quota_always_lights_a_brick(self):
        data = self.sample()
        fractions = (0, .001, .049, .05, .08, .099, .1, .15, 1)
        data['running']['quota'] = [dict(agent=str(fraction), remaining_fraction=fraction,
            measured='2026-11-06T10:00:00Z', unverified=False) for fraction in fractions]
        out = self.render_freshness(data, {'now': '2026-11-06T10:00:00Z'})
        bricks = self.marks(out, 'quota-brick')
        for i, (fraction, count) in enumerate(zip(fractions, (0, 1, 1, 1, 1, 1, 1, 2, 10))):
            lit = [m for m in bricks[i*10:(i+1)*10] if 'lit' in m['cls'].split()]
            self.assertEqual(len(lit), count)
            self.assertTrue(all(('low' if fraction <= .1 else 'done') in m['cls'].split() for m in lit))
        data['running']['quota'][1]['unverified'] = True
        out = self.render_freshness(data, {'now': '2026-11-06T10:00:00Z'})
        self.assertTrue(all('lit' not in m['cls'].split() for m in self.marks(out, 'quota-brick')[10:20]))

    def test_lanes_have_two_flush_clipped_segments_and_thin_ticks(self):
        data = self.sample()
        run = data['running']['open'][0]
        # Includes non-integral scales and both sides of each threshold.
        for budget in (15, 30, 37, 60):
            for age in (0, budget / 2, budget - .1, budget, budget + .1, budget * 2):
                data['running']['open'] = [dict(run, budget_min=budget, age_min=age)]
                out = self.render_freshness(data)
                segments = self.marks(out, 'lane-segment')
                self.assertEqual(len(segments), 2)
                first, second = [m['attrs'] for m in segments]
                self.assertEqual(float(first['x']) + float(first['width']), float(second['x']))
                self.assertEqual(float(second['x']) * 2 % 1, 0)
                self.assertEqual([m['attrs']['fill'] for m in segments], ['var(--p)', 'var(--crit)'])
                for rect in (first, second):
                    self.assertEqual(rect['height'], '8')
                    self.assertEqual(rect['shape-rendering'], 'crispEdges')
                    self.assertNotIn('rx', rect)
                    self.assertNotIn('stroke', rect)
                self.assertEqual(self.marks(out, 'lane-stud'), [])
                ground = self.marks(out, 'lane-ground')[0]['attrs']
                self.assertEqual((ground['height'], ground['rx']), ('8', '4'))
                self.assertNotIn('stroke', ground)
                self.assertEqual(ground['width'], '100%')
                self.assertNotIn('viewBox', self.marks(out, 'lane-track')[0]['attrs'])
                clip = next(m for m in out['picture'] if m['tag'] == 'clipPath')
                self.assertTrue(any(m['attrs'].get('clip-path') == 'url(#' + clip['attrs']['id'] + ')'
                                    for m in out['picture']))
                for tick in self.marks(out, 'lane-tick'):
                    self.assertEqual((tick['attrs']['width'], tick['attrs']['height'], tick['attrs']['fill']),
                                     ('1', '14', 'var(--faint)'))
                    self.assertEqual(tick['attrs']['transform'], 'translate(-.5 0)')
        # Unused space belongs to the neutral track; clipping ids never collide.
        out = self.render(FIXTURE)
        clips = [m for m in out['picture'] if m['tag'] == 'clipPath']
        self.assertEqual(len(clips), 4)
        self.assertEqual(len({m['attrs']['id'] for m in clips}), 4)

    def test_light_warning_tokens_hatch_and_small_brick_geometry(self):
        css = PAGE.read_text()
        self.assertNotIn('#9a6700', css)
        self.assertEqual(css.count('--warn: #d19a00; --warn-text: #8a6400; --crit: #cf222e;'), 2)
        self.assertIn('--warn: #e3b341; --crit: #ff7b72;', css)
        self.assertIn('--lane-track: var(--line)', css)
        self.assertEqual(css.count('--lane-track: #eeebf0'), 2)
        out = self.render(FIXTURE)
        for index, mark in enumerate(out['picture']):
            if mark['tag'] == 'pattern':
                stripes = []
                for child in out['picture'][index + 1:]:
                    if child['tag'] != 'rect':
                        break
                    stripes.append(child['attrs']['fill'])
                self.assertEqual(stripes, ['var(--warn)'])
        for cls, size in (('task-brick', ('15', '11')), ('quota-brick', ('14', '10')),
                          ('slot', ('18', '13')), ('project-done', ('22', '17'))):
            self.assertTrue(all((m['attrs']['width'], m['attrs']['height']) == size for m in self.marks(out, cls)))
        low = next(m for m in self.marks(out, 'quota-brick') if 'low' in m['cls'].split())
        pos = out['picture'].index(low)
        self.assertEqual(next(m['attrs']['fill'] for m in out['picture'][pos:] if m['cls'] == 'brick-body'), 'var(--crit)')

    def test_each_rich_tooltip_kind_has_structure_and_plain_aria_facts(self):
        cases = [('project', 'task-brick', 'T001', ['agent / model', 'session / host'], 0, 1, 0),
                 ('project', 'merged', 'T301 to T302', ['done', 'agent on it', 'not accepted', 'to do'], 0, 0, 0),
                 ('agents', 'lane', None, ['elapsed', 'budget', 'check at', 'cap'], 0, 0, 1),
                 ('agents', 'quota-bricks', 'claude quota', ['remaining', 'measured'], 0, 0, 1),
                 ('agents', 'slots', 'slots', ['lit'], 0, 0, 0),
                 ('project', 'active-host', 'claude', ['sessions'], 0, 0, 0),
                 ('agents', 'no-process', 'no process', [], 1, 0, 0),
                 ('agents', 'info-button', 'How to read this', [], 5, 0, 0),
                 ('project', 'info-button', 'How to read this', [], 5, 0, 0)]
        for tab, target, title, labels, items, chips, bars in cases:
            with self.subTest(kind=target, tab=tab):
                out = self.render(FIXTURE, {'hash': '#' + tab, 'actions': [dict(scope=tab, tooltip='focus', target=target)]})
                tip = out['tipStates'][0]
                self.assertFalse(tip['hidden'])
                parts = tip['picture']
                self.assertEqual(sum(m['cls'] == 'tip-divider' for m in parts), 1)
                titles = [m['text'] for m in parts if m['cls'] == 'tip-title']
                self.assertEqual(len(titles), 1)
                if title:
                    self.assertEqual(titles[0], title)
                self.assertEqual([m['text'] for m in parts if m['cls'] == 'tip-label'], labels)
                self.assertEqual(sum(m['cls'] == 'tip-item' for m in parts), items)
                self.assertEqual(sum('tip-chip' in m['cls'].split() for m in parts), chips)
                self.assertEqual(sum(m['cls'] == 'tip-bar' for m in parts), bars)
                self.assertLessEqual(items, 5)
                self.assertNotIn('img', [m['tag'] for m in parts])
                self.assertNotIn('script', [m['tag'] for m in parts])
        for mark in out['picture']:
            if mark.get('spec') and isinstance(mark['spec'], dict):
                self.assertEqual(mark['attrs']['data-tip'], '')
                self.assertIn('aria-label', mark['attrs'])
                self.assertNotIn('\n', mark['attrs']['aria-label'])
        js = (PAGE.parent / 'dashboard.js').read_text()
        self.assertIn('new WeakMap()', js)
        self.assertNotIn('getAttribute("data-tip")', js)
        css = PAGE.read_text()
        for declaration in ('max-height: 60vh', 'max-width: 260px', 'padding: 10px', 'border-radius: 8px', 'overflow-y: auto'):
            self.assertIn(declaration, re.search(r'#tip \{([^}]+)', css)[1])
        self.assertIn('tip-fade 120ms', css)
        self.assertIn('font-variant-numeric: tabular-nums', re.search(r'\.tip-value \{([^}]+)', css)[1])

    def test_hostile_structured_tooltip_values_are_inert_and_tap_pins(self):
        data = self.sample()
        attack = '<img src=x onerror=alert(1)></script><script>alert(2)</script>'
        for run in data['running']['open']:
            run.update(agent=attack, model=attack, task=attack)
        data['running']['quota'][0]['agent'] = attack
        for task in data['progress']['repositories']['aaaaaaaa']['features'][0]['tasks']:
            task.update(runs=[dict(agent=attack, model=attack)], sessions=[dict(id=attack, host=attack)])
        for tab, target in (('agents', 'lane'), ('agents', 'quota-bricks'), ('project', 'task-brick')):
            with self.subTest(target=target):
                out = self.render_freshness(data, {'hash': '#' + tab, 'actions': [
                    dict(scope=tab, tooltip='tap', target=target), dict(scope=tab, tooltip='leave', target=target),
                    dict(scope=tab, tooltip='surface', target=target), dict(scope=tab, tooltip='outside', target=target)]})
                self.assertEqual([tip['hidden'] for tip in out['tipStates']], [False, False, False, True])
                self.assertIn(attack, out['tipStates'][0]['text'])
                for tip in out['tipStates']:
                    self.assertNotIn('img', [m['tag'] for m in tip['picture']])
                    self.assertNotIn('script', [m['tag'] for m in tip['picture']])
                    self.assertFalse(any(k.startswith('on') for m in tip['picture'] for k in m['attrs']))
        # The quota's user-supplied title is rendered literally and never stored in a content attribute.
        out = self.render_freshness(data, {'actions': [dict(tooltip='focus', target='quota-bricks')]})
        self.assertIn(attack, out['tipStates'][0]['text'])
        self.assertEqual(self.marks(out, 'quota-bricks')[0]['attrs']['data-tip'], '')

    def test_quota_rounds_tooltip_and_aria_and_legacy_strings_still_work(self):
        data = self.sample()
        data['running']['quota'][0]['remaining_fraction'] = .6799999999
        out = self.render_freshness(data, {'now': '2026-11-06T10:00:00Z',
            'actions': [dict(tooltip='focus', target='quota-bricks')]})
        meter = self.marks(out, 'quota-bricks')[0]
        self.assertEqual(meter['spec']['rows'][0], ['remaining', '68%'])
        self.assertIn('remaining: 68%', meter['attrs']['aria-label'])
        self.assertNotIn('67.999', out['tip']['text'])
        out = self.render(FIXTURE, {'actions': [dict(tooltip='hover', target='lane-tick')]})
        self.assertEqual(out['tip']['text'], 'check deadline: half budget')
        self.assertFalse(any(m['cls'] == 'tip-title' for m in out['tip']['picture']))

    def test_footer_dot_uses_ten_minutes_and_six_hours_not_one_minute(self):
        data = self.freshness_data()
        data['freshness']['latest_event'] = {}
        for minutes, state in ((1, 'fresh'), (5, 'fresh'), (10, 'fresh'), (10.01, 'quiet'),
                               (120, 'quiet'), (360, 'quiet'), (360.01, 'stale'), (420, 'stale')):
            out = self.render_freshness(data, {'now': '2026-11-06T10:00:00Z', 'advance_ms': minutes * 60000})
            self.assertEqual(self.marks(out, 'status-dot')[0]['attrs']['data-state'], state)
        data['freshness']['latest_event'] = {'claude': None, 'codex': 'unknown'}
        out = self.render_freshness(data, {'now': '2026-11-06T10:05:00Z'})
        self.assertEqual(self.marks(out, 'status-dot')[0]['attrs']['data-state'], 'fresh')
        data['freshness']['latest_event'] = {'codex': '2026-11-06T09:49:00Z'}
        out = self.render_freshness(data, {'now': '2026-11-06T10:05:00Z'})
        self.assertEqual(self.marks(out, 'status-dot')[0]['attrs']['data-state'], 'quiet')

    def test_finished_project_uses_a_teal_check_brick_and_no_tasks_is_not_done(self):
        out = self.render(FIXTURE)
        marks = self.marks(out, 'project-done')
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0]['tag'], 'svg')
        self.assertEqual(marks[0]['attrs']['aria-label'], 'done')
        self.assertEqual(marks[0]['attrs']['aria-hidden'], 'false')
        self.assertEqual(marks[0]['attrs']['width'], '22')
        self.assertEqual(len(self.marks(out, 'done-check')), 1)
        self.assertIn('stroke', self.marks(out, 'done-check')[0]['attrs'])
        self.assertEqual([m['text'] for m in self.marks(out, 'active-percent')], ['46%', ''])
        done_index = next(i for i, m in enumerate(out['picture']) if 'project-done' in m['cls'].split())
        body = next(m for m in out['picture'][done_index:] if 'brick-body' in m['cls'].split())
        self.assertEqual(body['attrs']['fill'], 'var(--h2)')

    def test_merged_brick_tooltip_has_state_counts_instead_of_task_paragraphs(self):
        out = self.render(FIXTURE, {'hash': '#project', 'actions': [dict(scope='project', tooltip='hover', target='merged')]})
        tip = out['tipStates'][0]
        self.assertFalse(tip['hidden'])
        self.assertEqual(next(m['text'] for m in tip['picture'] if m['cls'] == 'tip-title'), 'T301 to T302')
        self.assertEqual([m['text'] for m in tip['picture'] if m['cls'] == 'tip-label'],
                         ['done', 'agent on it', 'not accepted', 'to do'])
        self.assertEqual([m['text'] for m in tip['picture'] if m['cls'] == 'tip-value'], ['2', '0', '0', '0'])

    def test_footer_dot_relative_age_and_tables_last_on_every_tab(self):
        data = self.freshness_data()
        cases = [('2026-11-06T10:00:00Z', None, 'fresh', 'updated 0 min ago'),
                 ('2026-11-06T10:00:00Z', '2026-11-06T09:44:59Z', 'quiet', 'updated 0 min ago'),
                 ('2026-11-06T10:00:00Z', 'unknown', 'fresh', 'updated 0 min ago'),
                 ('2026-11-06T10:01:00Z', None, 'quiet', 'updated 1 min ago'),
                 ('2026-11-06T10:03:00Z', None, 'quiet', 'updated 3 min ago')]
        for now, codex, state, relative in cases:
            with self.subTest(now=now, codex=codex):
                current = json.loads(json.dumps(data))
                if codex is not None:
                    current['freshness']['latest_event']['codex'] = codex
                out = self.render_freshness(current, {'now': now})
                self.assertEqual(self.marks(out, 'status-dot')[0]['attrs']['data-state'], state)
                self.assertEqual(self.marks(out, 'updated')[0]['text'], relative)
                self.assertNotIn('sources ', out['text'])
                self.assertNotIn('built ', out['text'])
                self.assertIn('sources hooks', self.footer_text(out))
                self.assertIn('sessions ', self.footer_text(out))
                self.assertIn('quota: ', self.footer_text(out))
        # The compact age follows generated, independently of the build timestamp.
        data['freshness']['built_at'] = '2026-11-06T10:02:50Z'
        data['freshness']['latest_event'] = {'codex': '2026-11-06T10:02:50Z'}
        out = self.render_freshness(data, {'now': '2026-11-06T10:03:00Z'})
        self.assertEqual(self.marks(out, 'updated')[0]['text'], 'updated 3 min ago')
        self.assertEqual(self.marks(out, 'status-dot')[0]['attrs']['data-state'], 'fresh')
        css = PAGE.read_text()
        for selector, color in (('.status-dot', '--status-fresh'), ('.status-dot[data-state="quiet"]', '--warn'),
                                ('.status-dot[data-state="stale"]', '--crit')):
            rule = re.search(re.escape(selector) + r' \{([^}]+)', css)[1]
            self.assertIn('background: var(' + color + ')', rule)
        for tab in ('overview', 'agents', 'project', 'delegation', 'reviews'):
            out = self.render(FIXTURE, {'actions': [{'click': tab.title()}]})
            index = ('overview', 'agents', 'project', 'delegation', 'reviews').index(tab)
            children = out['panelChildren'][index]
            self.assertEqual(children[-2]['cls'], 'status')
            self.assertEqual(children[-1]['tag'], 'details')
            self.assertTrue(children[-1]['text'].startswith('show the data as tables'))
            self.assertEqual(len(self.marks(out, 'status')), 1)
        data['generated'] = None
        out = self.render_freshness(data)
        self.assertEqual(self.marks(out, 'updated')[0]['text'], 'updated time unknown')
        data['generated'] = '2099-01-01T00:00:00Z'
        out = self.render_freshness(data)
        self.assertEqual(self.marks(out, 'updated')[0]['text'], 'updated 0 min ago')

    def test_completion_is_floored_for_project_spec_and_story(self):
        for done, total, percent in ((408, 410, 99), (56, 57, 98), (1, 3, 33),
                                     (2, 3, 66), (0, 5, 0), (5, 5, 100)):
            with self.subTest(done=done, total=total):
                data = self.sample()
                feature = dict(feature=1, done=done, total=total, tasks=[],
                               stories=[dict(story='US1', done=done, total=total)])
                data['progress']['repositories'] = {'aaaaaaaa': dict(features=[feature], done=done == total)}
                data['progress']['active'] = [dict(repo='aaaaaaaa', label='A', hosts=['codex'],
                    sessions=2, last='2026-11-06T09:48:00Z', percent=percent if done < total else None)]
                out = self.render_freshness(data, {'now': '2026-11-06T10:00:00Z'})
                if done == total:
                    self.assertEqual(self.marks(out, 'active-percent'), [])
                    self.assertEqual(self.marks(out, 'project-done')[0]['attrs']['aria-label'], 'done')
                    self.assertEqual(self.marks(out, 'story'), [])
                    self.assertTrue(any('100%' in m['text'] for m in self.marks(out, 'tbl', 'show the data as tables')))
                else:
                    self.assertEqual(self.marks(out, 'active-percent')[0]['text'], str(percent) + '%')
                    self.assertEqual(self.marks(out, 'project-done'), [])
                    self.assertIn(str(percent) + '%', self.marks(out, 'story')[0]['tooltip'])

    def test_active_strip_hosts_relative_time_and_no_task_list(self):
        data = self.sample()
        attack = '<img src=x onerror=alert(1)>'
        data['progress']['active'] = [dict(repo='aaaaaaaa', label=attack, hosts=['claude', 'codex', 'antigravity'],
            sessions=3, last='2026-11-06T09:48:00Z', percent=66),
            dict(repo='eeeeeeee', label='repo eeee', hosts=['codex'], sessions=1,
                 last='2026-11-06T09:00:00Z', percent=None)]
        out = self.render_freshness(data, {'now': '2026-11-06T10:00:00Z', 'hash': '#project'})
        rows = self.marks(out, 'active-project')
        self.assertEqual([r['attrs']['data-repo'] for r in rows], ['aaaaaaaa', 'eeeeeeee'])
        self.assertIn(attack, rows[0]['text'])
        self.assertNotIn('3 sessions · 24h', rows[0]['text'])
        self.assertIn('last 12 min ago', rows[0]['text'])
        self.assertNotIn('no task list', rows[1]['text'])
        self.assertIn('no task list', rows[1]['tooltip'])
        self.assertEqual(len(self.marks(out, 'active-percent')), 2)
        self.assertEqual([m['spec']['title'] for m in self.marks(out, 'active-host')],
                         ['claude', 'codex', 'antigravity', 'codex'])
        self.assertEqual(len({m['text'] for m in self.marks(out, 'active-host')}), 3)
        self.assertNotIn('img', out['tags'])
        data['progress']['active'] = []
        self.assertIn('No named project active in the last 24 hours. Run fnl-status inside a repository to add it.', self.render_freshness(data)['text'])

    def test_short_and_long_budget_track_uses_hard_cap(self):
        data = self.sample()
        template = data['running']['open'][0]
        for budget, age, cap in ((15, 24, 25), (60, 85, 80)):
            data['running']['open'] = [dict(template, budget_min=budget, age_min=age)]
            out = self.render_freshness(data)
            widths = [float(m['attrs']['width']) for m in self.marks(out, 'lane-segment')]
            self.assertAlmostEqual(sum(widths), round(min(560, age / cap * 560) * 2) / 2)
            self.assertAlmostEqual(float(self.marks(out, 'check-tick')[0]['attrs']['x'].rstrip('%')), budget / 2 / cap * 100)
            self.assertAlmostEqual(float(self.marks(out, 'budget-tick')[0]['attrs']['x'].rstrip('%')), round(budget / cap * 560 * 2) / 2 / 560 * 100)
            self.assertEqual(self.marks(out, 'lane-stud'), [])
            self.assertEqual(self.marks(out, 'lane')[0]['attrs']['data-state'], 'cap' if age > cap else 'over')

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
        self.assertIn('14 rounds', chains[0]['tooltip'])
        table = self.marks(out, 'tbl', 'show the data as tables')
        self.assertTrue(any('REWORK → REWORK' in row['text'] for row in table))

    def test_agents_lego_lanes_slots_quota_and_hostile_values(self):
        out = self.render(FIXTURE, {'hash': '#agents', 'now': '2026-11-06T10:00:00Z'})
        lanes = self.marks(out, 'lane')
        self.assertEqual([m['attrs']['data-run'] for m in lanes],
                         ['</script><img src=x onerror=alert(1)>', 'run3', 'run2', 'run1'])
        self.assertEqual([m['attrs']['data-state'] for m in lanes], ['cap', 'over', 'check', 'within'])
        self.assertEqual([m['attrs']['x'] for m in self.marks(out, 'check-tick')], ['37.5%'] * 4)
        self.assertEqual([m['attrs']['x'] for m in self.marks(out, 'budget-tick')], ['75%'] * 4)
        self.assertEqual([m['tag'] for m in self.marks(out, 'lane-track')], ['svg'] * 4)
        self.assertEqual(self.marks(out, 'lane-stud'), [])
        segments = self.marks(out, 'lane-segment')
        self.assertEqual([float(m['attrs']['width']) for m in segments],
                         [420, 140, 420, 14, 280, 0, 70, 0])
        self.assertEqual([m['attrs']['fill'] for m in segments[:2]], ['var(--p)', 'var(--crit)'])
        self.assertEqual([m['text'] for m in self.marks(out, 'lane-value')], ['45/30 m', '31/30 m', '20/30 m', '5/30 m'])
        tasks = self.marks(out, 'lane-task')
        self.assertTrue(all(m['tooltip'] is None for m in tasks))
        self.assertTrue(all(m['tooltip'] is None for m in self.marks(out, 'lane-identity')))
        self.assertIn('</script>', tasks[2]['text'])
        self.assertIn('no process', self.marks(out, 'no-process')[0]['tooltip'])
        self.assertEqual(self.marks(out, 'no-process')[0]['tag'], 'svg')
        self.assertEqual(self.marks(out, 'agent-kpis'), [])
        slots = self.marks(out, 'slot')
        self.assertEqual(len(slots), 5)
        self.assertEqual(sum('lit' in m['cls'].split() for m in slots), 4)
        quota = self.marks(out, 'quota-bricks')
        self.assertEqual(len(quota), 3)
        self.assertEqual([m['text'].strip() for m in quota], ['', '', '?'])
        self.assertTrue(all(value in m['tooltip'] for value, m in zip(['68%', '8%', '42%'], quota)))
        self.assertIn('unverified', quota[2]['cls'])
        blocks = self.marks(out, 'quota-brick')
        self.assertEqual(len(blocks), 30)
        self.assertEqual([sum('lit' in m['cls'].split() for m in blocks[i:i+10]) for i in range(0, 30, 10)], [7, 1, 0])
        self.assertIn('low', blocks[10]['cls'].split())
        self.assertEqual(self.marks(out, 'capacity-caption')[1]['text'], 'claude quota')
        self.assertEqual(self.marks(out, 'process-counts'), [])
        self.assertTrue(any('</script>' in (m.get('tooltip') or '') for m in lanes))
        tables = self.marks(out, 'tbl', 'show the data as tables')
        self.assertTrue(any('agent state' in row['text'] and 'past the check time' in row['text'] for row in tables))
        self.assertTrue(any('process roots' in row['text'] and 'descendants' in row['text'] for row in tables))
        notes = self.info_text(out, 'agents')
        self.assertIn('machine-wide', notes)
        self.assertIn('liveness is advisory', notes)
        self.assertNotIn('img', out['tags'])
        self.assertNotIn('script', out['tags'])

    def test_lego_geometry_and_mobile_wrap_contract(self):
        css = PAGE.read_text()
        def rule(selector):
            return re.search(r"(?m)^" + re.escape(selector) + r" \{([^}]+)\}", css).group(1)
        for cls in ('.lane-identity', '.lane-task', '.active-label'):
            self.assertIn('text-overflow: ellipsis', rule(cls))
            self.assertIn('overflow: hidden', rule(cls))
        for cls in ('.lane', '.active-project'):
            self.assertIn('grid-template-columns: 150px minmax(0, 1fr) 54px', rule(cls))
            self.assertIn('gap: 14px', rule(cls))
        self.assertIn('grid-template-columns: 30px minmax(0, 1fr) 38px', rule('.story'))
        self.assertIn('gap: 2px', rule('.cells'))
        self.assertIn('align-items: start', rule('.story'))
        self.assertIn('margin-top: 8px', rule('.story + .story'))
        self.assertNotIn('position: sticky', rule('.story-label'))
        self.assertIn('@media (max-width: 375px) {\n  .story + .story { margin-top: 6px; }', css)
        self.assertGreater(css.index('@media (max-width: 375px)'), css.index('.story + .story { margin-top: 8px; }'))
        self.assertIn('align-self: start', rule('.story-label'))
        self.assertIn('flex-wrap: wrap', rule('.cells'))
        self.assertIn('width: 15px; height: 11px', rule('.task-brick'))
        self.assertIn('stroke-dasharray: 2 2', rule('.quota-bricks.unverified .brick-body'))
        self.assertIn('font-size: 22px', rule('.active-percent'))
        self.assertIn('font-variant-numeric: tabular-nums', rule('.active-percent'))
        mobile = css[css.index('@media (max-width: 560px) {\n  #panel-agents'):]
        self.assertIn('#panel-agents, #panel-project { max-height: none; overflow: visible; }', mobile)
        self.assertIn('.lane { grid-template-columns: minmax(0, 1fr) 64px;', mobile)
        self.assertIn('.lane-label { grid-column: 1 / -1; }', mobile)
        self.assertIn('.project-detail { grid-column: 1 / -1; grid-row: 2; }', mobile)

    def test_story_priority_and_task_phase_then_id_order(self):
        data = self.sample()
        data['progress']['active'] = [dict(repo='bbbbbbbb', label='Shop app', hosts=['codex'], sessions=1, last='2026-11-06T10:00:00Z', percent=33)]
        f = data['progress']['repositories']['bbbbbbbb']['features'][0]
        f['tasks'] += [dict(id='T009', story='US1', phase=1, state='todo'),
                       dict(id='T001', story='US1', phase=2, state='todo')]
        out = self.render_freshness(data)
        self.assertEqual([m['attrs']['data-story'] for m in self.marks(out, 'story')], ['US1', 'US2'])
        self.assertEqual([m['attrs']['data-task'] for m in self.marks(out, 'task-brick')][:4], ['T009', 'T011', 'T012', 'T001'])
        f['stories'][1]['priority'] = 4
        self.assertEqual([m['attrs']['data-story'] for m in self.marks(self.render_freshness(data), 'story')], ['US2', 'US1'])

    def test_finished_story_plural(self):
        data = self.sample()
        feature = data['progress']['repositories']['aaaaaaaa']['features'][0]
        feature['stories'].append(dict(story='US8', total=2, done=2, priority=3))
        out = self.render_freshness(data)
        self.assertEqual([m['text'] for m in self.marks(out, 'finished-stories')], ['+2 done'])

    def test_agents_empty_state_and_omitted_quota(self):
        data = self.sample()
        # Unmatched machine processes stay in the info tooltip; only open dispatches light slots.
        data['running'] = dict(open=[], processes=[dict(family='codex')], snapshot=dict(reason='snapshot off'), ledger_note='')
        out = self.render_freshness(data, {'hash': '#agents'})
        self.assertEqual(len(self.marks(out, 'ghost-brick')), 3)
        self.assertIn('No agents running', out['panels'][1]['text'])
        self.assertEqual(len(self.marks(out, 'slot')), 5)
        self.assertFalse(any('lit' in m['cls'].split() for m in self.marks(out, 'slot')))
        self.assertEqual(self.marks(out, 'quota-bricks'), [])
        self.assertEqual(self.marks(out, 'agent-value'), [])
        data['running']['parallel_limit'] = 3
        out = self.render_freshness(data)
        self.assertEqual(len(self.marks(out, 'slot')), 3)
        self.assertEqual(self.marks(out, 'capacity-caption')[0]['text'], 'slots (3)')

    def test_named_project_story_bricks_and_tables(self):
        out = self.render(FIXTURE, {'hash': '#project', 'now': '2026-11-06T10:00:00Z'})
        rows = self.marks(out, 'active-project')
        self.assertEqual([p['attrs']['data-repo'] for p in rows], ['aaaaaaaa', 'cccccccc', 'eeeeeeee'])
        self.assertEqual(out['tabs'][2]['text'], 'Project 3')
        self.assertNotIn('repo bbbb', out['panels'][2]['text'])
        self.assertNotIn('repo dddd', out['panels'][2]['text'])
        self.assertEqual(self.marks(out, 'project-disclosure'), [])
        self.assertTrue(all(r['tag'] == 'div' for r in rows))
        self.assertEqual([p['text'] for p in self.marks(out, 'active-percent')], ['46%', ''])
        self.assertEqual([p['attrs']['data-story'] for p in self.marks(out, 'story')], ['US1', 'US4', 'US3'])
        self.assertEqual([p['text'] for p in self.marks(out, 'story-label')], ['US1', 'US4', 'US3'])
        cells = self.marks(out, 'task-brick')
        self.assertEqual(len(cells), 14 + 23 + 3)
        self.assertEqual(Counter(m['attrs']['data-state'] for m in cells[:14]),
                         dict(done=3, active=4, accepted=4, todo=3))
        self.assertEqual(Counter(m['attrs']['data-state'] for m in cells[-3:]), dict(done=1, todo=2))
        self.assertTrue(all(p['tag'] == 'svg' and p['disclosure'] is None for p in cells))
        self.assertEqual({p['attrs']['data-state'] for p in cells}, {'done', 'active', 'accepted', 'todo'})
        self.assertEqual([p['text'] for p in self.marks(out, 'spec-label')], ['spec 003'])
        self.assertEqual([p['text'] for p in self.marks(out, 'finished-stories')], ['+1 done'])
        self.assertFalse(any(p['attrs']['data-task'] in ('T005', 'T090') for p in cells))
        self.assertEqual(len(self.marks(out, 'brick-stud')), 2 * len(self.marks(out, 'lego-brick')))
        bodies = self.marks(out, 'brick-body')
        self.assertTrue(any(p['attrs']['fill'].startswith('url(#brick-hatch-') for p in bodies))
        self.assertTrue(any(p['attrs']['fill'] == 'none' and p['attrs']['stroke'] == 'var(--line)' for p in bodies))
        tips = [p['tooltip'] for p in cells]
        self.assertTrue(any(all(t in tip for t in ('T002', 'agent on it', 'codex', 'session1', '</script>')) for tip in tips))
        tables = [p for p in out['picture'] if p['disclosure'] == 'show the data as tables']
        self.assertTrue(any('project completion' in p['text'] and '46%' in p['text'] for p in tables))
        self.assertTrue(any('T090' in p['text'] for p in tables), 'finished feature remains in tables')
        self.assertTrue(all(p['disclosure'] == 'show the data as tables' for p in out['picture'] if p['tag'] == 'table'))
        self.assertNotIn('img', out['tags'])
        self.assertNotIn('script', out['tags'])

    def test_project_bricks_remain_visible_after_data_refresh(self):
        changed = self.sample()
        changed['progress']['active'][0]['sessions'] = 4
        out = self.render(FIXTURE, {'hash': '#project', 'next': changed})
        self.assertEqual(self.marks(out, 'project-disclosure'), [])
        self.assertEqual(len(self.marks(out, 'task-brick')), 40)
        self.assertEqual(out['panels'][2]['attrs']['data-enter'], 'true')

    def test_long_story_merges_consecutive_tasks_with_state_precedence(self):
        out = self.render(FIXTURE, {'hash': '#project'})
        cells = self.marks(out, 'task-brick')[14:37]
        self.assertEqual(len(cells), 23)
        self.assertEqual(sum(int(m['attrs']['data-count']) for m in cells), 45)
        self.assertEqual([m['attrs']['data-state'] for m in cells[:4]], ['done', 'todo', 'accepted', 'active'])
        self.assertTrue(all(int(m['attrs']['data-count']) == 2 for m in cells[:-1]))
        self.assertEqual(cells[-1]['attrs']['data-count'], '1')
        self.assertEqual(cells[0]['spec']['title'], 'T301 to T302')
        self.assertEqual(sum(row[1] for row in cells[0]['spec']['rows']), 2)
        self.assertIn('T345', cells[-1]['tooltip'])
        self.assertEqual([m['style']['--snap-delay'] for m in self.marks(out, 'task-brick')][:3], ['0ms', '10ms', '20ms'])

    def test_story_merge_boundary_and_stagger_cap(self):
        data = self.sample()
        feature = data['progress']['repositories']['aaaaaaaa']['features'][0]
        feature['stories'] = [dict(story='US1', total=36, done=0), dict(story='US2', total=37, done=0)]
        feature['tasks'] = [dict(id=f'T{n:03}', story=story, state='todo', phase=1)
                            for story, size in [('US1', 36), ('US2', 37)] for n in range(1, size + 1)]
        feature.update(total=73, done=0)
        out = self.render_freshness(data, {'hash': '#project'})
        bricks = self.marks(out, 'task-brick')
        self.assertEqual(len(bricks), 36 + 19)
        self.assertEqual([int(m['attrs']['data-count']) for m in bricks[:36]], [1] * 36)
        self.assertEqual(sum(int(m['attrs']['data-count']) for m in bricks[36:]), 37)
        self.assertEqual(bricks[49]['style']['--snap-delay'], '490ms')
        self.assertTrue(all(m['style']['--snap-delay'] == '500ms' for m in bricks[50:]))

    def test_task_svg_geometry_tokens_and_unique_hatches(self):
        out = self.render_freshness(self.sample())
        bricks = self.marks(out, 'task-brick')
        self.assertTrue(all(m['attrs']['width'] == '15' and m['attrs']['height'] == '11' for m in bricks))
        self.assertTrue(all(m['attrs']['viewBox'] == '0 0 15 11' for m in bricks))
        patterns = [m for m in out['picture'] if m['tag'] == 'pattern']
        self.assertEqual(len({m['attrs']['id'] for m in patterns}), len(patterns))
        self.assertTrue(all(m['attrs']['patternUnits'] == 'userSpaceOnUse' for m in patterns))
        self.assertNotIn('innerHTML', (PAGE.parent / 'dashboard.js').read_text())

    def test_header_only_projects_without_unfinished_tasks_and_hostile_name(self):
        data = self.sample()
        name = '<img src=x onerror=alert(1)> very long project name'
        data['progress']['active'][0]['label'] = name
        data['progress']['active'][0]['percent'] = 28.9
        out = self.render_freshness(data)
        self.assertEqual(self.marks(out, 'active-percent')[0]['text'], '28%')
        self.assertEqual(self.marks(out, 'active-label')[0]['tooltip'], name)
        self.assertEqual([len(m['text'].strip()) for m in self.marks(out, 'project-detail')][1:], [0, 0])
        self.assertNotIn('img', out['tags'])

    def test_single_legend_follows_all_project_blocks(self):
        out = self.render(FIXTURE, {'hash': '#project'})
        self.assertEqual(len(self.marks(out, 'task-legend')), 1)
        self.assertEqual([m['text'].strip() for m in self.marks(out, 'legend-item')],
                         ['done', 'agent on it', 'done, not accepted', 'to do'])
        self.assertEqual([m['cls'].split()[1] for m in self.marks(out, 'legend-brick')],
                         ['done', 'active', 'accepted', 'todo'])
        self.assertGreater(out['picture'].index(self.marks(out, 'task-legend')[0]),
                           out['picture'].index(self.marks(out, 'active-project')[-1]))

    def test_empty_named_list_and_latest_activity_order_ignores_priority(self):
        data = self.sample()
        data['progress']['active'][1]['last'] = '2026-11-06T10:01:00Z'
        out = self.render_freshness(data, {'hash': '#project'})
        self.assertEqual([p['attrs']['data-repo'] for p in self.marks(out, 'active-project')], ['cccccccc', 'aaaaaaaa', 'eeeeeeee'])
        data['progress']['active'] = [dict(repo='bbbbbbbb', label='', hosts=[], sessions=1, last='2026-11-06T10:00:00Z')]
        out = self.render_freshness(data, {'hash': '#project'})
        self.assertIn('No named project active in the last 24 hours. Run fnl-status inside a repository to add it.', out['panels'][2]['text'])
        self.assertEqual(self.marks(out, 'active-project'), [])
        self.assertEqual(self.marks(out, 'project-disclosure'), [])
        self.assertEqual(out['tabs'][2]['text'], 'Project 0')
        self.assertFalse(any('ghost' in p['cls'] for p in out['picture'] if p.get('panel') == 'panel-project'))

    def test_activity_input_coercion_and_named_cap(self):
        data = self.sample()
        row = data['progress']['active'][0]
        row.update(hosts=['codex', '__proto__', {}, 'codex'], percent='66.9', last={})
        out = self.render_freshness(data)
        self.assertEqual(self.marks(out, 'active-percent')[-1]['text'], '66%')
        self.assertIn('last unavailable', self.marks(out, 'active-project')[-1]['text'])
        self.assertEqual([m['spec']['title'] for m in self.marks(out, 'active-host')].count('codex'), 2)
        for bad in ('<img>', {}, None):
            row.update(hosts=bad, percent=bad, last=bad)
            out = self.render_freshness(data)
            self.assertEqual(self.marks(out, 'active-percent')[-1]['text'], '')
            self.assertNotIn('NaN', out['panels'][2]['text'])
        data['progress']['active'] = [dict(repo=str(n), label='Named', hosts=[], sessions=1, last='2026-11-06T10:00:00Z') for n in range(20)]
        out = self.render_freshness(data)
        self.assertEqual(len(self.marks(out, 'active-project')), 12)
        self.assertEqual(out['tabs'][2]['text'], 'Project 12')

    def test_motion_scoped_to_visible_tab_and_once_per_changed_data(self):
        page = PAGE.read_text()
        self.assertRegex(page, r'@media \(prefers-reduced-motion: reduce\)\s*\{\s*\*, \*::before, \*::after \{ animation: none !important; transition: none !important;')
        for selector, body in re.findall(r'([^{}]+)\{([^{}]+)\}', page.split('</style>')[0]):
            if 'animation:' in body and any(name in body for name in ('amount-grow', 'brick-snap', 'brick-breathe')):
                self.assertTrue(all('.tabpanel:not([hidden])' in part for part in selector.split(',')))
        out = self.render(FIXTURE, {'actions': [{'click': 'Agents'}, {'click': 'Project'}]})
        self.assertTrue(all(p['attrs'].get('data-enter') != 'true' for p in out['panels'] if p['hidden']))
        again = self.render(FIXTURE, {'actions': [{'click': 'Agents'}, {'click': 'Overview'}, {'click': 'Agents'}]})
        self.assertEqual(again['panels'][1]['attrs'].get('data-enter'), 'false')
        self.assertTrue(any('active' in p['cls'].split() for p in self.marks(out, 'task-brick')))

    def test_running_panel_off_and_failed_snapshots_do_not_claim_zero_processes(self):
        for reason in ('snapshot off', 'ps timed out'):
            data = self.sample()
            data['running'] = dict(processes=[], open=[], snapshot=dict(time='now', reason=reason, apps={}), ledger_note='')
            out = self.render_freshness(data)
            self.assertIn(reason, self.info_text(out, 'agents'))
            self.assertNotIn('No command-line agent processes found', self.info_text(out, 'agents'))
            self.assertNotIn('processes named claude: 0', self.info_text(out, 'agents'))

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
        data["generated"] = "2026-11-06T10:00:00Z"
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
            self.assertIn(value, self.footer_text(initial))
        self.assertNotIn("hooks may need trust", self.footer_text(initial))
        self.assertNotIn("it updates while a session runs tools", self.footer_text(initial))
        later = self.render_freshness(data, {"now": "2026-11-06T10:00:00Z", "advance_ms": 65000, "fail": True})
        self.assertIn("Codex: last event 2026-11-06T09:45:00Z; hooks may need trust", self.footer_text(later))
        self.assertNotIn("Claude Code: last event 2026-11-06T10:00:00Z; hooks may need trust", self.footer_text(later))
        self.assertIn("data is 1 minute old; it updates while a session runs tools", self.footer_text(later))
        self.assertIn("ledger: 3 minutes old", self.footer_text(later))
        self.assertFalse(later["redrawn"])
        quiet = self.render_freshness(data, {"now": "2026-11-06T10:16:00Z"})
        self.assertNotIn("hooks may need trust", self.footer_text(quiet), "no host is active")

    def test_freshness_stale_message_waits_for_visible_tab_and_rechecks_on_return(self):
        data = self.freshness_data()
        hidden = self.render_freshness(data, {"now": "2026-11-06T10:02:00Z", "hidden": True})
        self.assertNotIn("it updates while a session runs tools", self.footer_text(hidden))
        visible = self.render_freshness(data, {"now": "2026-11-06T10:02:00Z", "hidden": True, "reveal": True})
        self.assertIn("data is 2 minutes old; it updates while a session runs tools", self.footer_text(visible))

    def test_freshness_host_and_value_are_text_and_missing_times_are_named(self):
        data = self.freshness_data()
        attack = "<img src=x onerror=alert(1)>"
        data["freshness"].update(built_at=attack, latest_event={attack: attack},
                                 ledger_age_seconds=attack, quota_age_seconds=None)
        out = self.render_freshness(data)
        self.assertGreaterEqual(self.footer_text(out).count(attack), 4)
        self.assertIn("quota: no reading", self.footer_text(out))
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
        self.assertIn("with edits 98765", self.footer_text(out))

    def test_a_new_build_with_the_same_numbers_only_updates_the_generated_time(self):
        same = self.sample()
        same["generated"] = "2099-01-01T00:00:00+07:00"
        same["freshness"].update(built_at=same["generated"], ledger_age_seconds=180,
                                 latest_event={"antigravity": same["generated"]})
        out = self.render(FIXTURE, {"next": same, "actions": [dict(scope='footer', tooltip='focus')]})
        self.assertFalse(out["redrawn"])
        self.assertIn('updated 0 min ago', self.marks(out, 'status')[0]['text'])
        self.assertEqual(out['tip']['text'], self.footer_text(out))
        self.assertFalse(out['tip']['hidden'])
        self.assertIn("generated 2099-01-01T00:00:00+07:00", self.footer_text(out))
        self.assertIn("built 2099-01-01T00:00:00+07:00", self.footer_text(out))
        self.assertIn("Antigravity: last event 2099-01-01T00:00:00+07:00", self.footer_text(out))
        self.assertIn("ledger: 3 minutes old", self.footer_text(out))

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
