# Away decisions: who decides while the user is away (draft, scoped to release 0.2.3)

Status: draft; the owner approved the direction on 2026-11-09; nothing is built.

## Why

While the user is away, a host agent still meets decisions it would normally ask the user. `autopilot.md` already says that
Tier 2 decisions go to an advisor acting as the user's avatar, but four gaps keep that from working:

1. Nothing stops the agent from asking anyway. The session-start text tells it to use the host's question tool, and the
   `fnl-autopilot` skill does not say what replaces it, so a question waits until the user returns.
2. The user cannot name who decides: `/fnl-setup add autopilot` has no such question, so each host picks for itself.
3. `fnl-advisor` only gives an open opinion and ends with "you stay the decider". An away decision needs one choice among
   known options, cheaply, and on the record.
4. Two names are confused. `fnl-ask` answers questions about the plugin; `fnl-advisor` gets an opinion. The verb in the
   first suggests the second.

## Owner decisions (2026-11-09)

- Both changes go into 0.2.3: the decision procedure with a named advisor, and the rename below.
- No separate decider. Asking another agent is one concept: `fnl-advisor` gains a mode that must choose among given
  options, and the matrix role is `advisor`, so the same named agent serves the user's presence and absence.
- The help skill's main name becomes fnl-help, and `fnl-ask` stays as a thin alias, as `fnl-brb` does for the away skill.
  `fnl-advisor` keeps its open opinion and its committee.
