---
name: quality-fnl-coding-router-workflow-mattpocock
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

Add an optional `q` query parameter to `GET /api/products` in src/products.py that filters products by name. Before anyone changes code, tell me how this change should be routed and carried out in this repository. Do not edit files. End your answer with exactly two lines: `Workflow: speckit`, `Workflow: mattpocock`, `Workflow: superpowers` or `Workflow: none`, then `Depth: MIN`, `Depth: NORMAL` or `Depth: DEEP`.
