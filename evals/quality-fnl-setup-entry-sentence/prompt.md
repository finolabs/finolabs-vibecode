---
name: quality-fnl-setup-entry-sentence
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-setup set up everything and say yes to all the questions. This is a read-only response test: do not run or edit anything. Use these supplied facts as the full state: this is a Codex session where a word after the command may not be passed, so only this sentence reached you.
