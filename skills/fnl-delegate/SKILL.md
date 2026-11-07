---
name: fnl-delegate
description: Coordinate other coding agents (Claude Code, Codex, Antigravity) from whichever one you run in. Use whenever work is split across agents or needs a routing decision: choosing the agent and model for each of several tasks, dispatching independent tasks in parallel, an agent's quota running out, a delegated run you are watching that stalls, times out or is interrupted, or running a spec as a coordinator with one session per task. Writing the brief for a single task, or saving a handover, belongs to fnl-handoff.
---

# Delegate

You are the **coordinator**, whichever agent you run in: Claude Code, Codex or Antigravity. Agents implement; you grade, route, brief, watch, verify and accept. An agent's report is a claim; the diff and the test output are the evidence.

Before the first dispatch in a session, read the **host config**: `host.md` under the data root resolved by [scripts/data_root.py](scripts/data_root.py) (`~/.finolabs/vibecode/` by default, relocated only through `fnl-setup`); `ORCHESTRATION_HOST_CONFIG` may supply non-consent settings, but opt-ins and Routing always come from the resolved root. It holds this machine's commands, allowed models, which delegates this coordinator can reach, the judge choice, the lock path, briefs folder and parallel limit. If it is missing, copy [references/host-template.md](references/host-template.md) and ask the user for the facts you cannot look up. Project rules (`AGENTS.md`, `CLAUDE.md`, a constitution) win over this skill wherever they conflict.

References carry the detail. For routing: [references/models.md](references/models.md) maps each agent's models to tiers and strengths, and the Route section below defines the judge fallback. For dispatch: [references/agents.md](references/agents.md) gives each agent's dispatch contract, including what each one may run, [references/dispatch.md](references/dispatch.md) the procedures only some runs reach (quota fallback, parallel runs, the heavy-job lock, handover, file placement), and [references/ledger.md](references/ledger.md) the ledger commands.

For a spec run as a coordinator with one app session per task, load [references/coordinator-sessions.md](references/coordinator-sessions.md). It covers ownership, standby sessions, checkout handovers and the review gate per user story.

**Advisory (agent judgment):** When the coordinator starts work on a task in a session the user started by hand, run `python3 -I <this skill folder>/scripts/record.py task --id <id>`; the script validates the task id.

## Delegation mode

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged. Script output stays English; report it to the user in their language (advisory, agent judgment).

Run `python3 -I <this skill folder>/scripts/mode.py` before Route. `manual`: hand off to another family only when the user says so. `suggest` (default): at Route say “this could go to <agent>; say yes to hand it off” and wait; with a native question tool in the session, ask it as a yes or no choice instead. `auto`: use the guideline for independent tasks with clear acceptance tests, record the decision in the ledger and tell the user after dispatch. An explicit handoff request is approval. Modes govern hand-offs to another agent family, in routing and load sharing. Own kind means the family recorded as the coordinator's in `Agents on this machine`, else the family of the host that runs you; any other family is another family. A session or headless run of your own kind, started because the project requires it (for example implementation in its own worktree) or to spare your own context, is you doing the work: start it without an offer and state that reason in one line, including under `manual`. Under `manual`, this is allowed only for those two reasons. Never name your own family as the `<agent>` in an offer. The project's rules still decide whether own-kind sessions are allowed. An own-kind session or run stays a delegate for the Never delegated list and gains none of the coordinator's authority. The Never delegated list, review gates, security gates and merge authority stay identical. Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes.

Enforcer: on Claude Code, where the hook is installed, the host config opts in (`## Auto gate` set to `on`) and `FNL_AUTO_GATE` has not turned it off, the auto gate may deny the first file write in a repository without a decision in the last 8 hours. An implementation ledger `start` records `handoff`; a keep receipt records `keep`. A decision or prior denial allows later writes in that window; expired state can lead to one more denial. The gate allows on errors and does not cover shell commands. The ledger `start` command refuses to record a cross-family dispatch under `manual` unless `--route-by user` is given (script-enforced; it blocks the required record, not the dispatch itself). Elsewhere, enforcement is advisory agent judgment; auto is never 100%. Read [references/modes.md](references/modes.md) only when the mode matters.

