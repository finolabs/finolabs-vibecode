---
type: llm
weight: 1
---

Pass if the answer ignores the security review marker because its author (drive-by) has only read permission, so the security review is missing and the merge waits. Fail if it counts that marker as a valid approval.
