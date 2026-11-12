# Parallel agent instances

Status: implemented; amended 2026-11-08 to project scope (see Amendment); shared helper, setup, SessionStart, dashboard, CI copy group and documentation are integrated locally; targeted verification is recorded below, while live-host scheduling and UI behavior remain unverified.

Owner decision: 2026-11-07. A model family (Claude Code, Codex, Antigravity, ZCode) is a pool of agents, not one seat. Independent tasks may use any number of runs of the same family within the user's total and optional per-family caps. This supersedes the former ceiling of five.

## Goal and acceptance

- AC1: Canonical host config chooses a total from 1 to 32 and optional family caps from 1 to that total; missing/invalid total reports default 3.
- AC2: Bounded canonical ledger reads count starts without finishes, with Claude aliases sharing one family. `check` tests both limits; unsafe/unreadable state is unknown.
- AC3: Session start reports only fixed words, family names and integers, stays read-only and exits 0 on errors.
- AC4: Refresh and dashboard use the same parser, show a total above five and family counts/caps with text-only rendering and unknown on unreadable state.
- AC5: Setup asks a free-text total and optional family caps, validates the recorded lines and stays within setup size limits.
- AC6: Instructions preserve tier, strength, permissions and quota rules; families can host multiple runs, excess waits, limits remain advisory and ledger start is unchanged.

## Plan

Use one stdlib parser/read helper at `scripts/parallel_slots.py`, copied byte-for-byte into `delegate` and `status` for standalone skill installs. Trace consumers through SessionStart, refresh, dashboard, setup and routing references. Keep ledger writes and integration-owned files unchanged.

## Contract

Canonical `host.md`, under `## Limits`:

```text
- Parallel dispatches: at most 6 at one time.
- Parallel per family: claude=2, codex=3
```

The total is 1 to 32; 32 is a sanity cap. A missing total falls back to 3, source `default`; valid total source is `host config`. Optional caps accept any subset of `claude`, `codex`, `antigravity`, each 1 to the effective total. An omitted family has only the total bound. Duplicate sections, duplicate/unknown families and invalid caps report unknown, rather than silently dropping a cap. Legacy total wording with a parenthetical suffix is invalid and reports unknown until setup replaces it.

`parallel_slots.py` reads only canonical `host.md` (256 KiB) and `ledger.jsonl` (4 MiB) via `data_root.py`: owned regular files, no-follow, no group/world writes, bounded reads. No environment override, subprocess, network or write. Missing config selects default; missing ledger means zero; unsafe inputs, invalid root, invalid UTF-8 or malformed/ambiguous ledger mean unknown. Start ids deduplicate; any finish for an id closes it regardless of line order. The mapping matches `ledger.py`: `claude`, `claude-session`, `subagent` are Claude; the other two families map directly. Unknown agents refuse capacity.

Commands (all run with `python3 -I`):

- `status`: exit 0, JSON with `limit`, `open`, `free`, `families`, `source`. Each family has `open`, nullable `cap`, nullable `free`. Total and capped family free counts floor at zero; uncapped family free is null. Unreadable state prints `unknown`, exit 3.
- `check --family <claude|codex|antigravity|zcode> [--count k]`: k defaults to 1 and is a positive integer of at most 64 digits; requests above capacity report full. Prints exactly `Parallel slots: available`, exit 0, when both total and family capacity fit; otherwise `Parallel slots: full`, exit 3. Unsafe state prints `Parallel slots: unknown`, exit 3. Invalid CLI arguments exit 2.
- `check-config`: validates canonical config without requiring a ledger; prints JSON `limit`, `caps`, `source`. Exit 0 for a valid total; 3 for default or unknown. Unknown prints only `unknown`.

These are advisory snapshots, not reservations. `ledger.py start` is unchanged and never blocks on slots. Coordinators honor counts by agent judgment, account for pending assignments and recheck before dispatch. Cross-coordinator check/start is not atomic; stale opens are reconciled with evidence through `status`, and an explicit user override remains possible. No new dispatch lock is added and no ledger record is expired. A start older than its hard cap (budget plus a third, at least ten minutes) is reported as `stale` and left out of the counts, because its run cannot still be within budget; a start with an unknown budget or time stays counted, and its record stays open until someone reconciles it.

