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
- Test scope is a rule: run only the tests covering the changed code and its traced consumers, never batch more than two modules in one
  command, and check load first. Overlap is limited, not the run's own verification: a coordinator starts no test
  while a review or delegated run it started is active, but a delegate runs its assigned targeted checks and a reviewer
  runs its review checks, each serialised by the lock when heavy. Lifecycle example: the delegate edits, runs its
  assigned targeted checks, returns the evidence, and the coordinator then accepts and runs its own checks. The
  owner's user-scope line is broader than this and stays the owner's wording.
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
- Protected job: the whole foreground lifecycle of the work (container start, tests and cleanup), not a launcher that
  returns while the work continues. `run` refuses a command that asks for detached work (`-d` or `--detach` after
  `docker` `up`, `run` or `compose up`; exit 64 with a fixed message that tells the caller to wrap a foreground script
  that starts, tests and tears down). The lock is held until the child's process group is empty, checked with
  `os.killpg(pgid, 0)`, so a launcher that exits while a descendant in its group still runs keeps protection. Work
  that escapes the group (a container owned by the Docker daemon) is outside what the script can see, which is why
  detached launches are refused instead of tracked.
- Environment: the child and the script's own `vm_stat` launches start with the allowlisted environment of
  `run_env.py` (`run_env.environment()`), the same helper that `verify_claim.py` and `delegate_env.py` use, plus only
  the variable names the caller lists in `--pass-env NAME`; the structural launch-site test in `test_run_hygiene.py`
  covers the new script. The script never prints, logs or stores the environment, the command's arguments beyond a
  40-character label passed with `--label`, or any output. Working folder is the caller's, no shell.
- Release and exclusion: only the process that acquired the lock removes it, and only after its child has ended. A
  waiter whose wait cap ends exits 75 and never touches the lock. On SIGINT or SIGTERM the wrapper forwards the signal
  to the child's process group, keeps the lock until the child has actually exited, then removes it. The `owner` file
  records the wrapper pid and the child pid; the lock is stale only when both processes are gone, so a wrapper killed
  by SIGKILL with a surviving child keeps the lock held. A crash with both gone leaves a stale lock that the next run
  clears after confirming that.
- No network, no hook, no background process.

## B. Which commands are heavy

`## Heavy jobs` in the canonical host config lists patterns, the load limit, the memory minimum and the wait cap. A
missing section uses the defaults settled above and this built-in default list. A pattern is a command-token sequence
matched after splitting the command with `shlex` and skipping leading `NAME=value` words:

- `docker` with `run`, `build`, `compose` or `buildx`; `docker-compose`.
- `playwright test`, also behind `npx` or `pnpm exec`.
- `go test` with an argument containing `contract` or `integration`.
- `python3 -m unittest` or `python -m unittest` with no module name, `discover`, or more than two module names.

Default denial fixture: `docker compose up`. Categories a command string cannot show (a real PostgreSQL, large
builds, a repository's whole-package suite) are left to patterns the owner configures, and otherwise to the advisory
rule in part C. `fnl-setup add delegation` asks for the values, each write after a yes.

## C. Rules for agents (advisory, agent judgment)

- `fnl-delegate` replaces the recipe with this script and keeps one Codex or Antigravity run at a
  time per coordinator.
- `fnl-verification` gains the test-scope rule above and names `heavy_run.py` for any command the host config marks heavy.
- `fnl-coding-router` "Proportion" points to both.
- A repository's own lock script may stay; it should call `heavy_run.py` so two locks cannot allow two heavy jobs.

## D. The gate (opt-in, Claude Code only)

A `PreToolUse` hook on the `Bash` tool, in its own group in the user's Claude Code hook configuration, installed and removed by a script with a dry run and a backup.

- Off unless `Heavy-job gate: on` is recorded under `## Heavy jobs` in the canonical host config after a consent question of its own and a shown preview in `fnl-setup add delegation`. Unresolvable config means off. `FNL_HEAVY_GATE=off` disables it.
- Canonical launch form: `python3 -I <path>/heavy_run.py run [--label <text>] [--pass-env NAME]... -- <command...>`, or
  the same script run directly as an executable. The path may be absolute or relative. The script applies the
  allowlisted environment itself, so no outer `run_env.py` is required; an outer `python3 -I <path>/run_env.py --`
  prefix is also recognised and skipped. The gate recognises a wrapped command by this grammar: after `shlex` splitting,
  an optional `run_env.py --` prefix, then an optional `python3`/`python` word with `-I`, then a word whose basename is
  `heavy_run.py`, then `run`.
- It denies one Bash call only when the command matches a heavy pattern (the section's list, else the built-in default
  list in part B) and is not wrapped in that form. The denial is one fixed message that names the script. Anything it
  cannot classify with certainty is allowed.
- Matching is on the command string in memory. The command text is never stored, logged, sent or put in an event. It reads only the canonical host config, ignores a repository file, and allows on every error.
- It never denies another tool, a prompt, a session start or the user's own stop, and never edits or runs the command.
- Limits: it cannot see work started by a tool other than Bash, by a script a command calls, or by Codex or Antigravity; those rely on the rules in part C.
- Acceptance (synthetic payloads, in-process, no real heavy work): denied when on: `docker compose up`. Allowed:
  `python3 -I /abs/skills/fnl-delegate/scripts/heavy_run.py run --label t -- docker compose up --abort-on-container-exit`, the same with
  `run_env.py --` in front, the direct-executable form, a non-heavy command, gate off, config unreadable and malformed
  input. The hook script writes no file and prints nothing else.

## Acceptance

1. With the lock held by a live owner, a second `run` waits and then exits 75 when the cap ends, never starting its
   command and never removing the lock; a third waiter queued behind it still cannot start while the owner lives.
2. With the load or free memory beyond the limit, `run` waits; below it, `run` starts. Tests inject the readings.
3. A stale lock (wrapper and child both gone) is cleared once; a lock with either process alive is never cleared.
4. A signal sent only to the wrapper is forwarded to the child group and the lock stays until the child has exited;
   a wrapper killed with SIGKILL while a child survives leaves the lock held. Tests use short synthetic commands.
5. A symlinked or foreign-owned lock path is refused.
6. `status` prints owner label, age, load and free memory, and nothing from the environment or the command.
7. The child's environment contains only the allowlisted names plus the `--pass-env` names; tests compare variable
   names only and never print or inspect values.
8. A launcher that exits while a descendant in its process group is still alive keeps the lock held until the group is
   empty; a command with `docker compose up -d` or `--detach` is refused with exit 64 before the lock is taken. Tests
   use short synthetic commands and never start Docker.
9. The tests start no real heavy work: they use fake readers and short commands, and the module runs in under two
   seconds.

## Out of scope

Resource limits on a command (ulimit, cgroups), killing a running heavy job, scheduling other than first come first
served, and any enforcement for Codex or Antigravity.

## Consumers to trace

`fnl-delegate` SKILL and `references/dispatch.md`, `references/host-template.md`, `fnl-verification`,
`fnl-coding-router` "Proportion", `fnl-setup` delegation feature, the shared-copy check, `README.md` and the changelog.
