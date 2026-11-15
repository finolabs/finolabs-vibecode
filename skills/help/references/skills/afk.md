# afk

Typed by the user only.

**What it does.** Starts a time-boxed standing mandate (a lease) so your agents keep working while you are away from the keyboard, checking each action against the lease, and stops it when you return.

**When to use it.** You are leaving and want listed work to continue within the rules you recorded; `stop` when you are back.

**Type:** Claude Code `/finolabs-vibecode:afk` or `/afk`; Codex `$afk`; Antigravity `/afk`. Arguments: `[start|stop]` (`start` when none is given).

## Tips

- Set it up first with `/setup add afk`, which records the rules and an explicit Merge answer; without it `start` points there and stops.
- `start` prints a goal for you to type in the host's `/goal` command; the model cannot type it for you.
- One lease covers every session on the machine. On Claude Code the question tool is denied during the lease, so questions go up the decision ladder instead of to you.
- On `stop` you get parked work, decisions and runs still waiting, and you mark each decision `kept` or `reversed`. There is no status command.
