import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def description(skill):
    text = (ROOT / "skills" / skill / "SKILL.md").read_text()
    return re.search(r"^description: (.*)$", text, re.M).group(1)


class RouterDecisionsTest(unittest.TestCase):
    def test_router_asks_decisions_instead_of_listing_them(self):
        text = (ROOT / "skills" / "coding-router" / "SKILL.md").read_text()
        self.assertIn("A spec or plan asks the user the decisions the user can settle", text)
        self.assertIn("Enforcer: agent judgment, advisory.", text)


class SkillFiringTest(unittest.TestCase):
    def setUp(self):
        self.router = (ROOT / "skills" / "coding-router" / "SKILL.md").read_text()
        self.rules = (ROOT / "rules" / "AGENTS.md").read_text()

    def test_router_directs_session_naming_at_task_start_and_phase_change(self):
        step1 = self.router.split("## 1.", 1)[1].split("## 2.", 1)[0]
        flat = " ".join(step1.split())
        self.assertIn("invoke `session-hygiene` to name or rename the session", flat)
        self.assertIn("phase changes", flat)

    def test_router_invokes_checks_before_claims_and_delegated_acceptance(self):
        flat = " ".join(self.router.split())
        self.assertRegex(flat, r"Invoke `checks` before you report work as done, fixed or passing, and before you accept a delegated run")

    def test_rules_invoke_checks_before_claims_without_naming_the_router(self):
        [line] = [l for l in self.rules.splitlines() if "checks" in l]
        self.assertIn("before reporting work as done, fixed or passing, and before accepting a delegated run", line)
        self.assertNotIn("coding-router", line)  # survives the routing-off variant

    def test_checks_description_leads_with_the_words_users_type(self):
        text = description("checks")
        self.assertLessEqual(len(text), 1024)
        head = text[:300]
        for phrase in ('"is it done?"', '"did the tests pass?"', '"is it ready to merge?"', "done, fixed or passing"):
            self.assertIn(phrase, head)

    def test_checks_has_a_trigger_eval_for_a_typed_question(self):
        folder = ROOT / "evals" / "trigger-checks-done-question"
        self.assertIn("checks", (folder / "graders" / "skill-fired.md").read_text())
        self.assertIn("tags: [trigger]", (folder / "prompt.md").read_text())


if __name__ == "__main__":
    unittest.main()
