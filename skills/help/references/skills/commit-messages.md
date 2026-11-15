# commit-messages

Loaded by the agent when committing or working with branches; you can also type it.

**What it does.** Shapes atomic commits with imperative subjects, the pull request description, and the branch flow: naming, base, sync, conflicts, merge, cleanup and backports.

**When to use it.** Staging and committing, naming or creating a branch, syncing with the base, resolving conflicts, merging a pull request and cleaning up after it.

**Type:** Claude Code `/finolabs-vibecode:commit-messages` or `/commit-messages`; Codex `$commit-messages`; Antigravity `/commit-messages`.

## Tips

- The main checkout stays on the default branch and clean; every branch gets its own worktree.
- Branch names follow `<type>/<task>`, for example `fix/142-parser-null`.
- Merges are pinned to the reviewed head (`gh pr merge <number> --merge --match-head-commit <sha>`); after a merge, `worktree_sweep.py list` shows which worktrees can go and deletes nothing itself.
- Committing locally is part of the task; pushing, force-pushing and merging need your explicit go.
