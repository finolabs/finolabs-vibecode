---
name: fnl-delegate
description: Coordinate other coding agents (Claude Code, Codex, Antigravity) from whichever one you run in. Use whenever work is delegated to another agent or split across agents: choosing the agent and model for each task, dispatching independent tasks in parallel, an agent's quota runs out, or a delegated run stalls, times out or is interrupted.
---

# Delegate

You are the **coordinator**, whichever agent you run in: Claude Code, Codex or Antigravity. Agents implement; you grade, route, brief, watch, verify and accept. An agent's report is a claim; the diff and the test output are the evidence.

Before the first dispatch in a session, read the **host config**: the file named by `ORCHESTRATION_HOST_CONFIG`, else `~/.claude/orchestration/host.md`. It holds this machine's commands, allowed models, which delegates this coordinator can reach, the route judge, the lock path, briefs folder and parallel limit. If it is missing, copy [references/host-template.md](references/host-template.md) and ask the user for the facts you cannot look up. Project rules (`AGENTS.md`, `CLAUDE.md`, a constitution) win over this skill wherever they conflict.

Three references carry the detail: [references/models.md](references/models.md) maps each agent's models to tiers and strengths, [references/agents.md](references/agents.md) gives each agent's dispatch contract, and [references/route-judgment.md](references/route-judgment.md) covers the optional route judge.

## The loop

Run this loop for every delegated task. Each step ends on its criterion.

1. **Grade** the task: kind and difficulty (below). Done when both are named.
2. **Route** it to an agent and model (below). Done when you can state the choice and its reason in one line.
3. **Brief** it with the `fnl-handoff` template, saved as "Where files go" says. Without `fnl-handoff`, use its headings: Task, Checkout, Context, Relevant files, Current state, What was tried, Acceptance criteria, Tests to run, Constraints, Budget, Report. Done when an agent with zero context could finish the task from the brief alone.
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

Choose an agent **and a model**. A user who names either wins; otherwise:

1. **Tier** from the grade: very hard → frontier; hard → frontier, or strong for implementation with clear acceptance tests; medium → strong; easy → fast. Reviews take the tier above the work they review, at least strong.
2. **Strength overrides** from `models.md`: long logs, screenshots, recordings or PDFs; UI from a design; terminal-heavy work; bulk edits.
3. **Capability order** among what still fits: Claude Code, then Codex, then Antigravity. Fast-tier work goes instead to the agent with the most quota left, which keeps the stronger agents' quota for hard work.
4. **Reachability and quota**: skip delegates the host config marks unreachable from this coordinator, and models whose quota is out (below).

Done when you can state agent, model, effort and the reason in one line, for example "hard, terminal-heavy → Codex `gpt-6.1-sol` high: Claude Code quota at its 5-hour limit".

When the grade sits between two levels, or two routes still fit, the rules have left a judgment call:

- With a **route judge** in the host config, ask it as `route-judgment.md` says.
- Otherwise take the **higher grade** and the **earlier agent** in the capability order. This costs more quota, never quality.

More routing rules:

- **The route lands on your own host**: do the work yourself, or start a session or subagent of your own kind as `agents.md` says. Delegating to yourself through a headless CLI only adds overhead.
- **Reviews** go to a different agent from the implementer where one is reachable, in a fresh context, at strong tier or above. `fnl-review-gate` defines reviewer independence.
- **Antigravity headless** stops on any shell command outside its allow-rules. Give it edit-only briefs, or tasks whose commands fit the allow-rules.
- **Token budget**: when the coordinator's own budget is the scarce one, delegate implementation and keep yourself on briefing and acceptance.
- **User away**: questions that would go to the user go to an advisor or the route judge instead; record each decision and who settled it. Decisions that need the user's authority (merge, production, credentials, new spending) still wait.

### Quota fallback

When a model's quota runs out, move to the next route the rules give: another model of the same tier on the same agent, then the same tier on the next agent in the capability order. Antigravity pools are separate, so one empty pool leaves its other models usable. Moving up a tier spends more quota: ask first. Moving down a tier is allowed only for easy and medium work; for hard work, wait for the reset or ask. When every reachable agent is out, report the reset times and wait. Record a fallback as `--reason fallback-quota`.

