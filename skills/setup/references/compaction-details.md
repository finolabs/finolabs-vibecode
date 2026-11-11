# Compaction implementation details

Read the matching section before preparing or applying that feature’s change. Approval questions stay in [features/compaction.md](features/compaction.md).

## Native threshold preview

Run `python3 -I <this skill folder>/scripts/compact_setup.py preview --host <claude|codex> --tokens <chosen value>`. Claude defaults to the account home's `.claude/settings.json`; with chosen folders pass each as `--folder <absolute config folder>` (at most four, replacing the default). Codex uses an absolute `CODEX_HOME`, otherwise the account home's `.codex/config.toml`. Show every target, existence, key change, backup name, warning and `Digest:`, then ask separately:

## Native threshold apply and enforcers

Only after the yes run `compact_setup.py apply --digest <full digest> --yes`. Even quick setup keeps this approval separate. Removal uses `--off` instead of `--tokens` with the same preview and approval; it removes this key, not auto-compaction. Enforcers: the script checks the private stored plan, full digest, 60-minute expiry, unchanged targets and safe paths, keeps backups and writes atomically; asking and invoking only from a user's `fnl-setup` request are advisory (agent judgment), never a hook.
The host enforces the threshold; it applies to sessions started afterwards, and a running session and the Codex default remain unverified. Never write environment variables or the percent override.


## Antigravity stop preview

After a clear yes ask for an integer from 50000 to 20000000 bytes, then run `python3 -I <this skill folder>/scripts/compact_stop_setup.py preview --limit <chosen bytes>`.
The target is fixed at the account home's `.gemini/config/hooks.json`; the file and its folder must be owned by the user, not symlinks, not group- or world-writable, and outside every git work tree (the plugin folder follows the same rule, except Antigravity's own installed copy, which keeps its `.git` directory; a development checkout is refused, so install the plugin into Antigravity first). Show the host section and hooks change, group, absolute command, byte caveat, backup and full `Digest:`, then ask:

## Steward explanation

Explain `fnl-session-hygiene`'s threshold check (advisory, agent judgment); setup writes nothing new. The host enforces its threshold; `context_steward.py` decides `ok`, `prepare`, `wait` or `compact`. On `prepare` the agent writes a private handover (advisory); `handover_state.py` enforces size, safety and lifetime. SessionStart `source: compact` is the documented delivery path on both hosts (vendor docs, 07/11/2026; Codex 0.167.0); live plugin delivery is unverified.
Claude Code PreCompact stdout feeds summary instructions; on Codex a plain-text reminder does not reach the model. See `fnl-session-hygiene`'s `references/context-settings.md` for vendor sources and limits (07/11/2026). Writing before compaction remains advisory (agent judgment).
A standalone `fnl-session-hygiene` install includes its context reader and steward scripts; automatic handover re-injection still requires the plugin. Standalone setup keeps the manual status-line procedure above (advisory, agent judgment).
