"""Tests for scripts/route_task.py and its copy in delegate."""

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/route_task.py"
COPY = ROOT / "skills/delegate/scripts/route_task.py"
CODE_ORDER = "agents=claude-code>codex>antigravity>zcode"

# Written out from `delegate` "Decision matrix" and "Budget and liveness",
# independently of the script's tables.
EXPECTED = {
    ("implement", "easy"): "tier=fast effort=medium budget-min=20 runs-as=headless agents=most-quota-left",
    ("implement", "medium"): f"tier=strong effort=medium budget-min=30-45 runs-as=headless {CODE_ORDER}",
    ("implement", "hard"): "tier=frontier tier-alt=strong-with-clear-acceptance-tests effort=medium"
                           f" budget-min=60-90 runs-as=headless {CODE_ORDER}",
    ("implement", "very-hard"): f"tier=frontier effort=high budget-min=90-per-sub-run runs-as=session {CODE_ORDER}",
    ("implement", "ultra-hard"): "tier=frontier effort=xhigh retry-effort=max budget-min=90-per-sub-run"
                                 f" runs-as=session {CODE_ORDER}",
}
# Reviews take the tier above the work, at least strong; advice and committee seats at least strong.
OTHER_TIERS = {
    "review": ("strong", "frontier", "frontier", "frontier", "frontier"),
    "advise": ("strong", "strong", "frontier", "frontier", "frontier"),
    "committee": ("strong", "strong", "frontier", "frontier", "frontier"),
}
GRADES = ("easy", "medium", "hard", "very-hard", "ultra-hard")
EFFORT = ("effort=medium", "effort=medium", "effort=medium", "effort=high", "effort=xhigh retry-effort=max")
BUDGET = {"review": "30", "advise": "15-30", "committee": "30-45"}
for _kind, _tiers in OTHER_TIERS.items():
    for _grade, _tier, _effort in zip(GRADES, _tiers, EFFORT):
        EXPECTED[(_kind, _grade)] = (f"tier={_tier} {_effort} budget-min={BUDGET[_kind]} runs-as=fresh-context"
                                     f" {CODE_ORDER} agent-rule=not-the-implementer")


def run(*args, script=SCRIPT):
    return subprocess.run([sys.executable, "-I", str(script), *args], capture_output=True, text=True, timeout=30)


class RouteTaskTest(unittest.TestCase):
    def test_every_kind_and_grade_prints_its_matrix_row(self):
        self.assertEqual(len(EXPECTED), 20)
        for (kind, grade), fields in EXPECTED.items():
            with self.subTest(kind=kind, grade=grade):
                result = run("--kind", kind, "--grade", grade)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"route kind={kind} grade={grade} {fields} model=coordinator\n")

    def test_invalid_arguments_exit_2(self):
        for args in ([], ["--kind", "implement"], ["--grade", "easy"],
                     ["--kind", "build", "--grade", "easy"], ["--kind", "implement", "--grade", "trivial"],
                     ["--kin", "implement", "--grade", "easy"]):
            with self.subTest(args=args):
                result = run(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")

    def test_the_copy_in_fnl_delegate_is_identical(self):
        self.assertEqual(SCRIPT.read_bytes(), COPY.read_bytes())
        self.assertEqual(run("--kind", "review", "--grade", "hard", script=COPY).stdout,
                         run("--kind", "review", "--grade", "hard").stdout)

    def test_it_imports_nothing_that_runs_a_model_a_process_or_the_network(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, {"argparse", "sys"})
        self.assertFalse(any(isinstance(node, ast.Name) and node.id == "open" for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
