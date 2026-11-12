---
name: quality-review-gate-low-risk-lane
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:review-gate Two pull requests are ready: pr-51.txt and pr-52.txt list the files each one changes. The plugin's reviewer agents are available. Before merge, how many reviewers does each need: one reviewer covering both reviews, or two reviewers? Do not review or merge anything. End your answer with exactly two lines, `PR 51 reviewers: ONE` or `PR 51 reviewers: TWO`, then `PR 52 reviewers: ONE` or `PR 52 reviewers: TWO`.
