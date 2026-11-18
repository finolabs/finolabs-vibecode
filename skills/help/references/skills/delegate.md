# delegate

Loaded by the agent when work is split across agents; you can also type it.

**What it does.** Hands work to other coding agents (Claude Code, Codex, Antigravity, ZCode) and runs it from whichever one you are in: grade, route, brief, dispatch, watch, accept and record each run in the ledger.

**When to use it.** Giving a task to another agent, choosing the agent and model for several tasks, running independent tasks in parallel, a quota running out, or a watched run that stalls or times out.

**Type:** Claude Code `/finolabs-vibecode:delegate` or `/delegate`; Codex `$delegate`; Antigravity `/delegate`.

## Tips

- `/setup mode` shows or changes Delegation mode; `/setup scan` refreshes which agents and models are present.
- Parallel runs go up to the limit you set per repository (3 by default).
- Accepting a run needs a passing check receipt for its current head (`checks`).
- For the brief of a single task, use `handoff`.
- Worktrees of finished runs are removed in the background once their branch merges, clean and pushed. `ledger.py clean-worktrees` runs it by hand with a report; `FNL_WORKTREE_CLEAN=manual` keeps only that, and `off` stops it.
