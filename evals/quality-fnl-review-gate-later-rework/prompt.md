---
name: quality-fnl-review-gate-later-rework
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-review-gate Can pull request #42 merge now? `gh` is not available in this sandbox: pr-42.json holds the output of `gh pr view 42 --json headRefOid,comments`, and permissions.json holds each commenter's repository permission from the collaborators API. Do not merge anything. End your answer with exactly one line, `Merge: YES` or `Merge: NO`.
