# status

Typed by the user only.

**What it does.** Opens the usage dashboard, a local page built from the usage events and the dispatch ledger: router coverage, skill and agent use, load cost, depth against review outcome, delegation and the review gate (tab `overview`), and running lanes, quota (a weekly pool under the floor you recorded for that install shows amber, as routing counts it out) and active repositories (tab `now`). It also lists this repository's delegated runs still open. `purge` deletes the recorded usage data.

**When to use it.** You want to see how the practice is working for you, check open delegated runs, or delete what was recorded.

**Type:** Claude Code `/finolabs-vibecode:status` (the plain `/status` opens Claude Code's own status); Codex `$status`; Antigravity `/status`. Argument: `[purge]`.

## Tips

- Recording starts only after you consent in `/setup add metrics`; it holds metadata only, never prompts, code, command text or paths, and sends nothing anywhere.
- Leave the page open: while its tab is visible it reloads its data every 5 seconds.
- Run it inside a repository to add that repository to the page by name.
- `purge` asks before deleting; stopping the recording is a second, separate question.
