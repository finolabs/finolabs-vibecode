---
name: quality-coding-router-depth-deep
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:coding-router Change can_delete_invoice in src/auth.py so a platform support role can delete invoices of any tenant. Route this before anyone changes code: do not edit files. End your answer with exactly one line, `Depth: MIN`, `Depth: NORMAL` or `Depth: DEEP`.
