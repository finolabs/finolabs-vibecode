# restore-point

Typed by the user only. Git repositories only.

**What it does.** Saves the working tree to a private local git ref (`refs/finolabs/restore/<timestamp>`) without touching the index, branch or HEAD, lists the saved points, and restores one after a preview and your yes.

**When to use it.** Before the agent edits, to keep a point you can go back to; later, to see or restore one.

**Type:** Claude Code `/finolabs-vibecode:restore-point` or `/restore-point`; Codex `$restore-point`; Antigravity `/restore-point`. Arguments: `[list|create|restore <name>]` (`list` when none is given).

## Tips

- Restore shows a preview with a digest first and runs only after your clear yes; it saves a `pre-restore` point so the restore can be undone.
- Files that exist now but not in the point are kept, not deleted, so a restore is not an exact rollback.
- Untracked files such as `.env` are captured into the local object store; never push `refs/finolabs/*`.
- Outside a git repository it creates nothing and tells you to run `git init` yourself.
