---
name: quality-fnl-delegate-effort-hard
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-delegate You coordinate from Claude Code. Task to delegate: add per-tenant rate limiting across the API gateway, the worker queue and the admin settings page. The acceptance tests are written and failing, the consumers of each changed module are known, and nothing touches data that cannot be restored. Facts for this machine: Claude Code, Codex and Antigravity are all reachable and every model has quota left; there is no route judge and no host config preference for effort. Do not dispatch anything. Grade the task, route it, and choose the effort. End your answer with exactly one line in the form `Effort: <low|medium|high|xhigh|max>`.
