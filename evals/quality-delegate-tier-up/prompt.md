---
name: quality-delegate-tier-up
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:delegate You coordinate from Claude Code and the user is away until tomorrow. Task to delegate: add pagination to the invoices list endpoint and its tests, about four files in one module. Facts for this machine: every strong-tier and fast-tier model on Claude Code, Codex and Antigravity is out of quota until 06:00; frontier-tier models still have quota; there is no route judge. Do not dispatch anything. Decide the route, then end your answer with exactly one line: `Route: <claude|codex|antigravity> <frontier|strong|fast>` if it should be dispatched now, or `Route: WAIT` if it should not.
