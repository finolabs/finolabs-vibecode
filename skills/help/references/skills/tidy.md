# tidy

Typed by the user, or loaded by the agent when the task matches. `session-hygiene` is its older name.

**What it does.** Keeps sessions healthy: names and renames sessions, watches context pressure, saves handovers before a compaction or a fresh session, and remembers or recalls decisions, lessons and project state in one shared knowledge base. It reports and prepares; it never runs a compaction itself.

**When to use it.** A session's first task starts, right after a compaction, when the task or phase changes, when you ask to wrap up, save progress, hand over or resume later, or when you ask to remember or recall something.

**Type:** Claude Code `/finolabs-vibecode:tidy` or `/tidy`; Codex `$tidy`; Antigravity `/tidy`.

## Tips

- Titles read `<emoji> <project> <scope>: <activity>`, for example `🐛 billing-api: fix webhook retries`. The agent names the session at its first task, at a phase change, after a compaction, and when a spec, story or large pull request it ran is done, so a long coordinator session shows its current work.
- To rename a session yourself: in the Claude Code desktop app use the app's title control (or ask the agent, which uses its session-title tool); in the Claude Code CLI type `/rename <title>`; in Codex type `/rename`; Antigravity has no session titles.
- When the agent asks you to compact, it gives the command ready to copy: `/compact <focus>` on Claude Code, a bare `/compact` on Codex, `/new` or `/fork` with the handover on Antigravity.
- About 60% context is a point to consider a boundary, not the host's compaction threshold.
- A wholly new task starts in a fresh, correctly named session with a short handover.
- Notes, briefs and logs go in `.finolabs/` at the main checkout's root, kept out of git; temporary folders are wiped on restart.