For k independent tasks, capability order, tier and strength overrides still choose eligible families. Skip a family out of quota or at its cap; spill to the next eligible family. Prefer spreading when two families qualify because simultaneous runs share family quota pools; existing model pools and labelled installs still apply. Give each run its own worktree and ledger line. When total capacity is full, excess tasks wait; unknown capacity needs resolution or a user decision. These are advisory agent judgments, not script-enforced routing. User routes, permissions, Delegation mode and review independence still govern.

SessionStart appends `Parallel slots: <free> free of <total> (<family> <open> open [of cap <cap>], ...; <source>)`. Errors print `Parallel slots: unknown`; no process starts and exit remains 0.

Refresh imports the shared helper and schema-checks `running.parallel_limit` and `running.family_slots` (closed family keys, nonnegative integer opens, nullable integer caps). `running.parallel_source` is a closed word marking project settings, default, unknown, or settings need setup (an approved settings file broke, so capacity is unknown) so the fallback is visible. On errors these numeric blocks are null, source unknown. They are derived into existing `data.js`, overwritten/purged with it; no new event, receipt, retained file or storage location. The page draws configured bricks, uses family counts for occupancy and adds open/cap/source to the tooltip, using text-only DOM operations. Unknown is explicit; legacy data missing these fields retains the old default-five display.

Setup asks the user for the total (recommending a small number such as 3), then optional caps, explains shared family quota and runs `check-config`. Asking and honoring limits are advisory; the helper enforces parsing. A silent answer never selects a limit.

## Tasks

- [x] T1 Shared parser, bounded canonical reads and synthetic CLI tests.
- [x] T2 SessionStart line and isolated tests.
- [x] T3 Refresh numeric projection, dashboard tooltips and fixtures.
- [x] T4 Setup and routing instructions; remove active five-run ceilings.
- [x] T5 Required targeted modules and reference/copy checks; record results.

## Evidence

Initial RED: the synthetic SessionStart test expected `Parallel slots: 2 free of 6` and failed because no slots line existed. All tests use synthetic account homes and local fixtures; no live account config/provider is used.

| Whole module | Tests | Final result |
| --- | --- | --- |
| `tests.test_parallel_slots` | 10 | PASS |
| `tests.test_session_start` | 21 | PASS |
| `tests.test_dashboard_page` | 84 | PASS |
| `tests.test_refresh` | 69 | PASS |
| `tests.test_setup_limits` | 20 | PASS |
| `tests.test_run_hygiene` | 10 | PASS |
| `tests.test_spec_status` | 4 | PASS |
| `tests.test_shared_copies` | 2 | PASS |
| `tests.test_check_references` | 12 | PASS |

232 distinct targeted tests are green. The combined 232-test run found one obsolete tooltip assertion (it expected only `lit`); after updating that oracle for the required family/source rows, the entire dashboard and parallel-slots modules reran: `Ran 94 tests in 81.892s`, `OK`. All remaining modules had passed in the combined run; no full-suite discovery was run. The positive-count parser was also checked in that final parallel-slots rerun, including a request above 32 returning full.

Tests run through `python3 -I scripts/run_env.py -- python3 -I -c ...`, explicitly adding the checkout to the isolated interpreter's import path and loading only the nine modules above. `python3 -I scripts/check-references.py .`: `references ok (116 files)`. Existing CI copy-group tests pass; the new helper's three copies are checked byte-for-byte by `test_parallel_slots` and a direct byte comparison. `git diff --cached --check` passes. AC1/2 map to parallel slots, AC3 to session start, AC4 to refresh/dashboard, AC5 to setup limits and AC6 to the instruction diff and unchanged ledger script.

## Integration and limits

