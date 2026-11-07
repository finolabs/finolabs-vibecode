# Brief template

Use every heading except those marked optional; write "none" where one is empty, so the agent knows it was considered.

```
## Task
[Imperative description. Task IDs if the project tracks them. When the result is prose, its language and tone.]

## Checkout
[Absolute path, branch, base commit SHA. "You are the only writer here. Do not push."]

## Context
[Why this task exists; the decisions it rests on.]

## Relevant files
- `path/to/file` — [what it is and why it matters]

## Current state
[What is done, what works, what does not. After an interrupted run: its captured state.]

## What was tried
- [Approach] — [why it failed or was abandoned]

## Waiting on
[Optional. What blocks the work and who unblocks it: a decision, an approval, a fix elsewhere.]

## Linked runs or sessions
[Optional. Other runs or sessions on this work: id, task, state, where its report is.]

## Acceptance criteria
- [ ] [Checkable criterion]

## Tests to run
[The exact targeted commands, and only those.]

## Constraints
- [Project rules that bind this task, quoted or pointed at by path]
- [Files the agent must leave alone, e.g. the coordinator's task list or plan]
- The smallest change that meets the acceptance criteria: no extra abstraction, options, tests or scale work, and tests run only as the Tests to run says, at checkpoints (`fnl-coding-router` "Proportion").
- No secrets in code, commands or commits; never read env or credential files; never print, dump, log or assert on the process environment or any credential; tests build a synthetic environment and compare only variable names.
- [Commit format: atomic commits, subject line, trailers]

## Budget
[N minutes, from the `fnl-delegate` budget table. If the task cannot finish in time, stop, commit nothing broken, and report where it stands. Retry a failing step at most once, then report the failure.]

## Report
Base and new commit SHAs, the test output, uncommitted files, open points.
```

**Secrets and environments.** Run `python3 -I <this skill folder>/scripts/brief_check.py <brief>` before dispatch. This rule-1 lint requires the headings and environment constraint and refuses rule-4 secret patterns; diagnostics name only the rule and line. It is a lint, not the allowlist control.
