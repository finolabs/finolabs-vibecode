# Release 0.3.2: scope

Status: released; tagged v0.3.2 on 2026-11-17; live delivery of the afk check hook, the proof nudge and the merge notice rename reminder on a user's machine, and a real upgrade from 0.3.1, remain unverified.

## What shipped

| Pull request | Change |
| --- | --- |
| 317 | `main` moves to `0.3.2-dev`; v0.3.1 recorded as released. |
| 318 | The 22 `fnl-` skill aliases are removed; the agents are `reviewer`, `security-reviewer` and `navigator`. |
| 319 | The afk overlay rule, the ninth scoped exception in `CLAUDE.md`, with `PRIVACY.md` and the spec. |
| 320 | Questions follow the user's language: the session-start rule, `setup`, `afk` and `review-gate`. |
| 321 | The afk autonomy spec: `open` mode allows everything under a lease except credentials. |
| 322 | afk `open` mode (the default) with the credential floor and the default-branch guard; `strict` keeps the earlier rules. |
| 323 | `merge_check.py --fallback-family` accepts same-family markers with the fallback line under an `open` lease. |
| 324 | The afk overlay: `AGENTS.afk.md`, written by `instructions_write.py`, printed while a lease is live. |
| 325 | `/setup add afk` asks the mode first; `afk.py rules` generates the rule table in `skills/afk/references/rules.md`. |
| 326 | LOW findings of the overlay pull request. |
| 327 | README warning about running other agents' CLIs headless under your own accounts. |
| 328 | `/setup add delegation` picks helpers from one multiple-choice question and one picker per role; `matrix_setup.py choices`. |
| 329 | LOW findings of the rule table pull request. |
| 330 | afk and merge check LOW findings: a bare `env` in a search pattern floors; the overlay writer and `merge_check.py` fail closed on an unknown `## afk` key; NFKC reviewer names. |
| 331 | This release: the drift review below, upgrade notes, re-rendered afk diagrams, changelog and manifests. |
| 332 | Remaining 0.3.2 fixes: afk `check` reads `--author-email` on a pinned merge; a bare `export` or `set` after a lone `|` floors; `merge_check.py` refuses non-ASCII reviewer names under `open`; reviews route to ZCode; the security relay holds under an `open` lease. |
| 333 | Long skill sections load only when needed (`references/` disclosure). |
| 334 | The session-start text carries the proof rule and the session title format, scoped to this project. |
| 335 | `advisor` routes through the assignment matrix; shorter skill descriptions. |
| 336 | The afk check hook rule, the tenth scoped exception in `CLAUDE.md`, with `PRIVACY.md` and the spec. |
| 337 | The router judge step is removed; `## Instruction check` gets its own section; `Rework limit` under `## Reviews`. |
| 338 | The proof nudge (`Stop` reminder after an unverified commit) and the recorded same-family security fallback. |
| 339 | `/setup add compaction` recommends an auto-compact threshold and can write it for one repository (`compact_setup.py --project`). |
| 340 | `tidy` hands the user a ready `/compact <focus>` command (bare `/compact` on Codex, `/new` or `/fork` on Antigravity). |
| 341 | The afk check hook on Claude Code: a syntax allowlist that judges each Bash command as `afk.py check` does under a lease. |
| 342 | This record: rows 332 to 342, the second drift review below, upgrade notes for 336 to 341, and `merge_check.py --independent` counting ZCode reviews. |

The changelog's 0.3.2 section holds the user-facing wording; `update` carries the 0.3.2 upgrade notes. The afk-mechanism and away-decision-sequence PNGs were re-rendered (2530 pixels wide) through the shared Chromium.

## Drift review

