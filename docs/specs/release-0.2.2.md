# Release 0.2.2: scope

Status: in progress; scope settled by the owner on 2026-11-09; package 1 is merged and packages 2 to 6 are open.

## Why

0.2.1 shipped the autopilot first slice and the heavy-job wrapper, and moved the review residuals, the heavy-job gate and some setup items out. On 2026-11-09 the owner also asked for per-agent task levels, which landed as package 1. Using the machine that night showed four gaps worth closing together: users cannot find their own extra Claude Code commands, the heavy-job wrapper's memory minimum blocked a review on a 16 GB machine, the quota probe reads nothing useful for an install that goes through a gateway, and the new features have only unit tests.

## Delivered (merged pull requests)

| # | Package | Pull requests | Status |
| --- | --- | --- | --- |
| 1 | Agent levels | #189: `/fnl-setup add delegation` asks which of five task levels each helper takes, including extra Claude Code commands; the writer and strict reader are `levels_setup.py`; shell-function commands start behind the environment filter. Spec: `agent-levels.md`. | implemented; unit tests; routing by levels is advisory and unverified on a live host. |

## Scope (owner decision, 2026-11-09)

| # | Package | What it covers |
| --- | --- | --- |
| 2 | Find extra Claude Code commands | `scan` lists `claude*` programs on `PATH` and `~/.claude-*` folders as candidates and asks; a shell function is added only when the user types its name, because listing functions would run the user's startup file. |
| 3 | Heavy-job wrapper memory minimum and queue view | Review the default free-memory minimum that held back a review at 2.6 GB free on a 16 GB machine, and show who is waiting for the lock. |
| 4 | Review residuals and small setup items | The non-blocking notes of #172, #176, #177, #179 and #180 including the process-group wording, the duplicate-lines warning and the ledger project naming guidance. |
| 5 | Quota probe for gateway installs | Skip or mark an install whose usage output has no pools, so routing treats it as unverified and the probe stops asking. |
| 6 | Live-host check | Run `/fnl-brb`, `heavy_run.py` and a dispatch by level on this machine, and record what happened in the owner-facing evidence below. |

## Left out of 0.2.2

The heavy-job gate hook and its installer, the goal skill, the rest of autopilot (dashboard tab, live loop, scheduler, notice hook, host backstop), `README.vi.md` and the use-case table, a Codex `PreCompact` declaration, an Antigravity `/compact` message, the Codex ref in the catalog, relay receipts and counters, a private `HOME` per run and the merge guard. The owner can pull any of these in.

## Evidence

Package 1: `tests/test_levels_setup.py` (10 tests) and the two reviews on #189. Nothing else is verified yet.

## Release steps (after the scope is delivered)

Follow `fnl-versioning`: a release pull request that drops `-dev` and dates the changelog, the tag `v0.2.2` after CI on that commit, a bump to `0.2.3-dev`, then the catalog pin in `finolabs/plugins` and a Codex refresh, each with the owner's go.
