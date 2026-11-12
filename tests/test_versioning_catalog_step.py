import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class CatalogStepTest(unittest.TestCase):
    def test_catalog_pull_request_needs_the_owners_go(self):
        text = (ROOT / "skills" / "versioning" / "SKILL.md").read_text()
        self.assertIn("only with the owner's explicit go for that repository", text)
        self.assertIn("**Advisory (agent judgment):**", text)


if __name__ == "__main__":
    unittest.main()
