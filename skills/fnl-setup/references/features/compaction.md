# Feature: compaction (user scope)

Needs: nothing for the native threshold; the Antigravity stop needs Antigravity present in the scan findings, otherwise skip that step. Optional. Every question uses neutral Yes and No with none preselected or marked recommended; a default, timeout or auto-selected option never counts as the yes. Asking and rechecking are advisory (agent judgment).

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Native threshold (Claude Code, Codex)

Ask: "Would you like help setting a native compaction threshold?" After a clear yes, recheck the installed host's documented control from `fnl-session-hygiene` "Context pressure", then ask the token value as free text: "Which token value?" Claude Code allows 100000 to 1000000; Codex 1000 to 10000000. Explain that models with a 1M window compact late by default, so a lower value compacts earlier; prescribe no value. Antigravity has no documented native setting, only `/compact`: skip this and offer the stop below.

Run `python3 -I <this skill folder>/scripts/compact_setup.py preview --host <claude|codex> --tokens <chosen value>`. Claude defaults to the account home's `.claude/settings.json`; with chosen folders pass each as `--folder <absolute config folder>` (at most four, replacing the default). Codex uses an absolute `CODEX_HOME`, otherwise the account home's `.codex/config.toml`. Show every target, existence, key change, backup name, warning and `Digest:`, then ask separately:
"Apply this compaction plan?" Only after the yes run `compact_setup.py apply --digest <full digest> --yes`. Even quick setup keeps this approval separate. Removal uses `--off` instead of `--tokens` with the same preview and approval; it removes this key, not auto-compaction. Enforcers: the script checks the private stored plan, full digest, 60-minute expiry, unchanged targets and safe paths, keeps backups and writes atomically; asking and invoking only from a user's `fnl-setup` request are advisory (agent judgment), never a hook.
The host enforces the threshold; it applies to sessions started afterwards, and a running session and the Codex default remain unverified. Never write environment variables or the percent override.

## Antigravity stop

Offer only when the findings show Antigravity present. Ask: "Would you like a local hook to stop the start of a new turn when the conversation transcript exceeds a byte limit you choose, and ask you to run /compact or start a fresh session?" A No leaves it off. Explain that transcript bytes are a rough proxy, exclude the system prompt and are not a token count; recommend no default. Report the stop as "set up", not "enforced": the user-level hooks file and interactive TUI remain unverified; only the workspace hook in Antigravity 1.5.1 `agy -p` was verified.

After a clear yes ask for an integer from 50000 to 20000000 bytes, then run `python3 -I <this skill folder>/scripts/compact_stop_setup.py preview --limit <chosen bytes>`.
The target is fixed at the account home's `.gemini/config/hooks.json`; the file and its folder must be owned by the user, not symlinks, not group- or world-writable, and outside every git work tree (the plugin folder follows the same rule, except Antigravity's own installed copy, which keeps its `.git` directory; a development checkout is refused, so install the plugin into Antigravity first). Show the host section and hooks change, group, absolute command, byte caveat, backup and full `Digest:`, then ask:
"Apply this compaction stop preview?" Only after that yes run `compact_stop_setup.py apply --digest <full digest> --yes`; removal uses `preview --remove` with the same approval. Enforcer: the installer checks the stored private preview, full digest, 60-minute expiry, unchanged files, plugin root, owner, mode and safe paths; it writes the `## Compaction stop` section and its own `finolabs-vibecode-compact-stop` group atomically per file with a hooks backup, leaving the metrics group alone. It requires the whole plugin and an existing safe config folder.
Asking, showing and applying only the approved preview are advisory (agent judgment), including in quick setup.

Enforcer of the hook: `compact_stop_hook.py` acts only on Antigravity `PreInvocation` with `invocationNum` 0, never during a turn or on a tool call, prompt, session start or user stop. It checks only a regular, non-symlink transcript's size within the account's conversation folder, stops once until growth reaches both 10% and 20000 bytes, resets on shrink, and allows on every error, including a failed mark write. It never runs `/compact`, reads transcript content or sends data. `FNL_COMPACT_STOP=off` disables it.

## Steward explanation

Explain `fnl-session-hygiene`'s threshold check after the threshold step; this is advisory (agent judgment), and setup writes nothing new for it. The host enforces the native threshold; `context_steward.py` decides `ok`, `prepare`, `wait` or `compact` and `fnl-session-hygiene` holds its procedure. On `prepare` the working agent writes a private handover before compaction (advisory), while `handover_state.py` enforces its size, safety and lifetime. The session-start script re-injects it only on source `compact`; hook delivery is unverified on every host.
A standalone skill install has no steward scripts and keeps the manual `fnl-session-hygiene` handover procedure (advisory).
