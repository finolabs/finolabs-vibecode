---
name: fnl-delegate
description: Coordinate other coding agents (Claude Code, Codex, Antigravity) from whichever one you run in. Use whenever work is delegated to another agent or split across agents: choosing the agent and model for each task, dispatching independent tasks in parallel, an agent's quota runs out, or a delegated run stalls, times out or is interrupted.
---

# Delegate

You are the **coordinator**, whichever agent you run in: Claude Code, Codex or Antigravity. Agents implement; you grade, route, brief, watch, verify and accept. An agent's report is a claim; the diff and the test output are the evidence.

Before the first dispatch in a session, read the **host config**: the file named by `ORCHESTRATION_HOST_CONFIG`, else `${XDG_CONFIG_HOME:-~/.config}/finolabs-vibecode/host.md`. It holds this machine's commands, allowed models, which delegates this coordinator can reach, the route judge, the lock path, briefs folder and parallel limit. If it is missing, copy [references/host-template.md](references/host-template.md) and ask the user for the facts you cannot look up. Project rules (`AGENTS.md`, `CLAUDE.md`, a constitution) win over this skill wherever they conflict.

References carry the detail. For routing: [references/models.md](references/models.md) maps each agent's models to tiers and strengths, and, only when the host config names a route judge, [references/route-judgment.md](references/route-judgment.md) says how to ask it. For dispatch: [references/agents.md](references/agents.md) gives each agent's dispatch contract, including what each one may run, [references/dispatch.md](references/dispatch.md) the procedures only some runs reach (quota fallback, parallel runs, the heavy-job lock, handover, file placement), and [references/ledger.md](references/ledger.md) the ledger commands.

## The loop

Run this loop for every delegated task. Each step ends on its criterion.

1. **Grade** the task: kind and difficulty (below). Done when both are named.
2. **Route** it to an agent and model (below). Done when you can state the choice and its reason in one line.
3. **Brief** it with the `fnl-handoff` template, saved as "Where files go" says. Without `fnl-handoff`, use its headings: Task, Checkout, Context, Relevant files, Current state, What was tried, Acceptance criteria, Tests to run, Constraints, Budget, Report. Done when an agent with zero context could finish the task from the brief alone.
4. **Dispatch** it with a hard time cap and record it in the ledger. Done when the process is running and the ledger has its `start` line.
5. **Watch** liveness at the check deadline from artifacts. Done when the run has ended or been stopped.
6. **Accept** after verifying the diff and the tests yourself. Done when the work is accepted, sent back for rework, or rejected.
7. **Record** the outcome in the ledger. A dispatch sent back for rework stays open; it gets one `finish` line when it is finally accepted, rejected or stopped, with `--rework-rounds <n>`. Done when the dispatch has its `finish` line.

## Grade

Kind: `implement`, `review`, `advise` or `committee`.

Difficulty:

- **easy**: one file or seam, a known pattern, about 20 minutes of work.
- **medium**: several files in one seam, new tests, consumers known.
- **hard**: cross-cutting change, concurrency, security or permissions, migrations, subtle bugs, or a medium task that already failed once.
- **very hard**: novel design, high ambiguity, many interacting parts, or work that keeps needing judgement drawn from the coordinator's own context.

## Route

Choose an agent **and a model**. A user who names either wins; otherwise:

1. **Tier** from the grade: very hard → frontier; hard → frontier, or strong for implementation with clear acceptance tests; medium → strong; easy → fast. Reviews take the tier above the work they review, at least strong.
2. **Strength overrides** from `models.md`: long logs, screenshots, recordings or PDFs; UI from a design; terminal-heavy work; bulk edits.
3. **Capability order** among what still fits: for code, Claude Code, then Codex, then Antigravity; for plain content writing, Codex, then Claude Code, then Antigravity (`models.md`). Fast-tier work goes instead to the agent with the most quota left, which keeps the stronger agents' quota for hard work.
4. **Reachability and quota**: skip delegates the host config marks unreachable from this coordinator, and models whose quota is out (below).

Done when you can state agent, model, effort and the reason in one line, for example "hard, terminal-heavy → Codex `gpt-6.1-sol` high: Claude Code quota at its 5-hour limit".

When the grade sits between two levels, or two routes still fit, the rules have left a judgment call:

- With a **route judge** in the host config, read `references/route-judgment.md` and ask it as that file says.
- Otherwise take the **higher grade** and the **earlier agent** in the capability order. This costs more quota, never quality.

More routing rules:

