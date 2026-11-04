---
type: llm
weight: 1
---

Pass if the answer gives the first steps in order: run `/fnl-setup` (or `$fnl-setup` on Codex) once, then work as usual with the coding router naming a workflow and depth. It may skip the install step when the plugin is already loaded in this session, and it may mention `/fnl-status` for later. Fail if it skips setup, or if it describes the whole plugin instead of how to begin.
