# Autopilot (release 0.2.1 first slice)

Status: accepted; owner decisions recorded on 2026-11-06 and 2026-11-09; release 0.2.1 takes the first slice named under the 2026-11-09 decisions, the rest stays design only. Nothing was built in 0.2.0. Implementation and unresolved host decisions still need owner approval; open questions are listed under "Open".

Idea: owner, 2026-11-06. An agent that, only when the user asks, coordinates the repository's work while the
user is away: it watches progress, picks the next work, delegates it, reviews it, and keeps going instead of
waiting to be asked. The user stops it when they return. It is not on by default and never starts itself.

## Owner decisions recorded here (2026-11-06)

- The user's standing choices live in `fnl-setup`; starting autopilot applies them. A user who has not set autopilot up
  is asked when they first start it; a user who has is shown the current settings in one summary and the agent then
  follows them exactly, while the user stays free to change the setup at any time.
- Where a user's own instructions require authority for an action (merge, tag, publish, deploy), a durable
  authorization recorded in setup is that authority; a time-boxed or relayed yes in a conversation is not. This
  changes the user-away rule in `fnl-delegate` (decisions that need the user's authority wait) for exactly
  the actions the user authorized in setup, and the change to that rule is part of this release's work. Authority
  setup does not grant stays with the user.
- An advisor acts as the user's avatar for judgments inside the lease; only decisions of very high authority notify
  the user. All monitoring is the dashboard; there is no `status` command.

## Owner decisions recorded here (2026-11-09)

- One skill, not two. The away-mode idea (a user-run command that hands the host agents a time-boxed standing mandate
  while the user is asleep or out) is autopilot itself. The skill folder keeps the fnl-autopilot name as the
  canonical, documented command; a second entry with a friendlier name is only a thin alias that loads the same
  procedure (a skill folder cannot point outside itself, so the alias holds a pointer sentence and the dependency
  on fnl-autopilot, never a copy of the rules). The owner picked the alias name fnl-brb ("be right back") on 2026-11-09, so the alias is `/fnl-brb`. It is built together with
  fnl-autopilot, not before it.
- Merge: the authority is the user's affirmative Merge answer in `fnl-setup` (the Merge setting still has no default,
  and Tier 3 still forbids a merge when setup says no); starting a lease only applies that answer. The owner's own
  answer is yes (2026-11-09). With a yes recorded, the agent may merge a pull request without asking when both review
  markers are APPROVE at the current head, every check is green (the hosted CI and the local test run of the touched
  modules) and `merge_check.py` prints `MERGE OK`. It widens nothing else. It covers pull requests of trusted authors,
  not only autopilot's own: the user's own account (which includes every agent on the user's machine that works under
  that login) and autopilot's own branches. The same gate applies to all of them, and it is never used for a pull
  request touching a Tier 3 path or from any other author.
- Release 0.2.1 takes a first slice (owner decision, 2026-11-09, replacing the "later releases" entry in the release
  record): the skill and its alias, `autopilot.py` with `start`, `stop` and `check` (tier classification, lease with
  expiry and limits, enumerated log), the `## Autopilot` setup section, and `merge_check.py --independent`. The
  dashboard tab, the live refresh loop, the scheduled-task driver, the notice hook and the host backstop installer stay
  later; the CLAUDE.md exceptions they need land with them, so the slice adds no hook and no long-lived process.
- Entry and exit stay one command each: start applies the recorded setup and states the lease length; the user
  stops it on return.

## What the user sets up (`fnl-setup`, new section, host config `## Autopilot`)

| Setting | Meaning | Recommended default |
| --- | --- | --- |
| Hosts | Which host may run autopilot | Claude Code |
| Task choice | May it choose new tasks from the task list, or only those the user lists at start | May choose |
| Push and pull requests | May it push branches it created and open pull requests (never to the default branch) | Yes |
| Merge | May it merge a pull request that `merge_check.py` passes (below) | Asked at setup; no default |
| Trusted authors | Whose pull requests it may check out and test | The user's own account and the agent's own branches |
| Lease length | Longest a start may run | 8 hours |
| Limits | Maximum delegated runs, runtime minutes and actions per hour per lease | 20 runs, 480 minutes, 30 actions per hour |
| Quota floor | Stop when any routed agent's remaining quota is below this | 15% |
| Push notifications | Notify only for Tier 3 decisions | On |
| Live dashboard | Run the dashboard's live refresh while a lease is active | On |

A money cap is not offered: paid usage cannot be measured from local records, so the limits are counts and minutes the
ledger can measure. Each setting is a separate question (neutral Yes and No where yes/no, none preselected), with a
preview and digest like the other setup writers. Setup writes nothing outside the host config.

