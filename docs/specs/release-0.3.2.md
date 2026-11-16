# Release 0.3.2: scope

Status: accepted; prepared, to be tagged v0.3.2 after the owner's yes.

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

The changelog's 0.3.2 section holds the user-facing wording; `update` carries the 0.3.2 upgrade notes. The afk-mechanism and away-decision-sequence PNGs were re-rendered (2530 pixels wide) through the shared Chromium.

## Drift review

Every item that describes the product was checked against what ships at the release branch's base, `e1c8892`.

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

## Owner decisions

- 16/11/2026: ship the three breaking changes (the `fnl-` aliases removed, the agents renamed, afk `open` as the default) as 0.3.2, a patch, because the shipped text, upgrade notes and tests already name 0.3.2. This overrides `versioning`, which asks for a MINOR bump for a breaking change in phase 0, and applies to 0.3.2 only; the changelog marks the entries Breaking and the upgrade notes say what to do.
- 16/11/2026: remove the `fnl-` aliases and drop the prefix from the agents; afk `open` mode is the default, with the credential floor, the default-branch guard and the third-party-instructions guard; the afk overlay (see `CLAUDE.md`, the ninth scoped exception, and `docs/specs/afk-overlay.md`).

## The upgrade

- Type the current skill and agent names; `/setup check` lists the old ones it finds (`0.3.2/fnl-aliases-removed`).
- afk now runs in `open` mode by default; add `- Mode: strict` to `## afk` to keep the earlier rules (`0.3.2/afk-modes`).
- Codex: trust the plugin's hooks again with `/hooks` after the refresh (`0.3.2/codex-hook-trust`).

## Known follow-ups

- Live delivery of the afk overlay on Claude Code and Codex hosts remains unverified.
- A real upgrade from 0.3.1 on a user's machine remains unverified.
- The `finolabs/plugins` catalog entry moves only with the owner's go after the tag.
