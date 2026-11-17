# Codex

How Codex is dispatched as a delegate, what ends its run, and how its result maps to a ledger outcome. Read [agents.md](../agents.md) first: its common procedure (brief lint, private log folder, `delegate_env.py`, hard-cap wrapper, residual risk) holds for every family.

- **Headless**: `python3 -I <this skill folder>/scripts/delegate_env.py --family codex -- codex exec -m <model> -c model_reasoning_effort=<level> -s workspace-write -C <worktree> -o <last-message-file> "$(cat "$B")"`. Add only the directories the build needs with `--add-dir`. Use `--json` when you want the event stream.
- **Read-only work**: `-s read-only`. For a code review, `python3 -I <this skill folder>/scripts/delegate_env.py --family codex -- codex review --base <branch>` (or `--uncommitted`) runs Codex's own review flow.
- **Unsandboxed review and posting** (advisory, agent judgment): start `codex exec` with `-s danger-full-access` only for review and posting, never implementation. This is allowed only with a brief that is read-only except for the one posting command and passes `brief_check.py`; the posting helper needs network access and the git credential helper. Record the dispatch in the ledger as usual. The brief check is script-enforced; the run's scope is agent judgment.
- **End of run**: the exit status and the last-message file. Approvals cannot be granted in a headless run: an action that needs one fails.
- **Outcomes** (advisory, agent judgment): a dispatch ended by a command needing permission is `needs-permission`, never `quota`. Record `quota` only when the agent reported a limit; a `turn.failed`/`error` event alone is insufficient.
- **Rework**: a new `codex exec` in the same worktree with a short follow-up brief that names each defect and points at the original brief; prefer it over resuming a long run.
