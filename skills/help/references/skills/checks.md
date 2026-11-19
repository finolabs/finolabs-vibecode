# checks

Typed by the user, or loaded by the agent when the task matches.

**What it does.** Verifies before work is claimed or accepted: chooses the targeted tests, reads the evidence, binds proof to the exact revision, and checks a delegated run's report before the coordinator accepts it. It also runs a repository's stored check list locally.

**When to use it.** Before saying work is done, fixed or passing; when you ask "is it done?" or "is it ready to merge?"; when choosing which tests to run; when CI is red, slow or out of minutes.

**Type:** Claude Code `/finolabs-vibecode:checks` or `/checks`; Codex `$checks`; Antigravity `/checks`.

## Tips

- It runs targeted tests for the changed code and its consumers; a full suite runs only when you ask for one.
- A skipped or partly green run, a missing credential, an enabled setting or a tool's DONE is not a pass.
- Store a check list with `/setup add checks`; `checks.py run [--changed]` then runs it. Checks that name test modules are saved light and run at once, outside the heavy-job lock; the rest queue for it. A list saved before light checks existed is all heavy until you save it again.
- Each check is reported as PASS, FAIL, PENDING, SKIP, WAIVED or N/A; only you waive a check.
