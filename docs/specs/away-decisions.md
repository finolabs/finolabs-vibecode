# Away decisions: who decides while the user is away (draft, scoped to release 0.2.3)

Status: implemented; in release 0.2.3.

> Since 0.2.5 the `autopilot` skill is `afk`, its script `afk.py` and its host config section `## afk`; see the note at the top of [autopilot.md](autopilot.md). This document keeps the names of its time.

## Why

While the user is away, a host agent still meets decisions it would normally ask the user. `autopilot.md` already says that
Tier 2 decisions go to an advisor acting as the user's avatar, but four gaps keep that from working:

1. Nothing stops the agent from asking anyway. The session-start text tells it to use the host's question tool, and the
   `autopilot` skill does not say what replaces it, so a question waits until the user returns.
2. The user cannot name who decides: `/setup add afk` has no such question, so each host picks for itself.
3. `advisor` only gives an open opinion and ends with "you stay the decider". An away decision needs one choice among
   known options, cheaply, and on the record.
4. Two names are confused. `ask` answers questions about the plugin; `advisor` gets an opinion. The verb in the
   first suggests the second.

## Owner decisions (2026-11-09)

- Both changes go into 0.2.3: the decision procedure with a named advisor, and the rename below.
- No separate decider. Asking another agent is one concept: `advisor` gains a mode that must choose among given
  options, and the matrix role is `advisor`, so the same named agent serves the user's presence and absence.
- The help skill's main name becomes help, and `ask` stays as a thin alias, as `brb` does for the away skill.
  `advisor` keeps its open opinion and its committee.
- Inside a lease the advisor is always another model family, reached through its own command-line program, and has to be
  capable enough for the role: the frontier tier of that family in `delegate` `models.md` first, then its strong tier.
  Nothing below strong, and no advisor run of the host's own family (a Claude model served through another host counts as
  Claude): with no eligible advisor the host itself chooses, as "Outcomes when a rung cannot answer" says.
- The question gate below is built now rather than after a trial. The owner's practice is to apply the design predicted to
  work best, use it on this machine and improve it from what happens, so every decision must reach the ledger for that analysis.

## The ladder

While a lease is active, a decision the agent would otherwise ask the user goes up this ladder and stops at the first
rung that settles it. Each rung is cheaper than the next.

1. **A recorded rule.** The user's own instructions, the assignment matrix or the task's brief already settle it (agent
   judgment, advisory).
2. **Jev**, when the choice is among closed options and `judge: jev` is set: one call of a new `judge.py` site,
   `away-decision`, with the question, two to six options and the evidence the question needs. It settles the choice when the top option's
   probability is at least 0.8, a starting threshold that the first real uses must validate; below that, the next rung.
