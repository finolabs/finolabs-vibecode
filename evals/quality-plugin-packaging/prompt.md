---
name: quality-plugin-packaging
tags: [quality]
runs: 2
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

I maintain a repo with six agent skills under skills/. I want one GitHub repo that installs on Claude Code, Codex and Antigravity. Can I just put a single plugin.json at the repo root for all three? Tell me the layout, how to keep versions in sync, and how to check it before release.
