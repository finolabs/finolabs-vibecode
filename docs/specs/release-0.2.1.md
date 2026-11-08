# Release 0.2.1: scope

Status: released; v0.2.1 was tagged on commit 00dee56 and published on GitHub on 2026-11-09; the scope was cut by the coordinator that day (see Moved to a later release); packages 1 to 11, 12a and 15 are in it and nothing here is verified on a live host. The catalog pin in finolabs/plugins and the Codex refresh are not done.

## Why

0.2.0 shipped on 2026-11-08. The same day showed four gaps: delegation to other agent families drifted after a
compaction, delegated runs started in a way the host could not list, the parallel run limit applied machine-wide
instead of per project, and the machine reset several times under parallel heavy jobs. This release closes those
and the setup gaps found on the way.

## Delivered (merged pull requests)

| # | Package | Pull requests | Status |
| --- | --- | --- | --- |
| 1 | Baseline | #171 started the 0.2.1 development cycle. | implemented. |
| 2 | Check reports the live plugin version | #172: folder marketplace version beside the registry record, `CLAUDE_CONFIG_DIR`, other Claude homes. | implemented; fixture tests. |
| 3 | Delegation after a compaction | #173: fixed reminder in the session-start hook, handover line, coordinator session hash in the ledger. | implemented; delivery to the model unverified. |
| 4 | Plain delegate description | #174. | implemented. |
| 5 | Background run rule | #175: runs start in the host's background mode, never `( … ) &`, `nohup` or `disown`. | implemented. |
| 6 | Per-project parallel limit | #176: `parallel` and `parallel-caps` per repository, default 3. | implemented; live scheduling unverified. |
| 7 | Heavy-job design | #177: the spec and the fifth scoped exception in `CLAUDE.md`. | design only; no code. |
| 8 | Delegated-acceptance default | #178: one line in the user-contract template, defining the package boundary and the repository-owner exception. | implemented; template text only. |

## Delivered since the scope was settled

| # | Package | Pull requests | Status |
| --- | --- | --- | --- |
| 9 | `## Agent skills` block in every context file | #182. | implemented; setup text only. |
| 10 | Check reports plugin enablement | #184: `enabledPlugins` state per Claude home. | implemented; fixture tests. |
| 11 | Unsandboxed review runs | #184: documentation of the unsandboxed review and posting run, `needs-permission` versus `quota`, and which command refuses a review dispatch's acceptance. | implemented; documentation only. |
| 12a | Heavy-job wrapper | #180: `heavy_run.py`, a machine-wide one-at-a-time lock with load and memory gates, a wait cap and a maximum run time. | implemented; fixture tests, no live-host proof. |
| 15 | Autopilot first slice (`/fnl-brb`) | #183: `autopilot.py` start, stop, check and log, and `merge_check.py --independent`. #185: the `fnl-autopilot` skill, its `fnl-brb` alias and the `/fnl-setup add autopilot` feature. | implemented; classification only, nothing executes commands; the live loop, dashboard tab, scheduler, hooks and host backstop are deferred. |

## Moved to a later release

The owner was asleep when the cut was made (2026-11-09), so the coordinator moved these out of 0.2.1 to ship a
coherent release; each stays in the backlog and the owner can reverse the cut.

| # | Package | Why moved |
| --- | --- | --- |
| 12b | Heavy-job gate (the opt-in `PreToolUse` hook, its installer and setup question) | The spec is merged, but the hook, installer and consent flow need their own review cycle; until then agents rely on `heavy_run.py` and the advisory rule. |
| 13 | Review residuals (#176, #172, #177, #179, #180 non-blocking notes, including the process-group boundary wording) | Non-blocking notes. |
| 14 | Smaller setup items (duplicate-lines warning, ledger project naming guidance) | Not started. |

## Out of scope (later releases)

A goal skill, the rest of autopilot beyond its first slice (dashboard tab, live loop, scheduled driver, notice hook, host backstop), `README.vi.md` and the use-case table, a Codex `PreCompact` declaration, an
Antigravity `/compact` message, the Codex ref in the catalog, relay receipts and counters, a private `HOME` per run,
multi-account agents, a merge guard and live-host verification.

## Release steps (after the scope is delivered)

Bump the manifests from `0.2.1-dev`, date the changelog, tag `v0.2.1` (the unsigned-tag question stays the owner's),
open the catalog pin in `finolabs/plugins`, and refresh the Codex copy on purpose so the owner trusts its hooks once.
