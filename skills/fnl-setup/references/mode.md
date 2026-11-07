# Delegation mode and Routing (`/fnl-setup mode`)

Script: preview, atomic sections, no symlinks/network/model. Consent: advisory (agent judgment). Manual=requested, suggest=ask, auto=independent tested handoffs; authority/gates apply.

1. Run `python3 -I <this skill folder>/scripts/mode.py show`; report values/sources. `FNL_DELEGATION_MODE`/`FNL_ROUTING` wins over host config, then defaults suggest/on; invalid values use defaults. Auto gate needs canonical `## Auto gate` on; `FNL_AUTO_GATE=off|0|false|no` disables, environment cannot enable it. Explain overrides.
2. In every mode ask: "How should I hand work to other AI helpers: manual, suggest, or auto; and should the coding guideline start automatically: on or off?" Unchosen: suggest/on. Offer manual/suggest; auto separately asks: "Arm auto delegation, where the coordinator hands independent tasks to other agents without asking each time?" Preview `mode.py set --delegation-mode <m> --routing <on|off>` only requested flags; show changes/overrides, get yes.
3. Only for effective auto, preview `set --auto-gate on|off`. Explain: installed Claude Code hook may deny first repository write absent decision/prior denial in eight hours; excludes shell, grants no security/approval. Ask: "Turn the auto gate on?" Disable via `/fnl-setup mode auto-gate off` or `FNL_AUTO_GATE=off`; other hosts are advisory. Routing off removes the supported session-start reminder, not stronger/named instructions.
4. After yes repeat with `--yes`, then `show`; exit 0 alone does not prove a write. Routing/Auto gate: canonical host.md; Delegation mode: `ORCHESTRATION_HOST_CONFIG` if set, otherwise canonical. No legacy reads; split targets need separate confirmations. Report refusals/pending/overrides; never bypass. Only requested sections change.

Consent uses neutral Yes/No, none preselected or recommended; timeout/default is never yes.
