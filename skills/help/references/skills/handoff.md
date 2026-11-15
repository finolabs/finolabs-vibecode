# handoff

Typed by the user, or loaded by `delegate` or on session wrap-up.

**What it does.** Writes a self-contained brief for an agent that starts with zero context. In Dispatch mode it sends one task to another agent now, under a hard time budget; in Resume mode it saves a handover through `tidy` so a later session or another agent continues, and launches nothing.

**When to use it.** Handing one task or half-finished work to an agent, restarting a timed-out or stalled run with a fresh brief, sending review findings back for a fix, or wrapping up to resume later.

**Type:** Claude Code `/finolabs-vibecode:handoff` or `/handoff`; Codex `$handoff`; Antigravity `/handoff`. Arguments: `[--agent claude|codex|antigravity|zcode] [--model <id>] [--worktree] <task>`.

## Tips

- Without `--agent`, `delegate` picks the agent and model.
- `--worktree`, or any parallel dispatch, gives the run its own worktree on a short branch.
- The brief keeps your intent: investigate-only says "Do not edit files"; a refactor says "refactor, not rewrite".
- Dispatch needs `delegate` installed beside it and Resume needs `tidy`; a missing one is named with its install command.
