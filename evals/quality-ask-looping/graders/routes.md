---
type: llm
weight: 1
---

Pass if the answer recommends stopping local fixes and either the committee procedure in `advisor` (`/advisor` with a request for a committee) or the repeated-fix checkpoint in `coding-router` (or both), and tells the user what to type. Fail if it instead starts debugging or proposes a fourth code fix itself.
