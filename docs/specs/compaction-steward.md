> Retirement: `fnl-steward` is retired. Follow `fnl-session-hygiene` Context pressure and its `context_steward.py` script; this document retains the historical design.

# Compaction steward (option B)

Status: implemented; option B: local handover storage, threshold decision and compact re-injection (release 0.1.10, package 2, pull request 99); real-host delivery remains unverified.

Decision: 2026-11-06, owner: option B of the compaction analysis, built on the
host thresholds of `compaction-threshold.md`. Option A (a central orchestrator
that every session must ask) is not built. Scope: this document; the Antigravity
hard stop and any new blocking hook are out of scope (see Open decisions).

## Goal

Make sure a session past the chosen threshold does not silently drift: the user
learns of it, a handover survives the compaction, and the next story can start
in a fresh session. A script decides; the model only judges "safe boundary?".

## Verified limits the design rests on

- No hook receives the context percentage (Claude Code gives it to the status
  line only), and no hook can start a compaction.
- `send_message "/compact"` between desktop sessions is not executed as a
  command. `claude -p '/compact' --resume <id>` is, headlessly. `agy -p
  '/compact'` is unproven.
- A coordinator in the desktop app can read another session's context with
  `get_usage(session_id)`. Nothing else reads it across sessions.
- The compaction summary is written by the host model; a script controls only
  when to ask and what is re-injected afterwards.

Context numbers can now come from the opt-in Claude status-line [context snapshot](context-snapshot.md); missing or stale readings never supply invented counts.

## Parts

### 1. Handover state (F)

`scripts/handover_state.py`, stdlib only, no network, no subprocess.

- `write --session <id> [--repo <code>]` reads UTF-8 text on stdin (at most 8 KiB;
  more is refused, never truncated) and stores it at
  `<data root>/state/handover/<sha256(session id)[:16]>.md`, mode 0600 in a 0700
  folder, atomically. At most 20 files; the oldest by mtime is removed first.
- `read --session <id>` prints the file when it exists, is owned by the user, is
  not a symlink, is a regular file at most 8 KiB, and is younger than 24 hours;
  otherwise prints nothing and exits 0.
- The text is the agent's own handover (goal, decisions, work in progress, next
  action). It stays on the machine; nothing in it enters metrics.
- Data root resolution, ancestors, symlink and ownership checks reuse
  `data_root.py`; a folder that fails them disables the feature (exit 0, no output).
- Enforcer: the script checks file safety and limits. That an agent writes the
  file is advisory (agent judgment), prompted by the PreCompact reminder.

### 2. Re-injection

No hook file changes: the existing `session_start.py` entry already runs on
`compact` in Claude Code (its matcher lists it) and on every start in Codex, so
adding an entry would only make Codex hooks need trust again. `session_start.py`
reads the hook input from stdin (bounded, 64 KiB); when `source` is `compact` and
a `session_id` is present it appends the output of the `read` function of
`handover_state.py` under the heading `Handover before compaction`. It exits 0 and
fails closed (adds nothing) on any error, uses no network, and leaves its existing
output unchanged.
`precompact.py` text becomes: "Before compaction, write the handover (goal,
decisions, work in progress, next action) with handover_state.py write, then
write back decisions." Delivery of hook output to the model remains unverified
per host and is stated as such.

### 3. Steward check (the threshold decision)

`scripts/context_steward.py check --used <tokens> --window <tokens>
--threshold <tokens> [--boundary yes|no|unknown]` prints one JSON line with
`action` and a one-sentence `reason`:

| Condition | action |
|---|---|
| used < 80% of threshold | `ok` |
| 80% of threshold up to threshold | `prepare` (write the handover now) |
| used >= threshold and boundary `no` | `wait` (finish the unit of work first) |
| used >= threshold and boundary `yes` or `unknown` | `compact` (ask the user, or fresh session with handover when the story just closed) |

All numbers are integers in range; anything else is refused with exit 2 and a
fixed message. The script reads no file and runs nothing. Pure function, fully
tested. The threshold is the one the user chose in `fnl-setup`; the steward
never invents one.

### 4. Steward agent

`agents/fnl-steward.md`, read-only (`disallowedTools: [Write, Edit,
NotebookEdit]`), model tier fast (host config decides the model). Input: a
session's title, used and window tokens (from `get_usage`, a status line, or the
user), and a short summary of the last turns. It (a) runs `context_steward.py
check`, (b) when the answer is `compact` and the boundary is not obvious, asks
Jev one narrow question through the user's `typesafe-ai` skill ("is this a safe
boundary to compact: yes / no / unknown", over the supplied summary only, spend
guard on), (c) reports the action and a ready-to-send message for the user. It
changes nothing and starts no session. Without Jev it reports `unknown`.
Jev informs; the script's table decides. Report a Jev use only with a validated
reply.

### 5. Skill text

`fnl-session-hygiene` "Context pressure" names the steward, the `prepare`
action and who enforces what: the host enforces its threshold; the script
decides the action; the model judges the boundary; the agent writing the
handover is advisory. the load-sharing rule of `fnl-delegate` may call the steward for a
child session whose context it can read. `fnl-setup` explains the steward after
the threshold step and writes nothing new. README and `PRIVACY.md` (the
handover file: local, 0600, user's own text, never sent, 24-hour life).
CHANGELOG `Unreleased`.

## Not in scope

- A central orchestrator that sessions must consult (option A).
- Ordering `/compact` into another desktop session (does not execute).
- Antigravity `PreInvocation` hard stop (needs a new `CLAUDE.md` exception).
- Running `claude -p '/compact' --resume` automatically (a possible later,
  separate opt-in; untested against an interactively open session).
- New metrics events.

## Acceptance

1. `handover_state.py`: write/read round trip; refuses over 8 KiB, symlink,
   wrong owner, group/world-writable folder or file, expired file; keeps 20 files;
   exits 0 with no output on any failure of `read`.
2. `context_steward.py`: every row of the table, boundary values at 80% and
   100%, refusal of non-integers, negatives, zero window, used above window by
   more than 10x.
3. `session_start.py` with stdin `{"source":"compact","session_id":...}` appends
   the stored handover; with another source, no session id, malformed or
   oversized stdin, or an unsafe file it adds nothing and exits 0. Both hook
   files are byte-identical to main.
4. `fnl-steward` has the required front matter, forbids writes, and the skill
   text states each enforcer.
5. `PRIVACY.md`, README, CHANGELOG updated; `check-references.py`, `claude
   plugin validate .` and the targeted tests pass.

## Open decisions

- Antigravity hard stop: owner has not approved a second blocking hook.
- Headless `claude -p '/compact' --resume` as an optional actuator: owner's call
  after the steward has run for a while.
- Whether `get_usage` readings may feed the steward automatically from a
  coordinator session: advisory use only in this version.
