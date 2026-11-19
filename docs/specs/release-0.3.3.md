# Release 0.3.3: scope

Status: implemented; release prepared, not yet tagged.

## What shipped

| Pull request | Change |
| --- | --- |
| 345 | `main` moves to `0.3.3-dev`; v0.3.2 recorded as released. |
| 346 | A catalog pin (existing entries' `source.ref` moved to a release tag, and their descriptions) takes the low-risk lane; `merge_check.py --lane` decides. |
| 347 | Each release moves `ref` to the new tag in every host catalog that pins the plugin, Codex included (`versioning`, `update` hosts, `plugin-packaging` catalogs). |
| 348 | The live check of the Codex catalog pin: a refresh installed 0.3.2 from a `url` source pinned to `ref` v0.3.2 (codex-cli 0.169.0). |
| 349 | Compaction setup by session kind: the saved threshold serves task sessions, setup shows the `CLAUDE_CODE_AUTO_COMPACT_WINDOW=<tokens> claude` launch line for a coordinator, and `--clear-model-overrides` removes per-model values. |
| 350 | `select_tests.py` selects a module that declares `# select-tests: reads <folder>/`; the worktree sweep reads the user's global ignore file, so merged, clean worktrees are candidates again. |
| 351 | The per-model clause of the compaction nudge rule (eighth scoped exception in `CLAUDE.md`), with `PRIVACY.md` and the spec. |
| 352 | A split for an operator that ends a word in the afk check hook; removed with the hook in 360. |
| 353 | The compaction nudge follows the session model's `modelSettings.<model>.autoCompactWindow`; `compact_setup.py --model <id>` saves a threshold for one model. |
| 354 | The afk hook tokenizer spec (design only); deferred when the hook was removed, and its implementation, PR 358, closed unmerged. |
| 355 | `delegate` removes finished runs' merged, clean, pushed worktrees (`ledger.py start`, `finish`, `clean-worktrees`, and the merge notice); `FNL_WORKTREE_CLEAN=manual` or `off`. |
| 356 | Session titles: the agent names the session in its first turn whatever the task, and sessions it starts get the same format (`tidy`, the session-start rules). |
| 357 | The afk check hook read a wrapper name as a wrapper only where a command starts; removed with the hook in 360. |
| 359 | `coding-router`'s Spec Kit adapter covers `specify workflow` runs: the depth gate still decides, gate verdicts are the user's, and each agent step is a ledger dispatch. |
| 360 | The afk check hook is removed (owner decision, 18/11/2026); the tenth scoped exception becomes a removal record and the agent runs `afk.py check` itself on every host. |
| 361 | The afk decider spec: a stop hook, a permission hook, merge by the decider and native deny rules for the credential floor; owner decisions 1 to 6. |
| 362 | `/setup instructions` scans existing instruction files for lines that stop `afk` or `delegate` and proposes replacements; the contract template names the lease exception. |
| 363 | The afk decider on Claude Code: the afk stop hook (`Stop`), the afk permission hook (`PermissionRequest`, approvals by request digest), `merge: decide` per repository, `afk_native_rules.py`; the eleventh and twelfth scoped exceptions in `CLAUDE.md` and two `PRIVACY.md` sections. |
| 364 | The UI review gate spec (`docs/specs/ui-review-gate.md`); no code. |
| 365 | `/setup add quota --weekly-floor <family>/<label>=<percent>`: routing treats that install's weekly pools below the floor as out of quota. |
| 366 | The UI review gate (`ui-review-gate`) skill, implementing docs/specs/ui-review-gate.md: four modes on WCAG 2.2 AA, read-only measurement snippets, report-only and advisory; seven Codex review rounds on the target-size inline exception. |
| 367 | The inline target check skips hidden elements (last LOW finding of 366). |
| 373 | afk has one mode (owner decisions 1 to 4, 19/11/2026; `docs/specs/afk-one-mode.md`): `strict`, its lists, categories, Merge answer and the per-repository limits are removed; `Lease hours` stays; old `Mode: strict` and limit lines start normally with one notice line each; the stop hook's limit escape is the lease end only; the fallback under a lease needs only the lease, the author's family and the fallback line. Pull request 370 (decision 5, the strict syntax allowlist) closed unmerged. |
| 377 | UI review marker, opt-in per repository (`ui-review-gate` decision 4, owner decision 19/11/2026): a base whose `## Agent skills` section names `ui-review-gate` makes the router marker carry `ui=yes` or `ui=no`, and `merge_check.py` requires a `kind=ui` review approving the head for `ui=yes`; `/setup` offers the UI line. |
| this | This release: the drift review below, the Codex hook trust note, the README release section, changelog and manifests. |

The changelog's 0.3.3 section holds the user-facing wording; `update` carries the 0.3.3 upgrade notes. Pull request 358 (the tokenizer implementation) closed unmerged and is not part of 0.3.3.

## Drift review

Checked against `main` at `b03334c` (after pull request 365), surface by surface, for every merged pull request from 345 to 365. `CLAUDE.md` was read, not edited. Pull request 366 merged after the first pass; its own pull request updated the README skill table and companions, the skill count in the three manifests, its help page, the help map and tips, the upgrade notes and the changelog. Checked again at `a863cce` for 366: the release section below names it; `how-it-compares.md` names no individual gate, so it was left unchanged; the `skills-architecture` diagram drifted (its gates box named only `security-review-gate`, its description said 0.3.2): the box now reads `security-review-gate · ui-review-gate` and the PNGs were re-rendered.

| Surface | Result |
| --- | --- |
| README skill table, `afk` row | Current: no Bash hook, the stop and permission hooks (363). |
| README skill table, `coding-router` row | Drifted with 359: no `specify workflow` runs. Added that the depth gate governs them. |
| README skill table, `delegate` row | Drifted with 355: did not say finished runs' worktrees are removed. Added, with `FNL_WORKTREE_CLEAN`. |
| README skill table, `setup` row | Drifted with 362: `instructions` did not list conflicting lines first. Added. |
| README skill table, `tidy`, `commit-messages`, `review-gate`, `versioning` rows | Current: the title rule (356), the sweep (350), the catalog lane (346) and the catalog pin (347) are below the level of these rows. |
| README setup feature table, `afk` row | Current: native deny rules and the repository `merge: decide` question (363). |
| README setup feature table, `quota` row | Drifted with 365: no weekly floor. Added. |
| README setup feature table, `compaction` row | Drifted with 349 and 353: no per-model threshold or coordinator launch line. Added. |
| README compaction nudge paragraph | Drifted with 353: said the nudge reads only token counts and settings. Now names the model id, in memory only, on Claude Code. |
| README install section and host table | Current: the catalog pin (347) and the merge notice cleanup (355). |
| README file layout | Current: `hooks.json` lists the afk stop and permission hooks. |
| README release section and documented-release line | Added the 0.3.3 section; the line now names 0.3.3 and `0.3.4-dev`. |
| README diagram alt text | Current: afk mechanism (360, 363), session health (356). The away decision sequence alt shows a question's path, which the decider hooks do not change. |
| `skills/help/references/skills/afk.md` | Current (360, 363). |
| `skills/help/references/skills/setup.md` | Drifted with 365: no weekly floor. Added a tip. Compaction (349, 353) and instructions (362) current. |
| `skills/help/references/skills/tidy.md` | Current (349, 353, 356). |
| `skills/help/references/skills/delegate.md` | Current (355). |
| `skills/help/references/skills/coding-router.md` | Current (359). |
| `skills/help/references/skills/review-gate.md`, `update.md` | Current (346, 347). |
| `skills/help/references/skills/versioning.md`, `plugin-packaging.md`, `checks.md`, `commit-messages.md` | Current: their tips do not describe catalog pins, the `select-tests` marker or the sweep's ignore file. |
| `skills/help/references/map.md` | Drifted: the `compact_setup.py` row had no `--model` or `--clear-model-overrides` (349, 353); the `quota_probe.py`, `review_route.py` and `quota_setup.py` rows had no weekly floor (365). Updated. The afk hook, `afk_native_rules.py`, `ledger.py`, `merge_notice_hook.py` and `select_tests.py` rows were current. |
| `skills/help/references/tips.md` | Current (355). |
| `skills/help/references/troubleshooting.md` | Current: the check hook row replaced by the stop, permission and native-rule rows (360, 363). |
| `skills/setup/references/check.md` | Drifted with 355: the list of hooks that run automatically left out the merge notice, which now starts the worktree cleanup. Added. The decider hooks (363) and the weekly floor (365) were current. |
| `skills/update/references/upgrades.json` | Had 0.3.3 notes for 349, 353, 355, 360, 362, 363 and 365. Missing: Codex hook trust, though `scripts/compact_nudge.py`, which the Codex manifest runs, changed (353) while `.codex-plugin/hooks.json` did not. Added `0.3.3/codex-hook-trust`. |
| `PRIVACY.md` | Current: "Compaction nudge" (351), "afk check hook" as a removal record (360), "afk stop hook" and "afk permission hook" (363), `afk_native_rules.py` and the worktree cleanup. Drifted with 365: "Quota probe" did not list the weekly floor line in `## Quota probe`. Added. |
| `docs/how-it-compares.md` | Drifted with 363: the merge row did not name `merge: decide`, and the `afk` row did not say blocking is the host's or name the stop and permission hooks and native deny rules. Updated. |
| `docs/diagrams/afk-mechanism-*.html` | Current: updated in 360 and 363; the PNGs were re-rendered. |
| `docs/diagrams/delegation-sequence-*.html` | Drifted with 355: step 17, the subtitle and the description said the coordinator removes the worktree. They now say `ledger.py` removes the merged, clean worktree in the background. PNGs re-rendered through the shared Chromium. |
| `docs/diagrams/session-health-*.html` | Current: updated in 356; the PNGs were re-rendered. |
| Other diagrams (away decision sequence, request to merge, settings scopes, skills architecture, task lifecycle) | Checked for the check hook, worktree cleanup, merge authority and titles; none drifted. |
| `docs/specs/index.md` | The afk decider row said decision 5 was open; now parked on 19/11/2026 and left out of 0.3.3, as the spec's Status line now says. Added this record's row. |
| `CHANGELOG.md` | Unreleased matched the merged pull requests; moved to 0.3.3 with one entry for this pull request's docs changes. |

## Owner decisions

- 17/11/2026: a catalog pin takes the low-risk lane (346).
- 17/11/2026: compaction setup by session kind: the saved threshold serves task sessions, a coordinator gets a launch line with the variable, not `--autocompact`, and a hook that recognizes a coordinator is dropped (349).
- 17/11/2026: the UI review gate lives in vibecode as `ui-review-gate`, with WCAG 2.2 AA as its standard (spec decisions 1 to 3).
- 18/11/2026: follow Claude Code's per-model compaction threshold; the nudge may read the model id (351, 353).
- 18/11/2026: remove the afk check hook; blocking is the native harness's job (360). The seven tokenizer decisions settled the same day lapsed with it.
- 18/11/2026, afk decider ([spec](afk-decider.md)):
  1. the stop hook, a new scoped exception that may block an agent's stop once in a row under a lease (the eleventh);
  2. the permission hook, allowing only exact recorded approvals under a lease (the twelfth);
  3. merge authority: the lease's Merge answer or `open` mode, plus an optional per-repository `merge: decide` record with its own consent question;
  4. self-protection: a pull request changing the lease, setup, hooks or instruction files merges like any other when `MERGE OK` holds (the alternative taken);
  5. `check` keeps accounting, approvals and "Where it must stop" and drops its syntax allowlist and general argv classification. Parked on 19/11/2026 and left out of 0.3.3, because it redefines `strict` mode and the rules a live lease runs on;
  6. `setup` offers native deny rules for the credential floor; `afk start` warns when the host has none.
- 18/11/2026: the UI review gate is advisory in 0.3.3 (no `merge_check.py` change), runs read-only measurement snippets, adds axe-core only when the repository declares it or the user agrees, blocks below 24 px target size, reports only by default, and targets 0.3.3 (spec decisions 4 to 7).
- 19/11/2026: routing stops using an install below a weekly floor, starting with the `claudework` install at 85% of its week used (365).

## The upgrade

- Claude Code: the afk check hook is gone and `FNL_AFK_HOOK` does nothing; under a lease the agent runs `afk.py check` itself and the host's permissions block (`0.3.3/afk-check-hook-removed`).
- Claude Code: under a lease the afk stop hook and permission hook settle stops (`0.3.3/afk-decider-hooks`); `/setup add afk` can add native deny rules for the credential floor (`0.3.3/afk-native-rules`); afk has one mode, the limits are gone and an old lease needs `/afk stop`, then `/afk start` (`0.3.3/afk-one-mode`).
- Claude Code: open a coordinator with `CLAUDE_CODE_AUTO_COMPACT_WINDOW=<tokens> claude` (`0.3.3/coordinator-threshold`); the nudge follows the session model's `/autocompact` value, and setup can save a threshold for one model (`0.3.3/per-model-threshold`).
- `delegate` removes finished runs' merged worktrees in the background; runs started before 0.3.3 stay (`0.3.3/worktree-clean`).
- `/setup instructions` flags lines that stop `afk` or `delegate` (`0.3.3/instructions-conflict-scan`).
- `/setup add quota` can record a weekly floor per install (`0.3.3/quota-weekly-floor`).
- Codex: trust the plugin's hooks again with `/hooks` after the refresh; the compaction nudge script changed (`0.3.3/codex-hook-trust`).

## Known follow-ups

- afk decider decision 5 (drop `check`'s syntax allowlist and general argv classification) is superseded: `strict` is removed in this release (afk one mode, pull request 373), and pull request 370 closed unmerged.
- Live delivery of the afk stop and permission hooks on a user's machine remains unverified; the `Stop` and `PermissionRequest` schemas were checked against Claude Code 2.1.327 only.
- The new hooks load only in Claude Code sessions started after the update; a session open during the update keeps the old hook set.
- Codex: `.codex-plugin/hooks.json` did not change since v0.3.2, but `scripts/compact_nudge.py` did, so Codex asks to trust the hooks again; Codex and Antigravity have no stop or permission hook, so "Decide" stays advisory there.
- The `ui-review-gate` snippets ran only against a fake DOM in node; a run in a live browser remains unverified, and every inline target exception is marked uncertain for a check by eye.
- A real upgrade from 0.3.2 on a user's machine remains unverified.
- The `finolabs/plugins` catalog pins move only with the owner's go after the tag.
