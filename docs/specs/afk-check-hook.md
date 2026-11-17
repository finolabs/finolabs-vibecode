# afk check hook

Status: accepted; rule recorded as the tenth scoped exception in `CLAUDE.md` (owner decisions, 17/11/2026); code follows in its own pull request.

## Why

Under an away lease, `afk/references/lease-rules.md` asks the agent to run `afk.py check` before every action. That is advisory (agent judgment): one skipped call and the credential floor, the only limit `open` keeps, does not apply, and every action costs a second tool call. The pack review of 17/11/2026 (C10, A1) ranked a host-run check as the way to close that gap.

## Owner decisions (17/11/2026)

1. Ship it in 0.3.2.
2. Deny every Tier 3 answer, in both modes ("the most automated direction"): the hook replaces the agent's own `check` call for Bash on Claude Code.
3. A command that cannot be split into words is denied (the floor comes first), with a fixed message asking for a simpler command.

## Behavior

- One `PreToolUse` hook, matcher `Bash`, in its own group of the Claude Code manifest; never in the metrics group.
- Off unless a valid, unexpired away lease exists under the canonical data root; `FNL_AFK_HOOK=off` turns it off.
- Reads `tool_input.command` from the hook input, splits it with `shlex.split` (POSIX mode, no comments), and passes the argv to the same `afk.py` code path `check --coordinator claude --argv-json` runs, in the hook input's `cwd` when it is a directory, else the process working folder.
- Tier 1 answer: allow, print nothing. Tier 3 answer: deny with the fixed message `afk: <code>; this action is parked under the away lease (afk.py check)`. A split error: deny with `afk: the command could not be read; write it as a simpler command`. Any other error (lease, config, import, I/O): allow.
- Side effects are exactly those of a `check` call: counters, limits, merge pins and the approval-used record, in the private state folder. Nothing else is written; the command text is never stored, logged or sent.
- Paths changed through Edit or Write, and every action on Codex and Antigravity, still need the agent's own `check` (advisory, agent judgment). `lease-rules.md` says so.

## Not covered

Codex and Antigravity (no equivalent hook wired here), a Bash call that reaches the same work through another tool, and commands built at run time inside a script the check allowed.

## Verification

- A test per answer: no lease allows; an expired or stopped lease allows; a floor command (`printenv`) denies with `floor`; a strict unknown command denies with `unknown`; an open Tier 1 command allows; an unbalanced quote denies with the split message; an unreadable lease allows; `FNL_AFK_HOOK=off` allows.
- The hook output is checked byte for byte against the fixed messages, and no command text appears in any file the test can read afterwards.
- A merge command through the hook writes the same merge pin a `check` call writes.
