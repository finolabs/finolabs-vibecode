# Feature: compaction (user scope)

Needs: nothing for the native threshold; the Antigravity stop needs Antigravity present in the scan findings, otherwise skip that step. Optional. Every question uses neutral Yes and No with none preselected or marked recommended; a default, timeout or auto-selected option never counts as the yes. Asking and rechecking are advisory (agent judgment).

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Native threshold (Claude Code, Codex)

Ask: "Choose when Claude Code or Codex shortens a long conversation to make room?"
Yes: Choose a limit measured in tokens, small pieces of text; a separate approval follows before host settings change. Preparation stays local.
No: Leave conversation settings unchanged; ask later.
Undo: Cancel before applying; after applying, approve a removal plan.
Choices: "Yes, choose a limit" / "No, keep current settings".
After a clear yes, recheck the installed host's documented control from `session-hygiene` "Context pressure", then ask the token value as free text: "How many tokens should the conversation reach before it is shortened?"
Description: Enter a token count to prepare a local plan; nothing sent or applied. Skip to keep settings; choose later or change the number before approval.
Claude Code allows 100000 to 1000000; Codex 1000 to 10000000. Explain that models with a 1M window compact late by default, so a lower value compacts earlier; prescribe no value. Antigravity has no documented native setting: skip this and offer the stop below (advisory, agent judgment).
Antigravity vendor docs through 1.5.3 (07/11/2026) document automatic compaction and `/context`, but no threshold or off switch; `/compact` may not exist. Offer `/new` or `/fork` (advisory, agent judgment).

Before the limit approval, follow the native preview procedure in [compaction-details.md](../compaction-details.md).
"Save the shown limit for shortening future conversations?"
Yes: Change only the shown key in the listed Claude settings.json or Codex config.toml, with backups. It affects new sessions; saving sends nothing.
No: Leave those files unchanged; ask later.
Undo: Approve a plan using --off to remove this key, or restore the backup.
Choices: "Yes, save this limit" / "No, leave settings unchanged".
After its yes, follow the native apply procedure and enforcers in [compaction-details.md](../compaction-details.md).

## Context reading

Offer Claude Code context reading, and Antigravity context reading when present, each with its own neutral Yes/No question: "Show how much conversation space Claude Code or Antigravity is using?"
Yes: Prepare a local display-command plan for this host; save nothing in its settings until separate approval. The eventual reader keeps counts locally and sends nothing.
No: Leave this host’s display and recording unchanged; ask later.
Undo: Cancel now, or later approve removal of this command.
Choices: "Yes, prepare the space display" / "No, leave the display unchanged".
A No leaves it off.
After a yes follow [../context-reading.md](../context-reading.md): the previewed `statusline_setup.py` plan with its own separate approval, including in Quick setup, or the printed recipe when a status line already exists. Asking is advisory (agent judgment); the script enforces the plan, digest, expiry and safe writes. The reading is no compaction trigger; Codex is not covered. Antigravity uses `--host antigravity` and keeps its separate byte-proxy stop.

## Antigravity stop

Offer only when the findings show Antigravity present. Ask: "Set up Antigravity to ask for a fresh session when a saved conversation grows too large?"
Yes: Choose a byte limit to prepare a local stop-command plan; files change only after separate approval. It checks file size only, sends nothing and its first-call-of-turn assumption is unverified.
No: Leave this stop off; ask later.
Undo: Cancel now, or later approve removal of the stop.
Choices: "Yes, prepare the session stop" / "No, leave the stop off".

A No leaves it off. Explain that transcript bytes are a rough proxy, exclude the system prompt and are not tokens; recommend no default. Report "set up", not "enforced": live user-level delivery and TUI behavior remain unverified; the workspace hook was observed in Antigravity 1.5.1 `agy -p` on 06/11/2026 (advisory, agent judgment).
Antigravity [hooks docs](https://antigravity.google/docs/hooks), through installed 1.5.3 (07/11/2026), confirm `~/.gemini/config/hooks.json`; `~/.gemini/antigravity-cli/settings.json` is not loaded for hooks. The fixed script message still asks for `/compact`, which may not exist; explain `/new` or `/fork` instead (advisory, agent judgment). Changing that string needs an owner decision.

After its preparation yes, follow the stop preview procedure in [compaction-details.md](../compaction-details.md), then ask:
"Save the shown Antigravity session stop and its size limit?"
Yes: Write Compaction stop in local host.md and its own group in your account’s .gemini/config/hooks.json, with a hooks backup. It checks size locally and sends nothing; live behavior is unverified.
No: Leave both files unchanged; ask later.
Undo: Approve preview --remove, or disable with FNL_COMPACT_STOP=off.
Choices: "Yes, save the session stop" / "No, leave files unchanged".
Only after that yes run `compact_stop_setup.py apply --digest <full digest> --yes`; removal uses `preview --remove` with the same approval. Enforcer: the installer checks the stored private preview, full digest, 60-minute expiry, unchanged files, plugin root, owner, mode and safe paths; it writes the `## Compaction stop` section and its own `finolabs-vibecode-compact-stop` group atomically per file with a hooks backup, leaving the metrics group alone. It requires the whole plugin and an existing safe config folder.
Asking, showing and applying only the approved preview are advisory (agent judgment), including in quick setup.

Enforcer: `compact_stop_hook.py` acts only on Antigravity `PreInvocation` with `invocationNum` 0, never on a tool call, prompt, session start or user stop. The docs do not say whether the counter resets per user turn; the first-call-of-turn assumption remains unverified. It checks only a regular, non-symlink transcript's size within the account's conversation folder, stops again after both 10% and 20000 bytes of growth, resets on shrink, and allows on errors, including mark-write failure. It never runs `/compact`, reads content or sends data. `FNL_COMPACT_STOP=off` disables it.

## Steward explanation

Explain the existing session-hygiene check and its limits from [compaction-details.md](../compaction-details.md); this adds no setup write (advisory, agent judgment).
