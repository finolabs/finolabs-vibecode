# Models per kind of work in the assignment matrix

Status: accepted; owner decisions 14/11/2026 (review round 1 addressed); for 0.2.7, one pull request after the afk-per-project series; no code has landed yet.

This document extends [assignment-matrix.md](assignment-matrix.md) ("The section", "Routing query"). Where they disagree, this document wins.

## Why

The matrix gives each agent one model for all its work. On 14/11/2026 Antigravity offers three families of models with different strengths, and the owner wants each used for its own work. Today that preference can only be written as prose in the host config, which no script reads.

## Owner decisions (14/11/2026)

1. Antigravity models by work:
   - `gemini-4-hydrogen-*`: design and video work at level 4 or above, first choice there although it also codes well;
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
<kind> = implement | code-review | security-review | navigator | advisor
```

The kinds are the matrix's role names (`assignments.py` `ROLES`) plus `implement`, so a rule and a role use the same word.

Example (the owner's rules):

```
- antigravity: levels 1-5; works on design, video, image-generation, transcription; models gemini-4-argon-high then gemini-3.8-flash-high for security-review | gemini-4-hydrogen-high for design, video, three-d, image-generation, levels 4-5 | gemini-4-argon-high for implement, levels 4-5 | gemini-3.8-flash-high for code-review | gemini-3.8-flash-high for levels 3-4; roles security-review, navigator
```

- Rules are read in order and the first rule whose selectors all match the dispatch wins. Selectors of different sorts in one rule must all match (`implement, levels 4-5` = implement at level 4 or 5); several selectors of the same sort match any of them (`design, video` = either type). A rule with a type selector never matches a dispatch that has no type.
- `models` only chooses among the agent's own models; it never makes an agent a candidate. Which agents are candidates stays with `works on` (types), `levels` and `roles`, as today.
- No rule matches: the line's `model`, else the agent's default.
- At most 8 rules per line; each id follows the existing model rule (letters, digits, dot and dash, at most 64); at most one `then` per rule.
- A kind, type or level range outside the closed lists, a ninth rule or a second `then` is a parse problem like any other: the matrix is invalid as a whole, as [assignment-matrix.md](assignment-matrix.md) "Reading and migration" says (roles and judge unset, `show` and `checkup.py` give the reason). There is no partly valid line.
- `assignments.py render` writes the field back in the same form, so a parsed line renders unchanged; `matrix_setup.py show` lists the rules under the agent's row, one per line, in order.
- A model not among the allowed models of `## Agents on this machine` is shown as unverified, as today.

## Quota and the fallback

`then` names a fallback used only when the first model's pool is out of quota in the cached reading.

- Pools come from the cached Antigravity reading (`quota_probe.py` `parse_agy`): an id starting `gemini-4-argon-` reads the `argon` pool, any other `gemini-` id the `gemini` pool, a `claude-` or `gpt-` id the `claude-gpt` pool. A pool is out of quota by the rule `review_route.py` `blocked_families` uses today (under 10% remaining with a reset still ahead, reading at most 8 hours old); a missing or stale reading is unverified and keeps the first model.
- Other families have one reading for the whole install, so `then` on their lines never applies (the agent is dropped as out of quota instead); `show` notes this.
- An Antigravity line with `models` rules is out of quota as a whole only when every pool its rules and `model` name is out of quota; one depleted pool no longer drops it. `review_route.py` `blocked_families` applies the same reading to Antigravity when the matrix gives it `models` rules, and is unchanged otherwise.

## Routing

- `route_pick.py pick` gains `--kind` (the closed list above, default `implement`), and `--type` becomes optional: with a type, the candidates are the agents that work on it, as today; without one, every agent line is a candidate, then filtered by level, reach, quota and author as today. With `--kind code-review`, `security-review`, `navigator` or `advisor`, only the agents whose `roles` name that kind are candidates.
- Each survivor prints as `<agent> <model>` or `<agent> default`, with one more word, `quota-fallback`, when `then` applied. The model is always the second word, and `ledger.py start --model` gets only that word; a `quota-fallback` dispatch says so in its `ledger.py finish --note` (advisory, agent judgment: the coordinator passes it unchanged).
- Reviews: `review_route.py` still chooses the family and form, unchanged apart from the quota reading above. To choose the model, the coordinator then runs `route_pick.py pick --kind code-review` or `--kind security-review` with the level and reads the line of the chosen family (advisory, agent judgment).
- Enforcer: `assignments.py` for the grammar, `route_pick.py` for the choice (script); using the printed model is advisory (agent judgment).

## Setup

`/setup add delegation` asks, per agent, after the model question: "Should <agent> use different models for different kinds of work?" With yes, it asks for each rule in plain words (which model, for which kinds, types or levels, and a fallback when out of quota), reads them back as the line above and writes them with the existing digest-bound yes. It never fills in rules the user did not give.

## Acceptance

1. The owner's example parses, and `assignments.py render` writes it back unchanged; `matrix_setup.py show` lists its five rules in order (tests).
2. `route_pick.py pick --kind security-review --level 3` prints `antigravity gemini-4-argon-high`, and `antigravity gemini-3.8-flash-high quota-fallback` when the cached `argon` pool is out of quota while `gemini` is not (tests).
3. `--kind implement --level 4` gives Argon; `--type design --level 4` gives Hydrogen; `--kind code-review --level 2` gives Flash; `--level 2` with no type and no matching rule gives the line's `model` or `default`; `pick` without `--type` runs (tests).
4. A bad kind, type, level range, ninth rule or second `then` makes the matrix invalid with that reason (tests).
5. With `models` rules on the Antigravity line, a depleted `argon` pool alone leaves Antigravity routable in `review_route.py` and `route_pick.py`; without rules, behavior is unchanged (tests).
6. `/setup add delegation` asks the new question and its read-back matches the written line (test of the reference text).
7. `docs/specs/assignment-matrix.md` points here; `help`'s map and `CHANGELOG.md` describe the field.

## Open

- Whether other families (Claude, Codex) need the same rules now; the grammar allows it on any line.

## Settled

- Hydrogen (owner, 14/11/2026): design and video work first, at level 4 or above; it codes well, but code at level 4 or above goes to Argon.