Every item in the table below was checked against what ships at the release branch's base, `e1c8892`; `CLAUDE.md` and the `skills/*/SKILL.md` bodies were sampled only (old names, afk Merge wording). Review round 1 on pull request 331 then narrowed the wording: the third-party-instructions guard is marked advisory wherever it is listed with the enforced default-branch guard; the comparison page, the README, the help and the diagrams say that in `open` afk enforces neither reviews nor `merge_check.py`, that the default-branch guard covers `git commit` and `git push` only (not `gh pr merge` or `gh api` ref writes), and that only server-side branch protection or a required `merge_check.py --ci-context` status gates a merge, while the decision ladder, the merge-gate procedure and the kept-or-reversed review apply in both modes as advisory steps; the overlay is protected only in `strict`; the credential floor covers known forms (see `afk.py rules`).

| Item | Result |
| --- | --- |
| `CHANGELOG.md` Unreleased | Matches the merged pull requests; moved to 0.3.2, with one entry added for this pull request's docs and diagram changes. |
| README skill table, `afk` row | Drifted: no modes, credential floor or guards. Added them and the mode question; the help map row matches. |
| README setup feature table, `afk` row | Drifted: did not ask the mode first. Added the mode and what `open` asks. |
| README setup feature table, `delegation` row | Drifted: no helper question or role pickers. Added. |
| README skill-name paragraph | Already says the `fnl-` names were removed in 0.3.2; no change. |
| README "Supported agents" warning | Present (PR 327); no change. |
| README metrics paragraph | Drifted: "`fnl-` agents". Now "agents". |
| README file layout | Added `skills/afk/references/rules.md`. |
| README release section and documented-release line | Added the 0.3.2 section; the line now names 0.3.2 and `0.3.3-dev`. |
| README diagram alt text (afk mechanism, away decision sequence) | Drifted with the diagrams; each now says it shows `strict` and what `open` does. |
| `docs/diagrams/afk-mechanism-*.html`, `away-decision-sequence-*.html` | Drifted: they showed only the `strict` rules as if they were the only rules. The subtitle and description say the page shows `strict` and what `open` does; the account setup box names the mode; credentials park in both modes. PNGs re-rendered. |
| Other diagrams (request to merge, delegation sequence, session health, settings scopes, skills architecture, task lifecycle) | Checked for old agent names and afk rules; none drifted. |
| `docs/how-it-compares.md` | Drifted: the merge row and the `afk` row described only `strict`. Both name the two modes. |
| `skills/help/references/map.md` | Drifted: `afk` row, task row for working away, `instructions_write.py` (overlay) and `afk_setup.py` (`--mode`). Updated. `afk.py`, `merge_check.py`, `afk_overlay.py` and `matrix_setup.py choices` rows were already current; agent names already new. |
| `skills/help/references/skills/afk.md` | Drifted: said setup records an explicit Merge answer. Now names the modes, `afk.py rules` and the overlay. |
| `skills/help/references/skills/setup.md` | Added the helper question and role pickers. |
| `PRIVACY.md` | Current: "afk lease and log" covers the modes, the floor and the guard reads; "afk overlay" covers `AGENTS.afk.md`. No change. |
| `skills/update/references/upgrades.json` | Had 0.3.2 entries for the removed names, the modes and the `open` fallback. Added the overlay note and Codex hook trust (`session_start.py` changed). |
| `docs/specs/index.md` | The afk autonomy row said `accepted` while its spec says implemented; now `implemented`. Added this record's row. |
| Historical specs (`agent-roles.md` and earlier release records) | Still name `fnl-reviewer` and the other old names as history; left unchanged on purpose. |

### Second drift review (pull request 342)

Checked against `main` at `33fd133` (after pull request 341) for what 332 to 341 added.

