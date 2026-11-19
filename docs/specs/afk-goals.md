# afk goals: a queue per project, coordinators woken where they run, a lease each session can read

Status: accepted; owner decisions 19/11/2026; code lands in 0.3.3 after the decision 5 change of [afk-decider.md](afk-decider.md) merges, because both edit `afk.py`. It changes [afk-per-project.md](afk-per-project.md) and [afk-decider.md](afk-decider.md) where they say how a turn ends and what `stop` ends; where they disagree, this document wins from the release that ships its code.

## Why

The afk run of 18/11/2026 (five repositories, an 8-hour lease) did useful work for about 9 of roughly 40 session-hours:

- Every coordinator ended its turn and nothing woke it again. Child sessions that finished stayed idle.
- Goals were small and listed "parked" as a way out: about 25 minutes of work in one repository, "stop at PR-ready" in another, no goal at all in a third. No goal carried a queue of next work.
- One repository's coordinator did not know a lease was live, ran no `afk.py` call and asked questions in plain text.
- One session's `afk.py stop` ended the lease for every session on the machine.
- No merge the lease allowed was done: one repository reserved merges for the owner with no overlay offered, one had no hosted CI and no local receipt mode, and one could not tell the author's family.

The afk stop hook (0.3.3) now refuses the first stop of a turn under a lease. It still lets the turn end on a `parked` record, and it cannot give a session work it never had.

## Owner decisions (19/11/2026)

1. `/afk start` opens no new session. It finds, for each repository, the session that already holds the coordinator role, and sends it the lease there.
2. The repositories it covers are the ones set up for afk: a repository whose own settings record an afk section.
3. A park closes only that item; the agent goes on with the next one. The goal ends only when the project's queue is empty or the lease has ended.
4. The full spec and its code land in 0.3.3, together with the merge-blocker preflight (D) and the lease scope changes (E).

## Design

### A. The queue and the goal

- New command `afk.py goal --items-file <file>`: a JSON list of at most 30 items, each `{"label", "kind", "minutes"}`.
  - `label` is a short plain-words task label, as the ledger keeps (the `ID` character class plus spaces, at most 60 characters); no task data, paths or secrets.
  - `kind` is one of `pr`, `review`, `merge`, `task`, `fix`, `release-step`, `other`.
  - `minutes` is the agent's estimate, an integer from 1 to 480.
- The agent gathers the items before it runs the command, from the repository's open pull requests, the open tasks of the current spec, open review findings and the steps after a merge. It leaves out work the lease does not allow and work that waits on the owner.
- The command writes the project's queue to the lease's private state, keyed by the repository identity digest as the limit counters are (afk-per-project A), with each item numbered from 1 and `open`. A second `goal` call adds items to the queue and never removes one.
- It prints:
  - the goal line for the host's goal command: `Every item in the afk queue of this repository is done or parked, or the away lease has ended.`;
  - the queue, numbered, with the minutes left on the lease;
  - a fixed warning when the estimates add up to less than half of the minutes left (`the queue is short: add the next work`) or to more than the minutes left (it names the first item beyond).
- `afk.py log` takes `--item <n>` on `action`, `merge` and `parked` records. A `merge` or `action` record with `--item` and `--done` marks that item `done`; a `parked` record with `--item` marks it `parked`. An unknown number is refused.
- `afk.py log --kind idle` is refused while the repository's queue has an `open` item and the lease has not ended, and when the repository has no queue yet (run `goal` first, with an empty list when there is no work). The refusal names the open items.
- Enforcer: `afk.py` (script) for the queue file, its limits and the idle refusal. What goes into the queue, and the estimates, are agent judgment (advisory).

### B. How a turn ends

- The afk stop hook lets a stop through on an `idle` record of this session written since its previous stop, as today, and no longer on a `parked` record: a park closes an item, not the turn (decision 3). Its fixed reason names `afk.py log --kind idle` alone.
- Every other escape stays: `stop_hook_active`, the lease's limits for the repository reached, and no lease, an expired, stopped or unreadable lease, or any error.
- Since `idle` is refused while the queue has open items (A), a turn can end on its own only when the queue is empty, the limits are reached or the lease has ended.
- This changes the eleventh scoped exception in `CLAUDE.md` ("names `afk.py log --kind idle` and `--kind parked` as the way to end the turn"). The pull request that ships this code changes that text and the "afk stop hook" section of `PRIVACY.md` in the same commit.
- Enforcer: the stop hook (hook) on Claude Code. On Codex and Antigravity it is advisory (agent judgment).

### C. Waking the coordinators

`/afk start`, run by the user, wakes the sessions that already coordinate each repository (decision 1). The user's invocation is the authority to message those sessions; it covers this one start only.

1. After `afk.py start` succeeds, list the host's sessions with its session tool. The host facts (which tool, which fields) belong in `delegate` `references/agents/<host>.md`, never in the skill body.
2. Candidates are sessions that are not archived, were not started by another session, and whose working folder lies in a repository's main checkout or one of its worktrees. A child session is never messaged; its coordinator hands it work.
3. Keep a repository only when it is set up for afk (decision 2): run `afk.py effective` in that folder and keep it when the new `Project settings: recorded` line shows. The list of repositories is never stored; it is rebuilt from the sessions at each start, so no path is written anywhere.
4. One session per repository: the one whose title marks it as the coordinator (`tidy` "Titles"), else the most recently active candidate. Two or more marked coordinators in one repository: message none, and list the repository as ambiguous.
5. Send each one the same fixed message, with only the lease's end time, its mode and the repository's name filled in. It tells the session that a lease is live, to load the afk lease rules, to build its queue with `afk.py goal`, to set the host goal to the line it prints, to start a self-paced loop, to settle every question through afk "Decide", and to end a turn only through `afk.py log --kind idle`.
6. Report, in the start summary: each repository messaged and its session; each repository with no coordinator session, which gets nothing ("open a session there before you leave"); each ambiguous repository; and each candidate repository that is not set up for afk.
7. This session builds its own queue the same way.

