---
name: quality-plugin-packaging-prepare-only
tags: [quality, behavior]
runs: 2
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:plugin-packaging I want to list my plugin in Anthropic's plugin directory later. For now, only prepare it and check it: do not submit anything yet. List the steps you will take, in order, and end with exactly one line, `Portal validation: RUN NOW` or `Portal validation: WAITS FOR APPROVAL`.
