#!/usr/bin/env python3
"""Claude Code PostToolUse hook: after a successful `gh pr merge`, remind the agent to sweep its worktree.

Reads one hook payload from stdin. When the event is PostToolUse for the Bash tool, the call was not
interrupted, any exit code the payload reports is 0, and the last command of the line is `gh pr merge`
(not `--auto`, `--disable-auto` or `--help`), it prints one fixed line as context for the agent. A failed
Bash call reaches the PostToolUseFailure event instead, so it prints nothing. One Bash call prints the
line at most once. The command text is tested in memory and discarded: it is never stored, logged or sent.
The hook stores nothing, starts nothing, always exits 0 and never blocks the session.

The payload carries only the whole command's outcome, so the hook trusts it only where that outcome is
the merge's own: one line whose commands are joined by `;` or `&&` alone and whose last command is the
merge. It prints nothing for `||`, a pipe, a background `&`, a subshell or group, a redirection, a
command substitution, a line break, unbalanced quotes, or a merge that is not the last command. It cannot
tell from the payload whether the shell ran with errexit off inside a sourced script, whether an alias or
function named `gh` replaced the real program, or whether a merge queue only queued the pull request.
"""

import json
import shlex
import sys

OPERATORS = (";", "&&")  # the only separators whose last command decides the shell's exit status here
NOT_A_MERGE = ("--auto", "--disable-auto", "--help", "-h")
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


def last_command(command):
    """The words of the line's last command, or None when its outcome is not the line's outcome."""
    if "\n" in command.strip() or "`" in command or "$(" in command or "\\" in command:
        return None
    # Not posix: a quoted ';' keeps its quotes, so it never reads as an operator.
    lexer = shlex.shlex(command, posix=False, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes
        return None
    commands = [[]]
    for token in tokens:
        if token in OPERATORS:
            commands.append([])
        elif lexer.punctuation_chars and token and all(c in lexer.punctuation_chars for c in token):
            return None  # ||, |, &, (, ), <, > and the like
        else:
            commands[-1].append(token)
    while commands and not commands[-1]:
        commands.pop()  # a trailing ;
    return commands[-1] if commands else None


def merged(command):
    if isinstance(command, list) and all(isinstance(word, str) for word in command):
        words = command  # an argv array, as some hosts send it
    elif isinstance(command, str) and len(command) <= MAX_COMMAND and "merge" in command:
        words = last_command(command)
    else:
        return False
    if not words:
        return False
    while words and "=" in words[0] and words[0].split("=", 1)[0].isidentifier():
        words = words[1:]  # VAR=value words before the program
    return words[:3] == ["gh", "pr", "merge"] and not any(word in NOT_A_MERGE for word in words[3:])


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
