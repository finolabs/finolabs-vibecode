---
type: llm
weight: 1
---

Pass if the answer grades the task hard or very hard (concurrency and security), routes it at frontier tier, and skips Claude Code because its quota is out, choosing Codex as the next agent in the capability order. Fail if it routes to a strong or fast tier without stating clear acceptance tests, or to Claude Code.
