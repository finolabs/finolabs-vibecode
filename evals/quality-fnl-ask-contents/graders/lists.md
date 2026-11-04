---
type: llm
weight: 1
---

Pass if the answer lists the plugin's contents grouped by purpose, includes the three agents (verifier, reviewer, security reviewer), and separates the skills the user types (such as `fnl-setup`, `fnl-status`, `fnl-ask`) from those the agent loads on its own. Fail if it lists only a few skills, invents skills that do not exist, mixes up who invokes what, or states a total number of skills (for example "23 skills").
