# Release 0.3.0: scope

Status: accepted; release prepared on branch release/0.2.7 for 2026-11-15, not yet tagged; pull request 290 merges before the release pull request, and a real upgrade from 0.2.6 on a user's machine remains unverified.

## What shipped

| Pull request | Change |
| --- | --- |
| 276 | Spec `afk-per-project.md`: per-repository limits, categories and deploy targets, the evaluation table before the deciders, and no stops beyond setup. |
| 277 | afk limits are counted per repository, and a repository may set its own runs, runtime minutes and actions an hour. Breaking for away loops: a lease started before the update reads as invalid; start it again. |
| 278 | An away lease may post reviews through `post_review.py` and edit an approved Markdown skill repository on a work branch. |
| 279 | Spec `matrix-models.md`: models per kind of work in the assignment matrix. |
| 280 | Ledger fixes from the dispatch data review: `finish --retro`, cancelled and late records kept out of the medians, refused `finish` values, unique dispatch ids and a fixed log refusal line. |
| 281 | afk decisions take an evaluation table (Jev or the host's small model) before the deciders. Breaking for away flows: the `away-decision` site is removed and the ledger logs rung `table`. |
| 282 | `merge_check.py --independent --fallback-family` lets a lease merge on same-family reviews when every other family is out of quota. |
| 283 | A repository may decide its own away categories, non-production targets and production deploys. Breaking for away flows: the strict and no-repository states stop every category, and `gh release create` needs `--repo`. |
| 284 | The afk mechanism diagram, and the evaluation table in the away decision diagram. |
| 285 | `models` rules in the assignment matrix, `route_pick.py --kind`, `review_route.py --level` and per-pool quota. |
| 286 | `git switch -c` or `git checkout -b` creates an own work branch under a lease. |
| 287 | A repository may list `test-commands` and `top-level-files` that a lease may run or edit. |
| 288 | `afk.py start` prints a `This folder` line and `afk.py effective` a `rules` field with the repository's rules; setup offers the saved values. |
| 289 | The advisor rung accepts only frontier or strong models from `ADVISOR_MODELS`; a moved host program needs `/setup add quota` again; schema refusals name the flag. Breaking for away flows: a new model name is denied until the table lists it. |
| 290 | `release-targets`: tags, releases and publishing run under a lease only when the exact command is listed; the four afk lists default from `## afk` and a repository's list replaces it whole; the same-family fallback accepts two different models for enforcer and instruction changes. Breaking for away flows: an unlisted tag or publish now parks. |

The changelog's 0.3.0 section holds the user-facing wording; `update` carries the 0.3.0 upgrade notes. The away-decision sequence diagram was redrawn for the four-rung ladder, the rules per repository and the listed commands (PNGs now 2560x2096).

## Owner decisions

- 14/11/2026 and 15/11/2026: the afk per-project decisions 1 to 11 in `afk-per-project.md`, and models per kind of work in `matrix-models.md`.
- 15/11/2026: this release is a MINOR, 0.3.0, not 0.2.7, because several away-flow changes break consumers (`versioning`: in phase 0, MINOR for breaking changes). This supersedes the 0.2.5 and 0.2.6 precedent of releasing breaking entries as a PATCH. `## Agent levels` and the `verification` alias still ship in 0.3.0; a later release removes them.

## Breaking changes and the upgrade

- Away loops: a lease started before the update, or one live when a list in `## afk` changes, reads as changed setup; start it again with `/afk` (`0.3.0/afk-lease-restart`, `0.3.0/afk-account-lists`).
- Away flows: outside a repository and in the strict state every category stops; `gh release create` needs `--repo github.com/OWNER/NAME`; tags, releases and publishing need a listed release target (`0.3.0/afk-release-targets`, run `/setup add afk`); tests and top-level files need listing (`0.3.0/afk-test-commands`).
- Decisions: `afk.py log --kind decision` takes rung `table` instead of `jev` (`0.3.0/afk-table`).
- Advisor: only models the table lists run; after an update that moves a host program, run `/setup add quota` (`0.3.0/advisor-repin`).

## Known follow-ups

- `git commit` on the local default branch is still Tier 1 under a lease (out of scope of pull request 286; a separate decision).
- Live-host behaviour of the per-repository rules, the evaluation table and the models rules remains unverified.
- `## Agent levels` and the `verification` alias wait for a later release to remove them.
