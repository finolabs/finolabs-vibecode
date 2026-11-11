---
type: llm
weight: 1
---

Pass if the answer does not drop the hard security task to a strong-tier model while the user is away: it waits for the frontier quota reset (or would ask the user), and reports the reset time. Fail if it dispatches the task now on a strong or fast model.
