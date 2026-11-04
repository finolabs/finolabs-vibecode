---
type: llm
weight: 1
---

Pass if the answer lists the plugin's contents grouped by purpose, includes the three agents (verifier, reviewer, security reviewer), and separates the skills only the user types (`fnl-setup`, `fnl-setup-instructions`, `fnl-status`, `fnl-ask`) from `fnl-advisor`, `fnl-committee` and `fnl-handoff` (which the user can also type: `fnl-delegate` loads `fnl-handoff` directly, while the agent proposes `fnl-advisor` and `fnl-committee` and waits for a yes) and from the rest, which the agent loads on its own. Fail if it lists only a few skills, invents skills that do not exist, mixes up who invokes what (for example, says the agent never loads `fnl-handoff`), or states a total number of skills (for example "23 skills").
