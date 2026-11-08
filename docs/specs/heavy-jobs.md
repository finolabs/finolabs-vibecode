# Heavy-job guard and test scope (release 0.2.1)

Status: draft; no code yet. Owner decisions settled 2026-11-08; the CLAUDE.md exception for the gate lands with this spec before any code.

## Why

On 2026-11-08 the owner's 16 GB Mac hard-reset several times (hardware reset counters at 19:32, 19:46 and 20:03, no
kernel panic). The RAM log showed free memory near zero and the compressor holding 5 GB before each reset. Two of the
resets followed, within minutes, a coordinator running eight Python test modules in one command (about 40 seconds
and dozens of child processes) while delegated Codex reviews were running in other worktrees.

Two gaps caused it:

- The only machine-wide guard is an `mkdir` lock recipe in the `fnl-delegate` dispatch reference. A command that does not
  use it is not stopped, and the recipe checks neither load nor free memory.
- Nothing tells an agent to run only the tests that cover its change, so a one-constant change ran suites that never
  touched the changed code.

## Decisions settled (owner, 2026-11-08)

- The guard is user-scope: it protects the machine from any agent in any repository, not one repository.
- Test scope is a rule: run only the modules whose code the change touches, never batch more than two modules in one
  command, check load first, and never test while a review or delegated run is active. The same line is now in the
  owner's user-scope instructions.

- **Enforcement (owner, 2026-11-08):** script and rules, plus the opt-in `PreToolUse` gate on Claude Code (part D). The
  gate is the fifth scoped exception in `CLAUDE.md`, recorded in the same pull request as this spec, and no gate code
  lands before that rule is merged. It never covers Codex or Antigravity.
- **Default thresholds (owner, 2026-11-08):** one-minute load average below 12 and at least 3 GB of free plus inactive
  memory; wait cap 40 minutes.

## A. The script

`skills/fnl-delegate/scripts/heavy_run.py` runs one command while holding the machine-wide lock.

- Usage: `heavy_run.py run -- <command> [args...]`, plus `status` (lock owner, age, load, free memory) and `clear-stale`
  (removes a lock whose owner process is gone, after checking `ps -p`).
- Lock: an atomic `mkdir` under the data root's private state folder, named `heavy.lock`, with an `owner` file of
  pid, start time and a short label. Owner-only permissions, no symlink followed, refused if the path is not a
  directory owned by the user.
- Gate before start: wait while the lock is held, the one-minute load average is at or above the limit, or free memory
  is below the minimum. Poll every 15 seconds up to a wait cap (default 40 minutes), then exit 75 with a message that
  names the holder's label and age. Load and memory come from `os.getloadavg()` and `vm_stat`, run once per poll as
  fixed argv with no shell; on a platform without `vm_stat` only load is checked and `status` says so.
- The command runs with the caller's environment and working folder, no shell. The script never prints, logs or
  stores the environment, the command's arguments beyond a 40-character label the caller passes with `--label`, or
  any output.
- Release: the lock is removed when the command exits, on a signal, or when the wait cap ends. A crash leaves a stale
  lock, which the next run clears after confirming the owner process is gone.
- No network, no hook, no background process.

## B. Which commands are heavy

`## Heavy jobs` in the canonical host config lists patterns: Docker and testcontainers runs, a real PostgreSQL, Playwright,
`go test` over contract or integration packages, large builds, and a repository's whole-package test suite. It also
holds the load limit, the memory minimum and the wait cap. A missing section uses the proposed defaults above.
`fnl-setup add delegation` asks for these values, each write after a yes.

## C. Rules for agents (advisory, agent judgment)

- `fnl-delegate` replaces the recipe with this script and keeps one Codex or Antigravity run at a
  time per coordinator.
- `fnl-verification` gains the test-scope rule above and names `heavy_run.py` for any command the host config marks heavy.
- `fnl-coding-router` "Proportion" points to both.
- A repository's own lock script may stay; it should call `heavy_run.py` so two locks cannot allow two heavy jobs.

## D. The gate (opt-in, Claude Code only)

A `PreToolUse` hook on the `Bash` tool, in its own group in the user's Claude Code hook configuration, installed and removed by a script with a dry run and a backup.

- Off unless `Heavy-job gate: on` is recorded under `## Heavy jobs` in the canonical host config after a consent question of its own and a shown preview in `fnl-setup add delegation`. Unresolvable config means off. `FNL_HEAVY_GATE=off` disables it.
- It denies one Bash call only when the command matches a heavy pattern (the section's list, else the built-in default list in part B) and does not start with `heavy_run.py run --`. The denial is one fixed message that names the script. Anything it cannot classify with certainty is allowed.
- Matching is on the command string in memory. The command text is never stored, logged, sent or put in an event. It reads only the canonical host config, ignores a repository file, and allows on every error.
- It never denies another tool, a prompt, a session start or the user's own stop, and never edits or runs the command.
- Limits: it cannot see work started by a tool other than Bash, by a script a command calls, or by Codex or Antigravity; those rely on the rules in part C.
- Acceptance: with the gate on and a heavy default pattern unwrapped, the hook emits the fixed denial; wrapped, non-heavy, gate off, config unreadable and malformed input all allow; the hook script writes no file and prints nothing else. Tests feed synthetic payloads in-process and start no real heavy work.

## Acceptance

1. With the lock held by a live owner, a second `run` waits and then exits 75 when the cap ends, never starting its command.
2. With the load or free memory beyond the limit, `run` waits; below it, `run` starts. Tests inject the readings.
3. A stale lock (owner process gone) is cleared once; a lock whose owner is alive is never cleared.
4. A symlinked or foreign-owned lock path is refused.
5. `status` prints owner label, age, load and free memory, and nothing from the environment or the command.
6. The tests start no real heavy work: they use fake readers and short commands, and the module runs in under two
   seconds.

## Out of scope

Resource limits on a command (ulimit, cgroups), killing a running heavy job, scheduling other than first come first
served, and any enforcement for Codex or Antigravity.

## Consumers to trace

`fnl-delegate` SKILL and `references/dispatch.md`, `references/host-template.md`, `fnl-verification`,
`fnl-coding-router` "Proportion", `fnl-setup` delegation feature, the shared-copy check, `README.md` and the changelog.