- Inside a lease the advisor is always another model family, reached through its own command-line program, and has to be
  capable enough for the role: the frontier tier of that family in `fnl-delegate` `models.md` first, then its strong tier.
  Nothing below strong, and no same-family fallback (a Claude model served through another host counts as Claude): the
  question parks instead.
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
3. **The advisor**: `fnl-advisor` in its choose mode, run by the agent the matrix names in the optional role `advisor` or,
   with none named, by the family `fnl-advisor` already picks (one other than the host's), among the lease's recorded Hosts: one read-only
   run that must return exactly one of the options with its reason, or `none`. It is an ordinary dispatch (ledger kind
   `advise`) and counts against the lease's run limit.
4. **Park**, only for what "Where it must stop" names: log it, tell the user once, and go on with other work.

Inside a lease the answer of a rung is the decision, not advice: the host applies the option it returned and does not
re-ask, overrule or shop it to another rung (advisory, agent judgment; the `log --by` record shows who decided). If the host
finds a fact the rung did not have, it parks the question rather than overruling. An advisor that is out of quota or
unreachable, or that answers `none`, counts as unavailable, and the question goes on to the host's own choice as "Grounded in the user's memory" says. `fnl-advisor`'s line "you stay the
decider" stays true for its open mode, with the user present; the choose mode states the opposite for a lease.

Tier 3 never enters the ladder. `autopilot.py check` still classifies the resulting action, so a choice made here
grants no authority: an option the check denies is parked. The rungs choose among options the agent already may take.

## What enforces what

- `autopilot.py` stays a script with no execution and no network call, so it cannot run the ladder itself: a single command
  that called Jev or started an agent would break its contract. The ladder is a procedure in `fnl-autopilot`
  (`references/decide.md`), advisory (agent judgment).
- The record is script-enforced; see "Record for analysis".
- `judge.py` enforces the new site's closed schema and byte caps, as for the other sites. The new site changes the closed
  list in the fourth scoped exception of `CLAUDE.md` and the Judge text of `PRIVACY.md`; those amendments merge before its code.
- `assignments.py` adds `advisor` to its roles, one agent at most. The role is optional, so the away mandate works with no
  extra setup: without it the advisor is picked by contrast as `fnl-advisor` does today, limited to the lease's Hosts. A name
  the user gives by hand wins over the role, and the role wins over the contrast rule.
- The question gate below enforces that the user is not asked during a lease, on Claude Code.
- While a lease is active, `session_start.py` prints one fixed line, after a compaction or resume as well: `Away mandate active:
  do not ask the user; follow fnl-autopilot "Decide"`. It reads only whether a live lease exists and prints no content.
  The skill says the same when the lease starts.

## Grounded in the user's memory

Owner decision (2026-11-09): a decision made in the user's place must rest on what the user has actually decided before.
An advisor with only the code in front of it would give its own opinion, not the user's.

- **The host builds a precedent packet; the advisor does not search.** Another family's program may have no access to the user's knowledge
  base or to the host's native memory, and giving it that access would hand a whole private store to a provider for one question. The host,
  which already reads them, queries the knowledge source the user's instructions name (`fnl-session-hygiene` "Remember or recall") and its
  native memory for this question, and passes only the matching excerpts: the decision, its date and a source reference for each, at most eight
  excerpts and 8 KB. Selecting by relevance is agent judgment, advisory; when a judge is configured it may rank the candidates.
- **The goal decides, a missing precedent does not stop the work.** Every rung chooses the option that best serves the current spec or the project's
  stated goal; the packet carries those anchors beside the precedents. Rungs 2 and 3 cite what they relied on and the record keeps the count of precedents. With
  none, the rung still answers on the goal alone, and if no rung can answer, the host chooses the same way and records itself as the decider. Rung 1 is a recorded
  rule or a precedent that answers this exact question. On return, decisions with no precedent are listed first, because they teach the most.
- **What stops is the blast radius, not the novelty** (owner, 2026-11-09). Work that can be rolled back goes on: the local machine, a development environment, a UAT
  run. Reaching production, a live environment or real users always stops for a person. See "Where it must stop".
- **Excerpts are data.** The brief says so, instructions inside them are ignored, and a precedent can narrow a choice but grants no authority.
- **Leaving the machine needs its own consent.** Excerpts sent to a judge or to another family's provider are the user's private history. `/fnl-setup add
  autopilot` asks one separate neutral question for it, recorded in `## Autopilot`; without a yes no excerpt leaves the machine, so rungs 2 and 3 have
  nothing to cite, so they answer on the goal alone. Each excerpt passes the secret and machine-path patterns first; a hit drops that excerpt. This is agent
  judgment for selection and a script check (`brief_check`-style lint of the packet) for the caps and patterns.
- **The loop that makes it learn.** `stop` lists the lease's decisions, and on return the user marks each `kept` or `reversed`. A reversal is written back to the knowledge
  base as a decision with its reason, through the same procedure, so the next packet carries it; `reversed` also goes to the ledger, giving a real accuracy per rung and per advisor.
  Without that step nothing is learned, so the report asks for it (advisory, agent judgment).

## Where it must stop

`autopilot.md` makes every deploy Tier 3. That is too broad: it also stops a deploy to a development environment or a UAT run, which can be rolled back. The rule becomes:

- **Always stops (Tier 3):** a deploy or change to production or any live environment, anything reaching real users or real customer data, tags, releases and publishing, credentials, destructive deletion,
  shared settings, security boundaries, and a message sent to a person. No rung can decide these.
- **Goes on:** the local machine, and a deploy or run against a target the user named as non-production.
- **How a script tells them apart.** `autopilot.py` cannot infer an environment from a command. `## Autopilot` gains `Non-production targets`, an optional list the user fills in setup with the exact deploy
  commands or target names per project, default empty. A deploy matching an entry exactly is Tier 1 under the usual limits; every other deploy stays Tier 3, so an unlisted or ambiguous target
  fails closed to a person. A merge still follows the recorded Merge answer and the merge gate. Naming which targets are safe is the user's decision; an agent never adds an entry during a lease (script: setup changes deny further checks).

## The question gate (Claude Code)

One `PreToolUse` hook for the `AskUserQuestion` tool, in its own group, under the sixth scoped exception in `CLAUDE.md`. While a live
lease exists it denies that one call with one fixed message: the user is away, follow fnl-autopilot "Decide". It reads only whether
a valid, unexpired lease exists, through the same safe reader as `autopilot.py`; no lease, an expired, stopped or unreadable one, or any
error allows. It never reads the question, never denies another tool, a prompt, a session start or the user's own stop.
Starting the lease is the user's opt-in; `FNL_AWAY_GATE=off` disables it. It appends one ledger line (below) and sends nothing.
Codex and Antigravity have no such hook here and stay advisory. The first build step checks on the installed host that a hook fires for
that tool; if it does not, the gate is dropped and the report says so.

## Record for analysis

The owner reviews real use from the ledger, so one record covers every decision and `fnl-status` reads it.

- `autopilot.py log --kind decision` gains `--rung rule|jev|advisor|park`, `--by <rule, jev or the agent or install name>`, `--option <n> --of <m>`
  (`n` within `m`, absent for a park), `--probability` (rung 2), `--dispatch <ledger id>` (rung 3), `--model`, `--precedents <count>` and `--topic`, a short label under
  the ledger's task-label rule. It validates them and, in the same call, appends a `decision` line to the ledger with those fields, the
  time, the project and the lease's start time as the grouping key. The note stays in the autopilot log, capped, redacted and kept 30 days.
- The gate appends a `question_denied` line with the time and the lease's start time only.
- A rung that is tried and does not settle the question is recorded too (`--settled no`), so the path up the ladder can be rebuilt.
- On return, a `decision_review` line records `kept` or `reversed` for a decision by its time and lease, with no reason text.
- An away view of the ledger summary and the `fnl-status` tables show, per lease: decisions by rung, by advisor and model, the Jev probability
  spread, parked and denied questions, and the share reversed by the user. No question or option text is ever in the ledger; the topic label is the only words.

## Limits

- The gate stops the host asking the user; it does not make the host climb the ladder, which stays advisory, and whether the
  host applied the chosen option is not machine-checkable because options are free text. The ledger shows what was decided, not what was done.
- Probability is a judgment of fit among the options given, not proof the choice is right; a poorly framed question yields a
  confident wrong answer. The record lets the user review each decision on return.
- When the advisor's family wrote the work the decision concerns, the report says the opinion is from the same family.

## The rename

fnl-help is a new user-facing skill folder holding the content of `fnl-ask`; `fnl-ask` becomes a thin alias naming fnl-help as its
dependency. The description states in plain words that it answers questions about this plugin, not that it asks anyone. Counts, the map,
README and tests follow, as for `fnl-afk`.

## Open decisions

| Decision | Owner | What unblocks it |
| --- | --- | --- |
| Whether 0.8 is the right threshold for rung 2 | owner | the first real decisions in the log |
| Whether `fnl-advisor`'s committee is ever a rung for design decisions | owner | a preference |

## Evidence

None yet. A build needs a red test per behavior: the `log` fields and their refusals, the new judge site's schema and refusals, the gate (denies only with a live lease, allows on every error), the ledger `decision` and
`question_denied` lines being accepted by `ledger.load`, the `advisor` role and the single-agent rule, the tier and family rule, the packet caps and pattern drops, the zero-precedent record, the environment classification and its fail-closed default, the consent refusal, the choose mode's output contract, the lease line in `session_start.py` present and absent, and the alias and counts of the rename.
