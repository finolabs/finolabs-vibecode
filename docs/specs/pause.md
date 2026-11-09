# Pause (draft, scoped to release 0.2.3)

Status: draft; the owner described the idea and recorded the decisions below on 2026-11-09; nothing is built.

Idea: owner, 2026-11-09. The opposite of `fnl-brb`. Autopilot hands the agents a mandate to keep working while the
user is away; pause is what the user runs before a restart or shutdown of the machine, so that no running session or
process is stopped abruptly and nothing is lost when the machine goes down.

## Owner decisions (2026-11-09)


- Pause drains, then checkpoints. It stops starting new work, lets running work finish or reach a safe point, writes a
  handover for each session, and reports what recorded work remains so the user can decide. It does not stop running
  processes by itself and never declares the machine safe to shut down.
- It is its own user-run skill, not a branch of `fnl-autopilot`. It may read autopilot's state and end an active lease,
  and it shares no lease or log with it.
- Names (revised the same day): the documented skill is fnl-pause, and fnl-gtg ("got to go", the counterpart of
  "be right back") is its friendly alias, as fnl-brb is the alias of fnl-autopilot. Because an abbreviation says nothing
  to a new user, the alias skill's `description` must state in plain words what it does (drain running work before
  a restart or shutdown), with the same trigger phrases as the main skill.
- The away skill is renamed: fnl-afk becomes its main friendly name and fnl-brb stays as its alias (owner, confirmed
  2026-11-09; the earlier "brd" was a typo for "brb"). This changes a released skill, so it goes through the autopilot
  spec and skills in its own package.
- Release: the pause skill and the away-skill rename are both scoped to 0.2.3 (owner, 2026-11-09).
- `heavy_run.py` refuses to start a new command while the pause marker exists. This is the first script gate outside
  autopilot, so it needs its own security review before it lands.
- A deadline exists, and the user states it as the time left before the machine goes down, in minutes, in the user's
  own words: "I will shut the machine down (or restart it) in 15 minutes". The parameter is `--in <minutes>`, not
  `--wait-minutes`, because the user is not choosing how long to wait but when the machine goes away. The kind is the
  word `restart` or `shutdown` (for example "/fnl-gtg shutdown --in 15"). When the time is up, the skill asks the user
  about each remaining run, one at a time, and stops none by itself.

## What pause can and cannot do

A plugin cannot freeze a process across a restart: a stopped process (`SIGSTOP`) is gone when the machine powers
off. So "pause" here means a safe drain and a recorded checkpoint, with a resume step after the machine is back.
It sees only what the plugin already records: the ledger's open dispatches, the heavy-job lock holder and waiters,
the cached agent-process snapshot, an active autopilot lease, and the handovers written with `handover_state.py`.
Sessions and terminals it has no record of are listed as unknown and left to the user.

## Behavior

1. **Start** (`pause.py start [restart|shutdown] [--in <minutes>]`): writes a pause marker in the private state folder (time only, no content) and ends an
   active autopilot lease. While the marker exists the coordinator starts no delegated run and no heavy job, and
   `heavy_run.py` refuses to start a new command with one fixed message (the only script-enforced part; everything else
   is agent judgment, advisory).
