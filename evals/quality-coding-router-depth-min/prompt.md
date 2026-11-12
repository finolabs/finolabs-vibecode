---
name: quality-coding-router-depth-min
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:coding-router Fix the typo "recieve" in README.md. Route this before anyone changes code: do not edit files. End your answer with exactly one line, `Depth: MIN`, `Depth: NORMAL` or `Depth: DEEP`.
