# Agent contracts

How each agent is dispatched, what ends a run, and how its result maps to a ledger outcome. Exact commands, paths and permission rules for this machine live in the host config (see `SKILL.md`); this file holds what is true on any host.

## Codex CLI

- **Dispatch**: `codex exec` in non-interactive mode, run in the background from the task's worktree (`-C <worktree>`). Pass the brief as the prompt argument read from the brief file, close stdin (`< /dev/null`), write the final message with `-o <last-message-file>` and stream the log to a file beside it in the briefs folder.
- **Sandbox**: `-s workspace-write` for implementation; `-s read-only` for reviews and advice. Add only the extra directories the task's build needs (`--add-dir`).
- **Hard cap**: wrap the command in a kill timer (`timeout`, or `perl -e 'alarm N; exec @ARGV'` where `timeout` is missing). Keep the machine awake for long runs where the host needs it.
- **End of run**: the exit status and the last-message file. Exit 142 (SIGALRM from the `perl` timer) at the cap means `timeout`.
- **Quota**: a usage-limit message in the log with no work done → `quota`; follow the quota fallback in `SKILL.md`.
- **Rework**: start a new `codex exec` in the same worktree with a short follow-up brief naming each defect and pointing at the original brief. Prefer a fresh run over resuming a large one.

## Antigravity through agybird

Load the `agybird` skill and follow it: it owns invocation, modes, model choice, quota checks and permission handling. What the coordinator adds:

- Use `--category code --mode write` for implementation, with an absolute `--cwd` set to the task's worktree, `--new-session` on the first run of a task, and `--timeout` with units (for example `30m`). The runner path and the Node binary come from the host config.
- Pick the model per run from the allowed models in the host config. Quota is per model and per pool: before declaring Antigravity out, check `agy -p /usage` and try each other allowed model at the same tier.
- Antigravity runs headless: any command outside its allow-rules ends the run `needs_permission` or `blocked`, and only the user grants permissions. Write edit-only briefs when the user is away, and paste the search results or file excerpts the agent would otherwise have to fetch with a denied command.
- Antigravity takes no reviews and no correctness judgements.

Envelope status → ledger outcome:

| `status` | Outcome | Next |
| --- | --- | --- |
| `success` | verify, then `accepted` / rework / `rejected` | a `plan`-mode answer asking for approval is unfinished work, not success |
| `partial` | `timeout` if the timeout notice fired, else verify | run the handover |
| `needs_permission` | `needs-permission` | put the request to the user; never grant on their behalf |
| `blocked` | `blocked` | reroute or rewrite the brief edit-only |
| `error` | `quota` if `/usage` shows the model's limits at 0%, else `error` | try another allowed model, then Codex |

## Claude Code sessions

The owner for very hard implementation, and the stronger reviewer for very hard work.

- **Where the desktop app's session tools exist**: start a session in its own worktree with the brief as its first message, and give it a title naming the task. The app refuses to start sessions on turns that an automated event or another session began; before an unattended stretch, start the sessions you will need as standby ("reply Standing by and wait") and release each one later with a message carrying its base commit.
- **Elsewhere**: run `claude -p` headless in the worktree under the same hard cap, with the brief as the prompt and the output written to the briefs folder.
- A session owns its task end to end: it may delegate to Codex or Antigravity itself, but it verifies and commits its own work and reports base and new commit SHAs.

## Claude subagents

The in-session `Agent` tool: fine for advisors, committee members and read-only lookups, whose results come back into the coordinator's turn. It never owns an implementation task, because its work and state disappear with the turn.
