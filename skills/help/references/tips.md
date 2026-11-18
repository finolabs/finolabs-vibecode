# Tips

Read the shared rules in [map.md](map.md#rules). Give the tips that fit the user's question, not the whole list.

- **Open a new session after installing or updating.** Plugins load when a session starts.
- **Check before you change.** `/setup check` is read-only and shows what is set up and what happens automatically on this host.
- **Type the full name when a host command shares it.** On Claude Code, `/finolabs-vibecode:help` and `/finolabs-vibecode:status` reach this plugin; on Codex type `$` instead of `/`.
- **Keep the main checkout on the default branch.** Every branch gets its own worktree; after a merge, `worktree_sweep.py list` shows which ones can go (`commit-messages`), and `delegate` removes its finished runs' worktrees on its own once merged.
- **Save a point before a risky edit.** `/restore-point create` snapshots the working tree; `/restore-point restore <name>` previews first and asks.
- **Shape before you build.** Say "let's brainstorm" or "let's discuss" and `shape` interviews you; nothing is acted on until you confirm.
- **Ask for proof, not a summary.** "Did the tests pass?" makes the agent run `checks` and report what ran, what skipped and what was filtered out.
- **Ask for a UI review with evidence.** "Review the UI of this page" runs `ui-review-gate`: measured contrast, target sizes and overflow at four widths, plus one keyboard pass by hand, reported before anything is changed.
- **Drain before a restart.** `/pause restart` (or `/gtg`) lets running work finish and writes handovers; `/pause resume` afterwards.
- **Wrap up instead of losing context.** Ask to save progress or hand over; `tidy` writes the handover and the next session continues from it.
