---
name: fnl-session-hygiene
description: Keep agent sessions healthy across long work. Use when a session's context passes about 60%, a phase or task changes, a session title is stale, work moves to a fresh session or another writer, or the task ends with decisions and evidence to preserve.
---

# Session hygiene

## Context pressure

Before assigning new work, inspect actual context usage where the surface exposes it.

- Above about **60%**, at a safe idle boundary, compact the session for the same workstream. When the agent cannot compact itself, ask the user to, or propose a fresh session with a handover.
- A wholly new, independent task starts in a fresh, correctly named session in the matching checkout, with a short verified handover.
- Delegated agents follow the same rule: start a fresh run with a short handover brief rather than resuming a run that has used much of its window.
- Without usage telemetry, say so; never invent a percentage or interrupt active work.

## Handover content

Every compaction, fresh session or writer change carries: goal and acceptance, decisions, work in progress, evidence and its limits, and the next action. Unresolved decisions are recorded before dependent work starts.

## Titles

Name this session as project + current activity at entry, on a stale resume, and after a material change of task or phase. Use the host's supported title mechanism and its conventions; rename only sessions you started. Keep titles accurate without churn.

## Writers and checkouts

- One writer per scope, with an explicit handover between writers.
- Prefer a suitable existing checkout or worktree; stricter isolation rules win.
- Keep notes, briefs and logs in the durable folder `fnl-orchestration` "Where files go" names; temporary directories and scratchpads are wiped on restart.
