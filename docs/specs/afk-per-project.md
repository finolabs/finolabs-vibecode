# afk per project: limits per repository, an evaluation table before the deciders, no stops beyond setup

Status: accepted; owner decisions recorded and draft accepted on 14/11/2026; for 0.2.7, built in the six pull requests listed under "Order of pull requests"; no code has landed yet.

This document changes [autopilot.md](autopilot.md) ("Project scope", "Lease, state and what enforces what") and [away-decisions.md](away-decisions.md) ("The ladder", "Where it must stop"). Where they disagree, this document wins for 0.2.7 and the older text gets a pointer here.

## Owner decisions (14/11/2026)

1. afk is set up at user scope and at project scope. Every work limit (runs, runtime, actions per hour) is counted per project, never per machine.
2. Away means fully automatic. Whatever the user allowed in setup, review, merge or deploy included, the host does without stopping to wait or ask.
3. Decision flow: the host first asks Jev for an evaluation table of the options when the user has Jev. It then sends the context, Jev's table and every fact the question needs to the deciders, takes their decision and carries it out.
4. A project may allow production deploys under afk when it turns that on in its own setup, with a consent question of its own and the exact commands listed; otherwise production still waits for the user.
5. When no other model family is reachable for a review, a same-family review is allowed under afk. Its marker names the family, the lease log records the fallback, and the merge goes on.
6. Carried forward (PR 243): a project value may be wider or narrower than the user value (two-way override).

## What main does today, and the gap

| Topic | Main (0.2.6) | Gap to the decisions |
| --- | --- | --- |
| Scope of a lease | One lease per machine; every session shares it | Decision 1 |
| Limits | `Max runs`, `Max runtime minutes`, `Max actions per hour` are user scope only, one counter set in `lease.json` | Decision 1: 60 actions an hour ran out in about an hour of PR work across sessions on 13/11 |
| Project scope keys | Five: Task choice, Push and pull requests, Merge, Trusted authors, Roots | Limits, categories and deploy targets are user scope only |
| Jev | A deciding rung: settles alone at probability 0.8 or more | Decision 3: Jev evaluates, the deciders decide |
| Advisor brief | Question, options, goal, precedent packet | Decision 3: add Jev's table |
| Production | A fixed `stop` row; no setup can move it | Decision 4 |
| Independent review | `merge_check.py --independent` blocks same-family markers; with Codex and Antigravity out of quota every merge parks | Decision 5 |
| Other stoppers seen on 13/11 | `post_review.py` is not an allowed wrapper; a Markdown skill repository's paths are all unknown; `git add` costs one action per path | Decision 2 |

## Design

### A. Limits per project

- The lease stays one user mandate (start, expiry, stop, setup hash). Counters move under a key per project: the full identity digest from `project_store.identity`. `lease.json` holds `counters: {<digest>: {runs, runtime_minutes, actions, hour_actions}}`, at most 64 projects; a check in a repository it cannot identify uses one shared `unknown` counter with the strict values.
- The limit keys become project-scope keys too: `max-runs`, `max-runtime-minutes`, `max-actions-per-hour`. A project value replaces the user value for that project (decision 6). The user value stays the default.
- `Lease hours` and `Hosts` stay user scope: they describe the mandate, not the work.
- One `check --paths a b c` reserves one action, not one per path.
- Enforcer: `afk.py` (script). Tests: two projects each reach their own hourly limit independently; the `unknown` counter is shared; a project value replaces the user value both ways.

### B. Categories and deploy targets per project

- The stop/decide table (except the fixed rows below) and `Non-production targets` become project-scope keys: `decide` (a list of category keys) and `non-production-targets`.
- New project-only key `production-targets`: a list of exact deploy commands, matched like `Non-production targets` (words joined by single spaces). It is written only through its own setup question, with a preview, inside that repository; it is never read from user scope. A deploy that equals an entry is Tier 1 when the project's `Production` row is `decide`; any other production or live deploy parks.
- The fixed rows shrink to two: credentials, and real users or real customer data reached by anything other than a listed production target. `Production` becomes changeable at project scope only, never at user scope.
- `Real users and customer data` stays fixed `stop` for every action that is not a listed production deploy.
- Enforcer: `afk.py check` for deploy argv (script); rows that a command does not show stay advisory (agent judgment), a doubt counts as `stop`.

