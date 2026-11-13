# Delegation mode and Routing (`/setup mode`)

Script: preview, atomic sections, no symlinks/network/model. Questions: `interview.md` (advisory). Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes.

1. Run `python3 -I <this skill folder>/scripts/mode.py show`; show values/sources/overrides. `FNL_DELEGATION_MODE`/`FNL_ROUTING` wins, then host config, then suggest/on; invalid values use defaults. Auto gate needs canonical `## Auto gate` on; environment cannot enable it; `FNL_AUTO_GATE=off|0|false|no` disables.
2. Ask the preferences question in every mode: "When should other AI helpers join, and should the coding guide start with each session?"
Description: Choose requested-only (manual), ask-first (suggest) or independent tested handoffs (auto); coding guide on/off. Nothing is saved before a later approval; change via mode. Helpers use their providers.
Default suggest/on; offer manual/suggest; ask auto separately: "Let the lead AI hand independent tasks to other AI helpers without asking each time?"
Yes: Save auto in local host.md; helpers get tasks via providers.
No: Keep the mode; ask later.
Undo: /setup mode manual or suggest.
Choices: "Yes, allow handoffs" / "No, keep the mode".
Preview `mode.py set --delegation-mode <m> --routing <on|off>` (requested flags only); show changes/overrides; ask separately for each target:
"Save the shown helper preferences and coding-guide setting?"
Yes: Write shown local host.md sections; nothing sent now; helpers use providers.
No: Keep the sections; answer later.
Undo: /setup mode.
Choices: "Yes, save preferences" / "No, keep preferences".
3. Only for effective auto, preview `set --auto-gate on|off`. Claude Code hook may deny first repository write absent decision/prior denial in eight hours; excludes shell, grants no security/approval. Ask: "Require a handoff decision before the first file edit in a repository?"
Yes: Save Auto gate in local host.md; Claude may refuse that edit; elsewhere advisory. Nothing sent.
No: Keep that setting; ask later.
Undo: /setup mode auto-gate off.
Choices: "Yes, require a decision" / "No, keep the setting".
Routing off removes the supported session-start reminder; stronger/named instructions remain.
4. After yes repeat with `--yes`, then `show`; exit 0 alone proves nothing. Routing/Auto gate: canonical host.md; Delegation mode: `ORCHESTRATION_HOST_CONFIG` or canonical. No legacy reads. Confirm split targets separately; report refusals/pending/overrides, never bypass. Only requested sections change.
