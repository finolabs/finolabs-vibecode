# Scan agents (`/fnl-setup scan`)

Script enforces preview, atomic section-only writes, no symlinks. Consent: advisory (agent judgment).

1. Run `python3 -I <this skill folder>/scripts/agent_scan.py --host <claude|codex|antigravity>` with the known running host; ask if unknown. Checks claude/codex/agy PATH/`--version` (no shell, three seconds), canonical config/cache; prints root/source, quota times/pools. No network/probe. Read refusals even at exit 0. Screened versions prove no access; quota over eight hours is unverified; user wins.
2. Show coordinator and all three rows, including absent families. Confirm present families' full model IDs (free text), recorded or `fnl-delegate` tier seeds, never availability proof. Without dependency/confirmation leave unverified. Pass confirmed IDs as repeated quoted `--models '<family>=<models>'` arguments.
3. Ask: "Write this agent inventory section?" After clear yes repeat the command with confirmed models, `--yes --digest <printed Digest prefix, at least 8 hex>`. A mismatch writes nothing. Only canonical `## Agents on this machine` changes. Preview coordinator changes. Overrides/legacy config must read this inventory; leave their settings to the user.
4. Report changes/unverified. Suggest other present families for reach; confirm separately, never write `Coordinators and reach`. Refresh after CLI changes; inventory over 30 days is stale.

Consent: neutral Yes/No, no defaults/recommendation; timeout never means yes.
