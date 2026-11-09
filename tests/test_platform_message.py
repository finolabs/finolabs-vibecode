"""Native Windows is unsupported: scripts that need pwd or fcntl fail with one clear message."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MESSAGE = (
    "finolabs-vibecode needs POSIX file APIs (pwd, fcntl) and supports macOS and Linux; "
    "on Windows run it under WSL."
)
TOP_LEVEL_IMPORT = re.compile(
    r"^(?:try:\n    )?(?:import|from)\s+(?:pwd|fcntl)\b|^import\s+.*\b(?:pwd|fcntl)\b", re.M
)
PROBE = (
    "import runpy, sys\n"
    "sys.modules[sys.argv[2]] = None\n"
    "path = sys.argv[1]\n"
    "sys.path.insert(0, str(__import__('pathlib').Path(path).parent))\n"
    "runpy.run_path(path, run_name='probe')\n"
)


def imports_module(text, module):
    return re.search(
        r"^(?:try:\n    )?(?:import|from)\s+%s\b|^import\s+.*\b%s\b" % (module, module), text, re.M
    )


def affected_scripts():
    found = []
    for folder in ("skills", "scripts"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if TOP_LEVEL_IMPORT.search(path.read_text(encoding="utf-8")):
                found.append(path)
    return found


def affected_pairs():
    """Each (script, module) where the script imports that module at the top level."""
    return [
        (path, module)
        for path in affected_scripts()
        for module in ("pwd", "fcntl")
        if imports_module(path.read_text(encoding="utf-8"), module)
    ]


class PlatformMessageTests(unittest.TestCase):
    def test_affected_scripts_are_found(self):
        self.assertGreater(len(affected_scripts()), 0)

    def test_blocked_posix_modules_give_one_clear_error(self):
        # Each directly imported module is blocked on its own, so a guard missing after the first import shows.
        for path, module in affected_pairs():
            with self.subTest(script=str(path.relative_to(ROOT)), blocked=module):
                result = subprocess.run(
                    [sys.executable, "-I", "-c", PROBE, str(path), module],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(ROOT),
                    env={},
                )
                self.assertNotEqual(result.returncode, 0)
                lines = result.stderr.strip().splitlines()
                self.assertEqual(lines[0], "Traceback (most recent call last):")
                self.assertEqual(lines[-1], "ImportError: " + MESSAGE)
                self.assertNotIn("ModuleNotFoundError", result.stderr)
                self.assertNotIn("During handling of the above exception", result.stderr)

    def test_hook_commands_end_with_exit_zero(self):
        for manifest in (".claude-plugin/hooks.json", ".codex-plugin/hooks.json"):
            data = json.loads((ROOT / manifest).read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for groups in data["hooks"].values()
                for group in groups
                for hook in group.get("hooks", [])
                if "command" in hook
            ]
            self.assertTrue(commands, manifest)
            for command in commands:
                with self.subTest(manifest=manifest):
                    self.assertTrue(command.rstrip().endswith("exit 0"), command)


if __name__ == "__main__":
    unittest.main()
