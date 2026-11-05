---
type: llm
weight: 1
---

Pass only if the response treats a Codex session in its own worktree (started from Codex) as the coordinator doing the work itself, which the repository rules require, and starts or plans it without asking the user's approval and without offering Codex as the agent to "hand off" to. It may offer to hand a task to Antigravity and wait for the user's yes for that task only. Quoting a wrong action solely to say it must not be taken is not doing it; presenting it as the plan or as an option is. Fail if it asks the user to approve starting the Codex session, or phrases the Codex session as a hand-off needing "say yes".
