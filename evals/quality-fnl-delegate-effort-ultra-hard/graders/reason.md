---
type: llm
weight: 1
---

Pass if the answer grades the task ultra hard (very hard work where a wrong result is costly or hard to undo, and a `high` run already fell short) and picks `xhigh` effort for it, not `max` yet. Fail if it picks `high` or lower, or `max`, or grades it only hard or very hard.
