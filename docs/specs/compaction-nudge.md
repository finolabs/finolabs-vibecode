# Compaction nudge: tell the agent before the host compacts

Status: accepted; rule recorded as the eighth scoped exception in `CLAUDE.md` (owner decision 2026-11-12, Codex clause 2026-11-15, per-model clause 2026-11-18); code landed for 0.2.5, the Codex hook for 0.3.1 (`--host codex`) (`scripts/compact_nudge.py`, `tests/test_compact_nudge.py`; `precompact.py` reworded as the "During" row says).

## Why

A long session reaches the host's compaction threshold with no handover saved, so the summary is the only memory of the goal, the settled decisions and the work in flight. On 2026-11-12 a coordinator session reached 881k of 1M tokens before the user compacted by hand. Three facts make this a gap, not bad luck:

- `PreCompact` runs after compaction has started. Claude Code uses its stdout as summary instructions, not as model context, so the agent has no turn left to write a handover; Codex ignores plain PreCompact stdout.
- The context checks in `tidy` (about 60% to consider a boundary, `prepare` at 80% of the chosen threshold) and in `coding-router` are agent judgment: nothing starts them.
- A host setting can make the configured window inert (`autoCompactEnabled: false`, `DISABLE_AUTO_COMPACT`), and nothing tells the user.

## Three layers

| When | Mechanism | What it does |
| --- | --- | --- |
| Before (80% and 90% of the threshold) | the compaction nudge (this spec) | one fixed line tells the agent to run `tidy` now: save the handover, write back decisions and lessons, record the state of background runs and open pull requests, then offer compaction or a fresh session |
| During | `PreCompact` (`precompact.py`) | tells the summarizer what the summary must keep: goal and acceptance, settled decisions with dates, work in progress, open runs and pull requests, the next action, and whether a handover was saved |
| After | `SessionStart` with source `compact` | re-injects the saved handover (existing) |

## Design

