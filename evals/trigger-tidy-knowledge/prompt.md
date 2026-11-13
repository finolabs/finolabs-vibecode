---
name: trigger-tidy-knowledge
tags: [trigger]
runs: 3
max_turns: 5
timeout_seconds: 180
allowed_tools: [Skill]
---

We just decided to keep the payment retries idempotent by request ID, after the double-charge incident last week. Make sure every agent working on this project knows that decision and why, from now on.
