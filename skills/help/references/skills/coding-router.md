# coding-router

Loaded by the agent when coding work starts; you can also type it.

**What it does.** The entry point for coding work in any repository. It inspects the goal and sources, picks the workflow path (Spec Kit, mattpocock/skills, obra/superpowers, or none), sets the depth (MIN, NORMAL, DEEP), and names the review and security gates and the proof the work needs.

**When to use it.** Starting, resuming or redirecting an implementation, bug fix, refactor or feature, or brainstorming an idea that leads to code.

**Type:** Claude Code `/finolabs-vibecode:coding-router` or `/coding-router`; Codex `$coding-router`; Antigravity `/coding-router`.

## Tips

- Depth sets the ceremony: MIN for a bounded, reversible seam; DEEP for sensitive boundaries, unknown consumers or irreversible effects.
- A pull request body carries one marker line with the depth and trigger; a repository that adopted `review-gate` blocks the merge without it.
- After two failed corrections of the same invariant it stops before a third and runs a read-only architecture checkpoint.
- A request that is only a review goes to `review-gate`.
