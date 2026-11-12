---
name: quality-delegate-effort-ultra-hard
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:delegate You coordinate from Claude Code. Task to delegate: migrate the live customer-billing database to a new schema. There is no rollback path once the cutover runs, and an earlier run at `high` effort already fell short on the migration plan. Facts for this machine: Claude Code, Codex and Antigravity are all reachable and every model has quota left; there is no route judge and no host config preference for effort. Do not dispatch anything. Grade the task, route it, and choose the effort. End your answer with exactly one line in the form `Effort: <low|medium|high|xhigh|max>`.
