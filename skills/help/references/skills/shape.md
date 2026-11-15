# shape

Typed by the user, or loaded by the agent when the task matches.

**What it does.** Interviews you in short rounds that settle every decision an idea, plan or design depends on. Each question comes through the host's native question tool with a recommended answer first, and asks only what its earlier decisions allow. Nothing is built, written or dispatched until you confirm the summary.

**When to use it.** You want to brainstorm, discuss, shape or stress-test an idea, plan or design, or requirements are unclear before building; in any language.

**Type:** Claude Code `/finolabs-vibecode:shape` or `/shape`; Codex `$shape`; Antigravity `/shape`. Argument: `<idea, plan or design to shape>`.

## Tips

- The agent looks up facts itself; it asks you only for choices, priorities and trade-offs.
- Want raw ideas instead of decisions? The first round then offers two or three directions to pick from.
- `grilling` (`/grill-me`) runs instead when `shape` is missing or you ask for it by name.
- In a Spec Kit repository it yields to Spec Kit's own clarify step; at depth MIN it is skipped unless you ask.
