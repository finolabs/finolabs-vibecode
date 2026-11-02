---
name: quality-fnl-delegate-review-route
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-delegate You coordinate from Claude Code. Codex just finished a medium task (a new CSV export endpoint across three files, with tests) using `gpt-6.1-sol`. It now needs its code review. Claude Code, Codex and Antigravity are reachable and every model has quota; there is no route judge. Do not dispatch anything. Route the review, then end your answer with exactly one line in the form `Route: <claude|codex|antigravity> <frontier|strong|fast>`.
