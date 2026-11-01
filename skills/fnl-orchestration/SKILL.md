---
name: fnl-orchestration
description: Coordinate other coding agents (Codex CLI, Antigravity through agybird, Claude Code sessions). Use whenever work is delegated to another agent or split across agents: deciding which agent or model gets each task, dispatching independent tasks in parallel, an agent's quota runs out, or a delegated run stalls, times out or is interrupted.
---

# Orchestration

You are the **coordinator**. Agents implement; you grade, route, brief, watch, verify and accept. An agent's report is a claim; the diff and the test output are the evidence.

Before the first dispatch in a session, read the **host config**: the file named by `ORCHESTRATION_HOST_CONFIG`, else `~/.claude/orchestration/host.md`. It holds this machine's invocation commands, paths, permission rules, lock path, briefs folder and parallel limit. If it is missing, copy [references/host-template.md](references/host-template.md), read [references/agents.md](references/agents.md), and ask the user for the facts you lack. Project rules (`AGENTS.md`, `CLAUDE.md`, a constitution) win over this skill wherever they conflict.

## The loop

Run this loop for every delegated task. Each step ends on its criterion.

1. **Grade** the task: kind and difficulty (below). Done when both are named.
2. **Route** it to an agent and model (below). Done when you can state the choice and its reason in one line.
3. **Brief** it with the `fnl-orchestration-handoff` template, saved as "Where files go" says. Done when an agent with zero context could finish the task from the brief alone.
4. **Dispatch** it with a hard time cap and record it in the ledger. Done when the process is running and the ledger has its `start` line.
5. **Watch** liveness at the check deadline from artifacts. Done when the run has ended or been stopped.
6. **Accept** after verifying the diff and the tests yourself. Done when the work is accepted, sent back for rework, or rejected.
7. **Record** the outcome in the ledger. Done when the dispatch has its `finish` line.

## Grade

Kind: `implement`, `review`, `advise` or `committee`.

Difficulty:

- **easy**: one file or seam, a known pattern, about 30 minutes of work.
- **medium**: several files in one seam, new tests, consumers known.
- **hard**: cross-cutting change, concurrency, security or permissions, migrations, subtle bugs, or a medium task that already failed once.
- **very hard**: novel design, high ambiguity, many interacting parts, or work that keeps needing judgement drawn from the coordinator's own context.

## Route

These are preferences. A user who names an agent or model wins; otherwise follow the table and say why when you depart from it.

| Work | First choice | When that is unavailable |
| --- | --- | --- |
| very hard implementation | a Claude Code session, directly | Codex, split smaller |
| hard implementation | Codex | Antigravity on its heaviest allowed model, split smaller |
| medium implementation | Codex or Antigravity | the other one |
| easy implementation | Antigravity | Codex |
| code or security review | the stronger agent: Codex, or a Claude Code session for very hard work | the other of those two |
| second opinion, stuck, planning | `fnl-orchestration-advisor` or `fnl-orchestration-committee` | |

- **Medium tie-break**: Antigravity runs headless and stops `blocked` or `needs_permission` whenever a command falls outside its allow-rules, and only the user can grant one. Give medium work to Antigravity when the brief is edit-only or its commands fit the allow-rules, and to Codex when the work needs wider shell access or the user is away.
- **Reviews** go to the stronger agent in a fresh context; Antigravity takes no reviews. `fnl-review-gate` defines reviewer independence.
- **Token budget**: when the coordinator's own budget is the scarce one, prefer delegating implementation and keep the coordinator on briefing and acceptance.
- **User away**: questions that would go to the user go to an advisor or a semantic evaluator instead; record each decision and who settled it. Decisions that need the user's authority (merge, production, credentials, new spending) still wait.

### Quota fallback

When one agent's quota is fully exhausted, give its work to the other: Codex out → Antigravity, Antigravity out → Codex. Antigravity quota is per model (and per pool), so before calling Antigravity out, check usage and try each other allowed model listed in the host config at the same tier; the `agybird` skill covers the check. Moving up a tier spends more quota: ask first. When both are out, offer a Claude Code session or report the reset times and wait. Record a fallback as `--reason fallback-quota` in the ledger.

## Parallel dispatch

Tasks are independent when they touch disjoint files, need no ordering, and need not land in one commit. Independent tasks go one per agent run, in parallel, at most 5 dispatched at one time (the host config may set a lower limit). Tasks that share files or depend on each other run in sequence.