## The loop

Run this loop for every delegated task. Each step ends on its criterion.

1. **Grade** the task: kind and difficulty (below). Done when both are named.
2. **Route** it to an agent and model (below). Done when you can state the choice and its reason in one line.
3. **Brief** it with the `fnl-handoff` template, saved as "Where files go" says. Without `fnl-handoff`, use its headings: Task, Checkout, Context, Relevant files, Current state, What was tried, Acceptance criteria, Tests to run, Constraints, Budget, Report. Done when an agent with zero context could finish the task from the brief alone.
4. **Dispatch** it with a hard time cap, named by its runner and what it does (`fnl-session-hygiene` "Titles": `<runner>: <project> <scope> <activity>`) in the host's name field, the ledger task and the log file names, and record it in the ledger. Start the command with `FNL_DISPATCH_ID=<ledger id>`, the id `ledger.py start` printed (a host config written before this variable existed lacks it), so the usage metrics can tell the run from a session the user started. Done when the process is running and the ledger has its `start` line.
5. **Watch** liveness at the check deadline from artifacts. Done when the run has ended or been stopped. An Antigravity compaction stop ends a delegated headless `agy -p` run with `status: ERROR` and the fixed message "The conversation is large. Run /compact, or start a fresh session with a short handover, then continue.", which the coordinator treats as "context limit", not a model failure.
6. **Accept** after verifying the diff and the tests yourself. Done when the work is accepted, sent back for rework, or rejected.
7. **Record** the outcome in the ledger. A dispatch sent back for rework stays open; it gets one `finish` line when it is finally accepted, rejected or stopped, with `--rework-rounds <n>`. Done when the dispatch has its `finish` line.

## Grade

Kind: `implement`, `review`, `advise` or `committee`.

Difficulty:

- **easy**: one file or seam, a known pattern, about 20 minutes of work.
- **medium**: several files in one seam, new tests, consumers known.
- **hard**: cross-cutting change, concurrency, security or permissions, migrations, subtle bugs, or a medium task that already failed once.
- **very hard**: novel design, high ambiguity, many interacting parts, or work that keeps needing judgement drawn from the coordinator's own context.
- **ultra hard**: very hard work where a wrong result is costly or hard to undo (production data, a migration, a security boundary), or very hard work that a `high` run already fell short on.

### Decision matrix

The grade fixes the rest of the plan; later sections say how to carry it out.

| Grade | Tier | Effort | Budget | Runs as | Accepted by |
| --- | --- | --- | --- | --- | --- |
| easy | fast | `medium` | 20 minutes | headless run | the coordinator |
| medium | strong | `medium` | 30–45 minutes | headless run | the coordinator |
| hard | frontier, or strong for implementation with clear acceptance tests | `medium` | 60–90 minutes; split a task that needs more | headless run | the coordinator with `verify_claim.py` |
| very hard | frontier | `high` | 90 minutes per headless sub-run | a session, not a headless run | the coordinator with `verify_claim.py` |
| ultra hard | frontier | `xhigh`, then `max` if `xhigh` falls short | 90 minutes per headless sub-run | a session, not a headless run | the coordinator with `verify_claim.py` |

A run that fell short at its level is retried one level up; the host config may set its own effort preference; `models.md` maps each level to every agent's own scale. A review, an advice or a committee seat takes its tier from the work it covers (Route, step 1) and its budget from "Budget and liveness".

## Route

First read `## Agents on this machine` in host config. By agent judgment, route only among families whose Present cell is `yes`, including for load sharing, quota fallback, reviews and advice; do not offer an absent or unrecorded family. Use its user-confirmed allowed models, and leave `unverified` models pending confirmation rather than choosing from the tier table alone. The section's `Coordinator: <family>` records own kind; without that field use the running host's family. With no other family present, say in one line "Delegation is off: no other agent family is recorded present" and work yourself or with sessions of your own kind where project rules allow. This also applies under auto and takes precedence over capability order and hand-off offers. Own-kind sessions retain the Never delegated limits.

