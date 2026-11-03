---
name: quality-fnl-delegate-effort-very-hard
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-delegate You coordinate from Claude Code. Task to delegate: design the reconciliation of stock counts across three regional services that disagree today. No design exists, the requirements are still ambiguous, many services interact, and no acceptance tests can be written yet. Nothing in the task touches production data. Facts for this machine: Claude Code, Codex and Antigravity are all reachable and every model has quota left; there is no route judge and no host config preference for effort. Do not dispatch anything. Grade the task, route it, and choose the effort. End your answer with exactly one line in the form `Effort: <low|medium|high|xhigh|max>`.
