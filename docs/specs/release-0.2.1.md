# Release 0.2.1: scope

Status: draft; scope settled by the owner on 2026-11-08, one package merged in part; the release is not cut and nothing here is verified on a live host.

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

## In scope, not yet delivered

| # | Package | What | Owner decision |
| --- | --- | --- | --- |
| 8 | Delegated-acceptance default | #178: one line in the user-contract template. | 2026-11-08. |
| 9 | `## Agent skills` block in every context file | Setup recommends writing the block to every project context file the hosts read, `AGENTS.md` and `CLAUDE.md`, and skips a `CLAUDE.md` that only imports `AGENTS.md`. | 2026-11-08. |
| 10 | Check reports plugin enablement | `enabledPlugins` state per Claude home in `/fnl-setup check`. | 2026-11-08. |
| 11 | Unsandboxed review runs | Document the Codex review and posting run without a sandbox, record a needs-permission dispatch as such rather than as quota, and explain why `verify_claim.py` refused a valid brief. | 2026-11-08. |
| 12 | Heavy-job guard | `heavy_run.py`, the opt-in `PreToolUse` gate, setup, agent rules and tests, per `heavy-jobs.md`. | 2026-11-08: inside 0.2.1. |
| 13 | Review residuals | #176: legacy-limits detection, Check note for ignored global limits, refresh throttle scope. #172: plugins-dir check, truncation note. #177: test-scope wording, wrapper-identity note. | 2026-11-08. |
| 14 | Smaller setup items | Duplicate-lines warning on generated files; ledger project naming guidance. | 2026-11-08. |

## Out of scope (later releases)

The `fnl-goal` skill and autopilot, `README.vi.md` and the use-case table, a Codex `PreCompact` declaration, an
Antigravity `/compact` message, the Codex ref in the catalog, relay receipts and counters, a private `HOME` per run,
multi-account agents, a merge guard and live-host verification.

## Release steps (after the scope is delivered)

Bump the manifests from `0.2.1-dev`, date the changelog, tag `v0.2.1` (the unsigned-tag question stays the owner's),
open the catalog pin in `finolabs/plugins`, and refresh the Codex copy on purpose so the owner trusts its hooks once.
