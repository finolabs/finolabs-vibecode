# Models per kind of work in the assignment matrix

Status: accepted; owner decision 14/11/2026; for 0.2.7, one pull request after the afk-per-project series; no code has landed yet.

This document extends [assignment-matrix.md](assignment-matrix.md) ("The section", "Routing query"). Where they disagree, this document wins.

## Why

The matrix gives each agent one model for all its work. On 14/11/2026 Antigravity offers three families of models with different strengths, and the owner wants each used for its own work. Today that preference can only be written as prose in the host config, which no script reads.

## Owner decisions (14/11/2026)

1. Antigravity models by work:
   - `gemini-4-hydrogen-*`: design and media work at level 4 or above;
   - `gemini-4-argon-*`: code at level 4 or above;
   - `gemini-3.8-flash-*`: work at levels 3 to 4, code reviews included;
   - security reviews: `gemini-4-argon-high` first, `gemini-3.8-flash-high` only when Argon is out of quota.
2. The matrix carries these rules, so routing prints the model for each dispatch.
3. Ship it in the next release after 0.2.6 (0.2.6 is already published).

## The field

An agent line may add one `models` field after `model`:

```
- <agent>: levels L-H[; works on <type>, ...][; model <id>][; models <rule> | <rule> ...][; roles <role>, ...]
<rule> = <id>[ then <id>] for <selector>[, <selector>]...
<selector> = <kind> | <type> | levels L-H
<kind> = implement | review | security-review | advise
```

Example (the owner's rules):

```
- antigravity: levels 1-5; works on image-generation, transcription; models gemini-4-argon-high then gemini-3.8-flash-high for security-review | gemini-4-hydrogen-high for design, video, three-d, image-generation, levels 4-5 | gemini-4-argon-high for implement, levels 4-5 | gemini-3.8-flash-high for levels 3-4 | gemini-3.8-flash-high for review; roles navigator
```

- Rules are read in order and the first rule whose selectors all match the dispatch wins. Selectors of different sorts in one rule must all match (`implement, levels 4-5` = implement at level 4 or 5); several selectors of the same sort match any of them (`design, video` = either type).
- `then` names a fallback used only when the first model's cached quota reading says it is out of quota; at most one fallback per rule.
- No rule matches: the line's `model`, else the agent's default.
- At most 8 rules per line; each id follows the existing model rule (letters, digits, dot and dash, at most 64); a kind, type or level outside the closed lists is a parse problem shown by `show`, and the line keeps its other fields.
- A model not among the allowed models of `## Agents on this machine` is shown as unverified, as today.

## Routing

- `route_pick.py pick` gains `--kind implement|review|security-review|advise` (default `implement`) and prints each surviving agent with the model the rules choose: `<agent> <model>` or `<agent> default`, plus `(fallback: quota)` when `then` applied.
- `review_route.py` passes `review` or `security-review` as the kind when it reads the matrix for a review family.
- `ledger.py start --model` records the printed model; the coordinator passes it unchanged (advisory, agent judgment).
- Enforcer: `assignments.py` for the grammar, `route_pick.py` for the choice (script); using the printed model is advisory (agent judgment).

## Setup

`/setup add delegation` asks, per agent, after the model question: "Should <agent> use different models for different kinds of work?" With yes, it asks for each rule in plain words (which model, for which kinds, types or levels, and a fallback when out of quota), reads them back as the line above and writes them with the existing digest-bound yes. It never fills in rules the user did not give.

## Acceptance

1. The owner's example parses; `show` renders it unchanged (test).
2. `route_pick.py pick --kind security-review --level 3` picks `gemini-4-argon-high`, and `gemini-3.8-flash-high` with `(fallback: quota)` when Argon's cached reading is out of quota (test).
3. `--kind implement --level 4` gives Argon; `--type design --level 4` gives Hydrogen; `--kind review --level 2` gives Flash; level 2 implement with no matching rule gives the line's `model` or `default` (tests).
4. A bad kind, type, level range, ninth rule or second `then` is a parse problem and keeps the other fields (tests).
5. `/setup add delegation` asks the new question and its read-back matches the written line (test of the reference text).
6. `docs/specs/assignment-matrix.md` points here; `help`'s map and `CHANGELOG.md` describe the field.

## Open

- Whether other families (Claude, Codex) need the same rules now; the grammar allows it on any line.
- Hydrogen is read as design and media work at level 4 or above (the owner's words also allow "any work at level 4 or above", which would overlap Argon for code); owner to confirm.