- Size each run small: one task or a tight pair, budget up to 90 minutes. A long run holding many tasks is slower, bloats the agent's context and loses more when it breaks.
- Give each parallel run its own git worktree on its own branch, cut from the integration branch tip. One writer per worktree.
- Merge back one branch at a time into the integration branch, rerunning the targeted tests after each merge. Resolve conflicts yourself or brief a fix run.

## Budget and liveness

Every dispatch carries two numbers:

- a **hard cap** that kills the process (the host config gives the command form), set a little above the brief's time budget;
- a **check deadline**, about half the budget (15 minutes for a review), when you inspect the run.

Judge liveness from artifacts, never from status messages: the process and its elapsed time, growth of the log and output files, new commits or diff in the worktree, new transcript events. Two checks with no new artifact means the run has stalled: stop it, run the handover below, then retry once with a smaller scope or switch agents, and tell the user. Each brief tells the agent to report failure rather than retry more than once.

## Heavy jobs

Heavy jobs (container-backed suites, scale measurements, end-to-end runs; the host config lists them) run one at a time per machine; light targeted tests may overlap. Serialise them with an atomic `mkdir` lock at the path the host config names:

```bash
until mkdir "$LOCK" 2>/dev/null; do sleep 15; done
echo "<dispatch-id> $(date)" > "$LOCK/owner"
<heavy command>; status=$?
rm -rf "$LOCK"; exit $status
```

A lock whose owner process is gone is stale: confirm with `ps` before removing it. Test scope follows the `fnl-verification` skill.

## Accept

A task is done only when you have checked it yourself, as `fnl-verification` "Accepting someone else's work" lays out. Then decide: **accepted**; **rework**, a follow-up to the same agent run naming each defect (count the round); or **rejected**, rerouted with a new brief. The verdict is yours, whatever the agent's report says.

## Handover after an interrupted run

When a run times out, fails or stops with uncommitted work, before any other agent gets write access to that checkout:

1. Confirm the process has stopped (`ps`, the run's exit status).
2. Capture its state in the briefs folder: `git status`, the diff saved as a patch, the last lines of its log.
3. Keep the work: commit it on the run's behalf as work in progress, or name the files in the next brief.
4. Write the next brief's "Current state" and "What was tried" from that capture.

## Where files go

Sort every file the orchestration produces by who will read it:

- **Shared**: documentation, design notes and briefs with lasting value for the project's community or as future usage docs. Put them in the project's normal documentation folders (`docs/`, `specs/` or whatever the project uses) and commit them under the project's rules for public content.
- **Local**: logs, working notes, handoff briefs, captured state from interrupted runs; anything that only serves development on this machine. Put them in the hidden folder `.orchestration/` at the main checkout's root (`git rev-parse --path-format=absolute --git-common-dir`, then its parent): `briefs/` for briefs and notes, `logs/` for logs and final outputs. Keep it out of git with a local `.orchestration/` line in `.git/info/exclude`; the shared `.gitignore` changes only with the user's approval. The host config may name another durable local folder. Temporary directories and session scratchpads are wiped on restart, so never keep briefs there.

When unsure, treat a file as local; promoting it to shared later is a deliberate edit and commit.

## Ledger

Record every dispatch with `scripts/ledger.py` in this skill's base directory. It appends to `~/.claude/orchestration/ledger.jsonl` (override with `ORCHESTRATION_LEDGER`). The ledger measures whether this routing works, so write each line at the moment it happens:

```bash
L="<this skill's base directory>/scripts/ledger.py"
python3 -I "$L" start --project demo-app --task "T101 isolation check" \
  --kind implement --grade medium --agent codex --model default --reason routing --budget 45
python3 -I "$L" finish <id> --outcome accepted --rework-rounds 1 --tests passed
python3 -I "$L" open                     # dispatches with no finish line
python3 -I "$L" summary --since 2026-11-01
```

Task labels are short names; the ledger holds no task data, secrets or personal data. `summary` reports, per agent, kind and grade, the first-pass acceptance rate, timeouts and stalls, fallbacks and median duration.

## Related skills

- `fnl-orchestration-handoff`: write the brief and dispatch one task.
- `fnl-orchestration-advisor`: one second opinion, no edits.
- `fnl-orchestration-committee`: two contrasting agents for root cause or planning when stuck.
- `fnl-coordinator-sessions`: a spec run as coordinator plus task sessions in the desktop app.
- `agybird`: owns every Antigravity invocation detail.
