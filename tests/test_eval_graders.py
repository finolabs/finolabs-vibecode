import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class EvalGraderFormat(unittest.TestCase):
    def test_every_grader_opens_with_front_matter_on_its_own_line(self):
        graders = sorted((ROOT / "evals").glob("*/graders/*.md"))
        self.assertTrue(graders)
        bad = [str(p.relative_to(ROOT)) for p in graders
               if not p.read_text(encoding="utf-8").startswith("---\n")]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
