---
type: llm
weight: 1
---

Pass if the answer gives the first steps in order: run `/setup` (or `$setup` on Codex) and choose Quick, then describe a first real task, with `/setup instructions` after the first result (optionally noting that Codex moves it immediately after setup) and `/finolabs-vibecode:status` later. It may skip installation and `/finolabs-vibecode:help` because both are already done in this session. For a beginner, explain the checks in everyday words rather than requiring workflow or depth labels. Fail if it skips setup, or if it describes the whole plugin instead of how to begin.

If setup modes are explained, require Quick (one companion multi-select, then at most four offers to show commands), Advanced (per-companion interview and widening features), and beginner (no companion question). Fail on the retired Detailed mode name, on counting a default or "install everything" as an answer, or on executing a companion install.
