# Antigravity compaction stop

Status: implemented; local size-only hook and previewed installer; live user-level hook delivery, TUI behavior and the usefulness of a byte limit remain unverified.

Decision: 2026-11-06, owner: a second blocking hook, scoped by the second
exception in `CLAUDE.md` (merged). This spec comes before any code and carries the
`PRIVACY.md`, README and `setup` changes. Claude Code and Codex use host
thresholds written by `setup` (`compaction-threshold.md`); no Antigravity threshold is documented through 1.5.3.

## Vendor contracts researched 07/11/2026 (Antigravity 1.5.3)

Official [hooks docs](https://antigravity.google/docs/hooks) confirm the user-level file `~/.gemini/config/hooks.json`; `~/.gemini/antigravity-cli/settings.json` is not loaded for hooks. Payload fields are `conversationId`, `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, `modelName`, `lastUserInput`; PreInvocation and PostInvocation add 0-indexed `invocationNum` and `initialNumSteps`, with no token or context fields. Whether `invocationNum` resets per user turn is not documented: the implementation's first-call-of-turn assumption remains unverified.

Hook stdout is JSON: PreInvocation supports `injectSteps` and `terminationBehavior` (`terminate` or default). Plain printed text is not documented as reaching the model. Release 1.5.3, installed at research time, adds `PLUGIN_ROOT` and `PLUGIN_DATA` environment variables for plugin hook commands; these documentation facts do not verify this plugin live. The 1.5.1 observations below remain historical observations, not 1.5.3 runs.

The [context-command docs](https://antigravity.google/docs/cli/commands/context/) and release notes through 1.5.3 document automatic compaction, `/context` usage and `/clear`, `/new`, `/fork`, `/rewind` context controls; no threshold or off switch. `/compact` was not found and may not exist; offer `/new` or `/fork`. The fixed hook message below still names `/compact`; changing that script string needs an owner decision and is outside this docs-only package.

## Verified on 2026-11-06 (throwaway workspace, Antigravity 1.5.1, `agy -p`)

- Hooks from `<workspace>/.agents/hooks.json` ran with no trust prompt. Every event
  receives `conversationId`, `transcriptPath`, `workspacePaths`, `modelName`,
  `lastUserInput`; `PreInvocation` and `PostInvocation` add `invocationNum` and
  `initialNumSteps`.
- `transcriptPath` was a regular file under
  `~/.gemini/antigravity-cli/brain/<conversationId>/.system_generated/logs/`, and
  its size grew with each turn (588, then 777 bytes).
- The conversation id was a 36-character lower-case hex-and-dash UUID, and the transcript file was named
  `transcript_full.jsonl`.
- A `PreInvocation` hook answering
  `{"injectSteps":[{"errorMessage":{"userMessage":"…"}}],"terminationBehavior":"terminate"}`
  ended the turn before the model ran; the user saw the message and `-p` reported
  `status: ERROR`. The same hook ran on a resumed conversation.
- The transcript measures conversation content, not the whole context: 777 bytes of
  transcript against 26,108 input tokens, most of it the fixed system prompt. A
  byte limit is a rough proxy and must be presented as one.
- Consistent with, not proof of: `invocationNum` was 0 on both resumed turns, so it appears to restart
  at each user turn.
- Not verified live: the same hook in the documented user-level `~/.gemini/config/hooks.json`, and the interactive TUI;
  setup text must therefore say "set up", not "enforced", until it is.

## Parts

### 1. Hook `scripts/compact_stop_hook.py` (stdlib, no network, no subprocess)

Runs on Antigravity `PreInvocation` only. Reads the event from stdin (64 KiB bound,
select with a 0.5 s wait, as `session_start.py` does). It acts only when
`invocationNum` is 0, before that model invocation. This is intended to select the start of a user turn, but the reset semantics are undocumented; the claim that it never stops mid-turn remains unverified. Always exits 0 and prints exactly `{}` unless it stops the turn.

Decision, in this order; any failure allows:
1. `FNL_COMPACT_STOP=off` allows.
2. The data root resolves and `host.md` has the section `## Compaction stop` with
   `Enabled: yes` and `Limit bytes: <integer>` within the bounds below; otherwise allow.
3. `lstat` the `transcriptPath` as given: it must be a regular file, not a symlink; then its realpath
   must equal `~/.gemini/antigravity-cli/brain/<conversationId>/.system_generated/logs/transcript_full.jsonl`
   under the account home, with `conversationId` matching `^[0-9a-f-]{36}$`. Only its size is read.
   Anything else allows.
4. Size at or below the limit allows.
5. The mark for this conversation is `<data root>/state/compact-stop/<first 16 hex
   of sha256(conversationId)>.json` (0600, private folder, opened with no-follow semantics) holding only the integer size
   at the last stop. With a mark: a size below the mark resets it (allow); stop again
   only when the size is at least 10% and at least 20,000 bytes above the mark.
6. Write the mark atomically before answering. If the write fails, allow.
7. Answer with the fixed message "The conversation is large. Run /compact, or start a
   fresh session with a short handover, then continue." in the exact shape verified
   above.

The hook never denies a tool call, a prompt, a session start or the user's own stop,
never opens the transcript, and sends nothing anywhere. At most 200 mark files are
kept (oldest by mtime removed on write, excluding the current conversation's mark, matching only names `^[0-9a-f]{16}\.json$` and checked with `lstat`).

### 2. Installer `skills/setup/scripts/compact_stop_setup.py` (stdlib)

Pattern: `quota_setup.py` and `compact_setup.py` (stored private preview, digest,
expiry 60 minutes, owner and mode checks, refusal of symlinks and git work trees for
the data root).
- `preview --limit <bytes>` | `preview --remove`: prints the exact change to
  `host.md` (`## Compaction stop` section) and only its own pretty-printed group plus other group names in the user's Antigravity hooks file, which is fixed at
  `~/.gemini/config/hooks.json` under the account home (there is no `--config` option; the hooks file
  must be owned by the user, not a symlink, not group- or world-writable, and outside every git work tree,
  as must its folder), the group name, the
  absolute hook command, the limit with its caveat (a byte proxy; the system prompt
  is not counted), and the digest. This is the dry run; it writes only the private preview.
- `apply --digest <64 hex> --yes`: applies only the stored preview. Writes the
  section atomically, then the hooks file: its own group `finolabs-vibecode-compact-stop`
  (never the metrics group, which `refresh.py antigravity-hook` owns and must not touch
  this one), timestamped backup (created 0600, narrowed to the previous mode & 0o600), atomic write, target mode preserved, every other group
  byte-for-byte, JSON object required, duplicate keys and non-finite numbers refused.
- `--remove` deletes the group and sets `Enabled: no`.
- Limit bounds: 50,000 to 20,000,000 bytes (integer). The hook command is built with
  `shlex.quote` from a path that passes the same plugin-root check as `refresh.py`
  (the file is inside a `finolabs-vibecode` plugin), with the plugin root additionally
  checked like the hooks folder: outside git work trees and not group- or world-writable. One exception, because Antigravity keeps the repository's `.git` directory in the copy it installs: the exact unresolved path `<account home>/.gemini/config/plugins/finolabs-vibecode` is accepted when it is reached without a symlink, every folder above it passes the same checks with no `.git`, the folder is owned by the user and not group- or world-writable, and its `.git` is a real directory. A development checkout or any other git work tree stays refused. Removal needs no script, so it never checks the plugin folder.
  The stored shell command prints `{}` if the script is missing or fails; Antigravity
  shell execution of hook commands remains unverified.
- Refuses to run for any host but Antigravity; mentions Claude Code and Codex use
  `compact_setup.py`.

### 3. Skill and doc text

`setup` gains one optional step after the compaction threshold step, only when
Antigravity is present: a separate consent question (neutral Yes and No, none
preselected, through the host's native question tool), the preview, then apply.
Advisory (agent judgment) that the question is asked and the preview shown; the
installer enforces digest, expiry and file safety. `session-hygiene` "Context
pressure" names the stop and its limits. `PRIVACY.md`: the section in `host.md`, the
mark files (an integer per conversation, hashed key, local), nothing sent. README row.
CHANGELOG `Unreleased`.

## Side effects to document

A stop ends a delegated headless `agy -p` run with `status: ERROR` and the fixed message. `delegate`
says so, and a coordinator treats it as "context limit", not a model failure.

## Not in scope

- Reading transcript content, or deriving token counts from it.
- Running `/compact` for the user.
- Plugin-bundled Antigravity hooks (working folder unverified).
- A stop on any event but `PreInvocation`; Claude Code and Codex stops.

## Acceptance

1. Hook: allow on every row 1 to 3 failure; stop when over the limit; one stop until
   +10% and +20,000 bytes; allow after a mark write failure; reset on a smaller
   transcript; symlink and out-of-folder paths allow; `invocationNum` above 0 allows;
   malformed or idle stdin allows; output is exactly `{}` or the verified shape.
2. Installer: preview writes only the private preview; apply refuses a wrong or short
   digest, an expired preview, a changed hooks file; other groups unchanged; backup
   made; remove works; the metrics group is untouched by either command.
3. `refresh.py antigravity-hook` keeps its behaviour; a test shows both installers
   can run in either order.
4. Docs updated; `check-references.py`, `claude plugin validate .` and targeted tests pass
   with the temp folder under a world-writable `/tmp`.

## Open

- Whether the byte limit is a usable proxy in long real sessions: measure the
  transcript size against `usage` over a few real conversations before recommending a
  default; setup recommends none.
- Live delivery of this hook from the documented user-level hooks file and in the TUI: verify with a real install.
- Owner: decide the fixed `/compact` message wording and address the unverified `invocationNum == 0` first-call-of-turn assumption before claiming that boundary is enforced.