### C. The decision flow

The ladder becomes:

1. **A recorded rule** settles it, as today (rung `rule`).
2. **Evaluation by Jev**, when the assignment matrix's judge is `jev`: one `judge.py ask --site away-evaluation` call over the question, the options and the checked packet. It returns the probability of each option (the table). It never settles alone. When Jev is not configured, refuses, times out or fails, the table is absent and the record says why.
3. **The deciders**: `advisor` in choose mode receives the question, the options, the goal anchor, the precedent packet and Jev's table (marked as data, with its source), and returns one option or `none`.
4. **The host** decides when no decider answered, with Jev's table in view (rung `host`).

Then the host carries out the chosen option through `check` like any action. A decision still grants no authority.

- `judge.py` gets the site `away-evaluation` (closed schema, caps and refusals as the other sites); `away-decision` is kept for one release and then removed.
- `afk.py log --kind decision` gains rung `jev-table` with `--settled table|unavailable` and the top option's probability; the existing decider records are unchanged.
- Enforcer: the record and the site schema (script); the order of the rungs is advisory (agent judgment).
- CLAUDE.md: the fourth scoped exception's closed list names "an away decision among closed options"; it is renamed to "an away evaluation among closed options" in the pull request that records this rule, before any code.

### D. Same-family review fallback

- `merge_check.py --independent` accepts a same-family marker only with `--fallback-family <family>` when `review_route.py` reports, from the cached quota readings and rate-limit markers, that every other family in the lease's Hosts is out of quota or unreachable at that time. It prints `ok    same-family review: no other family reachable (<families>)`.
- The marker's second line names the reviewer family and the fallback. `afk.py log --kind review-fallback --pr <n> --head <sha>` records it for the user's return.
- Enforcer: `merge_check.py` for the reachability evidence it reads (script); routing the review to the other family first is advisory (agent judgment).

### E. Stoppers removed

- `post_review.py` becomes an allowed wrapper in `afk.py check`, with its own argv grammar (`<pr>` or `--body-file <file> <pr>`, the file under the checkout and at most 64 KiB).
- A Markdown skill repository (a root `SKILL.md`, and `references/`, `scripts/`, `evals/` beside it) gets those as known roots on a work branch.

## Acceptance

1. Two repositories under one lease: actions in one never consume the other's hourly, run or runtime limit (test).
2. A project limit wider than the user limit applies in that repository only (test).
3. A deploy equal to a listed `production-targets` entry is Tier 1 only in the repository that listed it with `Production` at `decide`; the same argv elsewhere, or any unlisted production deploy, parks (tests).
4. Under a lease with Jev configured, every decision record shows a `jev-table` attempt before the decider's record; without Jev it shows `unavailable` (test of the record schema; the order is advisory).
5. `merge_check.py --independent --fallback-family claude` passes on same-family markers only when every other family is out of quota or unreachable in the cache, and blocks otherwise (tests).
6. `post_review.py` and a skill repository's paths are Tier 1 on a work branch with Push and pull requests yes (tests).
7. `PRIVACY.md`, `setup` (`references/features/afk.md`, `afk-decisions.md`), the afk skill and `upgrades.json` describe the new keys; the upgrade note tells users to run `/setup add afk` inside each repository that wants its own limits or production targets.

## Order of pull requests

1. This spec and the CLAUDE.md rename of the judge site (no code).
2. A: per-project counters and limit keys.
3. E: stoppers removed (small; may land before A).
4. C: the evaluation site and the new ladder.
5. D: same-family fallback in `merge_check.py`.
6. B: per-project categories and production targets, last, because it widens what an unattended agent may reach.

## Open

- Default per-project limits when neither scope sets one: keep today's user defaults (20 runs, 480 minutes, 30 actions an hour) per project. Owner to confirm.
- Whether `Tags and releases` and `Publishing` at `decide` in a project should also need their own exact-command list like production. Owner to decide; until then they follow today's rule.
