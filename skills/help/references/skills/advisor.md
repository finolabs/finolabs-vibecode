# advisor

Typed by the user, or proposed by the agent, which waits for your yes.

**What it does.** Gets one second opinion from another model family, or convenes a committee of two contrasting families for root-cause analysis and a plan. Both are read-only: the advisor reads and judges, you stay the decider.

**When to use it.** Before a risky design or fix that cannot be undone or changes a contract, when you want to know what another model thinks, or when work is stuck or looping on failed fixes.

**Type:** Claude Code `/finolabs-vibecode:advisor` or `/advisor`; Codex `$advisor`; Antigravity `/advisor`. Arguments: `[--agent claude|codex|antigravity|zcode] <question>`.

## Tips

- Each run spends quota, so the agent proposes one and waits; asking for it yourself needs no proposal.
- `--agent` picks the advisor; otherwise it prefers a family other than the one you run on.
- You get the advisor's verdict and the agent's own recommendation, with where they agree and differ.
- It needs `delegate` installed beside it; when that is missing it tells you how to add it and stops.
