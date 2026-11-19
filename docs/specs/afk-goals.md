# afk goals: a queue per project, coordinators woken where they run, a lease each session can read

Status: implemented; owner decisions 19/11/2026; in 0.3.3 (decision 5 of [afk-decider.md](afk-decider.md), which this status once waited for, is superseded by [afk-one-mode.md](afk-one-mode.md)). Implementation notes: the queue also caps open items at 30 and all items at 120; an `idle` record outside a repository is refused, so a session outside one is sent back once at each stop; `stop --all` and a new `start` remove the queues; the start procedure and the preflight live in `skills/afk/references/start.md`. It changes [afk-per-project.md](afk-per-project.md) and [afk-decider.md](afk-decider.md) where they say how a turn ends and what `stop` ends; where they disagree, this document wins from the release that ships its code.

Since 0.3.3 afk has one mode: [afk-one-mode.md](afk-one-mode.md) (owner decisions, 19/11/2026) removes `strict` and wins where this document disagrees: the stop hook's limit escape below now means only that the lease has ended or its setup changed, and decision 5 of the afk decider, which the status above waits for, is superseded (pull request 370 closed unmerged).

## Why

The afk run of 18/11/2026 (five repositories, an 8-hour lease) did useful work for about 9 of roughly 40 session-hours:

- Every coordinator ended its turn and nothing woke it again. Child sessions that finished stayed idle.
- Goals were small and listed "parked" as a way out: about 25 minutes of work in one repository, "stop at PR-ready" in another, no goal at all in a third. No goal carried a queue of next work.
- One repository's coordinator did not know a lease was live, ran no `afk.py` call and asked questions in plain text.
- One coordinator ran `afk.py stop` when its own work was done, and that ended the lease for every session on the machine.
- No merge the lease allowed was done: one repository reserved merges for the owner with no overlay offered, one had no hosted CI and no local receipt mode, and one could not tell the author's family.

The afk stop hook (0.3.3) now refuses the first stop of a turn under a lease. It still lets the turn end on a `parked` record, and it cannot give a session work it never had.

## Owner decisions (19/11/2026)

1. `/afk start` opens no new session. It finds, for each repository, the session that already holds the coordinator role, and sends it the lease there.
2. The repositories it covers are the ones set up for afk: a repository whose own settings record an afk section.
3. A park closes only that item; the agent goes on with the next one. The goal ends only when the project's queue is empty or the lease has ended.
4. The full spec and its code land in 0.3.3, together with the merge-blocker preflight (D) and the lease scope changes (E).

Review of this spec (Codex, 19/11/2026) narrowed two points: a repository with no open session cannot be found without a stored list of paths, which the plugin never keeps (C), and a stop scoped to one repository would need every lease-based permission (recorded approvals, the merge fallback, the overlay) to become repository-aware, so an agent's `stop` is refused instead and only the user's `/afk stop` ends the lease (E).

## Design

### A. The queue and the goal

- New command `afk.py goal --items-file <file>`: a JSON list of at most 30 items, each `{"label", "kind", "minutes"}`.
  - `label` is a short plain-words task label, as the ledger keeps (the `ID` character class plus spaces, at most 60 characters); no task data, paths or secrets.
  - `kind` is one of `pr`, `review`, `merge`, `task`, `fix`, `release-step`, `other`.
  - `minutes` is the agent's estimate, an integer from 1 to 480.
- The agent gathers the items before it runs the command, from the repository's open pull requests, the open tasks of the current spec, open review findings and the steps after a merge. It leaves out work the lease does not allow and work that waits on the owner.
- The command refuses when no lease is live (no lease, expired, stopped or setup changed). It writes the project's queue to the lease's private state, keyed by the repository identity digest (afk-per-project A), with each item numbered from 1 and `open`, and an integer `revision` that every change to the queue increments. A second `goal` call adds items to the queue and never removes one.
- It prints:
  - the goal line for the host's goal command: `Every item in the afk queue of this repository is done or parked, or the away lease has ended.`;
  - the queue, numbered, with the minutes left on the lease;
  - a fixed warning when the estimates add up to less than half of the minutes left (`the queue is short: add the next work`) or to more than the minutes left (it names the first item beyond).
