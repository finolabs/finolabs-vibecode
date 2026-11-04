---
name: fnl-session-hygiene
description: Keep agent sessions healthy across long work. Use when a session's context passes about 60%, a phase or task changes, a session needs a name or its title is stale, work moves to a fresh session or another writer, or the task ends with decisions and evidence to preserve.
---

# Session hygiene

## Context pressure

Before assigning new work, inspect actual context usage where the surface exposes it.

- Above about **60%**, at a safe idle boundary, compact the session for the same workstream. When the agent cannot compact itself, ask the user to, or propose a fresh session with a handover. This is advisory unless the host's own threshold or a hook enforces it; no host signal this pack relies on gives exact usage, so check at task boundaries and when the host shows usage. `/fnl-setup` Check reports compaction enforcement as unverified until verified.
- A wholly new, independent task starts in a fresh, correctly named session in the matching checkout, with a short verified handover.
- A finished user story, with its review gate closed, is a natural boundary: prefer a fresh session for the next story with a short handover. A coordinator session whose context is still light may continue (`fnl-coordinator-sessions`).
- Delegated agents follow the same rule: start a fresh run with a short handover brief rather than resuming a run that has used much of its window.
- Without usage telemetry, say so; never invent a percentage or interrupt active work.

Before a compaction, a fresh session or the end of the work, write back a decision or lesson that would change what an agent does next time, as `fnl-knowledge` says. A compaction with nothing new to keep carries only the handover.

## Handover content

`fnl-handoff` Resume mode writes a handover for a later session or another agent.

For a portable handover document, the user can type `/handoff` from [mattpocock/skills](https://github.com/mattpocock/skills); its `/ask-matt` also explains when to continue, clear, hand off or compact.

Every compaction, fresh session or writer change carries: goal and acceptance, decisions, work in progress, evidence and its limits, and the next action. Unresolved decisions are recorded before dependent work starts.

## Titles

A title tells the user which session holds which work, without opening it. Format:

```
<project> <scope>: <activity>
```

- **project**: the repository or product name the user knows, as short as stays unambiguous (`billing-api`).
- **scope**, optional: the feature, spec or ticket the work belongs to (`003 search`, `PAY-142`, `US4`, `T044–T046`). Leave it out for work that has none.
- **activity**: what the session is doing now, verb-led, a few words (`fix webhook retries`, `review PR 12`, `plan rate limits`). A review, advice or committee session says so in its activity.

Keep the whole title near 50 characters, in English for the activity unless the user asks for their own language, with technical names intact. Examples: `billing-api: fix webhook retries`, `billing-api 003 search: T044–T046 rebuild CLI`, `docs-site: review PR 12`.

When to name: at entry, on a resume whose title no longer matches the work, and when the task or phase changes materially (a new story, from planning to implementation, from implementation to review). Do not rename for every step.

Whose: rename only this session and sessions you started; a session someone else started keeps its name unless the user asks. A delegated run takes its title, or its log file name where the host has no titles, from its ledger project and task label (`fnl-delegate`).

Titles carry no secrets, customer data or private history. Use the host's supported mechanism ([references/titles.md](references/titles.md)); where a host offers none, say so in one line and carry the name in the handover and log file names instead. Pin the active session and unpin retired ones only where the host supports it and the user allows it. Session stores and app databases are never edited by hand.

## Writers and checkouts

- One writer per scope, with an explicit handover between writers.
- Prefer a suitable existing checkout or worktree; stricter isolation rules win.
- Keep notes, briefs and logs in a durable local folder (`.finolabs/` at the main checkout's root, kept out of git, unless the host config names another); temporary directories and scratchpads are wiped on restart.
