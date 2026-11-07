## Parallel dispatch

Tasks are independent when they touch disjoint files, need no ordering, and need not land in one commit. Independent tasks go one per agent run, in parallel, at most 5 dispatched at one time (the host config may set a lower limit), each in its own worktree; tasks that share files or depend on each other run in sequence. Sizing, worktrees and merging back: [references/dispatch.md](dispatch.md) "Parallel dispatch".
