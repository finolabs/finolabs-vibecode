"""The merge notice hook prints one fixed line after a successful `gh pr merge`, and nothing otherwise."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/merge_notice_hook.py"
LINE = "fnl: a pull request merged; run worktree_sweep.py to remove its clean worktree (advisory)."


class MergeNoticeHookTest(unittest.TestCase):
    def run_hook(self, payload, raw=None):
        data = raw if raw is not None else json.dumps(payload)
        result = subprocess.run([sys.executable, "-I", str(HOOK)], input=data, capture_output=True, text=True,
                                env={"PATH": os.defpath})
        self.assertEqual(result.returncode, 0)
        return result.stdout

    def payload(self, command, response=None, event="PostToolUse", tool="Bash"):
        return {"hook_event_name": event, "session_id": "s1", "cwd": "/tmp", "tool_name": tool,
                "tool_input": {"command": command}, "tool_response": {} if response is None else response}

    def test_a_successful_merge_prints_the_fixed_line_once(self):
        for command in ("gh pr merge 12 --merge --match-head-commit 0123abc --delete-branch",
                        "cd repo && gh pr merge 12 --merge && gh pr merge 13 --merge",
                        ["gh", "pr", "merge", "4", "--merge"]):
            with self.subTest(command=command):
                output = self.run_hook(self.payload(command, {"stdout": "", "stderr": "", "interrupted": False}))
                printed = json.loads(output)
                self.assertEqual(printed["hookSpecificOutput"],
                                 {"hookEventName": "PostToolUse", "additionalContext": LINE})
                self.assertEqual(len(output.strip().splitlines()), 1)

    def test_nothing_is_printed_without_a_successful_merge(self):
        cases = [self.payload("gh pr merge 12 --merge", {"exit_code": 1}),
                 self.payload("gh pr merge 12 --merge", {"interrupted": True}),
                 self.payload("gh pr merge 12 --merge", event="PostToolUseFailure"),
                 self.payload("gh pr merge 12 --auto --merge"),
                 self.payload("gh pr merge --help"),
                 self.payload("echo gh pr merge 12"),
                 self.payload("gh pr view 12"),
                 self.payload("gh pr merge 12", tool="Edit"),
                 self.payload("x" * 9000 + "; gh pr merge 1")]
        for payload in cases:
            with self.subTest(payload=payload["tool_input"]["command"][:40]):
                self.assertEqual(self.run_hook(payload), "")
        for raw in ("", "not json", "[]", "{\"tool_input\": 3}"):
            self.assertEqual(self.run_hook(None, raw=raw), "")

    def test_the_hook_stores_and_sends_nothing(self):
        source = HOOK.read_text()
        for word in ("subprocess", "urllib", "socket", "http", "open(", "write_text", "logging"):
            self.assertNotIn(word, source)

    def test_the_manifest_declares_it_for_bash_on_claude_code_only(self):
        manifest = json.loads((ROOT / ".claude-plugin/hooks.json").read_text())
        groups = [g for g in manifest["hooks"]["PostToolUse"] if any("merge_notice_hook.py" in h["command"] for h in g["hooks"])]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["matcher"], "Bash")
        [hook] = groups[0]["hooks"]
        self.assertEqual(hook["command"], 'python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/merge_notice_hook.py" 2>/dev/null; exit 0')
        self.assertFalse(hook.get("async", False))
        self.assertNotIn("merge_notice_hook.py", (ROOT / ".codex-plugin/hooks.json").read_text())


if __name__ == "__main__":
    unittest.main()
