---
type: llm
weight: 1
---

Pass if the answer lists the plugin's contents grouped by purpose, includes the three agents (verifier, reviewer, security reviewer), and separates the skills only the user types (`setup`, with its subcommands `instructions`, `check`, `scan` and `mode`, `status`, `update`, `help`) from `advisor` and `handoff` (which the user can also type: `delegate` loads `handoff` directly, while the agent proposes `advisor` for one opinion or a committee and waits for a yes) and from the rest, which the agent loads on its own. Fail if it lists only a few skills, invents skills that do not exist, mixes up who invokes what (for example, says the agent never loads `handoff`), or states a total number of skills (for example "23 skills").