## Parallel dispatch

Tasks are independent when they touch disjoint files, need no ordering, and need not land in one commit. Independent tasks go one per agent run, in parallel, at most 5 dispatched at one time (the host config may set a lower limit). Tasks that share files or depend on each other run in sequence.

- Size each run small: one task or a tight pair, budget up to 90 minutes. A long run holding many tasks is slower, bloats the agent's context and loses more when it breaks.
- Give each parallel run its own git worktree on its own branch, cut from the integration branch tip. One writer per worktree.
- Merge back one branch at a time into the integration branch, rerunning the targeted tests after each merge. Resolve conflicts yourself or brief a fix run.

## Budget and liveness

Every dispatch carries a **budget**, written into the brief, and three numbers derived from it:

| Work | Budget |
| --- | --- |
| easy | 20 minutes |
| medium | 30–45 minutes |
| hard | 60–90 minutes; split a task that needs more |
| very hard | owned by a session, not a headless run; 90 minutes per headless sub-run |
| review | 30 minutes |
| advise | 15–30 minutes |
| committee member | 30–45 minutes |

Take the upper end for frontier models at high effort and for runs that build or test. Once `fnl-status` shows at least five finished runs for the same agent, model and grade, set the budget to about 1.5 times their median instead.

- The **agent's own timeout** (`--print-timeout`, the agybird `--timeout`, `--max-turns`), a few minutes under the hard cap, so the agent stops and reports before it is killed.
- The **hard cap** that kills the process (the host config gives the command form): the budget plus a third, and at least 10 minutes over it.
- The **check deadline**, half the budget, when you inspect the run.

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

Sort every file that delegation produces by who will read it:

- **Shared**: documentation, design notes and briefs with lasting value for the project's community or as future usage docs. Put them in the project's normal documentation folders (`docs/`, `specs/` or whatever the project uses) and commit them under the project's rules for public content.
- **Local**: logs, working notes, handoff briefs, captured state from interrupted runs; anything that only serves development on this machine. Put them in the hidden folder `.orchestration/` at the main checkout's root (`git rev-parse --path-format=absolute --git-common-dir`, then its parent): `briefs/` for briefs and notes, `logs/` for logs and final outputs. Keep it out of git with a local `.orchestration/` line in `.git/info/exclude`; the shared `.gitignore` changes only with the user's approval. The host config may name another durable local folder. Temporary directories and session scratchpads are wiped on restart, so never keep briefs there.

When unsure, treat a file as local; promoting it to shared later is a deliberate edit and commit.

## Ledger

Record every dispatch with `scripts/ledger.py` in this skill's base directory. It appends to `~/.claude/orchestration/ledger.jsonl` (override with `ORCHESTRATION_LEDGER`). The ledger measures whether this routing works, so write each line at the moment it happens:

```bash
L="<this skill's base directory>/scripts/ledger.py"
python3 -I "$L" start --project demo-app --task "T101 isolation check" \
  --kind implement --grade medium --coordinator claude --agent codex \
  --model gpt-6.1-sol --route-by table --budget 45
python3 -I "$L" finish <id> --outcome accepted --rework-rounds 1 --tests passed
python3 -I "$L" open                     # dispatches with no finish line
python3 -I "$L" summary --since 2026-11-01
```

Task labels are short names; the ledger holds no task data, secrets or personal data. `summary` reports, per agent, model, kind and grade, the first-pass acceptance rate, timeouts and stalls, fallbacks and median duration.

## Related skills

- `fnl-handoff`: write the brief and dispatch one task.
- `fnl-advisor`: one second opinion, no edits.
- `fnl-committee`: two contrasting agents for root cause or planning when stuck.
- `fnl-coordinator-sessions`: a spec run as coordinator plus task sessions in the desktop app.
- `fnl-status`: open runs and acceptance per agent and model, from the ledger.
