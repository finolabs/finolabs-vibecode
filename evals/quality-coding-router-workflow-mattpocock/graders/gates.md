---
type: llm
weight: 1
---

The repository uses mattpocock/skills (installed in .claude/skills). Pass if the answer routes the change through that pack's tools (for example `tdd` for the red-green loop) and recognizes that a new query parameter reaching a SQL query is untrusted input, so the change needs the security review gate (`security-review-gate` or a security review with a negative test for injection) as well as the code review gate before merge. Fail if it treats the change as MIN, skips the security review, or ignores the installed pack.
