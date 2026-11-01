# Agent contracts

How each agent is dispatched as a delegate, what ends a run, and how its result maps to a ledger outcome. These hold whichever agent coordinates. Exact paths, wrappers and allow-rules for this machine live in the host config (see `SKILL.md`); recheck flags with each CLI's `--help`, since they change between versions.

Common to every headless dispatch: run it in the background from the task's worktree, pass the brief from its file, close stdin (`< /dev/null`), wrap it in a hard-cap timer (`timeout`, or `perl -e 'alarm N; exec @ARGV'` where `timeout` is missing; exit 142 or 124 at the cap means `timeout`), and write the log and final message into the logs folder (`.orchestration/logs/`).

## Claude Code

- **Headless**: `claude -p "$(cat "$B")" --model <full model id> --effort <level> --output-format json`, run in the worktree. Headless runs start in a mode that denies anything needing approval: grant what the brief needs with `--allowedTools` (or `--permission-mode acceptEdits` for edit-only work), and cap spend with `--max-budget-usd` and `--max-turns`.
- **Read-only work** (review, advice): `--permission-mode plan`, or `--allowedTools` limited to read and search tools.
- **End of run**: exit status plus the JSON `result`. Check `permission_denials` in the output: a run that hit denials may report success without doing the work.
- **Desktop app sessions**: where the app's session tools exist, start a session with the brief as its first message, in its own worktree when it runs beside other writers (serial spec task sessions share the implementation checkout, as `fnl-coordinator-sessions` says), and a title naming the task. The app refuses to start sessions on turns an automated event or another session began; before an unattended stretch, start the sessions you will need as standby and release each with a message carrying its base commit.
- A Claude Code delegate owns its task end to end: it may delegate further itself, but it verifies and commits its own work and reports base and new commit SHAs.

## Codex

- **Headless**: `codex exec -m <model> -c model_reasoning_effort=<level> -s workspace-write -C <worktree> -o <last-message-file> "$(cat "$B")"`. Add only the directories the build needs with `--add-dir`. Use `--json` when you want the event stream.
- **Read-only work**: `-s read-only`. For a code review, `codex review --base <branch>` (or `--uncommitted`) runs Codex's own review flow.
- **End of run**: the exit status and the last-message file. Approvals cannot be granted in a headless run: an action that needs one fails.
- **Quota**: a usage-limit message in the log, or a `turn.failed`/`error` event, with no work done → `quota`.
- **Rework**: a new `codex exec` in the same worktree with a short follow-up brief that names each defect and points at the original brief; prefer it over resuming a long run.

## Antigravity

When the `agybird` skill ([fioenix/agybird](https://github.com/fioenix/agybird), MIT) is installed, it may run the dispatch: it wraps the same CLI with modes and quota checks. Without it, call `agy` directly:

- **Headless**: `agy -p "$(cat "$B")" --model <model id> --mode accept-edits --output-format json --print-timeout <minutes>m`, run in the worktree. Always pass `--print-timeout`: its default differs between versions.
- **Permissions**: reads and writes inside the workspace are allowed; every shell command outside the allow-rules is soft-denied. A soft-denied run can exit 0, so read `denied_actions` in the JSON. Pass a per-run settings file with `--settings` holding only the allow-rules this task needs, rather than widening the global rules; changing global rules needs the user's approval.
- **Quota**: check `agy -p /usage --output-format json` before calling Antigravity out: pools are separate, so try another allowed model in a pool with quota left. An exhausted quota ends the run with exit 3 and an `AGY_ERROR` line on stderr.
- **Reviews**: Argon and the Claude models it serves review at strong tier like any other agent. Antigravity has no native review command, so its reviewer reads the diff itself; a review that needs shell commands outside the allow-rules goes to Claude Code or Codex.

JSON result → ledger outcome:

| Result | Outcome | Next |
| --- | --- | --- |
| `status` SUCCESS, `denied_actions` empty | verify, then `accepted` / rework / `rejected` | an answer asking for approval is unfinished work |
| SUCCESS with `denied_actions` | `needs-permission` | put the request to the user, or rewrite the brief edit-only |
| `finished_reason` `print_timeout` | `timeout` | run the handover |
| exit 3 with a quota `AGY_ERROR` | `quota` | another pool, then the quota fallback |
| other errors | `error` | reroute |

Through the `agybird` runner, read its envelope `status` instead:

| `status` | Outcome | Next |
| --- | --- | --- |
| `success` | verify, then `accepted` / rework / `rejected` | a `plan`-mode answer asking for approval is unfinished work |
| `partial` | `timeout` if the timeout notice fired, else verify | run the handover |
| `needs_permission` | `needs-permission` | put the request to the user; never grant on their behalf |
| `blocked` | `blocked` | reroute, or rewrite the brief edit-only |
| `error` | `quota` if `/usage` shows that model's pool at 0%, else `error` | another allowed model, then the quota fallback |

## When an agent coordinates

The coordinator's own sandbox decides which delegates it can reach. Each delegate CLI needs network access and its own state and credential folders, which it reads by itself; the coordinator never reads them.

- **Claude Code coordinating**: Bash runs `codex exec` and `agy -p` under the session's permission rules; allow the exact command prefixes.
- **Codex coordinating**: the default `workspace-write` sandbox has no network and cannot reach other CLIs' home folders. Reaching `claude -p` or `agy -p` needs a sandbox the user has configured for it; without one, those delegates are unavailable. Codex's own subagents inherit its sandbox.
- **Antigravity coordinating**: allow `command(claude -p)` and `command(codex exec)` in the allow-rules and run without `--sandbox`; otherwise those calls are soft-denied.

A delegate the coordinator cannot reach is **unavailable** for routing; record it in the host config rather than retrying it on each task.

## In-session subagents

Every host has its own subagents (Claude Code's Agent tool, Codex agents, Antigravity agents). Use them for advisors, committee members and read-only lookups, whose results come back into the coordinator's turn. They never own an implementation task: their work and state disappear with the turn.
