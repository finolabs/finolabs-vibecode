import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RouterDecisionsTest(unittest.TestCase):
    def test_router_asks_decisions_instead_of_listing_them(self):
        text = (ROOT / "skills" / "fnl-coding-router" / "SKILL.md").read_text()
        self.assertIn("A spec or plan asks the user the decisions the user can settle", text)
        self.assertIn("Enforcer: agent judgment, advisory.", text)


if __name__ == "__main__":
    unittest.main()
