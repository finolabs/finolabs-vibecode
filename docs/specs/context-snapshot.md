# Context snapshot

Status: implemented; for release 0.2.0, targeted local fixtures pass. Live status-line payloads on the installed Claude Code and Antigravity versions, user-owned status-line composition and hook delivery remain unverified.

Owner decisions: Fio, 07/11/2026: measure the context window with a script, surface the number and ship it in 0.2.0. This document records the settled design, not a new compaction actuator.

## Goal and host limits

Give the agent real context counts for the existing steward table, without reading conversation content. No hook payload carries context size. Claude Code exposes it only to the user's status-line command as JSON on stdin: `context_window.used_percentage`, `context_window.context_window_size`, `context_window.current_usage` with `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`, plus `session_id`, `transcript_path` and `version`.

Used tokens are input + cache creation + cache read of the last main-conversation response. Output is excluded; percentage is calculated from those counts rather than trusting `used_percentage`. The reading is not a cumulative conversation sum or a continuously updated meter. `current_usage` is null before the first call and immediately after `/compact`; the status line runs after each assistant message, after `/compact` and on resume. These are the documented input contract supplied for this build; this package has not verified live delivery on the installed version.

A plugin cannot declare `statusLine`. Setup must offer a user-owned settings command. No transcript JSONL is read: its internal format and content are outside this design. Antigravity is covered by the extension in part 5. Codex has no equivalent status-line signal and stays out of scope; Antigravity retains its separate transcript-size proxy stop.

## 1. Recorder, reader and steward input

`scripts/context_snapshot.py` uses only the Python standard library, no subprocess and no network. The standalone copy in `fnl-session-hygiene` uses identical `data_root.py` and `context_steward.py` copies.

- `record [--host claude|antigravity] [--line]` reads one UTF-8 JSON object from stdin, at most 64 KiB. Invalid, oversized or duplicate-key JSON writes nothing. Invalid session/window data writes nothing. Null, missing, non-integer, negative or unreasonably large usage clears that session's old snapshot without creating a directory merely to clear it; an unsafe snapshot is never removed. Booleans are not integers. A valid reading stores only `used`, `window`, whole `percent` (integer floor), UTC `measured`, short numeric host `version` (sanitized to `unknown` if unsupported) and the explicit `host` (`claude` by default). Window is a positive integer up to 10 million; used is between zero and ten windows, matching the steward's upper bound. No output by default; `--line` emits one ASCII line such as `ctx 62%` only after a successful write. Record always exits 0 and errors disclose no input.
- The path is `<data root>/state/context/<sha256(session_id)[:16]>.json`, mode 0600 in a 0700 folder. `data_root.py` resolves from the account database and validates the pointer, owner and ancestors; environment variables cannot redirect trusted state. Descriptor-relative no-follow operations reject symlinks, wrong owners, non-regular files, extra hard links and non-private snapshots. A directory lock serializes scan/evict/write. At most 20 snapshots remain, oldest by mtime evicted first, before the atomic write so the cap also holds if a write fails. `data_root.atomic_write` fsyncs and replaces a temporary 0600 file; failed replacement leaves the target intact and removes its temporary file. An eviction can remain after a later write failure.
- `read --session <id> [--max-age-seconds N]` prints exactly `used`, `window`, `percent`, integer `age_seconds` and `stale: false` as JSON. Default maximum age is 3600 seconds, inclusive; an explicit integer from 0 to 86400 is accepted. Missing, unsafe, invalid, future-dated or older snapshots return exit 3 and the same fixed stderr message, with no JSON. `stale: true` is never returned because stale numbers are refused. Expiry does not automatically delete snapshots.
- `check --session <id> --threshold <tokens> [--boundary yes|no|unknown]` reads with the same freshness policy, imports the unchanged `context_steward.check` and prints its JSON `action` and `reason`. It accepts `--max-age-seconds` too. Missing counts or an invalid threshold return exit 3 with the same refusal, never invented numbers. The script never compacts or starts a session.

Both `read` and `check` also accept `--latest`, mutually exclusive with `--session`. It selects the newest safe snapshot by mtime, breaking ties by hashed filename; an invalid or stale newest reading is refused, without falling back to older data. It reads whichever session wrote last: after a session's own snapshot is cleared (after `/compact`), `--latest` can return another session's fresh reading, which is the stated parallel-session limit. Unsafe snapshot entries make latest selection fail closed.

### Why latest

