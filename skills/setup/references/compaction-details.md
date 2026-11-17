# Compaction implementation details

Read the matching section before preparing or applying that feature’s change. Approval questions stay in [features/compaction.md](features/compaction.md).

## Recommended threshold

The one place for the suggested numbers; they are advisory (agent judgment), never a default. Show the row that fits the session kind the user describes, with its reason, before the token question; never preselect or prefill a value, and preview only the number the user typed. The nudge prints at 80% and again at 90% of the threshold, so about a fifth of the threshold is left for the `tidy` handover whatever the user picks.

| Session kind | Suggested threshold | Reason |
| --- | --- | --- |
| Coordinator (many pull requests, a ledger, background reviews) on a 1M-window model | about 300000 to 500000 tokens | Its state lives in the ledger and the handover, not the conversation; compacting this early keeps the summary small, and the nudge at 240000 to 400000 leaves room for the handover, where the host default (about 967000) compacts very late. |
| Single-task implementation on a 1M-window model | later, about 600000 to 800000, or the host default with a fresh session per story | One task's context stays relevant longer, and `tidy` already advises a fresh session per story over a compaction. |
| A smaller window (for example 200000 tokens, or a Codex model) | about 70% to 80% of the window | Leaves the 80% nudge band room for a handover before the host compacts; Claude Code accepts no less than 100000. |

Scope follows the session kind: a coordinator that always runs in one repository fits that repository's local file; one value for every repository fits user scope; Claude Code's `--autocompact <tokens>` launch flag sets one session only (see `tidy`'s context settings).

## Native threshold preview

Run `python3 -I <this skill folder>/scripts/compact_setup.py preview --host <claude|codex> --tokens <chosen value>`. Claude defaults to the account home's `.claude/settings.json`; with chosen folders pass each as `--folder <absolute config folder>` (at most four, replacing the default). Codex uses an absolute `CODEX_HOME`, otherwise the account home's `.codex/config.toml`. For this repository only (Claude Code), pass `--project <absolute repository root>` instead of `--folder`: the target is `<root>/.claude/settings.local.json`. The script refuses a path that is not the checkout root and a file listed in Git's index (it would not stay on this machine), and creates `.claude` (mode 0700) only when applying; it never changes Git files, so if `git status` lists the new file, say it can go in `.git/info/exclude`. Show every target, scope, existence, key change, backup name, warning and `Digest:`, then ask separately:

## Native threshold apply and enforcers

Only after the yes run `compact_setup.py apply --digest <full digest> --yes`. Even quick setup keeps this approval separate. Removal uses `--off` instead of `--tokens` with the same preview and approval; it removes this key, not auto-compaction. Enforcers: the script checks the private stored plan (its scope included), full digest, 60-minute expiry, unchanged targets and safe paths (for `--project`, the checkout root and that the file is not in Git's index, again at apply), keeps backups and writes atomically; asking and invoking only from a user's `setup` request are advisory (agent judgment), never a hook.
The host enforces the threshold; it applies to sessions started afterwards, and a running session and the Codex default remain unverified. Never write environment variables or the percent override.


## Antigravity stop preview

After a clear yes ask for an integer from 50000 to 20000000 bytes, then run `python3 -I <this skill folder>/scripts/compact_stop_setup.py preview --limit <chosen bytes>`.
The target is fixed at the account home's `.gemini/config/hooks.json`; the file and its folder must be owned by the user, not symlinks, not group- or world-writable, and outside every git work tree (the plugin folder follows the same rule, except Antigravity's own installed copy, which keeps its `.git` directory; a development checkout is refused, so install the plugin into Antigravity first). Show the host section and hooks change, group, absolute command, byte caveat, backup and full `Digest:`, then ask:

## Steward explanation

Explain `tidy`'s threshold check (advisory, agent judgment); setup writes nothing new. The host enforces its threshold; `context_steward.py` decides `ok`, `prepare`, `wait` or `compact`. On `prepare` the agent writes a private handover (advisory); `handover_state.py` enforces size, safety and lifetime. SessionStart `source: compact` is the documented delivery path on both hosts (vendor docs, 07/11/2026; Codex 0.167.0); live plugin delivery is unverified.
Claude Code PreCompact stdout feeds summary instructions; on Codex a plain-text reminder does not reach the model. See `tidy`'s `references/context-settings.md` for vendor sources and limits (07/11/2026). Writing before compaction remains advisory (agent judgment).
A standalone `tidy` install includes its context reader and steward scripts; automatic handover re-injection still requires the plugin. Standalone setup keeps the manual status-line procedure above (advisory, agent judgment).