| Item | Result |
| --- | --- |
| README release 0.3.2 section | Drifted: no afk check hook, proof nudge, compaction threshold, `/compact` line, review and routing changes or leaner skills. Added five bullets. |
| README skill table, `afk` row | Drifted: did not say a hook judges each command on Claude Code. Added. |
| `skills/help/references/skills/afk.md` | Drifted: no afk check hook. Added one sentence. |
| `skills/help/references/map.md` | `afk_check_hook.py`, `proof_nudge.py` and `compact_setup.py --project` rows current (the hook row was corrected in 341). |
| `skills/update/references/upgrades.json` | Added `0.3.2/afk-check-hook`, `0.3.2/proof-nudge`, `0.3.2/compaction-threshold` (`/setup add compaction`) and `0.3.2/security-fallback` (`/setup add roles`). Codex hooks did not change after 334, so `0.3.2/codex-hook-trust` stands. |
| `PRIVACY.md` | Current: "Proof nudge" and "afk check hook" sections landed with their rule pull requests. |
| `docs/specs/index.md` | Current: afk check hook, proof nudge and compaction threshold rows say implemented. |
| `CHANGELOG.md` 0.3.2 | Current: each of 332 to 341 added its entry. |
| Diagrams | The afk mechanism diagram still shows the agent calling `check`; on Claude Code the hook now calls it for Bash. Left unchanged for 0.3.2 (the call and its rules are the same); noted here. |
| `docs/diagrams/task-lifecycle-*.html` and the README alt text | Drifted with the rework limit (337): said "max 2 rounds". Now the Rework limit, two by default; the PNGs were not re-rendered and still show the default. |
| `skills/help/references/skills/advisor.md` | Drifted with 335: gave the configured advisor role unconditional precedence. Now only when it is of another family, as `advisor` says. |
| `merge_check.py --independent` | Defect found by this review: the family check left out `zcode`, so ZCode reviews (332) could not pass. Fixed here with a regression test. |
| README and upgrade note for compaction | Now say the repository threshold and the ready `/compact <focus>` are Claude Code, a bare `/compact` on Codex and `/new` or `/fork` on Antigravity. |

## Owner decisions

- 16/11/2026: ship the three breaking changes (the `fnl-` aliases removed, the agents renamed, afk `open` as the default) as 0.3.2, a patch, because the shipped text, upgrade notes and tests already name 0.3.2. This overrides `versioning`, which asks for a MINOR bump for a breaking change in phase 0, and applies to 0.3.2 only; the changelog marks the entries Breaking and the upgrade notes say what to do.
- 16/11/2026: remove the `fnl-` aliases and drop the prefix from the agents; afk `open` mode is the default, with the credential floor, the default-branch guard and the third-party-instructions guard; the afk overlay (see `CLAUDE.md`, the ninth scoped exception, and `docs/specs/afk-overlay.md`).
- 17/11/2026: reviews of 333 to 341 went to the claudework install (headless Claude Code) and, once its quota ran out, the last rounds of 341 to Codex; the security review of 341 was relayed with the owner's approval for that pull request.
- 17/11/2026: the afk check hook (tenth scoped exception) is a syntax allowlist: false denials are accepted (the owner chose to block, then the syntax allowlist); the rule text is tighter than first approved.
- 17/11/2026: the auto-compact recommendation and the ready `/compact` command ship in 0.3.2; the setup bare-run budget moves from 15000 to 15050 bytes and the beginner threshold step gets a 16000-byte budget.
- 17/11/2026: reviews route to ZCode, headless in `plan` mode; the standing relay of a security review also holds under an `open` lease (the "Reviews" section of [CLAUDE.md](../../CLAUDE.md)).

## The upgrade

- Type the current skill and agent names; `/setup check` lists the old ones it finds (`0.3.2/fnl-aliases-removed`).
- afk now runs in `open` mode by default; add `- Mode: strict` to `## afk` to keep the earlier rules (`0.3.2/afk-modes`).
- Codex: trust the plugin's hooks again with `/hooks` after the refresh (`0.3.2/codex-hook-trust`).

## Known follow-ups

- Live delivery of the afk overlay on Claude Code and Codex hosts remains unverified.
- A real upgrade from 0.3.1 on a user's machine remains unverified.
- The `finolabs/plugins` catalog entry moves only with the owner's go after the tag.
