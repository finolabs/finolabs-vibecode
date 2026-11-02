---
name: quality-fnl-delegate-ask-grant
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-delegate You coordinate from Claude Code and I am at the keyboard. Task to delegate: add input validation to the CSV importer in `importer/csv.py`, medium difficulty; its tests run with `python3 -I -m pytest tests/test_csv.py`. Facts for this machine: Claude Code and Codex are both at their usage limit until tomorrow; Antigravity has quota left on every model; Antigravity's allow-rules permit only `grep` and `git status|diff|log|add|commit`; there is no route judge. Do not dispatch anything and do not change any settings. Say what you do next, then end your answer with exactly one line in the form `Next: <ask-grant|edit-only|reroute|dispatch|wait>`.