Where the host has no tool that lists and messages sessions (Codex and Antigravity today), the start prints the same message once per repository for the user to paste, and says so.

The message is text the coordinator writes; it carries no task data and no instruction beyond the lease's own rules. A receiving session treats it as the user's mandate, because the user started it, and still runs `afk.py check` before each action.

Enforcer: agent judgment (advisory) for finding and messaging sessions; `afk.py effective` (script) for the set-up test.

### D. Merge-blocker preflight

Before the user leaves, and only when the repository's `Merge` setting lets the lease merge, the starting session checks each covered repository's open pull requests for what would park a merge, and reports it with the fix. It fixes nothing in another repository without the user's answer.

- It runs `merge_check.py <n> --repo <owner/name>` for each open pull request the queue names, and `--independent` where the lease merges by independent review. It reports each `BLOCK` line once per cause:
  - no checks reported and no local receipt mode: "turn on local receipts with `/setup add checks` in that repository";
  - an author family it cannot tell;
  - a missing review marker.
- It reads the repository's instruction files for a rule that keeps merges for the owner's own session. When it finds one and no afk overlay is in force, it reports it with the fix: "add an override entry with `/setup instructions` in that repository". This reading is agent judgment.
- Enforcer: `merge_check.py` (script) for the blockers it prints. The instruction reading and the report are agent judgment (advisory).

### E. Lease scope

- `afk.py stop` ends only the current repository's part in the lease. It marks that repository's counters `stopped`, so its `check` answers `spent` while other repositories go on. `afk.py stop --all` ends the machine lease, as `stop` does today.
- The user-only `afk` skill runs `stop --all` on the user's `/afk stop` and on their return. An agent that ran out of work logs `idle` instead.
- `/afk start <duration>` passes the duration as `--hours <n>`. The existing bound stays: 1 to 24, and never more than the setup's `Lease hours`. A duration that is not a whole number of hours is rounded down; under one hour it is refused.
- A session that starts while a lease is live already gets the fixed away line from the session-start hook. That line gains one fixed sentence: load the afk lease rules and run `afk.py goal` for this repository before other work. So a session that joins late knows the lease is live and gets a goal of its own.
- Enforcer: `afk.py` (script) for `stop` and `--hours`. The session-start line is a hook; following it is agent judgment (advisory).

## What enforces what

| Rule | Enforcer |
| --- | --- |
| Queue shape, size, labels, item numbers | `afk.py goal` and `log --item` (script) |
| `idle` refused while the queue has open items | `afk.py log` (script) |
| A turn ends only on `idle` | afk stop hook, Claude Code (hook); elsewhere advisory |
| Which items enter the queue, the estimates | agent judgment (advisory) |
| Messaging the coordinators | agent judgment (advisory); host session tool |
| Set-up test for a repository | `afk.py effective` (script) |
| Merge blockers | `merge_check.py` (script); the instruction reading is advisory |
| `stop` ends one repository; `stop --all` ends the lease | `afk.py` (script) |
| Joining session gets the goal step | session-start hook line; following it is advisory |

## Privacy

- The queue holds only fixed kind words, integer estimates, numbers, states and short task labels, which are ledger-style labels the agent writes itself. It holds no task data, paths, branch names or content.
- It lives in the lease's private state folder, follows the lease's file rules (no-follow, owner-checked, atomic) and is removed with the lease.
- The start keeps no list of repositories or sessions.
- The message between sessions goes through the host's own session tool on this machine; the plugin sends nothing anywhere.
- `PRIVACY.md` ("afk lease") gains the queue in the same pull request as the code.

## Tests

- `goal` refuses a 31st item, a label over 60 characters or with a path or secret pattern, an unknown kind, and minutes outside 1 to 480. A second call appends.
- `log --kind idle` is refused with an open item and with no queue, and accepted when every item is `done` or `parked` and when the lease has ended.
- `log --item` refuses an unknown number. A `parked` record marks the item.
- The stop hook blocks on a `parked` record alone and lets an `idle` record through.
- `stop` marks only the current repository, and its `check` answers `spent` while another repository's `check` still runs. `stop --all` removes the lease.
- `start --hours` keeps its bounds (existing tests).
- `effective` prints `Project settings: recorded` only for a repository with its own afk section.
- The session-start away line carries the goal sentence.

## Surfaces to update in the code pull request

`skills/afk/SKILL.md` steps 1 and 3 and "Stop and return"; `skills/afk/references/lease-rules.md` and `stops.md`; `delegate` `references/agents/claude-code.md` (the session tools); `CLAUDE.md` exception 11; `PRIVACY.md` ("afk lease", "afk stop hook"); `README.md` (the afk row and the 0.3.3 section); `skills/help/references/skills/afk.md`, `map.md` and `troubleshooting.md`; `skills/setup/references/check.md`; `skills/update/references/upgrades.json`; `docs/diagrams/afk-mechanism` sources and PNGs; `docs/specs/release-0.3.3.md` and `CHANGELOG.md`.

## Open

- `afk.py log` ergonomics (package H of the 18/11 review): one `decide` command that prompts for its fields by name. It is left for a later release; this spec adds only `--item` and `--done`.
- Whether the Codex app exposes a session list and message tool. Until someone verifies one, Codex gets the printed message.
