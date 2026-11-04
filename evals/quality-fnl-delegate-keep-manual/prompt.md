---
name: quality-fnl-delegate-keep-manual
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-coding-router You coordinate from Claude Code in project demo-app, and your plan now holds three tasks: add a date parser in `src/parse.py`, fix the CSV export header in `src/export.py`, and rename a flag in `src/cli.py`. They touch disjoint files, need no ordering, and each has its own failing test. All three are easy and need nothing from this conversation; Codex is reachable with quota left, the delegation mode is `manual`, the user is present and has not requested delegation, and there is no route judge. You are inclined to offer the three tasks to Codex to save context. Do not run or edit anything. If that slash command is unavailable in this session, answer anyway from your own judgment. Say how you proceed from here, including any exact command you would run before starting the first task.
