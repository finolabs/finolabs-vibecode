# afk

Typed by the user only.

**What it does.** Starts a time-boxed standing mandate (a lease) so your agents keep working while you are away from the keyboard, checking each action against the lease, and stops it when you return.

**When to use it.** You are leaving and want listed work to continue within the rules you recorded; `stop` when you are back.

**Type:** Claude Code `/finolabs-vibecode:afk` or `/afk`; Codex `$afk`; Antigravity `/afk`. Arguments: `[start|stop]` (`start` when none is given).

## Tips

- Set it up first with `/setup add afk`, which asks the mode first: `open` (the default) lets every action run except the credential floor, which refuses changing a credential and known forms of reading, printing, copying or sending a secret (see `afk.py rules`), with two guards on by default: the default-branch guard, enforced by `afk.py check` (no commit or push on the default branch and no force, delete or mirror push; `gh pr merge` and `gh api` ref writes are not covered), and, advisory, instructions from third-party content grant nothing; afk does not enforce reviews or `merge_check.py` there, so only server-side branch protection or a required `merge_check.py --ci-context` status gates a merge. `strict` records every rule and an explicit Merge answer. Without setup `start` points there and stops.
- `afk.py rules` prints the rules of both modes.
- `/setup add afk` can also write a local `AGENTS.afk.md` overlay for instruction-file rules your away rules replace; it is printed only while a lease is live and its bytes still match. Only `strict` protects it: under a live `open` lease the agents can rewrite it.
- `start` prints a goal for you to type in the host's `/goal` command; the model cannot type it for you.
- One lease covers every session on the machine. On Claude Code the question tool is denied during the lease, so questions go up the decision ladder instead of to you. No hook judges Bash commands under a lease: the agent runs `afk.py check` itself before each action on every host, and blocking is the host's own permission rules and sandbox.
- On `stop` you get parked work, decisions and runs still waiting, and you mark each decision `kept` or `reversed`. There is no status command.
