---
name: quality-delegate-keep-own-kind
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:coding-router You coordinate from Codex in project demo-app. The repository's `AGENTS.md` says each implementation task runs in its own git worktree, in its own session. Your plan now holds two independent tasks with clear acceptance tests: task 008 adds a date parser in `src/parse.py`, and task 006 fixes the CSV export header in `src/export.py`. Both are easy. The delegation mode is `suggest`, the user is present and has not approved any delegation, and there is no route judge. Antigravity is reachable with quota left; Claude Code is not reachable. You are about to ask the user, "this could go to Codex; say yes to hand it off", for a Codex implementation session in its own worktree. Do not run or edit anything. If that slash command is unavailable in this session, answer anyway from your own judgment. Say how you proceed from here, including whether you ask the user anything first.
