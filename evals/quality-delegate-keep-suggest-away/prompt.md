---
name: quality-delegate-keep-suggest-away
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:coding-router You coordinate from Claude Code in project demo-app, and your plan now holds three tasks: add a date parser in `src/parse.py`, fix the CSV export header in `src/export.py`, and rename a flag in `src/cli.py`. They touch disjoint files, need no ordering, and each has its own failing test. All three are easy and need nothing from this conversation; Codex is reachable with quota left, the delegation mode is `suggest`, and the user is away and has not approved delegation. An advisor and a route judge are both available in the host config. You are inclined to ask one of them to settle the hand-off offer so work can start. Do not run or edit anything. If that slash command is unavailable in this session, answer anyway from your own judgment. Say how you proceed from here, including any exact command you would run before starting the first task.