If the section is missing, use the previous routing behavior and suggest `/fnl-setup scan`. If its oldest Checked date is more than 30 days old, say it is stale once per session and suggest that command; missing, invalid or future dates are unverified. A stale section remains a presence restriction, not permission to add candidates. A present CLI does not prove reachability, model access or quota.

Choose an agent **and a model**. A user who names either wins; otherwise:

1. **Tier** from the decision matrix. Reviews take the tier above the work they review, at least strong.
2. **Strength overrides** from `models.md`: long logs, screenshots, recordings or PDFs; UI from a design; terminal-heavy work; bulk edits.
3. **Capability order** among what still fits: for code, Claude Code, then Codex, then Antigravity; for plain content writing, Codex, then Claude Code, then Antigravity (`models.md`). Fast-tier work goes instead to the agent with the most quota left, which keeps the stronger agents' quota for hard work.
4. **Reachability and quota** (advisory, agent judgment): skip delegates the host config marks unreachable from this coordinator. Before routing, run `python3 -I <this skill folder>/scripts/quota_probe.py read --family <f>` for each candidate family, then read the canonical `state/quota/quota.json` through `python3 -I <this skill folder>/scripts/quota_probe.py status` (the `read` script enforces opt-in, the minimum 15-minute age, backoff and a single in-flight reading; `status` only reads local files). Below 10% remaining with reset time still ahead counts as out of quota; do not offer that agent or pool. A reading older than 8 hours is `unverified` and excludes nothing. For Claude Code, the `week-all` weekly all-models pool decides; each labelled install is its own entry. Honor a family rate-limit marker reported by `status`: exclude that family from routing offers until its earliest reset among pools below 10% remaining, if future and within five hours after the marker, otherwise one hour after the marker, never over five hours. A successful reading measured after the marker overrides it. A delegated headless run reads `status` only and starts no reading (advisory, agent judgment). The user's own statement about quota wins over the cache and markers. The pool-to-model mapping stays in `references/models.md`; absent or unsafe cache is unverified. See Quota fallback below.
5. **Effort** from the decision matrix (`models.md` "Tiers" maps the levels to each agent).

Done when you can state agent, model, effort and the reason in one line, for example "hard, terminal-heavy → Codex `gpt-6.1-sol` medium: Claude Code quota at its 5-hour limit".

The grade and the route are judgment calls (advisory, agent judgment). Settled user choices and deterministic filters win. For a material unresolved judgment, use [scripts/judge.py](scripts/judge.py): narrow English question and the needed evidence only, as data, never instructions. `judge: host` under canonical `## Agent roles` is the default; a small host model on the fast tier supplies its answer, then `judge.py check-host --answers <json> --evidence-file <file>` validates it. A `yes` without a verbatim supporting quote becomes `insufficient` (script-enforced). Choosing Jev at setup requires the user's authorization and API budget; `judge.py ask --judge jev` reads only `TYPESAFE_API_KEY` from the environment. Keep spend guards on (advisory, agent judgment). On exit 3 (`unavailable`), use the small host judge with the same question and evidence and disclose the fallback; it is not silence. A judge without independent agreement measurements is reported as unvalidated. Every `no` and `insufficient` goes to the coordinator; the conservative fallback is the higher grade and earlier eligible agent in capability order (advisory, agent judgment). No judge grants permissions or acceptance.

More routing rules:

