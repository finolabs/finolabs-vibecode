---
name: quality-coding-router-workflow-speckit
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

Add a CSV export of a shopper's own orders to this app. Before anyone changes code, tell me how this feature should be routed in this repository and what the first step is. Do not edit files. End your answer with exactly two lines: `Workflow: speckit`, `Workflow: mattpocock`, `Workflow: superpowers` or `Workflow: none`, then `Next: <the skill or step to run first>`.
