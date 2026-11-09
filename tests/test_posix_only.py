"""Scripts that need POSIX-only modules name the platform limit on native Windows (issue #193)."""
import json
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
NEEDS_POSIX = re.compile(r"^(?:try:\n    )?import (?:pwd|fcntl)$|^import data_root\b", re.M)

# Blocking the modules makes their import fail as it does on native Windows.
PROBE = textwrap.dedent("""
    import importlib.util, json, sys
    sys.dont_write_bytecode = True
    sys.modules["pwd"] = None
    sys.modules["fcntl"] = None
    results = {}
    for path in json.loads(sys.stdin.read()):
        spec = importlib.util.spec_from_file_location("posix_probe", path)
        try:
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            results[path] = "imported"
        except ImportError as error:
            results[path] = str(error)
        sys.modules.pop("data_root", None)
    print(json.dumps(results))
""")


def candidates():
    return sorted(str(p) for folder in ("scripts", "skills") for p in (ROOT / folder).rglob("*.py")
                  if NEEDS_POSIX.search(p.read_text(encoding="utf-8")))


class PosixOnlyTest(unittest.TestCase):
    def test_import_without_posix_modules_names_the_platform_limit(self):
        paths = candidates()
        self.assertTrue(any(p.endswith("data_root.py") for p in paths))
        out = subprocess.run([sys.executable, "-I", "-c", PROBE], input=json.dumps(paths),
                             capture_output=True, text=True, timeout=120, check=True).stdout
        for path, outcome in json.loads(out).items():
            if outcome == "imported":
                continue
            with self.subTest(path=str(Path(path).relative_to(ROOT))):
                self.assertIn("native Windows is not supported", outcome)


if __name__ == "__main__":
    unittest.main()
