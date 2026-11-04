---
type: llm
weight: 1
---

Pass if the answer gives the first steps in order: run `/fnl-setup` (or `$fnl-setup` on Codex) and choose Quick, then describe a first real task, with `/fnl-setup-instructions` after the first result (optionally noting that Codex moves it immediately after setup) and `/fnl-status` later. It may skip installation and `/fnl-ask` because both are already done in this session. For a beginner, explain the checks in everyday words rather than requiring workflow or depth labels. Fail if it skips setup, or if it describes the whole plugin instead of how to begin.