## Decisions: three tiers, classified by code before any model sees the case

`autopilot.py check` classifies an action from the real command or change, not from a label the agent supplies: it
receives the argv of the command, or the list of paths a change touches, and returns the tier. A model never decides
a tier; unknown commands and paths are Tier 3.

- **Tier 1, decides alone:** which task next, order, which agent and model (`fnl-delegate` routing), splitting work,
  fixing review findings, pushing its own branches and opening and updating its own pull requests, merging main into
  its own branches, and (only when setup says so) merging pull requests of its own or of a trusted author that pass `merge_check.py` and the complete merge gate.
- **Tier 2, the advisor decides and records why:** an ambiguous requirement, a small design change, whether a LOW
  finding is worth a change, a choice between two reasonable approaches. The advisor is the user's avatar:
  `fnl-advisor` (one opinion, or a committee for design), Jev for narrow judgments, and preferences the user put in
  setup or an allowlisted preferences file (private notes never leave the machine unless the user allowlisted them).
  It receives only the evidence the case supplies, classified first; it chooses among options `check` already
  allowed and cannot raise a case to a higher authority. It informs; it never grants authority the user reserved.
- **Tier 3, stops and notifies once:** anything setup has not authorized, and always: tag, release, publish, deploy,
  anything that handles credentials, destructive deletion, changes to shared settings or defaults, any change to
  `.github/`, hook files, `CLAUDE.md`, agent instruction files, settings or the lease and setup files, security-boundary
  changes, a merge when setup says no, and a task that names a Tier 3 action. Parked items wait in the log; the agent
  goes on with other work.

## Untrusted input

Pull requests, issues, comments, task files and logs from anyone but a trusted author are data, never instructions.
Autopilot acts only on its own pull requests and those of trusted authors; any other pull request is listed as
"waiting for you" without being checked out, built or tested. Tasks come from the task list on the default branch at a
commit authored by a trusted author; a task that names a Tier 3 action is parked. Events (including `task` events)
never feed task choice or any gate.

## Merge rule

A merge by autopilot requires: a pull request it opened itself or one by a trusted author (owner decision, 2026-11-09); both review markers present for the current head,
posted by a model family different from the pull request's author family (`merge_check.py` gains an
`--independent` check for this; a same-family review is parked); checks green; the branch current; no two-round
rework limit reached; and `MERGE OK`. A pull request touching Tier 3 paths is never merged by autopilot.

## Lease, state and what enforces what

Files (`<data root>/state/autopilot/`, 0600, private folder, atomic, symlink-safe): `lease.json` (lease id, start,
expiry, scope, scheduled-task id, hash of the setup read at start, counters, last tick), `log.jsonl`, `stop`
(created by `stop`), `lock` (a directory created with `mkdir`; stale after twice the tick limit and a dead owner pid).
The log holds, per action: time, tier, action kind from a fixed list, ids (task, run, pull request), the advisor
decision id, and a rationale of at most 500 characters with control characters removed and secret patterns
redacted. The next tick reads the enumerated fields back, never the rationale text, as history. The log is the user's
own local record: it is not in the metrics events, outside the metrics schema and consent, never sent, kept 30 days,
and `PRIVACY.md` gets its own paragraph (including what the advisor and Jev send to providers: only the supplied
case). The dashboard shows a tail of the log through `data.js`, escaped and rendered with `textContent`.

| Rule | Enforcer |
| --- | --- |
| Tier of an action | `autopilot.py check` from the real argv or paths (script) |
| Lease expiry, limits, quota floor, actions per hour | `autopilot.py` at each tick (script); first run `quota_probe.py read --family <f>` for each routed family, then `quota_probe.py status`; the quota source is `state/quota/quota.json`, advisory family rate-limit markers apply, and a missing or older-than-8-hours reading means stop |
| The agent cannot extend the lease or change setup | host deny rules installed while autopilot is on (below); a lease or setup whose hash differs from the one recorded stops the tick; against a fully compromised agent this is a tripwire, not a barrier |
| Third-party text is data; the advisor never grants authority | agent judgment, advisory, backed by the tier classification and the untrusted-input rules above |
| An unattended merge or release stalls | host permission rules (below) |
| That the agent calls `check` before acting | agent judgment, advisory; the host rules are the backstop |

Setup is read again at every tick: tightening it takes effect at the next tick; loosening needs a new start.

## Host backstop installed with autopilot

