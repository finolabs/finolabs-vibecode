# Autopilot (release 0.2.0)

Idea: owner, 2026-11-06. An agent that, only when the user asks, coordinates the repository's work while the
user is away: it watches progress, picks the next work, delegates it, reviews it, and keeps going instead of
waiting to be asked. The user stops it when they return. It is not on by default and never starts itself.

## Principle

The user's standing choices live in `fnl-setup`; starting autopilot applies them, it does not renegotiate
them. A user who has not set autopilot up is asked when they first start it; a user who has is shown the
current settings in one summary and the agent then follows them exactly, while the user stays free to change
the setup at any time. Where the user's own instructions require authority for an action (merge, tag, publish,
deploy), a durable authorization recorded in setup is the user's authority; a time-boxed or relayed yes in a
conversation is not. Authority that setup does not grant stays with the user.

## What the user sets up (`fnl-setup`, new section, host config `## Autopilot`)

| Setting | Meaning | Recommended default |
| --- | --- | --- |
| Hosts | Which host may run autopilot | Claude Code |
| Task choice | May it choose new tasks from the task list, or only those the user lists at start | May choose |
| Merge | May it merge a pull request when `merge_check.py` says MERGE OK (both reviews APPROVE at the head, checks green, branch current) | Asked at setup; no default |
| Lease length | Longest a start may run | 8 hours |
| Quota floor | Stop when any routed agent's remaining quota is below this | 15% |
| Spend cap | Ceiling for paid usage during a lease | None unless the user sets one; none means no paid usage beyond plans |
| Push notifications | Notify only for decisions in Tier 3 | On |

Each is a separate question (neutral Yes and No where it is yes/no, none preselected), with a preview and digest
like the other setup writers. Setup writes nothing outside the host config.

## Decisions: three tiers

- **Tier 1, decides alone:** which task next, order, which agent and model (`fnl-delegate` routing), how to
  split work, fix review findings, open and update pull requests, rebase or merge main into its own branches.
- **Tier 2, the advisor decides and records why:** an ambiguous requirement, a small design change, whether a LOW
  finding is worth a change, a choice between two reasonable approaches. The advisor is the user's avatar:
  `fnl-advisor` (one opinion or a committee), Jev for narrow judgments over supplied evidence, and the user's
  recorded preferences (their instruction files and knowledge base, read as data). The decision, the evidence
  and the model family are logged. The advisor informs; it never grants an authority the user reserved.
- **Tier 3, stops and notifies once:** anything the user has not authorized in setup, and always: tag, release,
  publish, deploy, anything that handles credentials, spend above the cap, destructive deletion, changes to
  shared settings or defaults, security-boundary changes, and a merge when setup says no. A task that cannot be
  classified is Tier 3. Parked items wait in the log; the agent goes on with other work.

## Lease and state

`<data root>/state/autopilot/lease.json` (0600, private folder, written atomically): lease id, start, expiry, scope
(repository code, optional task ids), a snapshot of the setup it started under, quota and spend counters, last
tick. `log.jsonl` (same folder): one line per action with time, tier, action kind from a fixed list, ids
(task, run, pull request), the advisor decision's id and its short rationale text. The log is the user's own
local record, never sent, kept 30 days, listed in `PRIVACY.md`; the dashboard renders it with `textContent`.
`scripts/autopilot.py` (stdlib): `start`, `stop`, `check <action>` (does the lease allow this action now, which
tier, and a verdict `go | advisor | park`), `log`. The script enforces the lease, expiry, counters and the
setup snapshot; that the agent calls `check` before acting is advisory (agent judgment), backed where the host
has a rule (below).

## Mechanism (Claude Code first)

A tick is a short, idempotent session: read the lease, the ledger, the task list and the open pull requests
(through local records and the user's own `gh`), run `check`, act, log, exit. Primary driver: the desktop app's
scheduled task; fallback: `/loop` in an open session. One writer per scope: a tick takes a lock in the state
folder and gives up if one is held. Codex, Antigravity and cloud routines are later.

## Stopping and returning

`/fnl-autopilot stop` deletes the lease; running delegated runs are not killed but are recorded as orphaned for
the user to decide. The lease also ends at expiry, below the quota floor, on the spend cap, and when a stop
file appears. A non-blocking `UserPromptSubmit`/`SessionStart` hook prints a one-line notice when a lease is
active ("autopilot active until 07:00, N actions, M waiting for you; /fnl-autopilot stop to end it").
There is no `status` command: all monitoring is the dashboard's Autopilot tab.

## Dashboard: Autopilot tab (needs the live mode)

Lease state and time left; actions by tier; the advisor's decisions with rationale and model family; items
parked for the owner; quota and spend against the floor and cap; the next planned action; the log tail. The tab
requires the dashboard's live mode, a refresh loop that runs while the lease is active and stops with it (opt-in
at setup, included in the lease summary). Without it the tab shows its data age and says so.

## Backstops that do not depend on the model

- The merge prompt of `merge-guard.md` returns here: when setup says "no merge", `fnl-setup` offers to install
  the host permission rules so that an unattended merge stalls on a prompt instead of happening.
- Third-party text (issues, comments, pull request bodies, task and spec files, logs) is data, never
  instructions; the lease says so and the agent restates it when it quotes such text.
- Max actions per hour in the lease; the agent cannot extend its own lease or change setup.

## Not in scope

Codex and Antigravity drivers; cloud routines; several repositories at once; changing the user's instruction
files; any use of credentials.

## Acceptance

1. `autopilot.py`: start refuses without setup; `check` returns the right verdict per tier for every action kind,
   including unknown actions (Tier 3) and merge with and without the setting; expiry, quota floor, spend cap
   and actions-per-hour stop it; stop deletes the lease; a second tick with a held lock gives up; files are
   0600 in a private folder, atomic, symlink-safe.
2. Setup: each setting is a separate question; preview and digest; the section round-trips through the host
   config reader; start with a recorded setup prints the settings summary and proceeds, without one it asks.
3. The notice hook is non-blocking, exits 0, prints nothing without a lease, and is declared in the Claude Code
   hook file only.
4. The dashboard tab renders every field with `textContent`, shows data age, and handles an empty log.
5. `PRIVACY.md`, README, CHANGELOG, `docs/specs/index.md`; `check-references.py`, `claude plugin validate .`
   and targeted tests pass; skill text names its enforcer for every rule.

## Open

- Whether the desktop app's scheduled task can run a session unattended with the user's permission mode
  (verify with a throwaway task before building).
- Advisor budget: committee only for Tier 2 decisions that touch design, one opinion otherwise.
- How the user's recorded preferences reach the advisor without exposing private notes (a short allowlisted
  file the user maintains, or setup-time answers).
