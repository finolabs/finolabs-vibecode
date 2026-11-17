# Agent contracts

What every delegate dispatch shares, whichever agent coordinates; each family's own contract is in its file under `agents/` (index below). Exact paths, wrappers and allow-rules for this machine live in the host config (see `SKILL.md`); recheck flags with each CLI's `--help`, since they change between versions.

By agent judgment, dispatch only families recorded present in host config's `Agents on this machine`, as `SKILL.md` "Route" says. A missing section keeps previous routing behavior and suggests `/setup scan`; recorded presence never grants reachability, model access or permissions.

Common to every headless dispatch: first lint the saved brief with `brief_check.py` from `handoff` (a required dependency for dispatch). Set `umask 077`; create `.finolabs/logs/` with `mkdir -p -m 700` before log redirection. `delegate_env.py` creates/checks that folder through `log_scan.py` and refuses an existing wider mode before starting the agent. Then run it in the background from the task's worktree, pass the brief from its file, close stdin (`< /dev/null`), wrap it in a hard-cap timer (`timeout`, or `perl -e 'alarm N; exec @ARGV'` where `timeout` is missing; exit 142 or 124 at the cap means `timeout`), and write the log and final message into the logs folder (`.finolabs/logs/`).

The wrapper is called only by these dispatch forms, never by a hook. `run_env.py` builds only
`PATH`, `HOME`, `LANG`, `TMPDIR`, `FNL_DISPATCH_ID` and the canonical host section's approved names.
For a second Claude install, pass `--claude-config-dir <absolute folder>` before `--`; the form chooses
that value explicitly, never inherits it. Put the hard-cap wrapper **after** `delegate_env.py --family <family> --`
so the timer and agent both receive the allowlist. `brief_check.py <brief>` must succeed before any form starts.
Use `log_scan.py show <log>` to read results; never read a raw log first (advisory, agent judgment).

**Residual risk:** HOME stays, so readable credential files, other agents' config, the plugin data root
and keychain-backed helpers remain reachable. The report says: "Protection is environment-only;
interactive, desktop-app and in-session subagents are not covered." Private HOME awaits the owner's decision.
A sandbox hiding those paths is stronger; do not create a private HOME here.

## Per-family contracts

Each family's headless form, read-only mode, end of run, quota and outcome mapping live in its own file. Read only the file of the family the route picked:

- Claude Code: [agents/claude-code.md](agents/claude-code.md)
- Codex: [agents/codex.md](agents/codex.md)
- Antigravity: [agents/antigravity.md](agents/antigravity.md)
- ZCode: [agents/zcode.md](agents/zcode.md)

## When an agent coordinates

The coordinator's own sandbox decides which delegates it can reach. Each delegate CLI needs network access and its own state and credential folders, which it reads by itself; the coordinator never reads them.

- **Claude Code coordinating**: Bash runs `codex exec` and `agy -p` under the session's permission rules; allow the exact command prefixes.
- **Codex coordinating**: the default `workspace-write` sandbox has no network and cannot reach other CLIs' home folders. Reaching `claude -p` or `agy -p` needs a sandbox the user has configured for it; without one, those delegates are unavailable. Codex's own subagents inherit its sandbox.
- **Antigravity coordinating**: allow `command(claude -p)` and `command(codex exec)` in the allow-rules and run without `--sandbox`; otherwise those calls are soft-denied. Both widen what Antigravity may run, so they need the user's approval and belong in the host config.

A delegate the coordinator cannot reach is **unavailable** for routing; record it in the host config rather than retrying it on each task.

## In-session subagents

Every host has its own subagents (Claude Code's Agent tool, Codex agents, Antigravity agents). Use them for advisors, committee members and read-only lookups, whose results come back into the coordinator's turn. They never own an implementation task: their work and state disappear with the turn.

`delegate_env.py --claude-config-dir` accepts only an absolute user-owned directory with no `..` or
symlink components, no group/world write permission and no git work tree at it or an ancestor, matching
the quota probe's directory checks. Refusal (including parsing) exits 125; child exit 2 stays 2.
Other child codes pass through except 125 and signal termination, which map to 1 to keep refusal distinct.
