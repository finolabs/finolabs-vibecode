# Settings and enforcement

The mode meanings live in the skill's Delegation mode section. These are user preferences for handing work off and entering the coding guideline. They grant no permissions. If a required review cannot be arranged under the chosen mode, obtain the needed authorization; never waive the gate.

## Read and change

The read-only `scripts/mode.py` prints JSON keys `delegation_mode`, `routing` and `auto_gate` and exits 0. For Delegation mode and Routing, precedence is `FNL_DELEGATION_MODE` / `FNL_ROUTING`, then the optional `## Delegation mode` / `## Routing` section in `ORCHESTRATION_HOST_CONFIG` or `~/.finolabs/vibecode/host.md`, then `suggest` / `on`. Put one bare lowercase value on its own line. A present but invalid environment value uses the default, not the file value. A missing, unreadable, non-UTF-8, oversized, non-regular or symlinked file supplies no settings; symlinked parent directories are refused too. Duplicate or invalid setting sections use that setting's default. Reading never writes config; the existing legacy config is used while the canonical file is absent. Auto gate defaults to `off`; only a valid `## Auto gate` section containing `on` opts in. `FNL_AUTO_GATE` values `off`, `0`, `false` or `no` (case-insensitive) disable it, and every other environment value leaves the file setting unchanged.

To change a preference, show the requested headings and values and write only what the user chooses. Environment overrides still win. Re-read before routing when the relevant environment or file changes. No mode substitutes for capability, quota, permission or acceptance evidence. Record an automatic routing decision using the existing ledger start reason and note; no new usage event is needed.

## Auto enforcement

| Mode | Enforcer and limits |
| --- | --- |
| `auto` | On Claude Code, the installed hook enforces the opt-in gate only with effective Delegation mode `auto`, host config `## Auto gate` set to `on`, and no environment off switch. It may deny the first file write in a repository without a decision in the last 8 hours. An implementation ledger start or keep receipt records a decision; either that decision or a prior denial allows subsequent writes within the window. Expired state can cause another single denial. Errors allow. Shell commands are not covered; this is a nudge, not an approval or security control. Elsewhere, agent judgment is advisory. |

Turn the gate off with `/fnl-set-mode auto-gate off` or `FNL_AUTO_GATE=off`.

## Host limits

| Host | What can support the preference | What remains unverified |
| --- | --- | --- |
| Claude Code | SessionStart builds a reminder when Routing is on; the opt-in auto gate is declared for file-write tools | Real-session auto gate delivery, timeout behavior and tool coverage in this implementation; this pack adds no continuation hook |
| Codex | SessionStart builds the same reminder, after the user trusts plugin hooks | Trust, installed hook execution and continued compliance |
| Antigravity | Agent judgment; no enforcement hook this pack relies on | Continued compliance; the always-on rule file is static and Routing cannot affect it |

Routing off removes the coding-router instruction from this pack's generated session-start hook text on Claude Code and Codex. The session-start hook fails open to on and never blocks; the separate file-write exception is described under Auto enforcement above. The skill remains available by name. Existing user or repository instructions can still require it; the switch does not rewrite those instructions. A file inspection or a successful local hook test cannot prove that an installed host invokes it.
