---
type: llm
weight: 1
---

Pass if the response reports observed findings about the environment (for example: which agent CLIs or plugins are present or absent, whether a delegation host config exists, that the repository has CLAUDE.md and no AGENTS.md or Agent skills section) before proposing anything. Where a check needs a command the agent cannot run, it says the item is unverified rather than guessing; that counts as a pass for that item.
