"""Pins the package 11 wording: limits, the checklist ids, the separate judge consent."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def text(*parts):
    return SKILLS.joinpath(*parts).read_text()


class InstructionStandardTests(unittest.TestCase):
    def test_hosts_reference_states_limits_and_mechanics(self):
        hosts = text("setup", "references", "instructions", "hosts.md")
        for needle in ("32 KiB", "24,000 bytes", "20,000 tokens", "2.1.277", "`trigger`",
                       "Superseded by the Antigravity CLI", "learn.chatgpt.com"):
            self.assertIn(needle, hosts)
        self.assertNotIn("](https://developers.openai.com", hosts)

    def test_skill_states_standard_thresholds_and_enforcer(self):
        skill = text("setup", "references", "instructions", "procedure.md")
        self.assertIn("## 3. The standard", skill)
        self.assertIn("150 lines", skill)
        self.assertIn("200 lines", skill)
        self.assertIn("advisory", skill)

    def test_explicit_yes_step_is_labelled_advisory(self):
        procedure = text("setup", "references", "instructions", "procedure.md")
        step = next(line for line in procedure.splitlines() if line.startswith("3. ") and "Ask for each file" in line)
        self.assertIn("**Advisory (agent judgment):**", step)
        self.assertIn("explicit yes", step)
        hosts = text("setup", "references", "instructions", "hosts.md")
        self.assertIn("ignores `CODEX_HOME`", hosts)
        self.assertIn("account-derived", hosts)

    def test_check_lists_exactly_twenty_items_with_types(self):
        check = text("setup", "references", "check.md")
        rows = re.findall(r"^\| (I\d+) \| [^|]+ \| ([SJ]) \|", check, re.M)
        self.assertEqual([r[0] for r in rows], ["I%d" % n for n in range(1, 21)])
        self.assertEqual({r[1] for r in rows}, {"S", "J"})

    def test_judge_order_and_separate_consent(self):
        check = text("setup", "references", "check.md")
        self.assertIn("1. **Judge.**", check)
        self.assertIn("2. **Agent.**", check)
        self.assertIn("Instruction check: on", check)
        judge = text("setup", "references", "features", "roles.md")
        self.assertIn("separate question", judge)
        self.assertIn("does not follow from the judge choice", judge)
        template = text("delegate", "references", "host-template.md")
        self.assertIn("Instruction check: <on | off>", template)
        self.assertIn("Default off", template)

    def test_route_judgment_exception_is_scoped(self):
        judgment = text("delegate", "references", "route-judgment.md")
        self.assertIn("Never send code, secrets, personal data or customer records.", judgment)
        self.assertIn("`Instruction check: on`", judgment)
        self.assertIn("never as part of a routing question", judgment)


if __name__ == "__main__":
    unittest.main()