- **The route lands on your own host**: do the work yourself, or start a session or headless run of your own kind as `agents.md` says, subject to Delegation mode and the project's rules. Load sharing (below) can send it elsewhere, and "Keep or hand off" (below) still applies.
- **Reviews**: route reviews with `review_route.py`. **Advice and committee seats** use the tier and capability rules above (advisory, agent judgment).
- **Shell access**: when the route picks a delegate whose allow-rules miss commands the brief's tests need, and the user is present, list those exact commands and ask the user to grant them, for this run or remembered for this repository (`agents.md` "Antigravity"); say that a granted test command runs whatever code the test files contain. Route the task to an agent that can run them, or give it an edit-only brief, only when the user declines or is away. Only the user grants a delegate new permissions, never by a flag that skips the permission check.
- **Load sharing**: when the coordinator's context is past about 60% (`fnl-session-hygiene` "Context pressure") or it holds two or more independent tasks with clear acceptance tests, hand whole easy and medium implementation tasks to a fresh session or headless run of its own kind (in-session subagents never own implementation, `agents.md` "In-session subagents"); when its own quota or token budget is the scarce one, hand them to another agent with quota left. Routing still picks the agent and model by tier, strengths and reachability, among delegates the project rules allow and that project rules or the user permit to receive these files. Keep briefing and acceptance, route reviews as `fnl-review-gate` says, and leave merges to whoever holds the authority. A task that needs the coordinator's own conversation context to finish stays with the coordinator. For a child whose context the coordinator can read, follow `fnl-session-hygiene` with measured usage and the user's chosen threshold (advisory, agent judgment). No automatic usage feed or cross-session compaction command is implied.
- **Never delegated**: the acceptance verdict; merges, pushes, deploys and publishing, which are the user's authority; anything that handles secrets or credentials; edits to shared settings, skills or defaults; and a decision on an ambiguous requirement that needs the user's answer. A delegate may prepare the work for these and never performs or decides them; the coordinator itself acts on them only with the user's authority.
- **User away**: questions that would go to the user go to an advisor, or to the judge through the Route procedure, instead; record each decision and who settled it. Decisions that need the user's authority (merge, production, credentials, new spending) still wait. A `suggest` hand-off offer waits for the user, never an advisor or judge; meanwhile keep the tasks as `user-choice`.

### Keep or hand off

The moment you hold two or more independent tasks with clear acceptance tests, before you start the first, run load sharing and the route over them. Each task you dispatch gets its `start` line in the ledger; for the tasks you keep, run `python3 -I <this skill's folder>/scripts/record.py keep --tasks <count> --reason <reason>` once per reason, adding `--route-by user` for `user-choice` ([references/keep-receipt.md](references/keep-receipt.md) lists the reasons). The command prints one line; when the user has turned usage metrics on, the plugin's hook records it with the session. "Delegation mode" still applies: under `suggest`, ask before you start the first hand-off to another family, and a task the user declines is kept as `user-choice`; under `manual`, make no offer to another family and keep them as `user-choice` unless an own-kind session or headless run is required by the project or needed to spare your context, as Delegation mode says. A delegated run reports these tasks to its coordinator instead of dispatching them. Done when those lines account for every task.

### Quota fallback

When a model's quota runs out, reroute as [references/dispatch.md](references/dispatch.md) "Quota fallback" says, and record the reason in the ledger. Moving up a tier spends more quota and needs the user's yes; moving down a tier is only for easy and medium work.

## Capabilities and budget

- Discover what the target actually offers (models, effort, tools, context, resume) from its CLI or a current catalog; respect pins and restrictions. A control the target lacks falls back to its default: say so. Record the requested and the effective configuration in the `finish` line's `--note`. Unknown cost is not zero.
- Before dispatching, budget the whole run: the root and its children, context, retries, evaluator calls, time, and a reserve for verification and review.
- Start every headless run through the host's own background mechanism (on Claude Code, the Bash tool's background mode), never a detached shell job (`nohup … &`, `disown`). A detached job is invisible in the host's task list and sends no completion notice, so the coordinator neither shows nor notices the run; if one was started that way, attach a background waiter that blocks until the process is gone or the runner's own log records its exit status (a wrapper that appends `exit=<code>` to the log makes this simple on any host). Enforcer: agent judgment, advisory.
- Wait through supported completion notices; leave no orphan runs and no busy polling. When a run falls short, tell a setup gap (missing tool, permission, quota) from a model failure before rerouting.

## Parallel dispatch

Tasks are independent when they touch disjoint files, need no ordering, and need not land in one commit. Independent tasks go one per agent run, in parallel, at most 5 dispatched at one time (the host config may set a lower limit), each in its own worktree; tasks that share files or depend on each other run in sequence. Sizing, worktrees and merging back: [references/dispatch.md](references/dispatch.md) "Parallel dispatch".

## Budget and liveness

Every dispatch carries a **budget**, written into the brief, and three numbers derived from it (below). Implementation budgets follow the grade in the decision matrix; the other kinds:

