# How finolabs-vibecode compares with the hosts' own agent features

Claude Code, Codex and Antigravity each ship ways to run more than one agent and to keep an agent working. This plugin does not replace them. It adds the engineering practice around them: which agent should take a task, what proof it must leave, who reviews it, what may merge, and what an agent may do while you are away. Host facts below were checked against each host's documentation on 2026-11-12; hosts change, so follow the links before relying on a detail.

## Agent teams and subagents versus delegation

| | Host features | This plugin |
| --- | --- | --- |
| What it is | Parallel helpers inside one host: Claude Code [subagents](https://code.claude.com/docs/en/sub-agents.md) and experimental [agent teams](https://code.claude.com/docs/en/agent-teams.md), Codex [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), Antigravity [subagents](https://antigravity.google/docs/subagents) and [`/swarm`](https://antigravity.google/docs/swarm). | `delegate` hands a task to Claude Code, Codex or Antigravity, from whichever one you run in. |
| Who does the work | Models of the same host, with the parent's permission mode. | The agent and model your assignment matrix and quota pick, across vendors: graphics work to one family, image generation to another, reviews to a family other than the author's. |
| What survives the session | Mostly nothing: a team's config ends with the session; subagent results return to the caller. | A local dispatch ledger, verification receipts bound to a checkout's head, review markers on the pull request, and a dashboard of what ran and how it went. |
| What gates a merge | Nothing beyond the host's permission prompts. | Independent code and security reviews by another model family, `merge_check.py` at the reviewed head, and your yes (or your recorded afk Merge answer). |
| How work is shaped | Whatever the prompt asks. | `coding-router` picks depth and gates before the first edit; `checks` decides what proof is enough; `session-hygiene` keeps sessions named and handovers saved. |

They work together: an agent following `delegate` may still use its host's subagents inside its own task. The plugin decides what reaches `main`; the host decides how one task's work is split.

## afk versus loops, goals and scheduled runs

The host features keep an agent working. `afk` decides what it may do while you are away.

| Feature | What it does | What it does not do |
| --- | --- | --- |
| [`/loop`](https://code.claude.com/docs/en/scheduled-tasks.md) (Claude Code) | Repeats a prompt on an interval or at a pace Claude picks, in an open session; recurring tasks expire after seven days. | Decide which actions are allowed. |
| `/goal` ([Claude Code](https://code.claude.com/docs/en/goal.md), [Codex](https://learn.chatgpt.com/docs/developer-commands?surface=cli), [Antigravity](https://antigravity.google/docs/commands/goal)) | Keeps taking turns until a stated condition is met, or the agent says it is done. | Change the permission mode or bound what a turn may do. |
| Scheduled runs: Claude Code [routines](https://code.claude.com/docs/en/routines.md) (cloud), Codex [automations](https://learn.chatgpt.com/docs/automations), Antigravity [`/schedule`](https://antigravity.google/docs/commands/schedule) and [`/automation`](https://antigravity.google/docs/commands/automation) | Start work on a schedule or an event, some in the cloud while your machine is off. | Read this plugin's local lease or settings: a cloud run has no data root on your machine. |
| `afk` (this plugin) | A time-boxed lease for the whole machine: every action is checked (allowed work runs, the rest is parked for you), questions go up a decision ladder instead of waiting for you, merges pass the merge gate, and on return you mark each decision kept or reversed. | Start work, wake a session or keep it taking turns. |

### Using them together

- **`/afk start` plus `/goal`.** The goal keeps the session taking turns until the work is done; the lease bounds every action in those turns. Write the goal so it can finish while you are away, for example "every task in the list is merged or parked". On Claude Code, run the session in auto mode as the goal page recommends; `afk`'s question gate already turns questions into decisions.
- **`/afk start` plus a self-paced `/loop`.** Useful when the work waits on others: CI, reviews by another agent, a delegated run. The loop wakes the session to check and continue; each action still goes through `check`. Stop the loop when the lease ends, since a loop can outlive an eight-hour lease.
- **Scheduled cloud runs stay separate.** Give them self-contained tasks with the host's own permission mode; the lease, the assignment matrix and the ledger live on your machine and do not travel with them.
