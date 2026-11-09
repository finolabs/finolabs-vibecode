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

## The ladder

While a lease is active, a decision the agent would otherwise ask the user goes up this ladder and stops at the first
rung that settles it. Each rung is cheaper than the next.

1. **A recorded rule.** The user's own instructions, the assignment matrix or the task's brief already settle it (agent
   judgment, advisory).
2. **Jev**, when the choice is among closed options and `judge: jev` is set: one call of a new `judge.py` site,
   `away-decision`, with the question, two to six options and the evidence the question needs. It settles the choice when the top option's
   probability is at least 0.8, a starting threshold that the first real uses must validate; below that, the next rung.
3. **The advisor**, the agent the matrix names in the new role `advisor`: `fnl-advisor` in its choose mode, one read-only
   run that must return exactly one of the options with its reason, or `none`. It is an ordinary dispatch (ledger kind
   `advise`) and counts against the lease's run limit.
4. **Park.** No rung settled it, or no judge or advisor is available: log it as parked, tell the user once, and go on with
   other work.

Inside a lease the answer of a rung is the decision, not advice: the host applies the option it returned and does not
re-ask, overrule or shop it to another rung (advisory, agent judgment; the `log --by` record shows who decided). If the host
finds a fact the rung did not have, it parks the question rather than overruling. A named advisor that is out of quota or
unreachable, or that answers `none`, counts as unavailable, and the question parks. `fnl-advisor`'s line "you stay the
decider" stays true for its open mode, with the user present; the choose mode states the opposite for a lease.

Tier 3 never enters the ladder. `autopilot.py check` still classifies the resulting action, so a choice made here
grants no authority: an option the check denies is parked. The rungs choose among options the agent already may take.

## What enforces what

- `autopilot.py` stays a script with no execution and no network call, so it cannot run the ladder itself: a single command
  that called Jev or started an agent would break its contract. The ladder is a procedure in `fnl-autopilot`
  (`references/decide.md`), advisory (agent judgment).
- The record is script-enforced: `autopilot.py log --kind decision` gains `--by rule|jev|<agent name>` and `--option <n>
  --of <m>`, validated (closed values, `n` within `m`) and stored without any option text. The note stays capped and redacted as today.
- `judge.py` enforces the new site's closed schema and byte caps, as for the other sites. The new site changes the closed
  list in the fourth scoped exception of `CLAUDE.md` and the Judge text of `PRIVACY.md`; those amendments merge before its code.
- `assignments.py` adds `advisor` to its roles, one agent at most. With no advisor named, rung 3 is skipped; `fnl-advisor`
  run by hand still picks by contrast as it does today, and the named agent takes precedence only when the user names none.
- While a lease is active, `session_start.py` prints one fixed line, after a compaction or resume as well: `Away mandate active:
  do not ask the user; follow fnl-autopilot "Decide"`. It reads only whether a live lease exists and prints no content.
  The skill says the same when the lease starts. The skill and that line replace the question tool for the lease
  (advisory, agent judgment).

## Limits

- Nothing blocks the question tool. A hook that denies it during a lease would be a new scoped exception to the hook rule,
  which only the owner can grant, and whether the host allows a hook on that tool is unverified. It is left out.
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
| Whether a hook should deny the question tool during a lease | owner | a new scoped exception, after checking the host allows it |
| Whether 0.8 is the right threshold for rung 2 | owner | the first real decisions in the log |
| Whether `fnl-advisor`'s committee is ever a rung for design decisions | owner | a preference |

## Evidence

None yet. A build needs a red test per behavior: the `log` fields and their refusals, the new judge site's schema and refusals, the `advisor`
role and the single-agent rule, the choose mode's output contract, the lease line in `session_start.py` present and absent, and the alias and counts of the rename.