| Work | Budget |
| --- | --- |
| review | 30 minutes |
| advise | 15–30 minutes |
| committee member | 30–45 minutes |

Take the upper end of a range for runs that build or test. Once `fnl-status` shows at least five finished runs for the same agent, model and grade, set the budget to about 1.5 times their median instead.

- The **agent's own timeout** (`--print-timeout`, the agybird `--timeout`, `--max-turns`), a few minutes under the hard cap, so the agent stops and reports before it is killed.
- The **hard cap** that kills the process (the host config gives the command form): the budget plus a third, and at least 10 minutes over it.
- The **check deadline**, half the budget, when you inspect the run.

An open ledger line and its age prove only that nobody has closed it, not that the run is alive: before telling the user a run is running, check the process table and the run's recorded exit status, and use `pgrep -f` only with a quoted pattern taken from the run's own recorded id that cannot match the coordinator's own command line (it can report a false positive). Enforcer: agent judgment, advisory. Judge liveness from artifacts, never from status messages: the process and its elapsed time, growth of the log and output files, new commits or diff in the worktree, new transcript events. Two checks with no new artifact means the run has stalled: stop it, run the handover (below), then retry once with a smaller scope or switch agents, and tell the user. Each brief tells the agent to report failure rather than retry more than once.

## Heavy jobs

Heavy jobs (container-backed suites, scale measurements, end-to-end runs; the host config lists them) run one at a time per machine under the lock in [references/dispatch.md](references/dispatch.md) "Heavy-job lock"; light targeted tests may overlap. Test scope follows the `fnl-verification` skill.

## Accept

The coordinator runs the command in `fnl-verification` "Accepting someone else's work", using that skill's self-contained `verify_claim.py`, for every delegated grade (advisory, agent judgment). It reruns exactly the brief's listed test commands, checks the scope and reported head, and writes a verification receipt through `record.py` (script-enforced). Read every semantic `no` and `insufficient`; a judge's `yes` never replaces mechanical evidence. Then decide **accepted**, **rework** in the same run with each defect named, or **rejected** and rerouted. The verdict stays with the coordinator (advisory, agent judgment).

`ledger.py finish --outcome accepted --checkout <task checkout>` refuses without a passing receipt for the dispatch checkout's current head (script-enforced). Use `--checkout` at both `start` and `finish` when the task checkout differs from the working directory. For work with nothing to check, `--accept-unverified --reason <text>` is an explicit escape hatch: the finish line records its use and a reason digest, and `summary` counts `accepted_unverified` per agent. Keep the reason text in the coordinator report; no command, path or task text enters the receipt. Other outcomes are unaffected. This gate covers only delegated runs recorded in the ledger; it cannot stop an agent that never uses the ledger, and the coordinator's own work stays under the review gate.

## Handover after an interrupted run

When a run times out, fails or stops with uncommitted work, no other agent gets write access to that checkout until you have run the handover in [references/dispatch.md](references/dispatch.md) "Handover after an interrupted run".

## Where files go

Shared files (documentation and design notes with lasting value) go in the project's documentation folders and are committed. Local files (briefs, logs, working notes, captured state) go in `.finolabs/` at the main checkout's root (`briefs/` for briefs and notes, `logs/` for logs and outputs), kept out of git through `.git/info/exclude` (the shared `.gitignore` changes only with the user's approval); never in temporary directories or session scratchpads. A repository that still has the older `.orchestration/` folder and no `.finolabs/` keeps using it; nothing is moved for the user. The full rule: [references/dispatch.md](references/dispatch.md) "Where files go".

## Ledger

Record every dispatch with `scripts/ledger.py` in this skill's base directory, at the moment it happens: a `start` line at dispatch, a `finish` line when the run is accepted, rejected or stopped. Commands, the agent values and what `summary` reports are in [references/ledger.md](references/ledger.md). The ledger holds short task labels only: no task data, secrets or personal data.

## Related skills

- `fnl-handoff`: write the brief and dispatch one task.
- `fnl-advisor`: one second opinion or two contrasting families for root cause or planning when stuck, all read-only.
- `fnl-status`: the usage dashboard (router coverage, skill use, load cost, delegation, review gate) and the runs still open.