3. **The advisor**: `advisor` in its choose mode, run by the agent the matrix names in the optional role `advisor` or,
   with none named, by the family `advisor` already picks (one other than the host's), among the lease's recorded Hosts: one read-only
   run that must return exactly one of the options with its reason, or `none`. It is an ordinary dispatch (ledger kind
   `advise`) and counts against the lease's run limit.
4. **The host's own choice**, when no rung above answered: it picks the option that best serves the spec or the project's stated goal and records itself as the decider (rung `host`).

**Parking is not a rung.** Before a question enters the ladder and again before the chosen action runs, the host checks it against "Where it must stop" (advisory, agent judgment, except for the command forms `autopilot.py check` classifies). What stops there is logged as rung `park`, the user is told once, and the host goes on with other work.

Inside a lease the answer of a rung is the decision, not advice: the host applies the option it returned and does not
re-ask, overrule or shop it to another rung (advisory, agent judgment; the `log --by` record shows who decided). `advisor`'s line "you stay the
decider" stays true for its open mode, with the user present; the choose mode states the opposite for a lease.

### Outcomes when a rung cannot answer

Each case has one outcome. A decision is never permission: the action it selects still goes through "Where it must stop" and `autopilot.py check`.

| Case | Outcome | Recorded as |
| --- | --- | --- |
| Jev not configured, or the options are not closed | go to the advisor | no attempt |
| Jev refuses, times out or fails | go to the advisor | `jev`, `unavailable` |
| Jev's top option is below 0.8 | go to the advisor | `jev`, `no`, with the probability |
| The lease's Hosts hold no family other than the host's, or no other family has a strong model | the host chooses | `advisor`, `unavailable`, then `host` |
| The advisor is out of quota, unreachable or its run fails | the host chooses | `advisor`, `unavailable`, then `host` |
| The advisor answers `none` | the host chooses | `advisor`, `no`, then `host` |
| The advisor names something outside the options | treated as `none` | `advisor`, `no`, then `host` |
| The host finds a fact the deciding rung did not have, and it changes which option fits | one new attempt at that same rung with the fact added, same decision id; if the answer does not hold, the host chooses | a further attempt, then `host` when it chooses |
| "Where it must stop" applies, at either check | parks, whatever a rung answered | `park` |

### How the ladder's calls pass the action gate

The skill requires a Tier 1 check before every action, so rungs 2 and 3 need command forms `autopilot.py` knows. Package 5 adds exactly two to `classify_argv`, and the script stays execution-free:

- `judge.py` of this install, with isolated Python, and only the site `away-decision` and its validated options. No other site, no base-URL flag.
- The advisor's run: this install's `delegate_env.py` wrapper followed by one closed read-only argv shape per family, taken from `advisor`'s own dispatch commands, the family being one of the lease's Hosts and other than the coordinator's. The program is the family's owner-approved executable: the absolute path recorded in the canonical host config for the quota probe (`Executable`, `Resolved` and its confirmed digest), passing that probe's owner, mode, repository and target checks at check time; no record means the form is denied, and a bare name, a PATH lookup, another path with the same name and a time-cap wrapper such as `perl`, which has no such record, deny. The brief is passed only by the mechanism those commands already use, behind an unambiguous boundary: Codex and Claude end their options with a literal `--` immediately before the brief, Antigravity takes it as the value of `-p`, and in every form a brief that starts with `-` (an option, or `-` for unvalidated standard input) denies. Any write-enabling flag, unknown option or other program denies.

Each Tier 1 check reserves an action, and the advisor's ledger start also reserves a run; a denied check reserves nothing. Acceptance cases show both calls returning Tier 1 under a live lease, and a changed site, a write flag, a family outside Hosts and an unknown program being denied.

Tier 3 never enters the ladder. `autopilot.py check` still classifies the resulting action, so a choice made here
grants no authority: an option the check denies is parked. The rungs choose among options the agent already may take.

## What enforces what

- `autopilot.py` stays a script with no execution and no network call, so it cannot run the ladder itself: a single command
  that called Jev or started an agent would break its contract. The ladder is a procedure in `autopilot`
  (`references/decide.md`), advisory (agent judgment).
- The record is script-enforced; see "Record for analysis".
- `judge.py` enforces the new site's closed schema and byte caps, as for the other sites. The new site changes the closed
  list in the fourth scoped exception of `CLAUDE.md` and the Judge text of `PRIVACY.md`; those amendments merge before its code.
- `assignments.py` adds `advisor` to its roles, one agent at most. The role is optional, so the away mandate works with no
  extra setup: without it the advisor is picked by contrast as `advisor` does today, limited to the lease's Hosts. A name
  the user gives by hand wins over the role, and the role wins over the contrast rule.
- The question gate below enforces that the user is not asked during a lease, on Claude Code.
- While a lease is active, `session_start.py` prints one fixed line, after a compaction or resume as well: `Away mandate active:
  do not ask the user; follow autopilot "Decide"`. It reads only whether a live lease exists and prints no content.
  The skill says the same when the lease starts.

## Grounded in the user's memory

Owner decision (2026-11-09): a decision made in the user's place must rest on what the user has actually decided before.
An advisor with only the code in front of it would give its own opinion, not the user's.

- **The host builds a precedent packet; the advisor does not search.** Another family's program may have no access to the user's knowledge
  base or to the host's native memory, and giving it that access would hand a whole private store to a provider for one question. The host,
  which already reads them, queries the knowledge source the user's instructions name (`tidy` "Remember or recall") and its
  native memory for this question, and passes only the matching excerpts: the decision, its date and a source reference for each, at most eight
  excerpts and 8 KB. Selecting by relevance is agent judgment, advisory; when a judge is configured it may rank the candidates, under the same consent and screening as any other excerpt that leaves the machine.
- **The goal decides, a missing precedent does not stop the work.** Every rung chooses the option that best serves the current spec or the project's
  stated goal; the packet carries those anchors beside the precedents. Rungs 2 and 3 cite what they relied on and the record keeps the count of precedents. With
  none, the rung still answers on the goal alone, and if no rung can answer, the host chooses the same way (rung `host`). Rung 1 is a recorded
  rule or a precedent that answers this exact question. On return, decisions with no precedent are listed first, because they teach the most.
- **What stops is the blast radius, not the novelty** (owner, 2026-11-09). Work that can be rolled back goes on: the local machine, a development environment, a UAT
  run. Reaching production, a live environment or real users always stops for a person, and no setting opens it. See "Where it must stop".
- **Excerpts are data.** The brief says so, instructions inside them are ignored, and a precedent can narrow a choice but grants no authority.
- **Leaving the machine needs its own consent.** Excerpts sent to a judge or to another family's provider are the user's private history. `/setup add
  autopilot` asks one separate neutral question for it, recorded in `## Autopilot`; without a yes no excerpt leaves the machine, so rungs 2 and 3 have
  nothing to cite, so they answer on the goal alone. Each excerpt passes the secret and machine-path patterns first; a hit drops that excerpt. This is agent
  judgment for selection and a script check (`brief_check`-style lint of the packet) for the caps and patterns.
- **The loop that makes it learn.** `stop` lists the lease's decisions, and on return the user marks each `kept` or `reversed`. A reversal is written back to the knowledge
  base as a decision with its reason, through the same procedure, so the next packet carries it; `reversed` also goes to the ledger, giving a real accuracy per rung and per advisor.
  Without that step nothing is learned, so the report asks for it (advisory, agent judgment).

## Where it must stop

`autopilot.md` makes every deploy Tier 3. That is too broad: it also stops a deploy to a development environment or a UAT run, which can be rolled back. The rule becomes:

The user chooses (owner, 2026-11-09). `/setup add afk` shows one table of closed categories with the starting choice beside each, and the user changes any row not marked fixed. Each category is `stop` (wait for a person) or `decide`
(the ladder decides). The choices are stored in `## Autopilot`; a missing or unknown value is `stop`.

| Category | Starting choice |
| --- | --- |
| Deploy or change to production or a live environment | stop, fixed |
| Anything reaching real users or real customer data | stop, fixed |
| Deletion that cannot be recovered (remote data, a forced push to a default branch) | stop |
| A message to a person outside the repository | stop |
| Tags and releases | stop |
| Publishing to the user's own catalog or package | stop |
| Repository-level shared settings such as CI configuration and defaults | stop |
| Deleting local or recoverable things (the session's own branches, worktrees, generated files) | decide |
| Comments and replies on the repository's own pull requests and issues | decide |

Moving any category from `stop` to `decide` is its own neutral question, with what could go wrong stated and no default, like Merge.
A change that touches security in code is not a category: it goes through the review gates and the merge gate.

**What no setting can open.** Production and live environments and real users or customer data, because the owner requires a person there (the two fixed rows). Credentials, because handling them is outside what any agent may do here. An agent changing its own limits (hooks, permission rules, agent instructions, the lease and setup files, and any path in the running install's own checkout on any branch, while its linked worktrees stay editable), because a limit the agent can
lift for itself is no limit. Approving its own work: pull request and commit text carrying a review gate marker is Tier 3, and reviews post only through `post_review.py`. Removing a worktree under the recoverable-deletion row covers only the worktree whose head a `log --kind merge --head` entry of the current lease recorded, never the one holding the install.

**One precedence rule.** An action goes on only when every category that applies to it permits it. Checked in this order, the first match wins:

| # | Condition | Result |
| --- | --- | --- |
| 1 | Credentials or the agent's own limits | Tier 3, parked |
| 2 | Production, live, real users or customer data, or uncertain whether it reaches them | Tier 3, parked |
| 3 | Any applicable category is `stop`, missing or invalid | Tier 3, parked |
| 4 | A deploy that does not match `Non-production targets` exactly | Tier 3, parked |
| 5 | Every applicable category is `decide`, or the deploy matches a listed target | Tier 1 |
| 6 | Local work no category names | classified as today |

A listed target relaxes only the deployment classification; it never overrides rows 1 to 3. Examples: a listed UAT run on synthetic data goes on; the same UAT holding real customer data parks; an action matching one `decide` and one `stop` category parks; a production deploy parks even if listed by mistake as a target, when the host can tell; a tag with the category moved to `decide` is Tier 1.

What the script can enforce: tags, releases, publishing, deploys and forced pushes are command forms that `autopilot.py check` classifies, so for those the choice is script-enforced. Whether an action reaches real users or real customer data, or whether a message goes to a person, cannot be read from a command: those categories are agent judgment, advisory, and a host in doubt treats them as `stop`.
- **How a script tells them apart.** `autopilot.py` cannot infer an environment from a command. `## Autopilot` gains `Non-production targets`, an optional list the user fills in setup with the exact deploy
  commands or target names per project, default empty. A deploy matching an entry exactly passes row 4 above; every other deploy stays Tier 3, so an unlisted or ambiguous target
  fails closed to a person. A merge still follows the recorded Merge answer and the merge gate. Naming which targets are safe is the user's decision; an agent never adds an entry during a lease (script: setup changes deny further checks).

## The question gate (Claude Code)

One `PreToolUse` hook for the `AskUserQuestion` tool, in its own group, under the sixth scoped exception in `CLAUDE.md`. While a live
lease exists it denies that one call with one fixed message: the user is away, follow autopilot "Decide". It reads only whether
a valid, unexpired lease exists, through the same safe reader as `autopilot.py`; no lease, an expired, stopped or unreadable one, or any
error allows. It never reads the question, never denies another tool, a prompt, a session start or the user's own stop.
Starting the lease is the user's opt-in; `FNL_AWAY_GATE=off` disables it. It appends one ledger line (below) and sends nothing.
Codex and Antigravity have no such hook here and stay advisory. The first build step checks on the installed host that a hook fires for
that tool; if it does not, the gate is dropped and the report says so.

## Record for analysis

The owner reviews real use from the ledger, so one record covers every decision and `status` reads it.

- `autopilot.py log --kind decision` records one attempt. All attempts on one question share `--decision <id>`, an id the first attempt's call generates and prints (`q<date>-<time>-<4 hex>`) and later calls must pass. Common fields: `--rung rule|jev|advisor|host|park`, `--settled yes|no|unavailable`, `--precedents <count>`, `--topic` (a short label under the ledger's task-label rule). The closed schema, refused otherwise:

  | Rung and result | Required | Absent |
  | --- | --- | --- |
  | `rule`, `yes` | `--by rule`, `--option`, `--of` | probability, dispatch |
  | `rule`, `no` (new evidence made the rule inapplicable) | `--by rule` | option, probability, dispatch |
  | `jev`, `yes` | `--by jev`, `--option`, `--of`, `--probability` | dispatch |
  | `jev`, `no` | `--by jev`, `--probability` | option |
  | `jev`, `unavailable` | `--by jev` | option, probability |
  | `advisor`, `yes` | `--by <agent or install>`, `--option`, `--of`, `--dispatch`, `--model` | probability |
  | `advisor`, `no` | `--by`, `--dispatch`, `--model` | option |
  | `advisor`, `unavailable`, an advisor was selected | `--by` (optional: `--dispatch` when a run was started) | option |
  | `advisor`, `unavailable`, selection found no candidate | nothing further | `--by`, option, dispatch, model |
  | `host`, `yes` | `--by <the host's family>`, `--option`, `--of`, `--model` | probability, dispatch |
  | `park`, `yes` | `--by` the deciding host | option |

  A field not listed as required or optional for its row is refused. Per-advisor reports count only attempts with a `--by`. It validates them and, in the same call, appends a `decision` line to the ledger with those fields, the time, the project and the lease's start time. The note stays in the autopilot log, capped, redacted and kept 30 days.
- The gate appends a `question_denied` line with the time and the lease's start time only.
- On return, `autopilot.py review --decision <id> kept|reversed` appends a `decision_review` line with no reason text. The id must exist in the ledger; a later review of the same id replaces the earlier one when read.
- `ledger.load()` keeps returning its two maps of `start` and `finish` records, which `pause.py`, the status refresh and `project_progress` consume. It skips the three new event types silently, without the malformed-line message; a separate reader returns them. A test runs mixed history through `load`, the new reader and `summary` and shows the dispatch numbers unchanged.
- An away view of the ledger summary and the `status` tables show, per lease: decisions by rung, by advisor and model, the Jev probability
  spread, parked and denied questions, and the share reversed by the user. No question or option text is ever in the ledger; the topic label is the only words.

## Limits

- Screening a brief or an excerpt lowers the risk of sending a credential to another provider; it cannot prove there is none. It refuses any sensitive name followed by `=` or `:` rather than parsing values, because every parser review tried could be bypassed by another value shape.
- The gate stops the host asking the user; it does not make the host climb the ladder, which stays advisory, and whether the
  host applied the chosen option is not machine-checkable because options are free text. The ledger shows what was decided, not what was done.
- Probability is a judgment of fit among the options given, not proof the choice is right; a poorly framed question yields a
  confident wrong answer. The record lets the user review each decision on return.
- When the advisor's family wrote the work the decision concerns, the report says the opinion is from the same family.

## The rename

help is a new user-facing skill folder holding the content of `ask`; `ask` becomes a thin alias naming help as its
dependency. The description states in plain words that it answers questions about this plugin, not that it asks anyone. Counts, the map,
README and tests follow, as for `afk`.

## Open decisions

| Decision | Owner | What unblocks it |
| --- | --- | --- |
| Whether 0.8 is the right threshold for rung 2 | owner | the first real decisions in the log |
| Whether `advisor`'s committee is ever a rung for design decisions | owner | a preference |

## Evidence

None yet. A build needs a red test per behavior: the `log` fields and their refusals, the new judge site's schema and refusals, the gate (denies only with a live lease, allows on every error), the ledger `decision`, `question_denied` and `decision_review` lines over mixed history with `load` unchanged, every row of the attempt schema (with table-driven cases for host-only Hosts and no advisor, and for a rule invalidated by new evidence, each ending in `host` under one decision id), every row of the outcomes table and of the precedence table, the two new Tier 1 forms and their denials, the `advisor` role and the single-agent rule, the tier and family rule, the packet caps and pattern drops, the zero-precedent record, the environment classification and its fail-closed default, the consent refusal, the choose mode's output contract, the lease line in `session_start.py` present and absent, and the alias and counts of the rename.
