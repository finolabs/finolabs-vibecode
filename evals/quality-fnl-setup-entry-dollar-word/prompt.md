---
name: quality-fnl-setup-entry-dollar-word
tags: [quality, behavior]
runs: 2
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-setup This is a Codex session and I typed `$fnl-setup instructions`. This is a read-only response test: do not run or edit anything. Use these supplied facts as the full state: no user-level instruction file exists, and I have said nothing else. Tell me what you would ask first and how any file would be written.