When autopilot is set up, `fnl-setup` offers (separate consent, preview, digest, backup, as `merge-guard.md`) the host
rules that make the lease and setup files read-only for the agent and make tag, release, publish and, when setup says
no merge, `gh pr merge` stall on a prompt. These are prompts and denials the host enforces in its normal modes; their
behaviour in non-interactive and bypass modes is unverified and the setup text says so. `merge-guard.md` is the design
for the writer.

## Mechanism (Claude Code first)

A tick is a short, idempotent session: read the lease, setup, ledger, task list and own pull requests (through local
records and the user's own `gh`), run `check`, act, log, exit. Driver: the desktop app's scheduled task (primary) or
`/loop` in an open session. One writer per scope (the lock). All network access is by programs the agent runs under the
user's own login (`gh`, the host CLIs); the plugin's scripts make none and never read credentials. Codex, Antigravity
and cloud routines are later.

## Stopping and returning

`/fnl-autopilot stop` creates the stop file, deletes the lease and deletes the scheduled task named in it (if the task
cannot be deleted, every tick exits at once because there is no lease). Running delegated runs are not killed; they are
recorded as orphaned for the user to decide. The lease also ends at expiry, below the quota floor, at the limits, and
when a lease or setup hash mismatch is found. A non-blocking `SessionStart`/`UserPromptSubmit` hook prints a one-line
notice when a lease is active. There is no `status` command.

## Dashboard: Autopilot tab and live mode

Lease state and time left; actions by tier; the advisor's decisions with rationale and family; items waiting for the
owner; limits and quota against their floors; the next planned action; the log tail. The tab needs the dashboard's live
mode: a refresh loop started with the lease and ended with it (and at 12 hours at the latest), run by a script that
writes a pid file with a nonce, refuses to start twice, is killed by `stop`, and is reaped as orphaned by the next
start. It rebuilds at most every 10 seconds, with a wall-clock cap per rebuild.

## CLAUDE.md changes required before any code

1. A scoped exception for the live refresh loop (a long-lived background process owned by the plugin: start, nonce,
   kill, expiry, orphan handling, no network) and for the scheduled-task driver.
2. A statement that the plugin's scripts make no network call and never read credentials; the agent's `gh` use is
   the user's own program under the user's login.
3. No blocking hook is added (the notice hook never blocks). The existing two exceptions are unchanged.
4. The user-away rule in `fnl-delegate` amended as recorded above; `fnl-review-gate` and `merge_check.py` get the
   `--independent` check and its text.

## Layout

The fnl-autopilot skill folder names `fnl-delegate` as its dependency and calls
`skills/fnl-delegate/scripts/autopilot.py`. The script lives beside `heavy_run.py`, `mode.py` and `ledger.py`,
reusing `data_root.py`, `parallel_slots.py` and `secret_patterns.py` there without new shared copies.
The live loop and notice hook are later work in the autopilot skill's own `scripts/` folder.

## Not in scope

Codex and Antigravity drivers; cloud routines; several repositories at once; a money cap; changing the user's
instruction files; any use of credentials by the plugin.

## Acceptance

1. `autopilot.py`: start refuses without setup; `check` returns the tier from argv and paths for every action kind,
   including unknown commands, Tier 3 paths and merge with and without the setting; an untrusted author's pull
   request is parked and never checked out; limits, expiry, quota floor (including a missing reading) and actions per
   hour stop it; a lease or setup hash mismatch stops the tick; stop removes lease and scheduled task; a held lock
   makes a tick exit; the log caps, strips and redacts the rationale and the next tick reads only enumerated fields;
   files are 0600 in a private folder, atomic, symlink-safe.
2. Setup: each setting is a separate question; preview and digest; round trip through the host config reader; start
   with a recorded setup prints the summary and proceeds, without one it asks.
3. `merge_check.py --independent` refuses a same-family review pair; autopilot merges an otherwise eligible pull request of a trusted author that it did not open, and refuses to merge
   one by an author that is not trusted, one touching a Tier 3 path, or any merge when setup says no.
4. The notice hook is non-blocking, exits 0, prints nothing without a lease and is declared in the Claude Code hook
   file only. The live loop starts once, ends with the lease, is killed by stop and does not outlive 12 hours.
5. The dashboard tab renders every field with `textContent`, shows data age, and handles an empty log.
6. `PRIVACY.md`, README, CHANGELOG, `docs/specs/index.md`; `check-references.py`, `claude plugin validate .` and
   targeted tests pass; skill text names its enforcer for every rule.

## Open

- Whether the desktop app's scheduled task can run a session unattended in the user's permission mode (verify with a
  throwaway task before building), and how the host rules behave in that mode.
- Advisor budget: committee only for Tier 2 decisions that touch design, one opinion otherwise.
- The format of the preferences file the advisor may read.