The hook's session id is not exposed to the model. `--latest` is simpler than introducing a second session token and avoids leaking the id into SessionStart output; it fits the usual single active session. It does not prove session identity with parallel sessions. The skill requires the agent to disclose this ambiguity and use a known host-provided id or report that its own reading is unavailable. The SessionStart line is always scoped to the starting session, unlike `--latest`. All use of these readings for a work boundary is advisory, enforced by agent judgment; the scripts enforce storage, freshness, input validation and the deterministic action table.

## 2. SessionStart

The existing `scripts/session_start.py` reads its bounded hook stdin, uses that event's session id for a local snapshot read, and appends to Plugin state:

`Context: 62% of a 200000 window, read 12s ago (status line)`

Every source qualifies except `compact`: right after a compaction the only snapshot is the pre-compact one, so no Context line is printed until the status line records a new reading. Missing ids/readings, expired snapshots, unsafe state, invalid or oversized stdin and all errors add nothing. It makes no network call, starts no process, writes no state and still exits 0. Existing handover re-injection remains scoped to source `compact`; hook declarations are unchanged. The Context line is a start-time observation, not a promise of current usage later in the session.

## 3. Session hygiene

`fnl-session-hygiene` replaces the absolute claim that an agent cannot see its own percentage with the conditional reader/check procedure. A correctly identified fresh snapshot supplies real numbers to the steward; without it the agent says that a reading is unavailable. About 60% remains advisory, not an enforced trigger. The user chooses the threshold, the host enforces its native threshold, the steward script chooses its action, the judge can inform an uncertain boundary, and the agent writes the handover and requests compaction. No new autonomous command or blocking hook is added.

## 4. Setup

`fnl-setup` compaction offers Context reading through a separate neutral Yes/No question and a preview, including Quick setup. The separate plan approval remains mandatory by agent judgment. `statusline_setup.py` supports only `preview`, `preview --remove`, and `apply --digest <full 64-hex digest> --yes`.

The default settings file is the account home's `.claude/settings.json`. `--folder` selects one to four existing config folders, replacing the default, under exactly the compaction writer's path rules: absolute, owned, no symlinks, no group/world writes, outside git work trees. No credential file is accessed. The writer reuses `compact_setup.py` helpers for checked paths, duplicate-safe finite JSON parsing, hashing, plan safety, backup names and atomic target writes. A byte-identical root copy of that helper supports the new root command; the existing standalone helper is unchanged.

With no status line in any selected target, preview shows every target, existence, command and backup, and saves a private digest-bound plan under `<data root>/state/statusline/preview.json`. The command is `python3 -I <shell-quoted absolute plugin>/scripts/context_snapshot.py record --host claude --line`, represented in settings as `{"type":"command","command":"..."}`. The installed full-plugin path is required; standalone setup documents the manual procedure instead. Apply validates the full digest, explicit yes, unchanged install command, unchanged root, plan no older than 60 minutes and unchanged target hashes/modes. All targets are checked before the first write. Existing settings get unique adjacent backups; backups and new settings are 0600. Each file is replaced atomically, not a multi-file transaction; a failure on a later target can leave earlier targets applied. On success the preview is deleted.

With any existing `statusLine`, even null, preview saves no new plan, changes no settings and prints an exact manual recipe. It never prints the user's command. The recipe uses a private `mktemp` file and EXIT cleanup to give the identical stdin JSON first to the silent `record` command, then to the user's existing command, which alone renders the line. Setup does not install a wrapper or edit the existing line. The user must compose and verify it by hand. Removal refuses a different status-line value and removes only the exact recorder command from this installation after the same preview/approval flow. Removing the command leaves snapshots until manually deleted or evicted.

### CLAUDE.md analysis

No change is required or made: this feature has no network call, no subprocess, no transcript-content read, no new hook and no new command launched by the plugin. The command is the user's own configured status line. Settings writes follow an explicit setup request and approved preview, as existing setup writers do. The private context counts and configuration preview are documented in `PRIVACY.md`.

## 5. Antigravity (owner decision, 07/11/2026)

