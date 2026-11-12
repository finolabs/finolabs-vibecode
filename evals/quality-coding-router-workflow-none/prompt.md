---
name: quality-coding-router-workflow-none
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

`slugify("Hello World!")` in src/text.py returns `hello-world-` with a trailing dash; it should return `hello-world`. Before anyone changes code, tell me how this fix should be routed and carried out in this repository. Do not edit files. End your answer with exactly two lines: `Workflow: speckit`, `Workflow: mattpocock`, `Workflow: superpowers` or `Workflow: none`, then `Depth: MIN`, `Depth: NORMAL` or `Depth: DEEP`.
