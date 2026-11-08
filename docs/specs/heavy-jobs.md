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

- Usage: `heavy_run.py run -- <command> [args...]` and `status` (whether the lock is held, the holder's label and
  age when known, load, free memory). There is no stale-lock cleanup command: the lock cannot go stale.
- Lock (design settled after four review rounds on a PID-and-directory scheme): a regular file `heavy.lock` in the data
  root's private state folder, created with `O_NOFOLLOW`, mode 0600, and refused unless `fstat` shows a regular file
  owned by the user. It is held with `fcntl.flock(fd, LOCK_EX | LOCK_NB)`, polled every 15 seconds. The file is never
  unlinked or replaced, so its identity is stable, and the kernel serialises every acquisition: exactly one process
  holds it, and no check-then-remove step exists to race. The descriptor stays inheritable, so the child and every
  descendant that keeps it open keep the lock after the wrapper dies; the kernel releases it when the last holder
  exits. After acquiring, the holder writes a one-line best-effort record (wrapper pid, start time, label) into the file
  for `status`. `status` never trusts that record: held or free is the result of a non-blocking `flock` probe, and a
  missing or partial record (a crash between acquiring and writing) shows "held, owner unknown". flock on a network
  filesystem is unverified; the data root is assumed local.
- Gate before start: wait while the lock is held, the one-minute load average is at or above the limit, or free memory
  is below the minimum. Poll every 15 seconds up to a wait cap (default 40 minutes), then exit 75 with a message that
  names the holder's label and age. Load and memory come from `os.getloadavg()` and `vm_stat`, run once per poll as
  fixed argv with no shell; on a platform without `vm_stat` only load is checked and `status` says so.
- Protected job: the whole foreground lifecycle of the work (container start, tests and cleanup), not a launcher that
  returns while the work continues. `run` refuses a command that asks for detached work: `-d` or `--detach` as an option
  of `up` or `run` in any Compose spelling (`docker compose`, `docker-compose`) or of `docker run` and `docker container
  run`; exit 64 with a fixed message that tells the caller to wrap a foreground script that starts, tests and tears
  down. Protection lasts while any process holds the inherited lock descriptor, so a launcher that exits while a
  descendant still runs keeps it. Work that closes the descriptor or is owned by another daemon (a container owned by
  the Docker daemon) is outside what the script can see, which is why detached launches are refused instead of tracked.
- Environment: the child and the script's own `vm_stat` launches start with the allowlisted environment of
  `run_env.py` (`run_env.environment()`), the same helper that `verify_claim.py` and `delegate_env.py` use, plus only
  the variable names the caller lists in `--pass-env NAME`; the structural launch-site test in `test_run_hygiene.py`
  covers the new script. The script never prints, logs or stores the environment, the command's arguments beyond a
  40-character label passed with `--label`, or any output. Working folder is the caller's, no shell.
- Release and exclusion: the kernel releases the lock when the last process holding the descriptor exits; the script
  removes nothing. A waiter whose wait cap ends exits 75 and closes only its own descriptor, which cannot affect the
  holder. On SIGINT or SIGTERM the wrapper forwards the signal to the child's process group and keeps running, still
  holding the descriptor, until the child has exited. A wrapper killed by SIGKILL with a surviving child or grandchild
  keeps the lock held through the inherited descriptor, and the next run acquires it as soon as the last holder exits,
  with no cleanup step.
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

1. With the lock held by a live holder, a second `run` waits and then exits 75 when the cap ends, never starting its
   command; the holder's lock is unaffected, and a third waiter still cannot start while the holder lives.
2. With the load or free memory beyond the limit, `run` waits; below it, `run` starts. Tests inject the readings.
3. Two processes racing for a free lock: exactly one acquires it (the other waits), checked with real `flock` between
   short synthetic Python processes. There is no cleanup path to race, and no test pauses a stale-cleanup step.
4. A signal sent only to the wrapper is forwarded to the child's group and the lock stays until the child has exited;
   a wrapper killed with SIGKILL while a child survives leaves the lock held. Tests use short synthetic commands.
5. A symlinked, non-regular or foreign-owned lock path is refused.
6. `status` prints held or free, the holder's label and age when known, load and free memory, and nothing from the
   environment or the command; a missing or partial record shows "held, owner unknown".
7. The child's environment contains only the allowlisted names plus the `--pass-env` names; tests compare variable
   names only and never print or inspect values.
8. A command with detached flags is refused with exit 64 before the lock is taken: fixtures `docker compose up -d`,
   `docker-compose up -d`, `docker compose run -d SERVICE` and `docker run --detach IMAGE`. Tests use short synthetic
   commands and never start Docker.
9. Combined case: a launcher starts a grandchild that keeps the descriptor and exits, then the wrapper is killed with
   SIGKILL; the lock stays held while the grandchild lives and a next `run` acquires it as soon as the grandchild
   exits, with no cleanup step.
10. The tests start no real heavy work: they use fake readers and short commands, and the module runs in under two
    seconds.

## Out of scope

Resource limits on a command (ulimit, cgroups), killing a running heavy job, scheduling and any admission order (waiters that poll first may win; first-come-first-served is not promised), and any enforcement for Codex or Antigravity.

## Consumers to trace

`fnl-delegate` SKILL and `references/dispatch.md`, `references/host-template.md`, `fnl-verification`,
`fnl-coding-router` "Proportion", `fnl-setup` delegation feature, the shared-copy check, `README.md` and the changelog.
