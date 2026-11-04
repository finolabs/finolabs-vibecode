# Settings and enforcement

The mode meanings live in the skill's Delegation mode section. These are user preferences for handing work off and entering the coding guideline. They grant no permissions. If a required review cannot be arranged under the chosen mode, obtain the needed authorization; never waive the gate.

## Read and change

The read-only `scripts/mode.py` prints JSON keys `delegation_mode` and `routing` and exits 0. For each key, precedence is `FNL_DELEGATION_MODE` / `FNL_ROUTING`, then the optional `## Delegation mode` / `## Routing` section in `ORCHESTRATION_HOST_CONFIG` or `~/.finolabs/vibecode/host.md`, then `suggest` / `on`. Put one bare lowercase value on its own line. A present but invalid environment value uses the default, not the file value. A missing, unreadable, non-UTF-8, oversized, non-regular or symlinked file supplies no settings; symlinked parent directories are refused too. Duplicate or invalid setting sections use that setting's default. The reader never writes config or follows the legacy config location.

To change a preference, show the two headings and values and write only what the user chooses. Environment overrides still win. Re-read before routing when the relevant environment or file changes. No mode substitutes for capability, quota, permission or acceptance evidence. Record an automatic routing decision using the existing ledger start reason and note; no new usage event is needed.

## Host limits

| Host | What can support the preference | What remains unverified |
| --- | --- | --- |
| Claude Code | SessionStart builds a reminder when Routing is on; hooks can add continuation reminders | Installed hook execution and continued compliance; this pack adds no continuation hook |
| Codex | SessionStart builds the same reminder, after the user trusts plugin hooks | Trust, installed hook execution and continued compliance |
| Antigravity | Agent judgment; no enforcement hook this pack relies on | Continued compliance; the always-on rule file is static and Routing cannot affect it |

Routing off removes the coding-router instruction from this pack's generated session-start hook text on Claude Code and Codex. The hook fails open to on and never blocks. The skill remains available by name. Existing user or repository instructions can still require it; the switch does not rewrite those instructions. A file inspection or a successful local hook test cannot prove that an installed host invokes it.
