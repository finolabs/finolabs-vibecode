# afk one mode: `strict` is removed

Status: implemented; owner decisions 19/11/2026; in 0.3.3.

This document changes [afk-autonomy.md](afk-autonomy.md), [afk-per-project.md](afk-per-project.md), [afk-decider.md](afk-decider.md) (its decision 5 is superseded), [afk-goals.md](afk-goals.md) and [afk-overlay.md](afk-overlay.md) wherever they describe `strict`, its lists, categories, limits or Merge answer. Where they disagree, this document wins from 0.3.3.

## Why

Owner, 19/11/2026: afk exists to be more autonomous than the host's auto mode. Blocking is the host's job: Claude Code auto mode and permission rules, the deny rules `afk_native_rules.py` offers in setup, Codex's sandbox and approval policy. A user who wants something forbidden while away writes a host deny rule. Keeping a second mode that re-implements blocking in `afk.py` doubled every afk surface and kept growing (pull request 370, the strict syntax allowlist of decision 5 of the afk decider, closed unmerged for this reason).

## Owner decisions (Fio, 19/11/2026)

1. afk has a single mode. `strict` is removed. afk exists to be more autonomous than the host's auto mode; blocking is the host's job (Claude Code auto mode and permission rules, `afk_native_rules.py` deny rules, Codex sandbox and approval policy). A user who wants something forbidden while away writes a host deny rule.
2. In 0.3.3.
3. A setup that still records `Mode: strict` (user scope `## afk` or a repository's `mode` key) runs as the single mode: `afk.py start` prints one fixed line saying `strict` was removed and the key is no longer read, then starts normally. Setup no longer asks the mode question and never writes the key.
4. The per-repository and account limits `Max runs`, `Max runtime minutes`, `Max actions per hour` (and the project keys `max-runs`, `max-runtime-minutes`, `max-actions-per-hour`) are removed; only `Lease hours` stays. Old lines and keys are ignored with the same kind of one-line notice (one combined line).

## What stays (the former `open`, unchanged)

- The lease: start, expiry, stop, the setup hash, one lease per machine; `Lease hours` (1 to 24) is its only limit.
- `check`: the credential floor (`floor`), the default-branch guard (`guarded`) when `Default branch: guard`, `unsafe` on a parser error, the ended codes with their `end` line, and Tier 1 `allowed` for everything else. `Third-party instructions: guard` stays advisory.
- A repository's approved, bound `third-party-instructions` and `default-branch` keys win there.
- `log`, Decide and its ladder, `review`, `effective`, `rules`, `packet-check` and the excerpt consent, `Hosts` and `Quota floor percent`.
- `--approve-request` and the afk permission hook; the away question gate.
- The afk stop hook, whose limit escape now means only that the lease lets no action run (it ended, its setup changed, or it has not started).
- The afk overlay, without its strict-only protections.
- The merge pin: an allowed `gh pr merge` check with `--match-head-commit` records its pin, and `log --kind merge --head` needs exactly one pin of this lease. As under `open` before, `check` does not answer `merge-unchecked`: the merge gate's `MERGE OK` is advisory under a lease. `merge_check.py --independent` still writes its receipt during a lease; nothing reads it now (kept so a later decision can gate on it again).
- The same-family review fallback as it worked under an `open` lease: under a live lease it needs only the lease, the author's family and, on each kind, the exact fallback reviewer line or a marker of a kind whose configured review role names another family. Outside a lease the recorded `Same-family security fallback: yes (date)` path keeps its quota evidence, the exact line and the two-model rule for enforcer and instruction-file changes.

## What goes

- The `Mode` setting and its setup question; the repository `mode` key.
- The strict classification in `afk.py`: the test, deploy (non-production and production) and release command lists, top-level files, known roots and paths, the protected hard and soft names, the `decide` and stop categories, the `Merge` answer and a repository's `merge: decide` (`merge_authority`), `Trusted authors`, `Task choice` and `Push and pull requests`, the ladder command forms `check` allowed, the work-tree, branch, worktree and merge rules, `merge-unchecked`, and the `decided` answer with `--approve-argv-json` and `--approve-paths`. `check --coordinator` is gone with them.
- The per-repository counters (`counters` in `lease.json`, `spent` and `limit` answers) and the three limits.
- The strict branch of the afk stop hook (repository limits).
- The overlay's strict-only protections: `instructions_write.py` refusing the overlay during a strict lease, and `check` protecting `AGENTS.afk.md*` and the Spec Kit constitution path.
- The strict conditions of `merge_check.py --fallback-family` under a lease (its `lease_mode` reading of `Mode` and the repository `mode`, the quota evidence, the router-trigger condition and the two-model rule) and the matching text of `review-gate`.

## Compatibility

- `afk.py settings` no longer reads `Mode`, the three limits or any other line only `strict` read; such a line is accepted and ignored, a repeated line still invalidates the section, and the setup hash covers only what is read. `start` prints `STRICT_REMOVED` once for `Mode: strict` and `LIMITS_REMOVED` once for any limit line, and one line each for a repository's `mode: strict` and limit keys.
- `afk_setup.py` writes only the guards, `Hosts`, `Lease hours`, `Quota floor percent` and the excerpt consent, and refuses every retired flag. `project_store.autopilot_value` (the repository writer behind `project_progress.py settings --set autopilot=`) refuses every key but `third-party-instructions` and `default-branch`; `valid_autopilot` still accepts an older approved object, so that file keeps its other settings.
- `away_lease.read_lease` no longer accepts `counters`: a lease written before 0.3.3 reads as invalid. `check` answers `unsafe`, `start` refuses, `stop` removes it; the upgrade note says to run `/afk stop`, then `/afk start`.

## Enforcers

- `afk.py` `read_settings`, `start`, `effective`, `check`, `lease_over`, `rules` (script).
- `away_lease.read_lease` (script); `afk_stop_hook.py` through `afk.lease_over` (hook).
- `afk_setup.py` and `project_store.autopilot_value` (script).
- `merge_check.py --fallback-family` (script).
- Host deny rules for anything else (host).

## Tests

- `tests/test_afk.py`: one-mode start summary and lease schema, lease guards with no counters, the retired-line notices (account lines and repository keys), the ignored values and the hash, an old lease with counters, setup and repository writers refusing retired keys, `lease_over`, the merge pin without `MERGE OK`, the removed approval flags.
- `tests/test_afk_open.py`, `test_afk_setup.py`, `test_afk_stop_hook.py`, `test_afk_overlay.py`, `test_afk_permit_hook.py`, `test_afk_rules.py`, `test_merge_check.py`, `test_project_progress.py`, `test_setup_limits.py`: strict-only tests deleted, the rest adjusted.
