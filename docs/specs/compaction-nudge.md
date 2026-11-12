# Compaction nudge: tell the agent before the host compacts

Status: accepted; rule recorded as the eighth scoped exception in `CLAUDE.md` (owner decision 2026-11-12); no code yet.

## Why

A long session reaches the host's compaction threshold with no handover saved, so the summary is the only memory of the goal, the settled decisions and the work in flight. On 2026-11-12 a coordinator session reached 881k of 1M tokens before the user compacted by hand. Three facts make this a gap, not bad luck:

- `PreCompact` runs after compaction has started. Claude Code uses its stdout as summary instructions, not as model context, so the agent has no turn left to write a handover; Codex ignores plain PreCompact stdout.
- The context checks in `session-hygiene` (about 60% to consider a boundary, `prepare` at 80% of the chosen threshold) and in `coding-router` are agent judgment: nothing starts them.
- A host setting can make the configured window inert (`autoCompactEnabled: false`, `DISABLE_AUTO_COMPACT`), and nothing tells the user.

## Three layers

| When | Mechanism | What it does |
| --- | --- | --- |
| Before (80% and 90% of the threshold) | the compaction nudge (this spec) | one fixed line tells the agent to run `session-hygiene` now: save the handover, write back decisions and lessons, record the state of background runs and open pull requests, then offer compaction or a fresh session |
| During | `PreCompact` (`precompact.py`) | tells the summarizer what the summary must keep: goal and acceptance, settled decisions with dates, work in progress, open runs and pull requests, the next action, and whether a handover was saved |
| After | `SessionStart` with source `compact` | re-injects the saved handover (existing) |

## Design

- Hook: `UserPromptSubmit` in its own group of the Claude Code manifest, `python3 -I scripts/compact_nudge.py; exit 0`. Never in the metrics group.
- Used tokens: from the hook input's `transcript_path`, open the file only when it is a regular file, not a symlink, and its resolved path lies inside `<config dir>/projects/` (the default `~/.claude` or `CLAUDE_CONFIG_DIR`). Read at most the last 256 KiB, split on newlines, parse each complete line as JSON, and take the latest entry whose type is an assistant message with a `message.usage` object. Used tokens are `input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens`, each a non-negative integer; anything else is skipped. No other field is kept.
- Threshold, first match wins: auto-compaction off (`DISABLE_AUTO_COMPACT` set to a true value, or `autoCompactEnabled` false in the most specific settings file that sets it) means print nothing; `CLAUDE_CODE_AUTO_COMPACT_WINDOW` when a valid integer; `autoCompactWindow` from local, project, then user settings (managed settings when readable win over all three); else the host default, which the spec records only after it is read from the host's documentation, and until then print nothing. `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, when a valid percent, lowers the threshold to that share. Settings files are read with the plugin's bounded safe reader and only those two keys are taken.
- Bands: 80 and 90 percent of the threshold. The hook prints when the current band is higher than the stored band for this session. A used count lower than at the last print (a compaction happened) resets the stored band to 0.
- Message, fixed text with one integer: "Context is at <n>% of this session's compaction threshold. Before the host compacts, run session-hygiene now: save the handover, write back decisions and lessons, note background runs and open pull requests, then offer to compact or start a fresh session." The skill name follows the rename to `tidy` when it lands.
- Mark: one integer, written atomically with mode 0600 in `<data root>/state/compaction-nudge/<sha256(session id)[:16]>`, at most 200 files, oldest removed first. The mark is written before printing; if it cannot be written, print nothing.
- Failure: any error, a missing or unsafe file, an unparsable count or an unresolved threshold prints nothing and exits 0. `FNL_COMPACT_NUDGE=off` disables it.
- Not covered: Codex (check whether its `UserPromptSubmit` delivers `additionalContext` before adding it) and Antigravity (keeps the opt-in compaction stop).

## Tests to write with the code

- Synthetic transcripts: latest assistant usage at 79%, 80%, 89%, 90% and after a drop; a symlinked transcript; a path outside `projects`; a 10 MB file read only at its tail; a line carrying text content beside usage, asserting no content reaches output or the mark.
- Threshold resolution with synthetic settings files and synthetic environments (names and integers only): each precedence step, auto-compaction off, override percent, invalid values.
- Mark: written before print, unwritable mark prints nothing, reset on drop, eviction.
- Manifest: the hook sits in its own group and the script always exits 0.

## Unverified

- Live delivery of `UserPromptSubmit` stdout into the model context in the desktop app and the CLI.
- The transcript's `usage` field names on future Claude Code versions; a changed shape prints nothing rather than a wrong number.
- The host's default compaction threshold when no setting is present.