- `afk.py log` takes `--item <n>` on `action`, `merge` and `parked` records. A `merge` or `action` record with `--item` and `--done` marks that item `done`; a `parked` record with `--item` marks it `parked`. An unknown number is refused.
- `afk.py log --kind idle` is refused while the repository's queue has an `open` item and the lease has not ended, and when the repository has no queue yet (run `goal` first, with an empty list when there is no work). The refusal names the open items. An accepted `idle` record keeps the queue's `revision` and the first 16 hex of the repository identity digest, so a later change to the queue (another session adds an item) makes that record stale.
- Enforcer: `afk.py` (script) for the queue file, its limits and the idle refusal. What goes into the queue, and the estimates, are agent judgment (advisory).

### B. How a turn ends

- The afk stop hook lets a stop through on an `idle` record of this session written since its previous stop whose repository digest equals the hook input's repository and whose `revision` equals the current revision of that repository's queue, and no longer on a `parked` record: a park closes an item, not the turn (decision 3). A stale `idle` record (the queue changed after it) does not count. Its fixed reason names `afk.py log --kind idle` alone. To compare, the hook reads one more value: the integer `revision` of that repository's queue file, nothing else from it.
- Every other escape stays: `stop_hook_active`, the lease no longer letting any action run (it ended or its setup changed; Lease hours is the only limit since [afk-one-mode.md](afk-one-mode.md)), and no lease, an expired, stopped or unreadable lease, or any error.
- What this guarantees, and what it does not: the hook sends the agent back once at each stop (`stop_hook_active` lets the next stop through, so it never loops). An agent that stops again right away can still end its turn with items open. What brings it back is the self-paced loop the goal step starts (`/loop` on Claude Code) and the host's goal command, which are agent judgment and host behaviour, not this hook.
- This changes the eleventh scoped exception in [CLAUDE.md](../../CLAUDE.md): its words naming `afk.py log --kind idle` and `--kind parked` as the way to end the turn, and the list of what the hook reads, which gains the queue's `revision`. The pull request that ships this code changes that text and the "afk stop hook" section of [PRIVACY.md](../../PRIVACY.md) in the same commit.
- Enforcer: the stop hook (hook) on Claude Code. On Codex and Antigravity it is advisory (agent judgment).

### C. Waking the coordinators

`/afk start`, run by the user, wakes the sessions that already coordinate each repository (decision 1). The user's invocation is the authority to message those sessions; it covers this one start only.

1. After `afk.py start` succeeds, list the host's sessions with its session tool. The host facts (which tool, which fields) belong in `delegate` `references/agents/<host>.md`, never in the skill body.
2. Candidates are sessions that are not archived, were not started by another session, and whose working folder lies in a repository's main checkout or one of its worktrees. A child session is never messaged; its coordinator hands it work.
3. Keep a repository only when it is set up for afk (decision 2): run `afk.py effective` in that folder and keep it when the new `Project settings: recorded` line shows. The list of repositories is never stored; it is rebuilt from the sessions at each start, so no path is written anywhere. A consequence: a repository set up for afk with no open session is not seen at all, and the start says so in one line ("repositories with no open session are not covered").
4. One session per repository: the one whose title marks it as the coordinator (`tidy` "Titles"), else the most recently active candidate. Two or more marked coordinators in one repository: message none, and list the repository as ambiguous.
5. Send each one the same fixed message, with only the repository's name filled in. It tells the session to check whether an away lease is live, and only if `afk.py goal` accepts, to load the afk lease rules, build its queue, set the host goal to the line it prints, start a self-paced loop, settle every question through afk "Decide", and end a turn only through `afk.py log --kind idle`.
6. Report, in the start summary: each repository messaged and its session; each ambiguous repository; each candidate repository that is not set up for afk; and the one line about repositories with no open session.
7. This session builds its own queue the same way.

