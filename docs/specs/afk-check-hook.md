# afk check hook

Status: accepted; rule recorded as the tenth scoped exception in `CLAUDE.md` (owner decisions, 17/11/2026); code follows in its own pull request.

## Why

Under an away lease, `afk/references/lease-rules.md` asks the agent to run `afk.py check` before every action. That is advisory (agent judgment): one skipped call and the credential floor, the only limit `open` keeps, does not apply, and every action costs a second tool call. The pack review of 17/11/2026 (C10, A1) named a host-run check as the way to close that gap and placed it under "too risky for 0.3.2, defer"; owner decision 1 below overrides that placement.

## Owner decisions (17/11/2026)

1. Ship it in 0.3.2.
2. Deny every Tier 3 answer, in both modes ("the most automated direction"): the hook replaces the agent's own `check` call for Bash on Claude Code.
3. A command that cannot be split into words is denied (the floor comes first), with a fixed message asking for a simpler command.

The review of this rule (PR 336) made the hook fail closed once a lease is live, as `check` does, in line with decision 3.

## Behavior

- One `PreToolUse` hook, matcher `Bash`, in its own group of the Claude Code manifest with `"timeout": 15`; never in the metrics group.
- Off unless a valid, unexpired away lease exists under the canonical data root; `FNL_AFK_HOOK=off` turns it off. No lease, an expired, stopped or unreadable lease, and any error before the lease is established allow with no output.
- Reads `tool_input.command` and `cwd` from the hook input. A newline outside single or double quotes becomes a ` ; ` separator, then `shlex.split` (POSIX mode, no comments) gives the argv. A heredoc body is therefore judged line by line: a false denial is possible, a missed floor command is not.
- This install's own `afk.py` (the resolved path of `skills/delegate/scripts/afk.py` beside the hook) run as `python3 [-I] <path> <sub>` with `<sub>` one of `stop`, `log`, `review`, `effective`, `rules`, `check`, `packet-check`, and nothing after an operator, is allowed without judgment, so `/afk stop`, Decide records and reviews keep working in `strict`.
- Every other argv goes to the same `afk.py main(['check', '--coordinator', 'claude', '--argv-json', ...])`, run in `cwd`. A missing `cwd`, or one that is not a directory, denies with `unsafe`.
- Each word holding `~`, `$` or a glob character (`*`, `?`, `[`) is also expanded in memory (`os.path.expanduser`, `os.path.expandvars`, then `glob`, at most 200 matches per word); when `afk.py`'s floor reads any match as a floor path, the hook denies with `floor`. Expanded values and paths are never stored, logged or printed.
- Tier 1 answer: print nothing, return no decision, so the user's own permission rules still apply (never `permissionDecision: allow`). Tier 3 answer: deny with `afk: <code>; this action is parked under the away lease (afk.py check)`. A split error: deny with `afk: the command could not be read; write it as a simpler command`. Any error once the lease is live, and the hook's own 12-second alarm: deny with `afk: unsafe; ...` (the same message form).
- Side effects are exactly those of a `check` call: counters, limits, merge pins and the approval-used record, in the private state folder.
- `lease-rules.md` on Claude Code: the agent does not run its own `check` before a Bash command and does not use `check ... && <command>` there (the hook judges the command; a second check would double the counters and spend a one-time approval). `check --paths` before an edit-tool change, and every check on Codex, stay the agent's (advisory, agent judgment).

## Not covered

Codex and Antigravity (no equivalent hook wired here); a Bash call that reaches the same work through another tool; commands built at run time inside a script the check allowed; and expansions the hook cannot reproduce (command substitution output, a variable set earlier in the same command).

## Verification

Tests in `tests/test_afk_check_hook.py`, each through the real script under a real `afk start` lease in a synthetic home:

- no lease allows; a stopped lease and `FNL_AFK_HOOK=off` allow; other tools and bad input allow;
- open: `printenv`, `echo ok && env`, `ls` then `printenv` on the next line, a heredoc followed by `printenv`, and `cat ~/.n?trc` (with a synthetic `.netrc`) deny with `floor`; `git status` and a multi-line quoted commit message are silent;
- strict: an unknown command denies with `unknown`; `afk.py stop`, `afk.py log ...` and `afk.py check ...` of this install are silent; `cd x && git status` follows `check`;
- an unbalanced quote denies with the split message; a non-directory `cwd` denies with `unsafe`; a classifier error under a live lease denies with `unsafe`;
- the command text and an expanded path appear in no file the test can read afterwards; a merge command writes the same merge pin a `check` call writes; the manifest holds the hook in its own group with its timeout.
