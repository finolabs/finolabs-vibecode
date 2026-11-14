# afk per project: limits per repository, an evaluation table before the deciders, no stops beyond setup

Status: accepted; owner decisions recorded and draft accepted on 14/11/2026; for 0.2.7, built in the six pull requests listed under "Order of pull requests"; no code has landed yet.

This document changes [autopilot.md](autopilot.md) ("Project scope", "Lease, state and what enforces what") and [away-decisions.md](away-decisions.md) ("The ladder", "Where it must stop"). Where they disagree, this document wins for 0.2.7 and the older text points here.

## Owner decisions (14/11/2026)

1. afk is set up at user scope and at project scope. Every work limit (runs, runtime, actions per hour) is counted per project, never per machine.
2. Away means fully automatic. Whatever the user allowed in setup, review, merge or deploy included, the host does without stopping to wait or ask.
3. Decision flow: the host first gets an evaluation table of the options, then sends the context, that table and every fact the question needs to the deciders, takes their decision and carries it out.
4. The table comes from Jev when the user has Jev; otherwise from an agent on a small, fast model that stands in for Jev.
5. A project may allow production deploys under afk when it turns that on in its own setup, with a consent question of its own and the exact commands listed; otherwise production still waits for the user.
6. When no other model family is reachable for a review, a same-family review is allowed under afk. Its marker names the family, the lease log records the fallback, and the merge goes on.
7. Carried forward (PR 243): a project value may be wider or narrower than the user value (two-way override).

## What main does today, and the gap

| Topic | Main (0.2.6) | Gap to the decisions |
| --- | --- | --- |
| Scope of a lease | One lease per machine; every session shares it | Decision 1 |
| Limits | `Max runs`, `Max runtime minutes`, `Max actions per hour` are user scope only, one counter set in `lease.json`; runtime is wall time since the lease started (`runtime_minutes` is never incremented) | Decision 1: 60 actions an hour ran out in about an hour of PR work across sessions on 13/11 |
| Project scope keys | Five: Task choice, Push and pull requests, Merge, Trusted authors, Roots | Limits, categories and deploy targets are user scope only |
| Jev | A deciding rung: settles alone at probability 0.8 or more; without Jev there is no table | Decisions 3 and 4 |
| Advisor brief | Question, options, goal, precedent packet | Decision 3: add the table |
| Production | A fixed `stop` row; a deploy argv with a `prod` or `live` word is always `forbidden` | Decision 5 |
| Independent review | `merge_check.py --independent` blocks same-family markers; with Codex and Antigravity out of quota every merge parks | Decision 6 |
| Other stoppers seen on 13/11 | `post_review.py` is not an allowed wrapper; a root `SKILL.md` is a protected name, and `references/` and `evals/` are not known roots, so a Markdown skill repository parks every commit; agents checked each path in its own `check` call (one `check` already reserves one action for all its paths) | Decision 2 |

## Design

### A. Limits per project (pull request 2)

- The lease stays one user mandate (start, expiry, stop, setup hash). `lease.json` holds `counters: {<key>: {runs, actions, hour_actions, first}}`, where `<key>` is the full identity digest of the main checkout from `project_store.identity`, or `unknown` for every check whose identity is unknown or absent (one shared entry). `first` is the time of the project's first reserved action. The table never evicts an entry during a lease; a 65th key answers `limit`.
- The limit keys become project-scope keys: `max-runs` (1 to 10000), `max-runtime-minutes` (1 to 1440), `max-actions-per-hour` (1 to 10000), integers. A project value replaces the user value for that project (decision 7). In the strict state and for the `unknown` entry, the user values apply; they are the user's own ceiling for an unidentified repository.
- Runtime of a project is the time since its `first` reserved action. `Lease hours` bounds the whole mandate.
- `lease_guard` keeps the lease-wide denials (no lease, expired, stopped, setup changed), which add the `end` line. The per-project check runs after `git -C` and `effective(applied, cwd)` resolve the repository: spent runs or runtime answer `spent`, the rolling hour or a full table answer `limit`; neither adds the `end` line, so the loop goes on in other projects. `exhausted` is no longer returned.
- `away_lease.read_lease` (shared by `afk.py`, `away_gate_hook.py` and `session_start.py`, and its copy under `scripts/`) validates the new schema; a lease written by 0.2.6 reads as invalid, so the user starts it again.
- `skills/afk/SKILL.md` tells agents to check all paths of one change in one `check --paths` call.
- Enforcer: `afk.py` and `away_lease.py` (script). Tests: two projects each reach their own hourly and run limits; a project value applies both ways; out-of-range values are refused.

