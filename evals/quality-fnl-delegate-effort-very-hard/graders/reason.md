---
type: llm
weight: 1
---

Pass if the answer grades the task very hard (novel design, high ambiguity, many interacting parts) and picks `high` effort for it. Fail if it picks `medium` or lower, or `xhigh` or `max`, or grades it hard, or grades it ultra hard without a costly or irreversible element in the task.