- Hook: `UserPromptSubmit` in its own group of the Claude Code manifest, `python3 -I scripts/compact_nudge.py; exit 0`. Never in the metrics group.
- Used tokens: from the hook input's `transcript_path`, open the file only when it is a regular file, not a symlink, and its resolved path lies inside `<config dir>/projects/` (the default `~/.claude` or `CLAUDE_CONFIG_DIR`). Read at most the last 256 KiB, split on newlines, parse each complete line as JSON, and take the latest entry whose type is an assistant message with a `message.usage` object. Used tokens are `input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens`, each a non-negative integer; anything else is skipped. From the same entry only the model id is also taken, as the per-model section below says; no other field is kept.
- Threshold, first match wins: auto-compaction off (`DISABLE_AUTO_COMPACT` set to a true value, or `autoCompactEnabled` false in the most specific settings file that sets it) means print nothing; `CLAUDE_CODE_AUTO_COMPACT_WINDOW` when a valid integer; `autoCompactWindow` from local, project, then user settings (managed settings when readable win over all three), where a file's `modelSettings.<model>.autoCompactWindow` for the session's model wins over that file's top-level value (per-model section below); else the host default, which the spec records only after it is read from the host's documentation, and until then print nothing. `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, when a valid percent, lowers the threshold to that share. Settings files are read with the plugin's bounded safe reader and only `autoCompactEnabled`, `autoCompactWindow` and the session model's `modelSettings.<model>.autoCompactWindow` are taken.
- Bands: 80 and 90 percent of the threshold. The hook prints when the current band is higher than the stored band for this session. A used count lower than at the last print (a compaction happened) resets the stored band to 0.
- Message, fixed text with one integer: "Context is at <n>% of this session's compaction threshold. Before the host compacts, run tidy now: save the handover, write back decisions and lessons, note background runs and open pull requests, then hand the user a ready /compact line that names the saved handover, or offer a fresh session." The skill was `session-hygiene` until its rename to `tidy` in 0.2.5.
- Mark: one integer, written atomically with mode 0600 in `<data root>/state/compaction-nudge/<sha256(session id)[:16]>`, at most 200 files, oldest removed first. The mark is written before printing; if it cannot be written, print nothing.
- Failure: any error, a missing or unsafe file, an unparsable count or an unresolved threshold prints nothing and exits 0. `FNL_COMPACT_NUDGE=off` disables it.
- Not covered: Antigravity (keeps the opt-in compaction stop). Codex: section "Codex" below.

## Per-model threshold (Claude Code)

Owner decision 2026-11-18: follow Claude Code's own per-model threshold. `/autocompact <tokens>` saves `modelSettings.<model>.autoCompactWindow` in the user's `settings.json` (checked on 2.1.325 in a throwaway `CLAUDE_CONFIG_DIR`: after `/autocompact 500000` on Opus 5.5, `/context` showed 500k for Opus and the 700k top-level value for Sonnet), so a value set "for this session" applies to every later session on that model, and the nudge, reading only the top-level key, printed too late.

- Model id: hook input carries none on 2.1.325 (`SessionStart` and `UserPromptSubmit` keys were checked with a probe hook), so the nudge takes `message.model` from the same latest assistant entry that gives the usage counts, only when it fully matches `[a-z0-9][a-z0-9.\[\]-]{0,63}`; it is used only as an exact dictionary key of `modelSettings` (dots and brackets are literal key characters, never path syntax), in memory, and never stored, logged, printed or sent. No assistant entry yet, or no valid id, means no per-model lookup.
- Precedence, measured with `/context` on 2.1.325: as a threshold source `CLAUDE_CODE_AUTO_COMPACT_WINDOW` wins over every settings value (the off switches and the percent override still apply as Design says); otherwise the files are taken in the order managed, local, project, user, and the first file holding a value that applies wins; within one file the per-model value for the session's model wins over its top-level `autoCompactWindow`. (A local top-level 600000 beat a user per-model 500000; a local per-model 300000 for Sonnet applied to Sonnet only, and Opus then fell through to the user per-model 500000.)
- Setup: `compact_setup.py preview --model <id>` writes `modelSettings.<id>.autoCompactWindow` instead of the top-level key, after the same digest-bound approval; `--clear-model-overrides` stays. The preview still prints only the count of models that carry their own value, never a key: a key matching the pattern can still hold arbitrary text (`compaction-threshold.md`).
- Unverified: whether a model id with a context-size suffix (such as `[1m]`) is the key Claude Code uses; a mismatch makes the nudge fall back to the top-level value.

## Codex

Owner decision 2026-11-15; the rule is the Codex clause of the eighth scoped exception in `CLAUDE.md`.

- Delivery: Codex 0.167's hook documentation lists `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, `turn_id` and `prompt` on stdin for `UserPromptSubmit`, and adds plain stdout of an exit-0 hook to the model's context as developer text. Exit 2 or `"decision": "block"` would block the prompt; the hook never uses either and always exits 0.
- Hook: `UserPromptSubmit` in its own group of `.codex-plugin/hooks.json`, `python3 -I scripts/compact_nudge.py --host codex; exit 0`. Never in the metrics group.
- Used tokens: open `transcript_path` only when it is a regular file, not a symlink, and its resolved path lies inside `<Codex home>/sessions/` (`CODEX_HOME`, else `~/.codex`). Read at most the last 256 KiB, parse each complete line as JSON, and take the latest entry whose `payload.type` is `token_count` with a non-null `payload.info`. Used tokens are `info.last_token_usage.total_tokens`, the window is `info.model_context_window`, each a positive integer within the existing bounds; nothing else is kept.
- Threshold: the top-level integer `model_auto_compact_token_limit` of `<Codex home>/config.toml`, read with the bounded safe reader and parsed with `tomllib`, the only key taken; a value above 90% of the window, or none, gives 90% of the window, which is how Codex resolves it (`ModelInfo::auto_compact_token_limit` in `codex-rs/protocol/src/openai_models.rs` on openai/codex main, read 2026-11-15: the smaller of the configured limit and 9/10 of the resolved context window; unverified on each installed version, and the transcript's `model_context_window` may differ from the resolved window). A value under a `[profiles.*]` table is not read. A file that cannot be parsed gives nothing (print nothing).
- Bands, message, mark (same folder, keyed by a hash of the Codex session id), failure and `FNL_COMPACT_NUDGE=off`: as for Claude Code.
- Unverified: live delivery in the Codex CLI and app; the `token_count` shape on later Codex versions (a changed shape prints nothing); whether a profile or project config changes the effective limit.

## Tests to write with the code

- Synthetic transcripts: latest assistant usage at 79%, 80%, 89%, 90% and after a drop; a symlinked transcript; a path outside `projects`; a 10 MB file read only at its tail; a line carrying text content beside usage, asserting no content reaches output or the mark.
- Threshold resolution with synthetic settings files and synthetic environments (names and integers only): each precedence step, auto-compaction off, override percent, invalid values.
- Mark: written before print, unwritable mark prints nothing, reset on drop, eviction.
- Manifest: the hook sits in its own group and the script always exits 0.

## Unverified

- Live delivery of `UserPromptSubmit` stdout into the model context in the desktop app and the CLI.
- The transcript's `usage` field names on future Claude Code versions; a changed shape prints nothing rather than a wrong number.
- The host's default compaction threshold when no setting is present.
