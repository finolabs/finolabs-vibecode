"""Agent definitions stay loadable on every host: Antigravity skips an agent whose model it does not know."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class AgentModelTest(unittest.TestCase):
    def test_every_agent_inherits_its_model(self):
        agents = sorted((ROOT / "agents").glob("*.md"))
        self.assertTrue(agents)
        for path in agents:
            front = path.read_text(encoding="utf-8").split("---", 2)[1]
            match = re.search(r"^model:\s*(\S+)\s*$", front, re.MULTILINE)
            self.assertIsNotNone(match, f"{path.name} has no model line")
            self.assertEqual(match.group(1), "inherit", path.name)


if __name__ == "__main__":
    unittest.main()