Extend the same recorder to Antigravity because its documented status-line stdin exposes the same context fields. [Official status-line documentation](https://antigravity.google/docs/cli/statusline/), fetched 07/11/2026, confirms the settings target and object shape below. There is no shape or path difference from the package brief. The docs also expose a compatibility `session_id`; this recorder deliberately uses only `conversation_id` for Antigravity. Live Antigravity payloads and `invocationNum` semantics remain unverified.

### Recorder and reader

`record --host antigravity` uses a required nonempty `conversation_id`, never guesses the host and never falls back to `session_id`. It computes used tokens from `current_usage.input_tokens + cache_creation_input_tokens + cache_read_input_tokens`, excluding output, totals and reported percentages. Bounds, version sanitization, failure behavior, private storage and the shared 20-file cap are unchanged. A zero window means unknown: valid usage with window zero writes nothing and preserves any previous reading. Null or invalid usage still clears only that host's matching reading, including with window zero. Missing conversation ids write and clear nothing.

The only stored change is `host: antigravity`; no field is added. Claude filenames remain `sha256(session_id)[:16]`; Antigravity filenames are `sha256("antigravity:" + conversation_id)[:16]`, with the same `.json` suffix. Neither id is retained in plaintext.

`read` and `check` accept optional `--host claude|antigravity`. With `--session <id>`, the host selects the filename namespace and must match the stored host; the default is Claude. With `--latest --host antigravity`, only snapshots labeled Antigravity participate in newest selection; `--host claude` selects Claude. Without a host, latest still selects the newest of either host. Outputs are exactly the existing read/check JSON, without a host key. The newest matching stale or invalid reading is refused without fallback. Unsafe files or unreadable host metadata fail closed even during filtering. A host filter narrows the parallel-session ambiguity, but cannot identify one session among several of that host.

### Separate setup consent and fixed target

When Antigravity is present, setup offers context reading with its own neutral Yes/No consent and a separately approved preview, including Quick setup. `statusline_setup.py preview --host antigravity` has one fixed target: the account home's `.gemini/antigravity-cli/settings.json`; `--folder` is refused. Apply and removal also require `--host antigravity`. The default host remains Claude for every setup action. The host is bound into the saved digest; applying with a different host is refused.

The target and folder follow `compact_stop_setup.py` safety rules: user-owned, no symlinks, no group/world writes, outside every git work tree. The plugin root follows the same checks, with only Antigravity's own account-home `.gemini/config/plugins/finolabs-vibecode` installation allowed to retain a real `.git` directory; its ancestors must remain safe and outside git. A development checkout is refused, so install the plugin into Antigravity first. Script and script-folder ownership, modes and symlinks are checked too. The existing safe settings folder must already exist.

The command is `python3 -I <shell-quoted absolute plugin>/scripts/context_snapshot.py record --host antigravity --line`, stored as `{"type":"command","command":"..."}`. Antigravity documents this same object shape as Claude. It invokes the command at most every 300 ms, kills it after 5 seconds and disables it after 30 consecutive failures. The recorder retains exit 0 and silent failure behavior.

The writer accepts strict JSON objects only (no duplicate keys, non-finite numbers or comments), preserves every other settings value in meaning, and keeps the existing preview, full digest, 60-minute expiry, backup, atomic write and exact-match removal rules. In particular Antigravity allow-rules are preserved; setup never prints other settings values or the existing command. Any existing `statusLine`, including null, means recipe only: the silent recipe passes `--host antigravity` and saves no new plan. Claude's generated command and recipe now also spell out `--host claude`. Pre-extension previews must be generated again; old commands can be removed by hand if they no longer match exactly.

### Scope and evidence

SessionStart's Context line stays Claude-only; there is no Antigravity SessionStart hook here. The Antigravity compaction stop continues to measure transcript size and is unchanged. Token snapshots do not alter that hook, run `/compact`, or create a new actuator. Fixture tests use synthetic account homes and temp data roots; no real settings, credential files or conversation contents are read. Independent code/security review and integration remain with the coordinator.

## Verification and remaining limits

Local fixture modules cover valid input and exclusion of output/reported percentage; invalid and oversized input; null usage invalidation; private modes; atomic replacement/failure; oldest-first 20-file retention; missing/stale/future readings; steward actions; symlinks, wrong owners and another user's file; safe latest selection; fresh-session-only SessionStart output; settings preview/apply/remove/backup; existing status-line preservation; expiry, digest and changed-target refusal. Tests use a synthetic account database and temporary roots, never real Claude settings, home/data writes, credentials or transcript reads. Shared-copy parity and reference validation also run.

Still unverified: live status-line JSON on the installed Claude Code and Antigravity versions; Antigravity `invocationNum` semantics; composition with a user-owned status line; live SessionStart delivery/order after resume or compact; Windows (directory locks use `fcntl`). The reading remains forgeable by the same OS user and advisory, not an authorization or billing fact. Independent code/security review and integration belong to the coordinator; no push or release is performed here.
