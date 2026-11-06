# Running agents on the dashboard

Idea: owner, 2026-11-06. Agents now start sub-agents of their own family and the coordinator delegates
to other families, so a user often cannot tell how many agents and background processes are alive.
`fnl-status` should show it. Phase 1 only; phase 2 is listed so the design does not close it off.

## What can be seen (and what cannot)

| Source | Shows | Limit |
| --- | --- | --- |
| Ledger (`ledger.py open`) | Delegated headless runs: agent, model, project, task label, started, budget, age against budget, liveness | Only runs the coordinator started and recorded |
| Process snapshot (new) | Every `claude`, `codex`, `agy` process alive on this machine, with its elapsed time and its descendants by program name | Machine-wide; cannot see inside an app's own session list; cannot tell a sub-agent from a session |
| Hook events (phase 2) | In-session sub-agent start and stop | Needs new hook declarations (Codex asks the user to trust hooks again) and a metrics schema field |

The desktop app's session list is not readable by a plugin; say so on the page.

## Phase 1

### Process snapshot `scripts/agent_processes.py` (stdlib; one local read-only command)

- Runs `ps -axo pid=,ppid=,etime=,comm=` with a fixed argv, no shell, a 5-second limit and a 256 KiB
  output cap (Linux and macOS). No other command except the optional step below.
- Roots: processes whose program name (basename of `comm`) is exactly `claude`, `codex` or `agy`.
  For each root: family, elapsed seconds, and its descendants counted by program name (basename only,
  at most 8 names shown, the rest as `other: N`). It never reads, keeps or prints arguments,
  environment, paths or file names.
- Repository attribution (optional, best effort): one `lsof -a -d cwd -Fn -p <root pids>` call for the
  root pids only (fixed argv, 5-second limit). A root whose working folder is inside the current
  repository root is labelled with the same short repository code the metrics use; any other root is
  `other`; a failure or a missing `lsof` makes every root `unknown`. The folder path itself is never kept.
- Output is a small JSON object (family, elapsed, children summary, repo label) handed to
  `refresh.py`; nothing is written to the events files. A failure yields an empty snapshot and a
  one-line reason.
- Ownership: only processes of the current user are listed (the user's own `ps` view).

### Dashboard (`refresh.py`, page)

- `data.js` gains a `running` block: ledger open dispatches (with age against budget and the
  liveness verdict `fnl-status` already computes) and the process snapshot with its time.
- A "Running now" panel at the top: counts by family; a row per root process; a row per open
  dispatch; ledger runs with no matching process are flagged "no process found" (finished without a
  line, or stalled), and processes with no ledger run are labelled "not started by the coordinator".
- States plainly: machine-wide; the app's own sessions are not listed; counts are a snapshot with its
  time. It refreshes with the existing 5-second reload, but the snapshot is taken at most every 10
  seconds (the existing throttle) and only when the dashboard exists.
- Tied to the metrics consent the dashboard already needs. `FNL_METRICS=off` stops it with the rest.
- `fnl-status` SKILL: step 3 reads the same data; the "Running now" panel replaces its manual
  liveness listing; enforcer is the script, the verdict wording is advisory (agent judgment).

### Docs

`PRIVACY.md`: the snapshot is transient, holds family names, elapsed times and program-name counts, no
arguments, paths or file names, and is not stored in the events files. README row, CHANGELOG
`Unreleased`, `docs/specs/index.md`.

## Phase 2 (not built here)

Hook-reported sub-agent starts and stops as a new metrics event (fields: host, phase), declared in the
Claude and Codex hook files and as an Antigravity user hook; the page then shows in-session
sub-agents per session. Cost: schema change, `PRIVACY.md`, and a Codex re-trust. Decide after phase 1
shows what users cannot see.

## Not in scope

Killing or controlling processes; reading prompts, command lines, paths or working folders into any
file; the desktop app's session list; remote machines; per-process CPU or memory.

## Acceptance

1. `agent_processes.py` with a fake `ps` output (injected): roots found by exact program name only
   (`claude-helper`, `codexd`, `node` are not roots); descendants counted by basename; caps (8 names,
   output size, line count); malformed lines skipped; no argument, path or environment text can reach
   the output (test with hostile `comm` values containing paths, spaces and control characters).
2. Failure paths: `ps` missing, timeout, non-zero exit, oversize output -> empty snapshot with a
   fixed reason, exit 0. Optional `lsof` failure -> labels `unknown`, snapshot still returned.
3. `refresh.py` writes the `running` block, merges ledger open dispatches, flags the two mismatch
   cases, and leaves the events files untouched; the throttle holds.
4. The page renders the panel (existing page tests with fake timers) including the empty state and
   the stated limits; no inline script or remote resource is added.
5. Docs updated; `check-references.py`, `claude plugin validate .` and targeted tests pass under a
   world-writable `/tmp`; no hook file changed.

## Open

- Observed on this Mac (macOS, 2026-11-06, `ps -axo comm=` basenames): `codex` (6), `codex-code-mode-host`,
  `Codex` (15, the app and its helpers), `Antigravity` (10, the app and helpers), `Claude` (24, the desktop
  app and helpers), `node` (46, MCP servers and wrappers); no lowercase `claude` and no `agy` was running at
  that moment. So exact names `claude`, `codex`, `agy` find CLI runs, while app sessions appear only as the
  app's helper family and cannot be told apart from sessions. Phase 1 therefore lists CLI roots by exact
  name and shows app helpers as one line per app ("Claude app: N processes"), never as sessions. Re-check
  `claude -p` and `agy -p` runs while they are alive before fixing the list.
