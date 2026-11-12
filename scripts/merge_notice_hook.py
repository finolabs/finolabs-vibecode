#!/usr/bin/env python3
"""Claude Code PostToolUse hook: after a successful `gh pr merge`, remind the agent to sweep its worktree.

Reads one hook payload from stdin. When the event is PostToolUse for the Bash tool, the call was not
interrupted, any exit code the payload reports is 0, and the command runs `gh pr merge` (not `--auto`,
`--disable-auto` or `--help`), it prints one fixed line as context for the agent. A failed Bash call
reaches the PostToolUseFailure event instead, so it prints nothing. One Bash call prints the line at
most once. The command text is tested in memory and discarded: it is never stored, logged or sent.
The hook stores nothing, starts nothing, always exits 0 and never blocks the session.
"""

import json
import re
import sys

# A command starts at the beginning of the text or after ; & | ( or a newline, optionally behind VAR=value words.
START = r"(?:^|[;&|(\n])[ \t]*(?:\w+=\S+[ \t]+)*"
MERGE = re.compile(START + r"gh[ \t]+pr[ \t]+merge(?![\w-])([^;&|)\n]*)")
NOT_A_MERGE = re.compile(r"(?:^|[ \t])(?:--auto|--disable-auto|--help|-h)(?![\w-])")
EXIT_KEYS = ("exit_code", "exitCode", "returnCode", "return_code")
MAX_COMMAND = 8192  # longer command text is not tested at all
LINE = "fnl: a pull request merged; run worktree_sweep.py to remove its clean worktree (advisory)."


def succeeded(response):
    """False when the payload says the call was interrupted or exited non-zero; True otherwise."""
    if not isinstance(response, dict):
        return True
    if response.get("interrupted") is True:
        return False
    for key in EXIT_KEYS:
        if key in response and response[key] not in (0, None):
            return False
    return True


def merged(command):
    if isinstance(command, list) and all(isinstance(word, str) for word in command):
        command = " ".join(command)  # an argv array, as some hosts send it
    if not isinstance(command, str) or len(command) > MAX_COMMAND or "merge" not in command:
        return False
    return any(not NOT_A_MERGE.search(found.group(1)) for found in MERGE.finditer(command))


def main():
    try:
        payload = json.loads(sys.stdin.read(65536) or "null")
        if not isinstance(payload, dict):
            return
        if payload.get("hook_event_name") != "PostToolUse" or payload.get("tool_name") != "Bash":
            return
        data = payload.get("tool_input")
        if not isinstance(data, dict) or not succeeded(payload.get("tool_response")):
            return
        if merged(data.get("command")):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": LINE}}))
    except Exception:
        pass  # a reminder never fails or blocks the session


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)
