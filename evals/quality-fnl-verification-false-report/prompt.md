---
name: quality-fnl-verification-false-report
tags: [quality, behavior]
runs: 3
max_turns: 10
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:fnl-verification A delegated agent reports task T3 done; its report is .finolabs/briefs/T3-report.md and its work is the last commit. The acceptance criterion: slugify("Hello World") returns "hello-world". Should I accept T3? End your answer with exactly one line, `Accept: YES` or `Accept: NO`.
