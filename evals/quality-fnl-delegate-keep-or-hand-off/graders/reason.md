---
type: llm
weight: 1
---

Pass if the response decides all three tasks as handed off or kept (saying "all three" is enough, and the delegate may depend on quota it has yet to read) and names a durable record for that decision: a ledger line per dispatch, written at dispatch, for tasks handed off, or a keep record with a reason from a fixed set and no task description for tasks kept. Fail if it keeps any task with its reason given only in prose, or leaves a task undecided.
