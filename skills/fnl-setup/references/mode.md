# Delegation mode and Routing (`/fnl-setup mode`)

Script: preview, atomic sections, no symlinks/network/model. Questions: `interview.md` (advisory). Manual=requested, suggest=ask, auto=independent tested handoffs; authority/gates apply.

1. Run `python3 -I <this skill folder>/scripts/mode.py show`; show values/sources/overrides. `FNL_DELEGATION_MODE`/`FNL_ROUTING` wins, then host config, then suggest/on; invalid values use defaults. Auto gate needs canonical `## Auto gate` on; environment cannot enable it; `FNL_AUTO_GATE=off|0|false|no` disables.
2. Ask the preferences question in every mode: "How should I hand work to other AI helpers: manual, suggest, or auto; and should the coding guideline start automatically: on or off?" Default: suggest/on. Offer manual/suggest; ask auto separately: "Arm auto delegation, where the coordinator hands independent tasks to other agents without asking each time?" Preview `mode.py set --delegation-mode <m> --routing <on|off>` (requested flags only); show changes/overrides; get yes.
3. Only for effective auto, preview `set --auto-gate on|off`. Claude Code hook may deny first repository write absent decision/prior denial in eight hours; excludes shell, grants no security/approval. Ask: "Turn the auto gate on?" Disable: `/fnl-setup mode auto-gate off` or `FNL_AUTO_GATE=off`; other hosts: advisory. Routing off removes the supported session-start reminder; stronger/named instructions remain.
4. After yes repeat with `--yes`, then `show`; exit 0 alone proves nothing. Routing/Auto gate: canonical host.md; Delegation mode: `ORCHESTRATION_HOST_CONFIG` or canonical. No legacy reads. Confirm split targets separately; report refusals/pending/overrides, never bypass. Only requested sections change.

Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes.