Where the host has no tool that lists and messages sessions (Codex and Antigravity today), the start cannot see other sessions either: it prints the message once, without a repository name, for the user to paste into each coordinator session they want covered, and says so.

The message is a notification, never a grant. It carries no task data, no lease time and no authority. The authority is the lease the user started, read from canonical state: `afk.py goal` refuses when no lease is live, so a message sent with no lease, after expiry or after the user's stop changes nothing. A receiving session ignores a message that names another repository than its own. A message replayed or sent by another session during a live lease asks for nothing the lease does not already cover, because one lease covers every session on the machine (afk-per-project A): it can only make the session build its queue under that lease, and every action still passes `afk.py check`.

Enforcer: agent judgment (advisory) for finding and messaging sessions and for ignoring a message about another repository; `afk.py effective` (script) for the set-up test; `afk.py goal` (script) for refusing without a live lease.

### D. Merge-blocker preflight

Before the user leaves, and only when the repository's `Merge` setting lets the lease merge, the starting session checks each covered repository's open pull requests for what would park a merge, and reports it with the fix. It fixes nothing in another repository without the user's answer.

- It runs `merge_check.py <n> --repo <owner/name>` for each open pull request the queue names, and `--independent` where the lease merges by independent review. It reports each `BLOCK` line once per cause:
  - no checks reported and no local receipt mode: "turn on local receipts with `/setup add checks` in that repository";
  - an author family it cannot tell;
  - a missing review marker.
- It reads the repository's instruction files for a rule that keeps merges for the owner's own session. When it finds one and no afk overlay is in force, it reports it with the fix: "add an override entry with `/setup instructions` in that repository". This reading is agent judgment.
- Enforcer: `merge_check.py` (script) for the blockers it prints. The instruction reading and the report are agent judgment (advisory).

### E. Lease scope

- `afk.py stop` without `--all` is refused with one fixed line: an agent whose work is done logs `idle`; only the user's `/afk stop` ends the lease. `afk.py stop --all` ends the machine lease, as `stop` does today. The user-only `afk` skill runs `stop --all` on the user's `/afk stop` and on their return.
- A stop scoped to one repository is not built: every lease-based permission (approvals the permission hook holds, the same-family merge fallback, the overlay) reads the machine lease, and making each repository-aware is a larger change than the evidence asks for. The evidence was an agent that ended the lease because its own work was done; refusing plain `stop` and pointing to `idle` removes that.
- `/afk start <duration>` passes the duration as `--hours <n>`. The existing bound stays: 1 to 24, and never more than the setup's `Lease hours`. A duration that is not a whole number of hours is rounded down; under one hour it is refused.
- A session that starts while a lease is live already gets the fixed away line from the session-start hook. That line gains one fixed sentence: load the afk lease rules and run `afk.py goal` for this repository before other work. So a session that joins late knows the lease is live and gets a goal of its own.
- Enforcer: `afk.py` (script) for refusing plain `stop` and for `--hours`. That only the user runs `stop --all` is advisory (agent judgment): the command is the same for both. The session-start line is a hook; following it is agent judgment (advisory).

### F. Permissions for the new commands

`goal` joins the afk lease commands the permission hook allows without a prompt (`log`, `stop`, `review`, `effective`, `rules`, `check`, `packet-check`), under the same conditions: this install's own `afk.py`, plain arguments only, no other tool-input key. The native allow rules `/afk start` prints gain the same command. This changes the twelfth scoped exception in [CLAUDE.md](../../CLAUDE.md) (its list of lease commands) and the "afk permission hook" section of [PRIVACY.md](../../PRIVACY.md), in the same commit as the code, with a test that `goal --items-file <file>` is allowed and that `goal` with a shell metacharacter is not. `--items-file` names a file under `.finolabs/briefs/`, the same folder `packet-check` reads.

