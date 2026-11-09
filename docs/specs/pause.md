# Pause (draft, no release assigned)

Status: draft; the owner described the idea and settled six decisions on 2026-11-09; nothing is built.

Idea: owner, 2026-11-09. The opposite of `fnl-brb`. Autopilot hands the agents a mandate to keep working while the
user is away; pause is what the user runs before a restart or shutdown of the machine, so that no running session or
process is stopped abruptly and nothing is lost when the machine goes down.

## Owner decisions (2026-11-09)


- Pause drains, then checkpoints. It stops starting new work, lets running work finish or reach a safe point, writes a
  handover for each session, and says when it is safe to shut down. It does not stop running processes by itself.
- It is its own user-run skill, not a branch of `fnl-autopilot`. It may read autopilot's state and end an active lease,
  and it shares no lease or log with it.
- Names (revised the same day): the documented skill is fnl-pause, and fnl-gtg ("got to go", the counterpart of
  "be right back") is its friendly alias, as fnl-brb is the alias of fnl-autopilot. Because an abbreviation says nothing
  to a new user, the alias skill's `description` must state in plain words what it does (drain running work before
  a restart or shutdown), with the same trigger phrases as the main skill.
- The owner also proposed fnl-afk as the main friendly name of the away skill, with fnl-brb kept as its alias. That
  changes a released skill and belongs to a separate change to the autopilot spec and skills; the message read
  "brd", taken here as a typo for "brb", to be confirmed.
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
2. **Drain**: `pause.py status` lists each open dispatch with its age against its budget, the heavy-job holder and
   waiters, and running agent processes by family, and prints `safe to shut down: yes` only when none remain and no
   waiter exists. A run that is past its budget is reported as stalled, never stopped.
3. **Checkpoint**: for each session the coordinator knows, it writes the handover (goal, decisions, work in progress,
   next action) with `handover_state.py write`, and for each dispatch that will not finish it records the outcome
   with `ledger.py finish` (`cancelled` or `stalled`) only after the user says to stop that run.
4. **Resume** (`pause.py resume`): removes the marker, lists the handovers still within their 24-hour read lifetime and
   the ledger records that ended without a finish line, and starts nothing by itself. Autopilot is not restarted.

## Boundaries

- The user invokes it; no hook starts, ends or reads it. The marker holds a timestamp only and is covered by
  `PRIVACY.md`'s state-folder wording. It runs no command beyond reading local state and, for the process
  snapshot, the existing snapshot reader when its setup consent is on. No network call.
- It never kills a process, never sends a signal and never shuts the machine down. Stopping a run is the user's
  decision, one run at a time.
- A pause marker left behind after a crash expires after 24 hours and is reported by `status`.

## Restart and shutdown differ

A restart returns in minutes, so a drain that cannot finish can leave its handovers to be read straight after boot.
A shutdown may last overnight, and a handover is readable for 24 hours only, so for `shutdown` the report says that
the handovers expire after 24 hours and offers to write a longer-lived note with the user's yes. Without `--in`, no
deadline applies and the skill waits until the user says to stop.

## Open decisions

| Decision | Owner | What unblocks it |
| --- | --- | --- |
| Rename the away skill to fnl-afk with fnl-brb as alias, and confirm that "brd" meant "brb" | owner | a yes, then a change to the autopilot spec and skills |
| Which release carries it | owner | scope for 0.2.3 or later |
| Security review of the `heavy_run.py` marker read | reviewer | the code pull request |

## Evidence

None yet. A build needs a red test per behavior above: the marker, the refusal in `heavy_run.py`, the safe-to-shut-down
rule and the resume listing.
