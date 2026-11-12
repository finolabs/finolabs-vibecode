# Running agents on the dashboard

Status: implemented; phase 1: ledger and opt-in process snapshot in Running now; liveness remains advisory, CLI name observations and real-host UI verification remain open.

Idea: owner, 2026-11-06. Agents now start sub-agents of their own family and the coordinator delegates
to other families, so a user often cannot tell how many agents and background processes are alive.
`status` should show it. Phase 1 only; phase 2 is listed so the design does not close it off.

## What can be seen (and what cannot)

| Source | Shows | Limit |
| --- | --- | --- |
| Ledger (`ledger.py open`) | Delegated headless runs: agent, model, project, task label, started, budget, age against budget, liveness | Only runs the coordinator started and recorded |
| Process snapshot (new) | Command-line agent processes of the current user, by family, with elapsed time and a count of their descendants | Machine-wide; cannot see inside an app's own session list; cannot tell a sub-agent from a session; names are best-effort |
| Hook events (phase 2) | In-session sub-agent start and stop | Needs new hook declarations (Codex asks the user to trust hooks again) and a metrics schema field |

The desktop app's session list is not readable by a plugin; the page says so.

## Live usage sessions (owner feedback, 2026-11-06)

Alongside the unchanged ledger lanes and opt-in process counts, show `running.live` with
`window_minutes: 15` and counts for `claude`, `codex`, `antigravity`. Count distinct sessions
having any existing event strictly less than 15 minutes old, never future events; join the family
from session-start receipts even when the start predates the window. Cap each count at 99 and
retain no session ids in this block. This does not enumerate desktop sessions or identify sub-agents:
it includes any of their sessions that emit existing usage events. No new event field or consent.
The rich tooltip states “sessions with activity in the last 15 min, from usage events; not a process
count; a session idle longer is not shown”, and notes when both this and process snapshot exist.

## Rule first

This adds a local command the plugin runs by itself, so it needs a scoped exception in `CLAUDE.md`
before any code (owner approval for the exception is part of approving this spec). Proposed text: the
dashboard refresh may run `ps` once per refresh, read-only, as the current user, to count
command-line agent processes; fixed argv, absolute owner-checked path, no shell, allowlisted
environment, neutral working folder, 2-second limit with the process group killed, 256 KiB output cap;
it keeps only fixed family names, counts and elapsed seconds, never arguments, paths, environment or user-chosen names;
it runs only when metrics consent is recorded and `setup` has turned the snapshot on (off by default); `FNL_AGENT_SNAPSHOT=off` stops it; no other command and
no network. No code lands before that rule is merged.

## Phase 1

Order inside the package: the ledger and hook-event parts of the panel first, the process snapshot last, off by
default until `setup` offers it. The `ps` exception merges into `CLAUDE.md` only when that code is about to
land (owner approved the text on 2026-11-06).

### Snapshot `scripts/agent_processes.py` (stdlib)

- Command: `ps -axo uid=,pid=,ppid=,etime=,comm=` run as described in "Rule first". `ps` is resolved once
  to an absolute path that is owned by root, not a symlink and not group- or world-writable (`/bin/ps`
  or `/usr/bin/ps`); anything else disables the snapshot. The environment is empty except `PATH`
  fixed to `/usr/bin:/bin` and `LC_ALL=C`; `PS_FORMAT` and similar variables are never inherited.
- Only rows whose uid equals the current uid are kept (filter in code, not by option, so it is the same
  on macOS and Linux).
- Roots: rows whose program name (the last path component of `comm`) is exactly `claude`, `codex` or
  `agy`. A hostile process can be given one of these names, so the page says "processes named ..." and
  nothing more is claimed.
- Descendants of each root (bounded: depth 6, 500 rows per root) are counted by program name against a
  fixed list (`node`, `python`, `python3`, `bash`, `zsh`, `sh`, `git`, `npm`, `pnpm`, `npx`, `pytest`,
  `cargo`, `go`, `make`, `docker`, `ssh`, `rg`, `grep`); every other name counts as `other`. No user-chosen
  name can reach the output.
