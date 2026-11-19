# Troubleshooting

Read the shared rules in [map.md](map.md#rules). Match the user's problem to one row, give the fix, and read the named skill's `SKILL.md` before going deeper. When no row fits, say so and offer the Explain mode for the skill involved.

| Problem | Fix |
| --- | --- |
| A script stops on Windows with a message about the platform | Native Windows is not supported: the scripts rely on POSIX file APIs. Run Claude Code, Codex or Antigravity with the plugin under WSL. The hooks never block a session on Windows. |
| The plugin's skills or hooks do not show up after installing | Plugins load when a session starts: open a new session. |
| Codex asks to trust the hooks again, or they stop running, after an update | Every change of hook content makes Codex ask again. In a new session open `/hooks` and trust the plugin's hooks. |
| Claude Code still runs the old version after `/update` | The host keeps the old copy loaded until a restart. Restart Claude Code, then run `/update` or `/update whats-new` to continue the checklist. |
| `/update` shows `stale`, or `available` is empty | The cache is refreshed in the background after 24 hours and read on a later startup; a stale or empty value is unknown, not proof the plugin is current. Start a new session later and check again. |
| `/update` prints nothing at all | The update check is off (`FNL_UPDATE_CHECK=off` stops the helper commands too) or a read failed. |
| Antigravity has no update command | Its update procedure is still unverified; `update` explains the gap and leaves the step to you. |
| The dashboard is empty or names a missing source | Consent not given: run `/setup add metrics`. No events: the hooks need the whole plugin installed and a session started after consent. A missing ledger: see `delegate`. |
| `/afk start` stops and points to setup | Record the away rules first with `/setup add afk`. |
| `/afk start` says `strict` was removed, or that the limits were removed | Your setup still holds lines from before 0.3.3 (`Mode: strict`, `Max runs`, `Max runtime minutes`, `Max actions per hour`); they are no longer read and the lease starts as usual. Nothing to do, or run `/setup add afk` again to rewrite the section. Anything that must stay forbidden while you are away is a host deny rule (Claude Code permission rules, Codex sandbox and approval policy). |
| After upgrading, afk answers "afk refused: setup or private state is missing, invalid, unsafe or already active" | A lease started before 0.3.3 holds counters the new lease format does not read. Run `/afk stop`, then `/afk start`. |
| Under a lease the agent keeps going after it tried to stop | The afk stop hook (Claude Code) sends a turn back once until the session records why it ends: `afk.py log --kind idle --session <id>` or `--kind parked`. `FNL_AFK_STOP=off` turns it off. |
| Under a lease a tool call is denied with a request digest | The afk permission hook answers host prompts while you are away: the agent settles it through afk "Decide" and records `--approve-request <digest>`, or parks it. `FNL_AFK_PERMIT=off` brings the host's prompt back. |
| `/afk start` warns that nothing blocks credential reads | Add Claude Code's deny rules for the credential floor with `/setup add afk`, or run with an approval mode that asks. |
| `heavy_run.py` refuses a command with exit 77 | A pause marker is active. Run `/pause resume` once you are back from the restart; a marker older than 24 hours never blocks. |
| `/restore-point` says "Not a git repository" | It works in git repositories only and creates nothing. Run `git init` yourself if you want one. |
| A skill says a dependency is missing | It was installed on its own. Add the named skill, for example `npx skills add finolabs/vibecode --skill delegate`, or install the whole plugin. |
| The agent does not list `setup`, `status` or another typed skill | Those skills are typed by the user only and may be missing from the agent's own list; type the command yourself. |
