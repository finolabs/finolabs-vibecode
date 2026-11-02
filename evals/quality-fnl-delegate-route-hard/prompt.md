---
name: quality-fnl-delegate-route-hard
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-delegate You coordinate from Claude Code. Task to delegate: fix an intermittent race in the session-token refresh, where two concurrent refreshes can leave a revoked token valid; no test reproduces the race yet. Facts for this machine: Claude Code, Codex and Antigravity are all reachable; Claude Code's quota is at its 5-hour limit until tonight; Codex and Antigravity have quota left on every model; there is no route judge. Do not dispatch anything. Grade and route the task, then end your answer with exactly one line in the form `Route: <claude|codex|antigravity> <frontier|strong|fast>`.