- Desktop app helpers are not roots. One summary line per app family ("Claude app: N processes",
  "Codex app: N", "Antigravity app: N") is produced from fixed exact names (`Claude`, `Codex`,
  `Antigravity`) and shown as "app processes, sessions not listed".
- No `lsof`, no working folder, no repository attribution: the snapshot is machine-wide and says so.
- Output: a JSON object with family, elapsed seconds, descendant counts, and the snapshot time. Failure
  of any step gives an empty snapshot and a fixed one-line reason; exit 0.

### Dashboard (`refresh.py`, page)

- `data.js` gains a `running` block: ledger open dispatches (age against budget, the liveness verdict
  `status` already computes) and the snapshot. It is written to `data.js` (a local file the
  dashboard owns), overwritten at each refresh and removed by `purge`; it is not written to the events
  files.
- All values are emitted through `json.dumps` with `<`, `>` and `&` escaped, and rendered with
  `textContent`, never `innerHTML`; a test feeds hostile names.
- A "Running now" panel at the top: counts by family; a row per root process; a row per open dispatch;
  a ledger run with no process is flagged "no process found", a process with no ledger run is labelled
  "not started by the coordinator". States plainly: machine-wide, app sessions not listed, a snapshot
  with its time.
- The snapshot is taken only by `refresh.py`, at most every 10 seconds (the existing throttle), only
  when metrics consent is recorded in the canonical consent file; the hook path starts the refresh
  exactly as it does today and never waits for it. `status` runs it in the foreground.
- `status` SKILL: step 3 reads the same data; verdict wording is advisory (agent judgment), the
  data is produced by the script.

### Docs

`PRIVACY.md`: what the snapshot keeps (fixed family names, counts, elapsed times), what it never keeps
(arguments, paths, environment, user-chosen names), where it lives (`data.js`, overwritten, purged),
that macOS `comm` can be a full path and only its last component is read, and the off switch. README
row, CHANGELOG `Unreleased`, `docs/specs/index.md`.

## Phase 2 (not built here)

Hook-reported sub-agent starts and stops as a new metrics event (fields: host, phase), declared in the
Claude and Codex hook files and as an Antigravity user hook. Cost: schema change, `PRIVACY.md`, and a
Codex re-trust. Decide after phase 1 shows what users cannot see. Repository attribution through
`lsof` is also deferred: it reads working folders and needs its own review.

## Not in scope

Killing or controlling processes; reading prompts, command lines, paths or working folders; the
desktop app's session list; remote machines; per-process CPU or memory.

## Acceptance

1. `agent_processes.py` with a fake `ps` output (injected): other users' rows dropped; roots by exact
   name only (`claude-helper`, `codexd`, `node` are not roots); descendants only by the fixed list,
   the rest `other`; depth and row bounds hold; malformed lines skipped; hostile names (paths, spaces,
   control characters, `</script>`) never appear in the output.
2. Execution: a `ps` path that is a symlink, not root-owned or writable by others disables the
   snapshot; the environment passed is exactly the allowlist; timeout, non-zero exit and oversize
   output give an empty snapshot with a fixed reason, exit 0.
3. `refresh.py` writes the `running` block with merged ledger data and the two mismatch flags, leaves
   the events files untouched, does nothing without recorded metrics consent or with
   `FNL_AGENT_SNAPSHOT=off`, keeps the throttle; `purge` removes the block.
4. The page renders the panel via `textContent` (existing page tests with fake timers), the empty
   state and the stated limits; no inline script or remote resource is added.
5. `CLAUDE.md` rule merged first; docs updated; `check-references.py`, `claude plugin validate .` and
   targeted tests pass under a world-writable `/tmp`; no hook file changed.

## Open

- Observed on this Mac (macOS, 2026-11-06, `ps -axo comm=` program names): `codex` (6),
  `codex-code-mode-host`, `Codex` (15), `Antigravity` (10), `Claude` (24), `node` (46); no lowercase
  `claude` and no `agy` was running at that moment. Re-check `claude -p` and `agy -p` runs while they
  are alive before fixing the root list, and record the result here.
