# afk

Typed by the user only.

**What it does.** Starts a time-boxed standing mandate (a lease) so your agents keep working while you are away from the keyboard, checking each action against the lease, and stops it when you return.

**When to use it.** You are leaving and want listed work to continue within the rules you recorded; `stop` when you are back.

**Type:** Claude Code `/finolabs-vibecode:afk` or `/afk`; Codex `$afk`; Antigravity `/afk`. Arguments: `[start|stop]` (`start` when none is given).

## Tips

- Set it up first with `/setup add afk`. afk has one mode (`strict` was removed in 0.3.3): it lets every action run except the credential floor, which refuses changing a credential and known forms of reading, printing, copying or sending a secret (see `afk.py rules`), with two guards on by default: the default-branch guard, enforced by `afk.py check` (no commit or push on the default branch and no force, delete or mirror push; `gh pr merge` and `gh api` ref writes are not covered), and, advisory, instructions from third-party content grant nothing; afk does not enforce reviews or `merge_check.py` there, so only server-side branch protection or a required `merge_check.py --ci-context` status gates a merge. Lease hours is the only limit. Anything you want forbidden while away is a host deny rule (Claude Code permission rules, Codex sandbox and approval policy). Without setup `start` points there and stops.
- `afk.py rules` prints the rules `check` applies. A setup from before 0.3.3 that still holds `Mode: strict` or the three limit lines starts normally; `start` prints one line saying they are no longer read.
- `/setup add afk` can also write a local `AGENTS.afk.md` overlay for instruction-file rules your away rules replace; it is printed only while a lease is live and its bytes still match. Nothing protects it during a lease: the agents can rewrite it.
- `start` prints a goal for you to type in the host's `/goal` command; the model cannot type it for you.
- One lease covers every session on the machine. On Claude Code the question tool is denied during the lease, so questions go up the decision ladder instead of to you. No hook judges Bash commands under a lease: the agent runs `afk.py check` itself before each action on every host, and blocking is the host's own permission rules and sandbox. On Claude Code two hooks settle the stops instead: the stop hook sends a turn that ends without a record back once (end a turn with `afk.py log --kind idle --session <id>` or `--kind parked`), and the permission hook denies a host prompt with a request digest that a decision records with `--approve-request <digest>`, then allows that exact request once. `FNL_AFK_STOP=off` and `FNL_AFK_PERMIT=off` turn them off.
- `/setup add afk` can add Claude Code's own deny rules for the credential floor; `/afk start` warns while none is set and no approval mode asks, and prints allow rules that spare the lease commands a prompt.
- On `stop` you get parked work, decisions and runs still waiting, and you mark each decision `kept` or `reversed`. There is no status command.