2. **Drain**: `pause.py status` lists each open dispatch with its age against its budget and the heavy-job holder and
   waiters. A run past its budget is reported as stalled, never stopped. The plugin can know only what it records, so
   the verdict is a statement about recorded work and never a claim that the machine is safe to shut down: that call
   stays with the user. The verdict has three values and the first applicable one wins:
   - `blocked: <what remains>`: an open dispatch other than the coordinator's own record, a heavy job started through
     `heavy_run.py` that holds the lock, a waiting wrapper, or a job from a stopped wrapper whose recorded process
     group still runs (the case `heavy_run.py status` prints as `heavy lock: free, but a job from a stopped wrapper is
     still running`; a free lock alone is not an empty one).
   - `unknown: <reasons>`: the ledger is unreadable, the lock or its waiter count is unreadable (`waiting: unknown` is
     not zero), or a checkpoint cannot be read back. Each reason names its source.
   - `no recorded work remains`: none of the above; every checkpoint the coordinator wrote was read again at this
     moment, belongs to its session, was written after the marker's start time and is still within its 24-hour read
     lifetime, so an older handover of the same session cannot stand in for the current one.
   The lock covers only commands started through `heavy_run.py`; a job started another way is not seen, and the
   output says so. The agent-process snapshot is never an input to the verdict, because it keeps only family, elapsed
   seconds and descendant counts, so it cannot identify the coordinator or tell an idle session from a working one.
   `status` prints it after the verdict from the existing cache as data (no collection, only when metrics consent and
   the snapshot setting allow it, and a missing, stale or disabled cache is printed as "not observed"), under the
   heading "agent processes seen, not identified: check these yourself before you restart".
3. **Checkpoint**: for each session the coordinator knows, it writes the handover (goal, decisions, work in progress,
   next action) with `handover_state.py write`, and for each dispatch that will not finish it records the outcome
   with `ledger.py finish` (`cancelled` or `stalled`) only after the user says to stop that run. `handover_state.py
   write` returns silently when its storage is unsafe, so a checkpoint counts only after it is read back.
4. **Resume** (`pause.py resume`): removes the marker, lists the handovers still within their 24-hour read lifetime and
   the ledger records that ended without a finish line, and starts nothing by itself. Autopilot is not restarted.

## Boundaries

- The user invokes it; no hook starts, ends or reads it. The marker holds a timestamp only and is covered by
  `PRIVACY.md`'s state-folder wording. It adds no command of its own: it reads local state and the existing process-snapshot cache as data, never running
  `ps` for it (the dashboard refresh stays the only collector, as `CLAUDE.md` scopes it). The heavy-job part of the
  report comes from calling the existing read-only `heavy_run.py status`, which already runs its own fixed probes
  (`pgrep`, `ps -p` and the memory reading) under its own bounds; pause adds none to them. No network call.
- It never kills a process, never sends a signal and never shuts the machine down. Stopping a run is the user's
  decision, one run at a time.
- The marker is the one file here that controls command admission, so it is read like the lease and the host config:
  the path comes only from the canonical account-owned data root (never from a repository, an environment variable
  or an argument), opened by descriptor with no-follow, a private regular file owned by the user, a bounded read, a
  validated timestamp that is not in the future by more than a small skew, and written atomically. Missing means not
  paused. Unreadable, invalid or not safe means `heavy_run.py` runs as if not paused and `status` reports the marker
  as invalid, so a damaged file never blocks work and never silently pauses it. A marker older than 24 hours expires:
  `heavy_run.py` ignores it and `status` reports it.
- Ordering: marker publication is the admission point. `heavy_run.py` checks the marker at entry, again after it gets
  the lock and before it starts the command (a wrapper that waited up to its wait cap across the start of a pause
  refuses at that second check), and a command that already started is never touched. The window between the last
  check and the start is the one race left; the spec accepts it and the code pull request documents it.

## Restart and shutdown differ

A restart returns in minutes, so a drain that cannot finish can leave its handovers to be read straight after boot.
A shutdown may last overnight, and a handover is readable for 24 hours only, so for `shutdown` the report says that
the handovers expire after 24 hours and offers to write a longer-lived note with the user's yes. Without `--in`, no
deadline applies and the skill waits until the user says to stop.

## Open decisions

| Decision | Owner | What unblocks it |
| --- | --- | --- |
| Security review of the `heavy_run.py` marker read | reviewer | the code pull request |

## Evidence

None yet. A build needs a red test per behavior above: the marker, the refusal in `heavy_run.py`, the three-value
recorded-work verdict (including the stopped-wrapper case and unknown sources) and the resume listing.