## What enforces what

| Rule | Enforcer |
| --- | --- |
| Queue shape, size, labels, item numbers | `afk.py goal` and `log --item` (script) |
| `goal` runs without a prompt under a lease | afk permission hook (hook), as for the other lease commands |
| `goal` refused without a live lease | `afk.py goal` (script) |
| `idle` refused while the queue has open items | `afk.py log` (script) |
| A stop goes back to work once unless a current `idle` record exists | afk stop hook, Claude Code (hook); elsewhere advisory |
| The agent keeps working after that one block | self-paced loop and host goal (agent judgment, advisory) |
| Which items enter the queue, the estimates | agent judgment (advisory) |
| Messaging the coordinators | agent judgment (advisory); host session tool |
| Set-up test for a repository | `afk.py effective` (script) |
| Merge blockers | `merge_check.py` (script); the instruction reading is advisory |
| Plain `stop` refused; `stop --all` ends the lease | `afk.py` (script); who runs `--all` is advisory |
| Joining session gets the goal step | session-start hook line; following it is advisory |

## Privacy

- The queue holds only fixed kind words, integer estimates, numbers, states and short task labels, which are ledger-style labels the agent writes itself. It holds no task data, paths, branch names or content.
- It lives in the lease's private state folder, follows the lease's file rules (no-follow, owner-checked, atomic) and is removed with the lease.
- The start keeps no list of repositories or sessions.
- The message between sessions goes through the host's own session tool on this machine; the plugin sends nothing anywhere.
- The "afk lease and log" section of [PRIVACY.md](../../PRIVACY.md) gains the queue in the same pull request as the code.

## Tests

- `goal` refuses a 31st item, a label over 60 characters or with a path or secret pattern, an unknown kind, and minutes outside 1 to 480. A second call appends.
- `log --kind idle` is refused with an open item and with no queue, and accepted when every item is `done` or `parked` and when the lease has ended.
- `log --item` refuses an unknown number. A `parked` record marks the item.
- `goal` refuses with no lease, an expired lease, a stopped lease and a changed setup.
- The stop hook blocks on a `parked` record alone, lets a current `idle` record through, and blocks on an `idle` record made stale by a later `goal` append (append-after-idle) and on an `idle` record of another repository whose queue has the same revision (cross-repository).
- Plain `stop` is refused and leaves the lease; `stop --all` removes it.
- `start --hours` keeps its bounds (existing tests).
- `effective` prints `Project settings: recorded` only for a repository with its own afk section.
- The session-start away line carries the goal sentence.

## Surfaces to update in the code pull request

`skills/afk/SKILL.md` steps 1 and 3 and "Stop and return" (`stop --all`); `scripts/afk_stop_hook.py`; `skills/afk/references/lease-rules.md` and `stops.md`; `delegate` `references/agents/claude-code.md` (the session tools); [CLAUDE.md](../../CLAUDE.md) exceptions 11 and 12; `scripts/afk_permit_hook.py` and `afk_native_rules.py`; the sections "afk lease and log", "afk stop hook" and "afk permission hook" of [PRIVACY.md](../../PRIVACY.md); `README.md` (the afk row and the 0.3.3 section); `skills/help/references/skills/afk.md`, `map.md` and `troubleshooting.md`; `skills/setup/references/check.md`; `skills/update/references/upgrades.json`; `docs/diagrams/afk-mechanism` sources and PNGs; `docs/specs/release-0.3.3.md` and `CHANGELOG.md`.

## Open

- `afk.py log` ergonomics (package H of the 18/11 review): one `decide` command that prompts for its fields by name. It is left for a later release; this spec adds only `--item` and `--done`.
- Whether the Codex app exposes a session list and message tool. Until someone verifies one, Codex gets the printed message.