### B. Categories and deploy targets per project (pull request 6)

- Project-scope keys: `decide` (a list of category keys) and `non-production-targets` (a list of exact commands). An explicit `decide` list, `[]` included, replaces the user's category answers for that project, and every category not listed is `stop`; an omitted `decide` inherits the user's answers. An explicit `non-production-targets` replaces the user's list; an omitted one inherits it.
- New project-only key `production-targets`: a list of exact deploy commands, matched like `Non-production targets` (words joined by single spaces), written only through its own setup question with a preview, inside that repository; it is never read from user scope. `Production` may appear in a project's `decide` list and never in the user's.
- A deploy argv is Tier 1 only when it equals a `production-targets` entry of this project and `Production` is in this project's `decide`, or equals a `non-production-targets` entry and has no production or live word. Every other deploy parks.
- The strict state and the no-repository state reset every category to `stop` and both target lists to empty. `release_command` (tags, releases, publishing, deploys) denies in those states, and `gh release create` needs exactly one `--repo github.com/OWNER/NAME` equal to the verified target, like a pull request merge.
- `Real users and customer data` and credentials stay fixed `stop`.
- Enforcer: `afk.py check` for argv it reads (script); a row a command does not show stays advisory (agent judgment), and a doubt counts as `stop`.

### C. The decision flow (pull request 4)

The ladder becomes:

