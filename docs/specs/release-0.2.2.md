# Release 0.2.2: scope

Status: in progress; scope settled by the owner on 2026-11-09; packages 1 to 4 and 7 are merged and packages 5 and 6 are open.

## Why

0.2.1 shipped the autopilot first slice and the heavy-job wrapper, and moved the review residuals, the heavy-job gate and some setup items out. On 2026-11-09 the owner also asked for per-agent task levels, which landed as package 1. Using the machine that night showed four gaps worth closing together: users cannot find their own extra Claude Code commands, the heavy-job wrapper's memory minimum blocked a review on a 16 GB machine, the quota probe reads nothing useful for an install that goes through a gateway, and the new features have only unit tests.

## Delivered (merged pull requests)

| # | Package | Pull requests | Status |
| --- | --- | --- | --- |
| 1 | Agent levels | #189: `/fnl-setup add delegation` asks which of five task levels each helper takes, including extra Claude Code commands; the writer and strict reader are `levels_setup.py`; shell-function commands start behind the environment filter. Spec: `agent-levels.md`. | implemented; unit tests, no live-host proof |
| 2 | Find extra Claude Code commands | #191: `levels_setup.py candidates` prints, as names only, the `claude*` programs on `PATH` and the `~/.claude-*` folder labels, and `add delegation` offers them as candidates; a shell function is added only when the user types its name, because listing functions would run the user's startup file. | implemented; unit tests, no live-host proof |
| 3 | Heavy-job wrapper memory minimum and queue view | #192: `heavy_run.py` reads free memory from the kernel's own figure (`memory_pressure` free percentage times `hw.memsize`, with a conservative `vm_stat` estimate as fallback), after a 2.6 GB reading refused a review on a 16 GB machine that the kernel reported 31% free; `status` prints `waiting: about <n>`. | implemented; unit tests, no live-host proof |
| 4 | Review residuals and small setup items | #195 and #196: records and status cells brought in line, the process-group wording, a symlinked-manifest test for Check, a 256 KiB bound on the `ps` snapshot behind `waiting:` and a ledger project-label paragraph. The duplicate-lines warning already exists as Check item I5. | implemented; unit tests, no live-host proof |
| 7 | Native Windows message (issue 193) | #197: no Windows support, which would need a new security design; every script that imports `pwd` or `fcntl` stops with one clear message, the README names macOS and Linux (Windows through WSL), and a test pins it. | implemented; simulated by blocking the modules, not run on Windows |

## Scope (owner decision, 2026-11-09)

| # | Package | What it covers |
| --- | --- | --- |
| 5 | Quota probe for gateway installs | Skip or mark an install whose usage output has no pools, so routing treats it as unverified and the probe stops asking. |
| 6 | Live-host check | Run `/fnl-brb`, `heavy_run.py` and a dispatch by level on this machine, and record what happened in the owner-facing evidence below. |

## Left out of 0.2.2

The heavy-job gate hook and its installer, the goal skill, the rest of autopilot (dashboard tab, live loop, scheduler, notice hook, host backstop), `README.vi.md` and the use-case table, a Codex `PreCompact` declaration, an Antigravity `/compact` message, the Codex ref in the catalog, relay receipts and counters, a private `HOME` per run and the merge guard. The owner can pull any of these in.

## Carried to the release pull request

Two non-blocking notes from the review of #197: the platform-message test blocks both modules at once, so the `pwd` guards that follow an `fcntl` import in `auto_gate.py` and the five `quota_probe.py` copies are not exercised on their own; and the README sentence about Windows should say that scripts run by hand stop with the message while hooks stay fail-open.

## Evidence

Package 1 (#189): `tests/test_levels_setup.py` and the two reviews. Package 2 (#191): the candidates fixtures in `tests/test_levels_setup.py` and its reviews. Package 3 (#192): the memory and waiting fixtures in `tests/test_heavy_run.py` and its reviews. All three are unit tests with synthetic input; nothing is verified on a live host yet.

## Release steps (after the scope is delivered)

Follow `fnl-versioning`: a release pull request that drops `-dev` and dates the changelog, the tag `v0.2.2` after CI on that commit, a bump to `0.2.3-dev`, then the catalog pin in `finolabs/plugins` and a Codex refresh, each with the owner's go.
