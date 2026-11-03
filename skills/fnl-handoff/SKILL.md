---
name: fnl-handoff
description: Write a self-contained brief and dispatch one task to Claude Code, Codex or Antigravity under a hard time budget. Use when handing a task or half-finished work to another agent, restarting a stalled or timed-out run, or sending review findings back for a fix.
user-invocable: true
argument-hint: "[--agent claude|codex|antigravity] [--model <id>] [--worktree] <task>"
---

# Handoff

The receiving agent starts with **zero context**: the brief is everything it knows. Write it so the agent could finish the task with no question back to you.

**User's arguments:** $ARGUMENTS

## Prerequisites

Load the `fnl-delegate` skill and the host config it names. Requires the `fnl-delegate` skill installed beside this one. When it is missing, tell the user to add it (`npx skills add finolabs/finolabs-vibecode --skill fnl-delegate`, or install the whole plugin) and stop. Grade and route the task there unless the arguments name an agent.

## Arguments

1. **Agent and model**: `--agent` and `--model`, or ones named in the text; otherwise the `fnl-delegate` routing.
2. **Isolation**: `--worktree`, or any parallel dispatch → a new git worktree on a short branch named after the task, cut from the integration branch tip (`fnl-commit-messages` "Branches").
3. **Task**: everything else.

## The brief

Use every heading; write "none" where one is empty, so the agent knows it was considered.

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

## Acceptance criteria
- [ ] [Checkable criterion]

## Tests to run
[The exact targeted commands, and only those.]

## Constraints
- [Project rules that bind this task, quoted or pointed at by path]
- [Files the agent must leave alone, e.g. the coordinator's task list or plan]
- The smallest change that meets the acceptance criteria: no extra abstraction, options, tests or scale work, and tests run only as the Tests to run says, at checkpoints (`fnl-coding-router` "Proportion").
- No secrets in code, commands or commits; never read env or credential files.
- [Commit format: atomic commits, subject line, trailers]

## Budget
[N minutes, from the `fnl-delegate` budget table. If the task cannot finish in time, stop, commit nothing broken, and report where it stands. Retry a failing step at most once, then report the failure.]

## Report
Base and new commit SHAs, the test output, uncommitted files, open points.
```

**Preserve task semantics.** Investigate-only → "Do not edit files." Fix → "implement the fix." Refactor → "refactor, not rewrite." Carry the user's exact intent and scope.

**Findings sent back.** While the run is still light, send the findings as a follow-up to the same run, one defect per item. Open a new run with a new brief, carrying what was tried, when the run has used about 60% of its context or two rework rounds have not cleared the defects (`fnl-session-hygiene` "Context pressure").

**Prose output.** Write the brief in English and name the output language and tone in the Task. When the result is social content or a document for readers, and the user's instructions give an editing pass for that language, the coordinator runs the pass at acceptance; the agent does not. A plain reply to a user needs no pass.

For Antigravity, write an edit-only brief when its commands fall outside both its allow-rules and what the user granted for this run (`fnl-delegate` "Route"), and paste the search results or excerpts it would otherwise fetch.

## Dispatch

1. Save the brief where `fnl-delegate` "Where files go" puts it, as `<slug>.md` (`fnl-session-hygiene` titles): a local handoff brief in `.finolabs/briefs/`, a brief worth keeping as project documentation in the project's documentation folder.
2. Record the dispatch: `ledger.py start ...` (see `fnl-delegate`), keeping the id.
3. Launch the agent with the host config's command, under the hard cap, in the background, with its log and final output in `.finolabs/logs/`.
4. Tell the user in one line: agent, model, worktree, budget, check deadline, ledger id.

The completion notice brings you back. At the check deadline, judge liveness from artifacts as `fnl-delegate` describes, then accept and record the outcome there.
