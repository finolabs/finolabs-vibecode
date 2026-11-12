"""Exercise the exact copy groups CI executes after setup relocation."""
import ast
import filecmp
from pathlib import Path
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


def ci_copy_groups():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text()
    step = workflow.split("- name: Copies of shared skill files match\n", 1)[1].split("      - ", 1)[0]
    source = textwrap.dedent(step.split("python3 - <<'PY'\n", 1)[1].rsplit("          PY", 1)[0])
    tree = ast.parse(source)
    return ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)
                                 and any(isinstance(t, ast.Name) and t.id == "groups" for t in node.targets)))


class SharedCopiesTest(unittest.TestCase):
    def test_every_ci_group_exists_and_matches(self):
        groups = ci_copy_groups()
        self.assertTrue(groups)
        for group in groups:
            self.assertGreaterEqual(len(group), 2)
            for name in group:
                with self.subTest(path=name):
                    self.assertTrue((ROOT / name).is_file(), name)
                    self.assertTrue(filecmp.cmp(ROOT / group[0], ROOT / name, shallow=False), name)

    def test_ci_lists_every_surviving_copy_of_shared_scripts(self):
        groups = ci_copy_groups()
        self.assertIn(["scripts/instructions_write.py", "skills/setup/scripts/instructions_write.py"], groups)
        for group in groups:
            source = ROOT / group[0]
            if source.parent != ROOT / "scripts":
                continue
            copies = {str(p.relative_to(ROOT)) for p in (ROOT / "skills").rglob(source.name)}
            if copies:
                with self.subTest(script=source.name):
                    expected = {str(source.relative_to(ROOT)), *copies}
                    self.assertEqual([set(g) for g in groups if str(source.relative_to(ROOT)) in g], [expected])


if __name__ == "__main__":
    unittest.main()
