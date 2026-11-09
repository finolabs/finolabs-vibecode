"""fnl-advisor's choose mode: the stated output contract, bound to the record autopilot.py accepts."""
import argparse
import importlib.util
from pathlib import Path
import re
import shlex
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADVISOR = ROOT / "skills/fnl-advisor"
CHOOSE = ADVISOR / "references/choose.md"
SYNTHETIC = {"<agent>": "codex", "<n>": "2", "<k>": "3", "<id>": "d20261110-010000-abcd", "<model>": "gpt-6-astra"}


def reader():
    spec = importlib.util.spec_from_file_location("autopilot_choose_test", ROOT / "skills/fnl-delegate/scripts/autopilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(text, settled):
    """The documented `log` flags for one outcome, filled with synthetic values."""
    [flags] = re.findall(r"Record `(--rung advisor --settled %s [^`]+)`" % settled, text)
    tokens = shlex.split(flags)
    values = {}
    for flag, value in zip(tokens[::2], tokens[1::2]):
        values[flag[2:]] = SYNTHETIC.get(value, value)
    return values


def attempt(module, values):
    fields = {f: None for f in module.FIELDS}
    fields.update(values)
    return module.attempt(argparse.Namespace(project="demo", topic="pick a cache", precedents="0", **fields))


class ChooseModeTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CHOOSE.is_file(), "fnl-advisor has no choose mode")
        self.text = CHOOSE.read_text()

    def test_skill_keeps_the_open_mode_decider_line_and_points_to_choose_mode(self):
        skill = (ADVISOR / "SKILL.md").read_text()
        self.assertIn("You stay the decider", skill)
        self.assertIn("(references/choose.md)", skill)
        self.assertIn("You do not stay the decider", self.text)
        self.assertLessEqual(len(skill.encode()), 10000)

    def test_reply_contract_is_exactly_one_option_or_none(self):
        self.assertIn("CHOICE: <option number> | none\nREASON: <one or two sentences>\n", self.text)
        self.assertIn("This is analysis only. Do NOT edit, create, or delete any files. Do NOT write code.", self.text)
        for case in ("a number out of range", "a second `CHOICE` line", "option text instead of a number", "no `CHOICE` line"):
            self.assertIn(case, self.text)

    def test_the_documented_check_names_the_coordinator(self):
        self.assertIn("autopilot.py check --coordinator <your own family> --argv-json", CHOOSE.read_text())

    def test_tier_and_family_rule(self):
        for rule in ("frontier tier", "else its strong tier", "Nothing below strong", "is not yours",
                     "Never a subagent of your own host", "a Claude model served through another host counts as Claude",
                     "matrix role `advisor`", "lease's recorded Hosts", "An agent the user named"):
            self.assertIn(rule, self.text)
        self.assertLess(self.text.index("An agent the user named"), self.text.index("matrix role `advisor`"))
        self.assertLess(self.text.index("matrix role `advisor`"), self.text.index("Otherwise contrast"))

    def test_documented_records_match_the_attempt_schema(self):
        module = reader()
        chosen = attempt(module, record(self.text, "yes"))
        self.assertEqual((chosen["rung"], chosen["settled"], chosen["option"], chosen["of"]), ("advisor", "yes", 2, 3))
        none = record(self.text, "no")
        self.assertNotIn("option", none)
        self.assertEqual(attempt(module, none)["settled"], "no")
        with self.assertRaises(ValueError):  # `none` never carries an option
            attempt(module, {**none, "option": "1", "of": "3"})
        with self.assertRaises(ValueError):  # a chosen option out of range is refused
            attempt(module, {**record(self.text, "yes"), "option": "4"})


if __name__ == "__main__":
    unittest.main()
