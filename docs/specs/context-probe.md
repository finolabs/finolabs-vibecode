# Context probe: read the session's context size from the host CLI

Status: accepted; owner decision 2026-11-11, scoped exception recorded in `CLAUDE.md`; no code yet.

## Why

`fnl-session-hygiene` needs a real context reading to decide when to prepare a handover or compact. The status-line recorder (`context-snapshot.md`) only works where the host delivers status-line input; its delivery in the Claude Code desktop app is undocumented, and the desktop session observed on 2026-11-11 had no fresh snapshot (exit 3 from `read --latest`). Local usage data from November 2026 showed no model-initiated call of `fnl-session-hygiene`.

## Owner decision (2026-11-11)

The skill triggers a command that asks the host CLI for the current session's context. Checked by hand that day:

- Claude Code 2.1.322: `claude -p /context --resume <id> --fork-session --no-session-persistence --output-format json` printed `Tokens: 412.1k / 1m (41%)` for a live desktop session with `num_turns` 0, so no model turn ran; quota use was not measured.
- Codex 0.167.1: `codex app-server`, after `initialize`, `initialized` and `thread/resume` of a thread, sent `thread/tokenUsage/updated` with `modelContextWindow` 475000 and `last.totalTokens` 36528, with no turn. The thread goal read `null` before and after, and the thread's rollout file was not modified. The server started the user's configured MCP servers even with `-c mcp_servers={}`.
- Antigravity 1.5.5: `agy -p /context` is refused in print mode ("opens the interactive context breakdown"); not covered.

## Design

- `context_snapshot.py probe --host claude|codex --session <id>`: run once, parse only the used and window counts, write them through the existing snapshot writer with its existing fields (used, window, whole percent, measured time, short sanitized version, host; Codex stored as host `codex`, which the reader and its tests must accept) and its file rules, freshness and retention, print the same JSON as `read`, and exit 3 with a fixed message on any failure. `check` can then feed the steward.
- Claude: parse the `Tokens: <used> / <window>` line of the `/context` result; keep no category rows.
- Codex: the fixed payloads in `CLAUDE.md`, sent in that order: a constant `initialize`, `initialized`, `thread/read` and `thread/goal/get` for the session's thread; stop with exit 3 unless the thread status is idle or not loaded and the goal is null; then `thread/resume` with only `threadId`; take `last.totalTokens` as used and `modelContextWindow` as window from the first `thread/tokenUsage/updated` for that thread; ignore every server request; stop the process group after the first reading or 30 seconds.
- Session id: the session-start hook prints one line `Session id: <id>` (Claude `session_id`, Codex thread id) so the model can pass its own id; the hook validates the id's character set and length before printing it and prints nothing otherwise. The id then sits in the host's model context, which the host may keep; this is a change from the snapshot design, which avoided exposing the id.
- Executables are resolved and confirmed in `fnl-setup` as the quota probe does; the probe refuses an unconfirmed path.
- `FNL_CONTEXT_PROBE=off` disables it; the probe is never run from a hook, a timer or a worker.

## Open

- Live behavior on a Codex thread that has a goal set is unverified.
- Whether a Codex resume can change thread metadata in other states (archived, running, goal set) is unverified; the probe refuses those states before resume.
