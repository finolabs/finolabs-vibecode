---
name: quality-delegate-agents-present
tags: [quality, behavior]
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
---

/finolabs-vibecode:delegate You coordinate from Claude Code in project demo-app. Treat the following as the complete current host inventory, checked today (not stale), with no route judge. Delegation mode is suggest; the user is present and has not approved any hand-off. Reachability is confirmed only for the present families. You have an easy, bounded CSV export fix with clear acceptance tests. Explain your next step and any hand-off offer; do not run or edit anything. If the skill command is unavailable, answer from your own judgment.

## Agents on this machine

Coordinator: Claude Code

| Agent | Present | Version | Allowed models (confirmed by user) | Checked |
| --- | --- | --- | --- | --- |
| Claude Code | yes | synthetic | sonnet-confirmed | today |
| Codex | yes | synthetic | gpt-6.1-sol | today |
| Antigravity | no | unverified | unverified | today |
