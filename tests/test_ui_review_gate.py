"""The ui-review-gate snippets give known answers on a fixed fixture, read the page only, and the skill stays self-contained.

The snippets run in node against the fake DOM of tests/ui_snippet_runner.js: no browser is launched, and the
fixture's boxes come from its style attributes, so real layout and the CSS cascade are not exercised here.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

# select-tests: reads skills/ui-review-gate/

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/ui-review-gate"
SCRIPTS = SKILL / "scripts"
FIXTURE = ROOT / "tests/fixtures/ui-review-gate/page.html"
RUNNER = ROOT / "tests/ui_snippet_runner.js"
NODE = shutil.which("node") or ("/opt/homebrew/bin/node" if Path("/opt/homebrew/bin/node").exists() else None)
VOID = {"input", "meta", "link", "br", "img", "hr"}


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": {k: (v if v is not None else "") for k, v in attrs}, "children": []}
        if self.stack:
            self.stack[-1]["children"].append(node)
        else:
            self.root = node
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()["tag"] == tag:
                break

    def handle_data(self, data):
        if self.stack and data.strip():
            self.stack[-1]["children"].append({"text": data})


def fixture_tree():
    parser = _Tree()
    parser.feed(FIXTURE.read_text(encoding="utf-8"))
    return parser.root


@unittest.skipUnless(NODE, "node is not installed")
class SnippetResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.tree = Path(cls.tmp.name) / "tree.json"
        cls.tree.write_text(json.dumps(fixture_tree()), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_snippet(self, name, viewport=390):
        done = subprocess.run([NODE, str(RUNNER), str(SCRIPTS / name), str(self.tree), str(viewport)],
                              capture_output=True, text=True, timeout=30, env={})
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_contrast_applies_the_threshold_by_text_size(self):
        out = self.run_snippet("contrast.js")
        by_id = {(r["kind"], r["id"]): r for r in out["results"]}
        grey = by_id[("text", "grey-text")]
        self.assertEqual((grey["ratio"], grey["threshold"], grey["pass"], grey["large"]), (3.89, 4.5, False, False))
        large = by_id[("text", "large-grey")]
        self.assertEqual((large["ratio"], large["threshold"], large["pass"], large["large"]), (3.89, 3, True, True))
        self.assertEqual(by_id[("text", "dark-text")]["ratio"], 21)
        button = by_id[("component", "small")]
        self.assertEqual((button["boundary"], button["threshold"], button["pass"]), ("background", 3, True))
        field = by_id[("component", "email")]
        self.assertIsNone(field["pass"])
        self.assertTrue(field["uncertain"])
        near = by_id[("text", "near-threshold")]
        # 4.4968:1 is a failure; the ratio is compared raw and shown rounded down, never up to 4.5.
        self.assertEqual((near["ratio"], near["pass"]), (4.49, False))
        faded = by_id[("text", "faded-text")]
        self.assertTrue(faded["uncertain"], "opacity on an ancestor above an opaque background is uncertain")
        self.assertEqual(out["failures"], 2)

    def test_targets_block_below_24_px_and_flag_24_to_43_as_low(self):
        out = self.run_snippet("targets.js")
        by_id = {r["id"]: r for r in out["results"]}
        self.assertEqual((by_id["small"]["size"], by_id["small"]["severity"], by_id["small"]["exception"]),
                         ("below-24", "blocking", None))
        self.assertEqual(by_id["small"]["criterion"], "2.5.8")
        self.assertEqual((by_id["medium"]["size"], by_id["medium"]["severity"]), ("24-43", "low"))
        self.assertEqual((by_id["spaced"]["severity"], by_id["spaced"]["exception"]), ("low", "spacing"))
        self.assertEqual((by_id["inline-link"]["severity"], by_id["inline-link"]["exception"]), ("low", "inline"))
        self.assertEqual((by_id["wrapped-link"]["severity"], by_id["wrapped-link"]["exception"]), ("low", "inline"))
        # Text in a sibling block is not the link's sentence: close, undersized links there stay blocking.
        self.assertEqual((by_id["standalone-link"]["severity"], by_id["standalone-link"]["exception"]), ("blocking", None))
        # Text before an intervening block is another line: the links after it stay blocking.
        self.assertEqual((by_id["run-link"]["severity"], by_id["run-link"]["exception"]), ("blocking", None))
        # A block inside the wrapper breaks the run as well.
        self.assertEqual((by_id["nested-link"]["severity"], by_id["nested-link"]["exception"]), ("blocking", None))
        # Every inline exception is a heuristic reading, marked for a check by eye.
        self.assertTrue(by_id["inline-link"]["uncertain"] and by_id["wrapped-link"]["uncertain"])
        self.assertNotIn("email", by_id, "a 48 px tall field is not reported")
        self.assertEqual(out["blocking"], 7)

    def test_overflow_names_the_outermost_cause_and_allows_scroll_regions(self):
        out = self.run_snippet("overflow.js")
        self.assertTrue(out["horizontalScroll"])
        self.assertEqual((out["viewport"], out["scrollWidth"]), (390, 600))
        self.assertEqual([c["id"] for c in out["culprits"]], ["wide"])
        self.assertEqual([r["id"] for r in out["scrollRegions"]], ["table-wrap"])

    def test_overflow_is_clear_when_the_viewport_is_wide_enough(self):
        out = self.run_snippet("overflow.js", viewport=1440)
        self.assertFalse(out["horizontalScroll"])
        self.assertEqual(out["culprits"], [])

    def test_fields_lists_the_form_in_order_without_values(self):
        out = self.run_snippet("fields.js")
        self.assertEqual(out["order"], ["email", "full_name", "phone"])
        email, name, phone = out["fields"]
        self.assertEqual((email["type"], email["autocomplete"], email["label"], email["labelSource"], email["required"]),
                         ("email", "email", "Email", "label-for", True))
        self.assertEqual((name["label"], name["labelSource"], name["required"]), ("Full name", "aria-label", False))
        self.assertEqual((phone["type"], phone["inputmode"], phone["labelSource"]), ("tel", "tel", "placeholder-only"))
        self.assertTrue(all(f["form"] == 0 for f in out["fields"]))
        self.assertFalse(any("value" in f for f in out["fields"]))


class SnippetRules(unittest.TestCase):
    SNIPPETS = ("contrast.js", "targets.js", "overflow.js", "fields.js")
    # Page reads only: nothing that reaches the network, writes storage, navigates, changes the DOM or reads a value.
    FORBIDDEN = re.compile(r"\bfetch\b|XMLHttpRequest|WebSocket|sendBeacon|EventSource|\bimport\s*\(|localStorage|"
                           r"sessionStorage|indexedDB|document\.cookie|\blocation\b|\bhistory\b|window\.open|"
                           r"\.submit\(|\.click\(|\.focus\(|setAttribute|removeAttribute|appendChild|insertBefore|"
                           r"\.remove\(|innerHTML|outerHTML|\.value\b|\.style\.|classList")

    def test_snippets_are_one_read_only_expression(self):
        for name in self.SNIPPETS:
            text = (SCRIPTS / name).read_text(encoding="utf-8")
            code = re.sub(r"/\*.*?\*/", "", text, flags=re.S).strip()
            with self.subTest(snippet=name):
                self.assertTrue(code.startswith("(() => {") and code.endswith("})()"), "one expression")
                self.assertNotRegex(code, r"(?m)//")
                self.assertIsNone(self.FORBIDDEN.search(code), self.FORBIDDEN.search(code))

    def test_skill_states_the_settled_decisions(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for needed in ("Report only", "BLOCKED", "pinned dev dependency", "axe pass skipped",
                       "below 24 by 24 CSS px", "24 to 43 px", "advisory", "`merge_check.py` does not read"):
            self.assertIn(needed, text)
        a11y = (SKILL / "references/accessibility.md").read_text(encoding="utf-8")
        for criterion in ("1.4.3", "1.4.10", "1.4.11", "2.4.11", "2.5.7", "2.5.8", "3.3.7", "3.3.8"):
            self.assertIn(f"| {criterion} ", a11y)
        self.assertIn("2.3.3", a11y)

    def test_skill_folder_is_self_contained(self):
        for path in SKILL.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                with self.subTest(file=str(path.relative_to(ROOT))):
                    self.assertNotIn("../", text)
                    for link in re.findall(r"\]\(([^)#]+)", text):
                        if not link.startswith("http"):
                            self.assertTrue((path.parent / link).is_file(), link)


if __name__ == "__main__":
    unittest.main()
