"""The merge notice hook prints one fixed line after a successful `gh pr merge`, and nothing otherwise."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/merge_notice_hook.py"
LINE = ("fnl: a pull request merged; merged worktrees of finished delegated runs are being removed in the "
        "background (ledger.py clean-worktrees shows them); for a worktree you made yourself, run "
        "worktree_sweep.py list and, when a candidate, the two git commands it prints; if it closed a spec, "
        "story or large pull request, rename the session for its next work (tidy Titles) (advisory).")


class MergeNoticeHookTest(unittest.TestCase):
    def test_a_merge_starts_one_detached_cleanup_and_respects_the_switch(self):
        import importlib.util
        import io
        from unittest import mock
        spec = importlib.util.spec_from_file_location("merge_notice_under_test", HOOK)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        payload = json.dumps(self.payload("gh pr merge 3 --merge"))
        for mode, expected in (("", 1), ("manual", 0), ("off", 0)):
            with self.subTest(mode=mode), mock.patch.dict(os.environ, {"FNL_WORKTREE_CLEAN": mode}), \
                    mock.patch.object(hook.subprocess, "Popen") as popen, \
                    mock.patch("sys.stdin", io.StringIO(payload)), mock.patch("sys.stdout", io.StringIO()):
                hook.main()
                self.assertEqual(popen.call_count, expected)
                for call in popen.call_args_list:
                    self.assertEqual(call.args[0][2:], [str(hook.LEDGER), "clean-worktrees", "--background",
                                                        "--checkout", "/tmp"])
                    self.assertTrue(call.kwargs["start_new_session"])
        with mock.patch.dict(os.environ, {"FNL_WORKTREE_CLEAN": ""}), \
                mock.patch.object(hook.subprocess, "Popen") as popen, \
                mock.patch("sys.stdin", io.StringIO(json.dumps(self.payload("gh pr view 3")))), \
                mock.patch("sys.stdout", io.StringIO()):
            hook.main()
        popen.assert_not_called()

    def run_hook(self, payload, raw=None):
        data = raw if raw is not None else json.dumps(payload)
        result = subprocess.run([sys.executable, "-I", str(HOOK)], input=data, capture_output=True, text=True,
                                env={"PATH": os.defpath, "FNL_WORKTREE_CLEAN": "off"})
        self.assertEqual(result.returncode, 0)
        return result.stdout

    def payload(self, command, response=None, event="PostToolUse", tool="Bash"):
        return {"hook_event_name": event, "session_id": "s1", "cwd": "/tmp", "tool_name": tool,
                "tool_input": {"command": command}, "tool_response": {} if response is None else response}

    def test_a_successful_merge_prints_the_fixed_line_once(self):
        for command in ("gh pr merge 12 --merge --match-head-commit 0123abc --delete-branch",
                        "cd repo && gh pr merge 12 --merge && gh pr merge 13 --merge",
                        "git fetch; GH_REPO=demo/repo gh pr merge 5 --squash;",
                        "gh pr merge 6 --merge --subject 'Merge the sweep; keep it'",
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
                 self.payload("x" * 9000 + "; gh pr merge 1"),
                 # The overall exit status does not say the merge ran and succeeded.
                 self.payload("gh pr merge 245 --merge || true"),
                 self.payload("false && gh pr merge 245 --merge; true"),
                 self.payload("printf '%s\\n' '; gh pr merge 245 --merge'"),
                 self.payload("gh pr merge 245 --merge | cat"),
                 self.payload("gh pr merge 245 --merge &"),
                 self.payload("(gh pr merge 245 --merge)"),
                 self.payload("gh pr merge 245 --merge\ntrue"),
                 self.payload("echo `gh pr merge 245`"),
                 self.payload("echo ';' gh pr merge 245"),
                 self.payload("echo \\; gh pr merge 245"),
                 self.payload("gh pr merge 245 2>&1"),
                 self.payload("gh pr merge 245 --merge 'unclosed"),
                 # The shell strips quotes, so a quoted excluded flag is still that flag.
                 self.payload('gh pr merge 245 "--help"'),
                 self.payload("gh pr merge 245 '--auto'"),
                 self.payload("gh pr merge 245 --merge \"--\"auto"),
                 self.payload("gh pr merge 245 '-h'"),
                 self.payload("gh pr merge 245 \"--disable-auto\" --merge")]
        for payload in cases:
            with self.subTest(payload=payload["tool_input"]["command"][:40]):
                self.assertEqual(self.run_hook(payload), "")
        for raw in ("", "not json", "[]", "{\"tool_input\": 3}"):
            self.assertEqual(self.run_hook(None, raw=raw), "")

    def test_the_hook_stores_and_sends_nothing(self):
        source = HOOK.read_text()
        rest = source.replace("subprocess.Popen(", "")
        for word in ("urllib", "socket", "http", "open(", "write_text", "logging", "subprocess.run",
                     "subprocess.call", "check_output", "os.system", "shell=True"):
            self.assertNotIn(word, rest)
        # The one process it may start is the delegate skill's own background worktree cleanup.
        self.assertEqual(source.count("subprocess.Popen("), 1)
        self.assertIn('[sys.executable, "-I", str(LEDGER), "clean-worktrees", "--background"', source)

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
