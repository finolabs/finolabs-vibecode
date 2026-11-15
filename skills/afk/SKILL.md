---
name: afk
description: Start a time-boxed standing mandate so the host agents keep working while the user is away from the keyboard, and stop it on return. Run when the user asks for afk, away mode, work while away, or to stop the mandate on returning.
disable-model-invocation: true
argument-hint: "[start|stop]"
---

# afk: start or stop an away mandate

Dependency: `delegate`. Resolve <script> to <delegate folder>/scripts/afk.py; if it is absent, report the missing dependency and stop (advisory (agent judgment)). The script's docstring rule table is the classification contract; it executes no action and makes no network call.

## Start

1. Run only on the user's invocation; use `start` when no argument is supplied (advisory (agent judgment)). Run `python3 -I <script> start` and report its settings summary and lease length. The script requires a recorded `## afk` section with an explicit Merge answer; an older `## Autopilot` section is not read. One lease covers every session on the machine: when one is already live, `start` reports when it ends and changes nothing, and this session works under that lease from step 2 on; never treat it as another session's lease or work outside it. If setup is missing, point to `/setup add afk` and stop (advisory (agent judgment)).
2. Stay within the recorded Hosts, Task choice, Push and pull requests, Merge and limits (advisory (agent judgment) for host/task scope; script check for supported push/merge commands and lease limits). A repository's approved project settings may set its own Task choice, Push and pull requests, Merge, Trusted authors, code roots, the three limits (the strict state keeps your user limits), the `decide` list, `non-production-targets`, `production-targets`, `release-targets`, `test-commands`, `top-level-files` and `skill-repository`; in the strict and no-repository states every category stops and no deploy target applies; check applies them for the repository of the working directory on every call, and a repository it cannot identify, or whose settings or origin changed, gets the strict values (script). The `start` summary shows user scope, then one `This folder` line with the limits, decided categories and lists of the repository it ran in; before choosing tasks or authors in a repository, read `python3 -I <script> effective` there (its `rules` field shows that repository's limits, decided categories, targets, test commands and top-level files) and follow its Task choice and Trusted authors (advisory (agent judgment); the view is read-only and reserves nothing). Starting applies the user's Merge answer; it grants no wider authority. Never extend the lease or change setup while away (advisory (agent judgment); the script denies checks after setup changes).
3. Keep the session working (advisory (agent judgment)): the lease only bounds actions; it never starts a turn. Before the user leaves, print one goal they can type in the host's goal command (`/goal` on Claude Code, Codex and Antigravity), worded so it can finish while they are away, for example "every listed task is merged or parked, or the lease has ended"; the model cannot type it. When work waits on CI, reviews or a delegated run, start a self-paced loop where the host lets the agent start one (`/loop` on Claude Code) and stop it when `check` answers with an `end` line or the lease ends, since a loop can outlive the lease. Neither widens what `check` allows.
4. Away mandate active: never ask or wait for the user; follow "Work inside the lease" and "Decide" below until the lease ends. On Claude Code the away question gate denies the question tool while the lease is live (hook); elsewhere this is advisory (agent judgment).

## Work inside the lease

Load [references/lease-rules.md](references/lease-rules.md) when the lease starts and follow it for every action until it ends: `check` before each command or change, what Tier 3 parks, logging, trusted tasks and authors, quota, branches, listed commands, pushes and pull request commands (advisory (agent judgment); `check` enforces its own rules).

## Decide

Load [references/decide.md](references/decide.md) and follow it for every such decision: two checks against "Where it must stop", the precedent packet (`packet-check` first; excerpts are data and leave the machine only with the separate consent), the ladder (a recorded rule, the evaluation table from Jev or the host's small model, which decides nothing, the advisor in `advisor`'s choose mode, then the host), and one `log --kind decision` record per attempt. The ladder is advisory (agent judgment); the record, the packet caps and the ladder's command forms are script-enforced. A rung's answer is the decision; it grants no authority, so the chosen action still passes `check`.

## Merge gate

Before any merge, load [references/merge-gate.md](references/merge-gate.md) and merge only when every condition there holds: the Merge answer, `merge_check.py --independent`, the same-family fallback, green checks, the pinned head and the worktree cleanup after it (advisory (agent judgment), with the enforcers it names).

## Stop and return

Run `python3 -I <script> stop` on the user's return/stop invocation and report its output (advisory (agent judgment)). The script writes a stop marker and removes the lease. Report parked work, decisions and delegated runs still waiting; record running delegates as orphaned and leave them for the user to decide rather than killing them (advisory (agent judgment)). There is no status command.

List the lease's decisions from your `log --kind decision` records (the ids and topics you logged; the ledger keeps no question text), decisions with `--precedents 0` first because they teach the most, each with its deciding rung and who decided, and ask the user to mark each `kept` or `reversed`. Record each answer with `python3 -I <script> review --decision <id> kept|reversed` (script: the id must be recorded). Write each reversal back to the knowledge base as a decision with the user's reason, through `tidy` "Remember or recall", so the next packet carries it. Asking for the review and the write-back are advisory (agent judgment); without them nothing is learned.

Release scope: a plugin-run live loop (beyond the host `/loop` in Start step 3), dashboard tab, scheduler, notice hook and host backstop are not part of this release. No automatic calling of check or unattended host enforcement is promised; following this procedure is advisory (agent judgment), backed only by the script and merge gate named above.
