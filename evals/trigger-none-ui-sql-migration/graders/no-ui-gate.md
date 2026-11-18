---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?ui-review-gate"'
min: 0
max: 0
---

`ui-review-gate` is not invoked: a database migration touches no user-facing UI. Other skills, such as `coding-router`, may fire.
