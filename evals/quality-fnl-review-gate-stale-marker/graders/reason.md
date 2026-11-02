---
type: llm
weight: 1
---

Pass if the answer says the code review comment is bound to an older commit than the current head (1111… versus 2222…), so it is stale and the code reviewer must review the new head and post again before merging. Fail if it treats the code approval as valid for the current head.
