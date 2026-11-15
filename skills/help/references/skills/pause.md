# pause

Typed by the user only. `gtg` is its short name.

**What it does.** Before you restart or shut the machine down, it stops new work, lets running work finish, writes handovers and reports what recorded work remains. It never stops a process, sends a signal or declares the machine safe: restarting is your call.

**When to use it.** You are about to restart or shut down and want running work drained first; `resume` after the restart.

**Type:** Claude Code `/finolabs-vibecode:pause` or `/pause`; Codex `$pause`; Antigravity `/pause`. Arguments: `[restart|shutdown] [--in <minutes>] | status | resume`.

## Tips

- `--in` is the time left before the machine goes down, 1 to 1440 minutes.
- Starting it ends an active `afk` lease; `heavy_run.py` refuses new commands (exit 77) while it is active.
- The verdict covers recorded work only; check jobs started outside `heavy_run.py` yourself.
- Handovers expire after 24 hours; for a shutdown the agent offers a longer-lived note.