- **The route lands on your own host**: do the work yourself, or start a session or subagent of your own kind as `agents.md` says. Delegating to yourself through a headless CLI only adds overhead. Load sharing (below) can send it elsewhere.
- **Reviews, advice and committee seats** go by capability, like implementation: strong tier or above, a different agent from the implementer, a different model family where one is reachable, in a fresh context. Any of the three agents qualifies. A review that must run commands an agent's allow-rules block (tests, builds) goes to an agent that can run them. `fnl-review-gate` defines reviewer independence. When the implementer's family is the only one with a posting reviewer, the other family reviews read-only and the coordinator posts its report as `fnl-review-gate` relays allow. When the other family is out of quota, a same-family fresh-context reviewer stands in and the report says so; for a pull request that hits a `fnl-security-review-gate` trigger, stop and ask the user first.
- **Shell access**: when the route picks a delegate whose allow-rules miss commands the brief's tests need, and the user is present, list those exact commands and ask the user to grant them, for this run or remembered for this repository (`agents.md` "Antigravity"); say that a granted test command runs whatever code the test files contain. Route the task to an agent that can run them, or give it an edit-only brief, only when the user declines or is away. Only the user grants a delegate new permissions, never by a flag that skips the permission check.
- **Load sharing**: when the coordinator's context is past about 60% (`fnl-session-hygiene` "Context pressure") or it holds two or more independent tasks with clear acceptance tests, hand whole easy and medium implementation tasks to a fresh session or headless run of its own kind (in-session subagents never own implementation, `agents.md` "In-session subagents"); when its own quota or token budget is the scarce one, hand them to another agent with quota left. Routing still picks the agent and model by tier, strengths and reachability, among delegates the project rules allow. Keep briefing and acceptance, route reviews as `fnl-review-gate` says, and leave merges to whoever holds the authority. A task that needs the coordinator's own conversation context to finish stays with the coordinator.
- **Stays with the coordinator**: the acceptance verdict; merges, pushes, deploys and publishing, which are the user's authority; anything that handles secrets or credentials; edits to shared settings, skills or defaults; and a decision on an ambiguous requirement that needs the user's answer. A delegate may prepare the work for these and never performs or decides them.
- **User away**: questions that would go to the user go to an advisor, or to the route judge when the host config names one, instead; record each decision and who settled it. Decisions that need the user's authority (merge, production, credentials, new spending) still wait.

### Quota fallback

When a model's quota runs out, reroute as [references/dispatch.md](references/dispatch.md) "Quota fallback" says, and record the reason in the ledger. Moving up a tier spends more quota and needs the user's yes; moving down a tier is only for easy and medium work.

## Capabilities and budget

- Discover what the target actually offers (models, effort, tools, context, resume) from its CLI or a current catalog; respect pins and restrictions. A control the target lacks falls back to its default: say so. Record the requested and the effective configuration in the `finish` line's `--note`. Unknown cost is not zero.
- Before dispatching, budget the whole run: the root and its children, context, retries, evaluator calls, time, and a reserve for verification and review.
- Wait through supported completion notices; leave no orphan runs and no busy polling. When a run falls short, tell a setup gap (missing tool, permission, quota) from a model failure before rerouting.

## Parallel dispatch

Tasks are independent when they touch disjoint files, need no ordering, and need not land in one commit. Independent tasks go one per agent run, in parallel, at most 5 dispatched at one time (the host config may set a lower limit), each in its own worktree; tasks that share files or depend on each other run in sequence. Sizing, worktrees and merging back: [references/dispatch.md](references/dispatch.md) "Parallel dispatch".

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

Judge liveness from artifacts, never from status messages: the process and its elapsed time, growth of the log and output files, new commits or diff in the worktree, new transcript events. Two checks with no new artifact means the run has stalled: stop it, run the handover (below), then retry once with a smaller scope or switch agents, and tell the user. Each brief tells the agent to report failure rather than retry more than once.

## Heavy jobs

Heavy jobs (container-backed suites, scale measurements, end-to-end runs; the host config lists them) run one at a time per machine under the lock in [references/dispatch.md](references/dispatch.md) "Heavy-job lock"; light targeted tests may overlap. Test scope follows the `fnl-verification` skill.

## Accept

A task is done only when you have checked it yourself, as `fnl-verification` "Accepting someone else's work" lays out. Then decide: **accepted**; **rework**, a follow-up to the same agent run naming each defect (count the round); or **rejected**, rerouted with a new brief. The verdict is yours, whatever the agent's report says.

## Handover after an interrupted run

When a run times out, fails or stops with uncommitted work, no other agent gets write access to that checkout until you have run the handover in [references/dispatch.md](references/dispatch.md) "Handover after an interrupted run".

## Where files go

Shared files (documentation and design notes with lasting value) go in the project's documentation folders and are committed. Local files (briefs, logs, working notes, captured state) go in `.orchestration/` at the main checkout's root (`briefs/` for briefs and notes, `logs/` for logs and outputs), kept out of git through `.git/info/exclude` (the shared `.gitignore` changes only with the user's approval); never in temporary directories or session scratchpads. The full rule: [references/dispatch.md](references/dispatch.md) "Where files go".

## Ledger

Record every dispatch with `scripts/ledger.py` in this skill's base directory, at the moment it happens: a `start` line at dispatch, a `finish` line when the run is accepted, rejected or stopped. Commands, the agent values and what `summary` reports are in [references/ledger.md](references/ledger.md). The ledger holds short task labels only: no task data, secrets or personal data.

## Related skills

- `fnl-handoff`: write the brief and dispatch one task.
- `fnl-advisor`: one second opinion, no edits.
- `fnl-committee`: two contrasting agents for root cause or planning when stuck.
- `fnl-coordinator-sessions`: a spec run as coordinator plus task sessions in the desktop app.
- `fnl-status`: open runs and acceptance per agent and model, from the ledger.