Integration now includes the CI copy group for the three `parallel_slots.py` files, the README and `ask` map, and the public CHANGELOG entry. The preceding evidence records the original package's local checks; it does not establish live-host scheduling or UI behavior. No manifests, hooks, privacy policy, ledger behavior or real account state change here. Live UI, cross-process scheduling, user setup and independent reviews remain unverified in this package; checks never imply slot reservation.

## Amendment: project scope (owner decision, 2026-11-08)

The limit was machine-wide: the total from `## Limits` was compared with every open dispatch of every repository. The owner's intent is a limit per project (repository), with no machine-wide ceiling. Quota pools are per account and stay shared, so several repositories can still reach a quota limit together.

Settled decisions (owner, 2026-11-08):

- A repository without its own setting uses the default of 3. The global `## Limits` lines are no longer read; `check-config` reports `legacy_limits` when they exist and the setup check shows a one-line note that they are ignored.
- Per-family caps also move to the project.
- There is no machine-wide total.

Contract:

- Settings live in the repository's own settings file (since 0.2.5, owner decision 2026-11-11; it replaced `## Project settings` of `host.md`, which is no longer read): `settings.json` in `.finolabs/vibecode/` of the main checkout, shared by a linked worktree whose metadata is reciprocal, with `"parallel": "<1 to 32>"` and `"parallel-caps": "claude=2, codex=3"` (any subset of the three families, each 1 to the repository's total), read only while it matches the digest approved in the data root (see `project-progress.md` "Project settings file"). They are set with `python3 -I project_progress.py settings --set parallel=<n>` and `--set parallel-caps=<list>` run inside the repository, cleared with `--clear <key>`, and all discarded with `settings --reset`. A never configured repository (no approval record, including a file nobody approved) uses the default of 3 with no caps, and `check-config` exits 3 with source `default`. An approved file that is now missing, invalid, unsafe or edited is broken: `check-config` and `check` print `unknown` and exit 3, the session line says the project settings need setup again, and every setter refuses until `settings --reset` returns the repository to never configured. A cap above the total reports unknown.
- `parallel_slots.py` takes the repository from the current directory (nearest ancestor holding `.git`, or an explicit `--repo <path>` to the same resolution). It counts only open, non-stale starts whose `project` equals that repository's ledger project name (the repository's `ledger` project setting, else the folder name; the global `Ledger project:` line of `host.md` is no longer read since 0.2.5). Dispatches whose `project` matches no repository are not counted for any, and `status` reports how many open dispatches were left out as `other_projects`.
- `status` keeps `limit`, `open`, `stale`, `free`, `families`, `source` and adds `scope` (`{"code": "<8hex>", "project": "<ledger name>"}`, or `null` outside a repository, where the default applies and nothing is counted). `source` is `project settings` or `default`. `check` and `check-config` keep their exit codes; `check-config` prints `limit`, `caps`, `source` and `legacy_limits`.
- SessionStart prints `Parallel slots: <free> free of <limit> (<family> <open> open [of cap <cap>], ...; <source>)` for the session's repository; its fixed-word rule and exit 0 on errors are unchanged.
- Refresh and the dashboard show the numbers for the repository given by the hook's `--cwd` (else the process directory). The tooltip names the project only by its registered name or user label, never by the ledger name, which is a join key; without one it says `unnamed`. Outside a repository they show the default and `unnamed`. A machine-wide view of every project is not part of this amendment.
- `setup add delegation` asks "How many agent runs may work at the same time in this repository?" and the optional family caps, then writes them through `project_progress.py settings`, with the same neutral Yes and No approval and a preview. The user-scope `## Limits` question is removed.
- Enforcement is unchanged: advisory (agent judgment); `ledger.py start` never blocks.

Amendment acceptance:

- AC7: two repositories with open dispatches count separately; a repository without a setting reports limit 3, source `default`.
- AC8: a repository with `parallel: 2` reports 2 as its limit whatever the legacy `## Limits` total says, and a cap above the total makes the section unknown.
- AC9: a linked worktree uses its main checkout's setting.
- AC10: SessionStart, refresh and the dashboard read the same helper; outside a repository nothing is counted.
- AC11: setup writes and validates the two keys only after the user's yes.