1. **A recorded rule** settles it, as today (rung `rule`).
2. **The evaluation table.** With `Judge: jev`: one `judge.py ask --site away-evaluation` call over the question, the options and the checked packet. Without Jev, or when Jev refuses, times out or fails: one read-only run of a small, fast model (the host's fast tier, such as a Haiku-class subagent on Claude Code) given the identical question, options and packet, asked for the probability of each option. The table never settles the choice alone. Rung `table`.
3. **The deciders**: `advisor` in choose mode receives the question, the options, the goal anchor, the precedent packet and the table (marked as data, with its source), and returns one option or `none`.
4. **The host** decides when no decider answered, with the table in view (rung `host`).

Then the host carries out the chosen option through `check` like any action. A decision still grants no authority.

- `judge.py ask --site away-evaluation` prints `{"source": "jev", "of": <k>, "probabilities": [<p1>, ..., <pk>]}` with each probability in 0 to 1; the `away-decision` site and its 0.8 threshold are removed. The small-model table is written by the host to a file under `.finolabs/briefs/` in the same shape with `"source": "host-small"` and is checked by `judge.py check-table --file <file>` (closed schema, k equal to the options, values in 0 to 1).
- `afk.py check` allows `judge.py ask --site away-evaluation` (replacing `away-decision`) and `judge.py check-table`.
- `afk.py log --kind decision` replaces rung `jev` with rung `table`: `--settled table` with `--by jev|host-small --of <k> --probability <top p>`, or `--settled unavailable --by jev|host-small`; it never takes `--option` and has no threshold. `ledger.py` `away_rows` reads the probability of rung `table`.
- Enforcer: the record, the site schema and `check-table` (script); the order of the rungs is advisory (agent judgment).
- [CLAUDE.md](../../CLAUDE.md) (fourth scoped exception) and [PRIVACY.md](../../PRIVACY.md) ("Judge", "Away decisions") describe the evaluation from pull request 1, before any code.

### D. Same-family review fallback (pull request 5)

`merge_check.py --independent --fallback-family <family>` accepts current-head markers posted by `<family>` only when all of these hold:

1. A live, valid away lease exists (`away_lease.live_lease`).
2. `<family>` is the pull request author's family (`review_route.author_family`).
3. Every other family that `review_config.present_families` reports for this machine has positive evidence of being out: a reading younger than 8 hours in `state/quota/quota.json` with every pool below the routing floor, or a live rate-limit marker in `limits.json`. A missing, stale, failed or backed-off reading is not evidence; the family counts as reachable and the fallback is refused.
4. The pull request's `fnl-router` trigger is not `security`, `permission` or `privacy`, and the pull request changes no enforcer script (the `ENFORCERS` list of `afk.py`) and no instruction file (`CLAUDE.md`, `AGENTS.md`, `SKILL.md`); those park for the user.
5. Each counted marker's second line is exactly `Reviewer: <family> (same family as the author; no other family reachable)` followed by free text.

It prints `ok    same-family review: no other family reachable (<families>)`. `afk.py check` allows `--fallback-family <family>` on `merge_check.py`. `afk.py log --kind review-fallback --pr <n> --head <full sha>` (Tier 1, same `--pr`/`--head` rules as `merge`) records it for the user's return.

Enforcer: `merge_check.py` for conditions 1 to 5 (script); trying the other families first is advisory (agent judgment).

### E. Stoppers removed (pull request 3)

- `post_review.py` becomes an allowed wrapper in `afk.py check`, in both orders `<pr> --body-file <file>` and `--body-file <file> <pr>`, and bare `<pr>` (which creates the run folder). The file must be the run body `post_review.py` itself accepts: `<data root>/state/review-posting/post-<32 hex>/body.md`, a regular 0600 file, no link, at most 64 KiB. `check` screens the text after its first line with the pull request text screens (no secret, machine path, sensitive assignment or second `<!-- fnl-` marker), requires the verified target (not the strict state) and `Repository comments` at `decide`.
- A Markdown skill repository: when the default branch's committed tree (read from local Git objects, never the work tree) has a root `SKILL.md`, and `source_mode` holds (a non-default work branch with Push and pull requests or Merge yes), the root `SKILL.md` and `references/**`, `scripts/**` and `evals/**` are source paths. The hard names and the enforcer scripts stay protected.

## Acceptance

1. Two repositories under one lease: actions in one never consume the other's hourly, run or runtime limit (test).
2. A project limit wider or narrower than the user limit applies in that repository only (test).
3. A deploy equal to a listed `production-targets` entry is Tier 1 only in the repository that listed it with `Production` in its `decide`; the same argv elsewhere, in the strict state or any unlisted production deploy parks (tests).
4. Every decision record shows a `table` attempt (from `jev` or `host-small`, or `unavailable`) before the decider's record (test of the record schema; the order is advisory).
5. `merge_check.py --independent --fallback-family claude` passes on same-family markers only with a live lease, the author's family, fresh out-of-quota evidence for every other present family, no security trigger or enforcer or instruction file change, and the exact second line; it blocks in each other case (tests).
6. `post_review.py` with a valid run body, and a skill repository's paths, are Tier 1 on a work branch with the needed settings; a body file elsewhere, a body with a secret, or a skill repository whose default branch has no root `SKILL.md`, is Tier 3 (tests).
7. `PRIVACY.md`, `setup` (`references/features/afk.md`, `afk-project.md`, `afk-decisions.md`), the afk skill and `upgrades.json` describe the new keys; the upgrade note tells users to start the lease again and to run `/setup add afk` inside each repository that wants its own limits or production targets.

## Order of pull requests

1. This spec, `CLAUDE.md` and `PRIVACY.md` (no code).
2. A: per-project counters and limit keys.
3. E: stoppers removed.
4. C: the evaluation table and the new ladder.
5. D: same-family fallback in `merge_check.py`.
6. B: per-project categories and production targets, last, because it widens what an unattended agent may reach.

## Open

- Default per-project limits when neither scope sets one: keep today's user defaults (20 runs, 480 minutes, 30 actions an hour) per project. Owner to confirm.
- Whether `Tags and releases` and `Publishing` at `decide` in a project should also need their own exact-command list like production. Owner to decide; until then they follow today's rule.
- Condition 4 of D parks same-family merges of security-sensitive changes even under decision 6 (reviewer finding on pull request 276). Owner to confirm or lift.
