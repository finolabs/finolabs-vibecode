# The map

## Skills

The skill folders and their purposes match the README.

| Skill | Use it when |
| --- | --- |
| `coding-router` | Starting or resuming any coding work, in any repository: depth (MIN, NORMAL, DEEP), review and security gates, proof, the stop-before-a-third-fix checkpoint, and a workflow path for Spec Kit (with its depth gate), mattpocock/skills, obra/superpowers, or none. |
| `tidy` | Keeping sessions healthy: context pressure, phase changes, stale titles, handovers, and remembering or recalling decisions, lessons and project state in one shared knowledge base (Orrery or an Obsidian vault); code facts stay in the repository. Opt-in Claude Code/Antigravity context snapshots, or an on-request Claude Code/Codex context probe, feed the compaction steward. Session titles start with one emoji for the kind of work. |
| `delegate` | Handing work to other agents (Claude Code, Codex, Antigravity, ZCode) and running it, coordinated from whichever one you run in: grading on five levels with one decision matrix (tier, effort, budget, who accepts), routing by agent and model through a dated capability map, the configured judge, quota fallback, parallel runs up to the limit you set for each project, across any mix of agent families, time budgets, liveness from artifacts, the heavy-job lock, verify-before-accept, handover and the dispatch ledger; running a spec as a coordinator with one app session per task, standby sessions and review gates. |
| `handoff` | Writing a self-contained brief and dispatching one task, or saving a handover through `tidy` so a later session or another agent continues the work. |
| `shape` | Brainstorming, discussing or stress-testing an idea, plan or design, or unclear requirements before building: an interview in rounds where each question waits for the decisions it depends on and comes with a recommended answer, through the host's native question tool; nothing is acted on until the user confirms the result. It runs first; `grilling` runs when `shape` is missing or the user asks for it by name. |
| `advisor` | Getting one second opinion from another model family, or convening two contrasting families for root-cause analysis and a plan when stuck or looping; both are read-only and spend quota, with approval governed by their procedure. |
| `versioning` | Bumping a version, tagging a release, or writing the changelog and release notes: SemVer, `0.y.z` until a stable release is declared, immutable `vX.Y.Z` tags, Keep a Changelog; runs the README checklist of `plugin-packaging` before a release. |
| `commit-messages` | Committing, writing a pull request description, or working with branches: atomic commits, imperative subjects, no secrets or build output, the host attribution trailer, and the branch flow (naming, base, sync, conflicts, merge, cleanup, backports). |
| `restore-point` | Saving the working tree to a private git ref before the agent edits, listing restore points and restoring one after a preview and a yes. User-invoked, git repositories only. |
| `afk` | Away from keyboard: starting a time-boxed standing mandate so your agents keep working while you are away, checking each action against its lease and tiers, and stopping on return. User-invoked; requires recorded setup. One mode (`strict` was removed in 0.3.3): every action runs under a lease except the credential floor, which refuses changing a credential and known forms of reading, printing, copying or sending a secret (see `afk.py rules`), with two guards on by default: the default-branch guard, enforced by `afk.py check` (no commit or push on the default branch and no force, delete or mirror push; `gh pr merge` and `gh api` ref writes are not covered), and, advisory, instructions from third-party content grant nothing. Lease hours is the only limit; anything else you want forbidden while away is a host deny rule (Claude Code permission rules and the native deny rules setup offers, Codex sandbox and approval policy). afk's check enforces neither reviews nor `merge_check.py`: only server-side branch protection or a required `merge_check.py --ci-context` status gates a merge. The decision ladder, the merge-gate procedure and the kept-or-reversed review are advisory steps. `afk.py rules` prints the rules. Set up with `/setup add afk`, which first asks whether the rules are for your account or only this repository; for a repository it asks only the guards you want different and saves them in its settings file. A setup from before 0.3.3 that still holds `Mode: strict` or the limit lines starts normally with one line saying they are no longer read. `/afk start [hours]` wakes the session that already coordinates each repository set up for afk and reports merge blockers; each repository keeps a queue (`afk.py goal`) whose goal line goes in the host's `/goal`, a park closes one item and the agent takes the next, and only the user's `/afk stop` ends the lease; on Claude Code a self-paced `/loop` keeps the session working, a question gate denies the question tool during the lease, a stop hook sends a turn back once unless the session recorded `idle` for its repository's current queue, and a permission hook answers the host's prompts only from approvals the decision ladder recorded (`--approve-request`). It runs the own-branch flow (edit, commit, pull request, review posting, merge gate, cleanup) without you; `check` exits 3 on Tier 3. A plugin-run loop, dashboard tab and scheduler are deferred. |
| `brb` | Older short name (be right back), kept as an alias of `afk`; follows the same procedure and arguments. |
| `pause` | Before you restart or shut the machine down: stops new work, lets running work finish, writes handovers and reports what recorded work remains, with an optional `--in <minutes>` deadline; `heavy_run.py` refuses new commands while it is active. User-invoked; never stops a process or declares the machine safe. |
| `gtg` | Short name (got to go) for `pause`; follows the same procedure and arguments. |
| `review-gate` | A user story is done or a pull request is about to merge: an independent code review, a disposition for every finding, a regression test per runtime fix. |
| `security-review-gate` | A change touches auth, permissions, private data, untrusted input or payments: a permission-boundary review, with negative tests proving that not even a record's existence leaks. |
| `ui-review-gate` | A change touches user-facing UI, or you ask to review the UI, audit the design, check accessibility or responsiveness, or optimise a form: a report-only review against WCAG 2.2 AA with measured evidence (contrast, target size, overflow, form fields) from read-only snippets run in the browser your host already exposes, and constraints such as "desktop layout unchanged" proved before and after a fix. Advisory: `merge_check.py` does not read it. |
| `checks` | Choosing targeted tests, checking current-head verification receipts, completing host/judge criterion checks and deciding whether to accept reported work; the coordinator keeps the verdict. Also runs a repository's stored checks locally (`checks.py run`, set up with `/setup add checks`), and covers a cheaper CI workflow and what CI minutes cost. |
| `plugin-packaging` | Packaging skills as a plugin for Claude Code, Codex and Antigravity from one repository: layout, manifests, the README standard and checklist, icon, marketplaces, checks. |
| `setup` | Configure user scope, project scope or both: Quick confirms inert defaults and asks companion choices; Advanced interviews each companion and offers widening features. `add <feature>` opens one feature, `check` is read-only, `scan` refreshes inventory, `mode` manages Delegation mode and Routing, and `instructions` drafts instruction files with approval per file; setup installs nothing. |
| `status` | Opening the usage dashboard: router coverage, skill and agent use, load cost, depth against review outcome, delegation and the review gate, from the usage events (after you consent in setup) and the dispatch ledger. Overview holds activity and reviews; Now shows repository-labelled running lanes, advisory slots, per-install quota and named repositories active in the last 24 hours. It also lists this repository's delegated runs still open. |
| `update` | Showing installed and cached available versions, updating through the host after a clear yes and walking the new version's setup checklist, showing what is new, targeting a chosen or pinned version, skipping a release, or stopping update notices. |
| `help` | Plugin help: you are new and do not know where to start, want to know what the plugin holds, or have a question about a skill, agent or script; it gives the first steps, lists the contents, explains the piece you name, or maps your situation to the next command, including companion skills from other packs. It answers questions; it does not ask another agent. |
| `ask` | Older name for `help`, kept as an alias; follows the same procedure and arguments. |
| `session-hygiene` | Older name for `tidy`, kept as an alias; follows the same procedure and arguments. |
| `open-source-review` | Before a repository goes public, and after: license, secrets in tree and history, internal leaks, clean payload, community files, repository settings, identity, data flow, plugin checks. |

## Situations

| Situation | Skill | Companion skills and native commands |
| --- | --- | --- |
| New to the plugin, or not sure what it holds | `help`, "Start" or "Contents" (`ask` is its older name) | |
| "Is it set up right?" or what happens automatically on this host | `/setup check` | |
| First time in this repository or on this machine | `/setup` | `/setup-matt-pocock-skills` if that pack is installed |
| Writing or revising your own instructions for every agent and repository | `/setup instructions` | |
| Adding or removing an agent, or refreshing allowed models | `/setup scan` | |
| Saving the working tree before the agent edits, or going back to a saved point | `/restore-point` | |
| Working while away, or stopping the mandate on return | `/afk start [hours]` or `/afk stop`, with `/brb` kept as an alias; start wakes each repository's coordinator session and each builds a queue whose goal line goes in `/goal`; during the lease a question goes up the decision ladder (`afk` "Decide") instead of to you | Recorded setup required (`/setup add afk` first asks account or this repository; for a repository it asks only the guards you want different); `/goal` and `/loop` keep the session taking turns |
| Cleaning up worktrees after a pull request merges | `commit-messages` "Branches" (`worktree_sweep.py list`; git does the removal); delegated runs' worktrees: `delegate` (`ledger.py` removes them once merged) | |
| About to restart or shut the machine down, and wanting running work drained first | `/pause [restart\|shutdown] [--in <minutes>]`; `/gtg` is the short name; `/pause resume` after the restart | |
| Showing or changing Delegation mode or Routing, including environment overrides | `/setup mode` | |
| Starting, resuming or redirecting coding work | `coding-router` | |
| Requirements unclear | `coding-router` (workflow adapter's clarification step, with questions put through the host's native question tool; advisory, agent judgment) | `/grill-me`, or `/grill-with-docs` to keep a glossary and ADRs |
| Brainstorming or discussing an idea, plan or design ("let's brainstorm", "let's discuss", in any language) | `shape` first (`coding-router` routes it when the idea leads to code) | `/grill-me` when `shape` is missing or you ask for it; `brainstorming` from obra/superpowers when you want many divergent design ideas |
| A design question only code can answer | `coding-router` | `prototype` |
| Ready to implement one seam | `coding-router` (depth, gates) | `tdd` for the red-green loop |
| Bug, failing CI, unexplained behavior | `coding-router` (workflow adapter's debug path, router checkpoint) | `diagnosing-bugs` |
| Handing one task to another agent (Claude Code, Codex, Antigravity, ZCode) with a brief, or restarting a timed-out run | `handoff`, which loads `delegate` for the route and gates | `/handoff` for a portable handoff document |
| Giving work to another agent, splitting work across agents, choosing an agent and model, parallel dispatch, quota, a watched run that stalls | `delegate` | |
| Which agent takes which work: who implements a work type at a level, who reviews, who advises and who judges | `delegate`, whose `route_pick.py pick` answers from the assignment matrix before each dispatch (a preference, never a block); set the matrix with `/setup add delegation` and review families, judge and posting with `/setup add roles` | |
| Stopping or switching and wanting the work continued later by a new session or another agent | `handoff` (Resume mode: writes a handover note and launches nothing) | |
| How the practice is working for you: router coverage, skill use, load cost, delegated runs, review outcomes | `/finolabs-vibecode:status` (opens the usage dashboard) | |
| Deleting the recorded usage data, or stopping the recording | `/finolabs-vibecode:status purge` (asks before deleting) | |
| Checking for a plugin update, skipping a release, or stopping update notices | `/update` (shows versions, asks before updating, then offers each open setup step of the new version) | |
| Seeing what a new version changed or asks of you, without changing anything | `/update whats-new` (`update_check.py whats-new`; read-only checklist) | |
| Updating to, or rolling back to, one exact released version | `/update <version>` (`update_check.py target <version> --evidence <file>` from `gh release view`) | |
| Holding the plugin on a version so newer-release notices stop | `/update pin <version>`, then `/update unpin` (`update_check.py pin` / `unpin`) | |
| Want a second opinion | `advisor` (proposed first and waits for your yes; spends quota) | |
| Stuck or looping on fixes | `advisor` committee procedure (proposed first and waits for your yes; spends two families' quota) | |
| A query on live data, an infrastructure change, a dashboard or a forecast | `coding-router`, which reads `references/non-code-work.md` | |
| Coordinating a spec across desktop app sessions | `delegate` | |
| Remembering a decision or lesson, or finding what was decided before | `tidy` | `obsidian-cli` from kepano/obsidian-skills for an Obsidian vault |
| Project drift or a milestone course check | `delegate`, then the `navigator` agent | |
| Confirm outcome anchors, work records or dashboard project settings | `/setup instructions` for conventions/anchors; `/setup add project` for settings | |
| Save which checks a repository runs before a push (read from its CI, `package.json`, `pyproject.toml` or `Makefile`) | `/setup add checks` (reads the files, runs nothing, saves after a yes) | |
| Assign review families, judge or posting setup | `/setup add roles` | |
| Set concurrent-run total and optional family caps, or the assignment matrix | `/setup add delegation` | |
| Read how much quota each agent has left before routing, or stop using one install before its week runs out | `/setup add quota` (opt-in, off by default; `--weekly-floor` per install) | |
| Turn usage metrics, project progress or the running-agent snapshot on or off | `/setup add metrics` (each needs its own consent) | |
| Optional companion skills from other packs | `/setup add companions` (questions and install commands only; installs nothing) | |
| Choose when the host compacts, so the `tidy` nudge has a threshold | `/setup add compaction` (also asked in the beginner and Quick paths): an advisory value by session kind, your number, user scope or one repository's untracked Claude Code local file | Without a window the Claude Code nudge stays silent |
| Read context counts for compaction | `/setup add compaction`, then `tidy` | Claude Code/Antigravity status line only; live delivery unverified |
| Read this session's context size on request | `tidy` (`context_snapshot.py probe`, needs `/setup add quota` to confirm `claude` or `codex`) | Claude Code and Codex; live delivery unverified |
| Long session, phase change, compaction | `tidy` | `/ask-matt` covers its phase-boundary choices |
| A story is done, or before merge | `review-gate` | `/code-review` (Claude Code), `codex review`, or `code-review` from Matt's pack |
| Change touches auth, permissions, private data, untrusted input | `security-review-gate` | `/security-review` (Claude Code); `security-audit` from Cloudflare for a full audit |
| Change touches user-facing UI, or a design, accessibility, responsive or form review | `ui-review-gate` | `shadcn` for requested fixes, `frontend-design` for a requested redesign, when installed |
| "Is it done?" or accepting someone else's work | `checks` | |
| Writing a commit | `commit-messages` | `pr` for the pull request body |
| Creating, syncing or merging a branch, or a backport | `commit-messages` "Branches" | |
| Release, tag, changelog | `versioning` | |
| Making a repository public, or checking a public repository's settings | `open-source-review` | `security-audit` from Cloudflare |
| Packaging skills as a plugin | `plugin-packaging` | |
| Checking a plugin's README before a release | `plugin-packaging` `references/readme.md` (`readme_check.py`, then the agent items) | |

## Agents and scripts

Paths below are relative to the full plugin root. There are three agent definitions; every distinct script name is listed once, either in root `scripts/` or as available only under a skill. Shared root scripts also have byte-identical copies in consuming skill folders. A standalone skill has only its own helpers; find the installed folder before giving a command. Explaining these pieces runs nothing.

| Agent | Purpose | Procedure |
| --- | --- | --- |
| `reviewer` | Reads changed hunks and their impact set, or reports native-engine coverage; no project edits. Authorized posting uses a private draft. | `review-gate` |
| `security-reviewer` | Traces the change and trust paths; no project edits. Authorized posting uses a private draft. | `security-review-gate` |
| `navigator` | Compares confirmed anchors with bounded evidence and proposes up to three corrections without editing; independent validation remains pending. | `delegate` |

### Shared and repository scripts

| Path | Purpose |
| --- | --- |
| `scripts/agent_processes.py` | Opt-in bounded process-name/elapsed-time snapshot for the dashboard; no repository attribution. |
| `scripts/assignments.py` | Parses, validates and renders the host config's `## Assignment matrix`, including each agent's `models` rules (which model for which kind, type or level, with a quota fallback); pure, reads no file and runs nothing. |
| `scripts/auto_gate.py` | Stores local repository-window handoff/keep decisions for the opt-in auto gate. |
| `scripts/auto_gate_hook.py` | Claude Code first-write nudge; allows on errors, never covers shell writes. |
| `scripts/away_gate_hook.py` | Claude Code question gate: denies `AskUserQuestion` only while a valid away lease exists, never reads the question, allows on every error. |
| `scripts/afk_overlay.py` | The afk overlay reader, trust anchor and Git index check shared by session start, afk and the instruction writer; `status` prints its state for `/setup check`. |
| `scripts/away_lease.py` | Safe away-lease reader, the permission hook's approval store and away ledger appender shared by afk, the question gate, the afk hooks and session start; any error means no lease. |
| `scripts/afk_stop_hook.py` | Claude Code `Stop` hook: under a live lease sends a turn back once unless the session wrote an `idle` record since its last stop for the hook folder's repository at its current queue revision, or the lease has ended or its setup changed; reads only the lease, its log, that queue's revision and the afk setup, keeps a per-session time mark, lets the stop through on every error. |
| `scripts/afk_permit_hook.py` | Claude Code `PermissionRequest` hook: under a live lease allows the install's own lease commands and an exact request a decision approved by digest, once; denies the rest with the request digest; compares digests only and falls back to the host prompt on every error. |
| `scripts/brief_check.py` | Lints brief headings, the environment rule and secret patterns without quoting matches; standalone copy in `handoff`. |
| `scripts/build-parity-plugins.sh` | Builds local evaluation plugins from this checkout and a supplied upstream skill checkout. |
| `scripts/check-references.py` | Checks local links, headings, names, inventories, ledger flags and shared mode copies. |
| `scripts/compact_nudge.py` | Claude Code and Codex (`--host codex`) `UserPromptSubmit` nudge: reads only the latest turn's token counts, its model id (held in memory only, to find a per-model threshold) and compaction settings, and at 80% and 90% of the threshold prints one line to run `tidy`; never blocks, always exits 0. |
| `scripts/compact_setup.py` | Previews/applies an approved documented native compaction threshold, at user scope or (`--project`, Claude Code) in a repository's untracked `.claude/settings.local.json`; on Claude Code `--model <id>` saves it for one model only, and `--clear-model-overrides` removes per-model values in the same write. |
| `scripts/compact_stop_hook.py` | Opt-in Antigravity transcript-size stop; no content read, live delivery unverified. |
| `scripts/checks_list.py` | Reads a repository's `.finolabs/vibecode/checks.json` only while it matches its approved digest (never the host config), with its local-receipt mode, digests a list, and writes or matches the private local checks receipt; runs no command. |
| `scripts/context_snapshot.py` | Records/reads Claude Code or Antigravity status-line context counts, probes Claude Code or Codex on request through the confirmed program, and feeds the steward. |
| `scripts/context_steward.py` | Applies the deterministic action table to supplied counts, threshold and boundary; never compacts. |
| `scripts/data_root.py` | Resolves account-owned canonical storage and checks safe paths; environment overrides cannot select trusted state. |
| `scripts/delegate_env.py` | Starts headless forms with approved environment names; HOME remains reachable. With a valid `FNL_DISPATCH_ID` it appends one `ended` ledger line (id, time, exit code) after the child exits. |
| `scripts/fnl_metrics.py` | Shared consent, metadata schema, storage, retention and event helpers. |
| `scripts/git_metadata.py` | Reads bounded local Git metadata without starting Git. |
| `scripts/handover_state.py` | Stores/reads private bounded handovers; compact SessionStart can re-inject them on Claude Code/Codex. |
| `scripts/instructions_write.py` | Previews and writes one approved instruction file/block with digest and backups, including the local afk overlay `AGENTS.afk.md` (kept out of Git, digest recorded). |
| `scripts/judge.py` | Screens bounded questions, validates supplied host answers or calls optional Jev, checks an away evaluation table (`check-table`), and discloses fallback; neither judge accepts work. |
| `scripts/log_scan.py` | Scans logs, shows redacted views and applies digest-bound local redaction; never reads a raw log into a receipt. |
| `scripts/merge_notice_hook.py` | Claude Code reminder after a successful `gh pr merge` that ends the command line: one fixed line saying finished delegated runs' merged worktrees are being removed (with `FNL_WORKTREE_CLEAN=manual`, that `ledger.py clean-worktrees` removes them by hand; with `off`, that nothing removes them), pointing to `worktree_sweep.py list` for others and to renaming the session when the merge closed a spec, story or its main task; it starts one detached `ledger.py clean-worktrees --background` run (`FNL_WORKTREE_CLEAN=manual` or `off` stops it); quoted excluded flags print nothing; stores nothing, always exits 0. |
| `scripts/metrics_hook.py` | Records consented usage metadata and triggers local dashboard refreshes. |
| `scripts/mode.py` | Shows effective settings/sources and writes previewed confirmed changes for `/setup mode`. |
| `scripts/nav_state.py` | Collects bounded current anchors/metadata, screens payloads and checks report references; it does not prove drift. |
| `scripts/open_dispatch_nudge.py` | Claude Code prompt reminder: one fixed line, at most every 30 minutes per session, counting this session's dispatches with no ledger outcome that ended or passed their budget; reads only the ledger and its own mark, never denies, `FNL_DISPATCH_NUDGE=off` disables it. |
| `scripts/parallel_slots.py` | Reads user-set total/per-family capacity; advisory snapshots, not reservations or a ledger-start gate. |
| `scripts/post_review.py` | Posts a bounded marker-checked private draft to the checkout's repository only when authorized. |
| `scripts/precompact.py` | Prints constant summary instructions (what the summary must keep); Claude stdout feeds summary instructions, Codex plain stdout does not reach the model. |
| `scripts/proof_nudge.py` | Claude Code `Stop` reminder: when this session committed the current head and no `checks` or `verify_claim.py` receipt names it, one fixed line asks for the targeted tests (or `checks`) before reporting done, once per head per session; reads only git refs, the HEAD reflog and receipt heads, never blocks, `FNL_PROOF_NUDGE=off` disables it. |
| `scripts/project_progress.py` | Reads bounded task/work-record/repository facts and manages consented per-repository settings, labels and registration. |
| `scripts/project_store.py` | Resolves a validated repository identity (a linked worktree only when its metadata points back) and reads or writes the approved project settings file. |
| `scripts/quota_limit_hook.py` | Records only Claude family/time on opt-in StopFailure `rate_limit`; starts no reading. |
| `scripts/quota_probe.py` | Reads quota on demand before routing and reports cached per-install pools and advisory markers; `status` shows an install's weekly floor. |
| `scripts/record.py` | Router, keep, task and judge metadata receipts; persists current-head verification metadata. |
| `scripts/review_config.py` | Reads canonical role/posting settings; writes nothing. |
| `scripts/review_route.py` | Chooses review families before a run, prefers independence and discloses same-family fallbacks; `--level` applies level-bound `models` rules; treats an install's weekly pools below its recorded weekly floor as out of quota; builds an in-memory review packet. |
| `scripts/route_task.py` | Prints matrix tier, effort, budget and family order for a kind/grade; the coordinator chooses the model. |
| `scripts/run_env.py` | Builds the allowlisted child environment for headless delegates and verification commands. |
| `scripts/secret_patterns.py` | Shared secret-pattern and environment-dump detection for briefs and logs. |
| `scripts/session_start.py` | Read-only Claude Code/Codex reminder and fixed state summary, with advisory slots, a fixed warning when the main checkout is off its default branch, a validated session id line, under a live lease the away line asking the session to run `afk.py goal`, and optional context/handover. |
| `scripts/statusline_setup.py` | Previews/applies/removes the opt-in context recorder; existing status lines get a manual recipe. |
| `scripts/update_check.py` | Cached update status, skip/never/pin preferences, the detached fixed-endpoint release check, the upgrade-notes checklist (`whats-new`, `onboard seen`/`skip`) and evidence-checked `target`. |
| `skills/setup/scripts/upgrade_state.py` | Read-only checks behind the upgrade-notes checklist and `setup check`: whether each note's legacy host settings or approved files are still present, so a done step shows as done. |
| `scripts/verify_claim.py` | Checks head, scope and targeted tests, writes verification metadata and prepares host-judge evidence; grants no acceptance. |
| `scripts/select_tests.py` | Lists the test modules that name a file changed since a base, treating shared copies as one and selecting a module whose `# select-tests: reads <folder>/` line covers the file, with commands of at most two modules; runs no test. |

### Skill-only scripts

| Path | Purpose |
| --- | --- |
| `skills/commit-messages/scripts/worktree_sweep.py` | Read-only list of linked worktrees (escaped path, branch, size, clean or dirty, unpushed, merged, candidate); under each candidate prints `git worktree remove -- <path>` and `git branch -d -- <branch>`, shell-quoted, for the agent to run, so git does the removal. Deletes nothing. Copies in `review-gate` and `delegate`, where `ledger.py` uses it to remove finished runs' merged worktrees. |
| `skills/plugin-packaging/scripts/readme_check.py` | Checks a plugin repository's README against the standard in `plugin-packaging` `references/readme.md`: section order, badges, counts and tables, hosts and install commands, descriptions, license, images, links and placeholders; prints `FAIL`/`PASS` per item and the external links to open. Reads files only; advisory. |
| `skills/checks/scripts/checks.py` | Runs or shows the repository's approved stored checks (a changed or unapproved check file runs nothing) in order, heavy checks through `heavy_run.py` and checks the file marks light directly outside the heavy-job lock, stops at the first failure, narrows Python test modules with `--changed`, and writes a local receipt only for a whole passing run on a clean, unmoved head when that mode is on; `run --dispatch <id>` writes, on the same conditions and whatever that mode, the verification receipt `ledger.py finish --outcome accepted` needs. `usage --from <file>` summarises hosted CI runs, minutes, the document-only share and days left from a run list the agent produced; no network call and no process. |
| `skills/delegate/scripts/afk.py` | afk lease, action classification (Tier 1, or Tier 3 for the credential floor, the default-branch guard and parser errors) against one repository identity, a read-only view of the guards it applies (also printed by `start` as a `This folder` line), and private action log, `log --kind review-fallback` included; an allowed `gh pr merge --match-head-commit` records the pin that `log --kind merge --head` needs; `log --kind decision --approve-request <digest>` records a one-time approval for the afk permission hook; `goal --items-file` keeps a private queue per repository, `log --item <n> [--done]` closes items and `log --kind idle` is refused while one is open; plain `stop` is refused and `stop --all` ends the lease; `effective` adds `Project settings: recorded|none`; `start` prints one line for a retired `Mode: strict` or limit line; `rules` prints the rule table (`skills/afk/references/rules.md`); executes nothing. |
| `skills/delegate/scripts/heavy_run.py` | Runs one heavy command at a time per machine under a kernel lock, with load and memory gates, a wait cap and a maximum run time. |
| `skills/delegate/scripts/ledger.py` | Records runs; accepted finishes need a current-head receipt or explicit reason-digested exception, except a review dispatch, accepted on its posted review (`--review-url`). `stale [--older-than-hours <n>]` previews this repository's open records past twice their budget and 24 hours (id, age, label); `--all-projects` widens it with a warning; `stale --close --digest <digest>` appends one closing `finish` line per previewed record, never `accepted`; summaries leave those closed-late records out of the rates and medians. `finish --retro` marks a record written after the fact, left out of the medians. |
| `skills/delegate/scripts/pause.py` | `pause` marker: start, status (open dispatches, heavy jobs, checkpoints) and resume; stops no process and runs nothing. |
| `skills/delegate/scripts/route_pick.py` | Answers which agent takes a work type at a level from the assignment matrix and cached quota, with the dropped agents and why, and with `--kind` the model each agent would use for that kind of work (its `models` rules, falling back when an Antigravity model pool is out of quota), dropping an install whose weekly pool is under the user's weekly floor; a preference that never blocks. |
| `skills/restore-point/scripts/restore_point.py` | Saves/lists/previews/restores private git snapshots; captures non-ignored untracked files and keeps extra current files on restore. |
| `skills/review-gate/scripts/merge_check.py` | Checks posted reviews (and, where the base names `ui-review-gate`, the router marker's `ui=yes|no` and a `kind=ui` review for `ui=yes`), the low-risk lane and router marker when the base adopted the gate; with the local-receipt mode on, a matching local checks receipt stands in for missing or failing hosted checks and is named as such. `--ci-context <name>` runs it as a hosted commit status (leaves its own status out, accepts `BLOCKED`, no local receipt, exits 3 while another hosted check runs). `--independent` requires each reviewing family to differ from the author's; `--fallback-family <family>` counts the author's own family's markers during a live lease, or outside one when `## Reviews` records `Same-family security fallback: yes` (no router-trigger condition there), only when every other family is out and the fallback reviewer line is present; under an `open` lease, with the fallback line (or a non-author configured role) alone. A weekly floor is never evidence that a family is out. |
| `skills/setup/scripts/agent_scan.py` | Previews fixed local `--version` inventory; writes only after confirmation. |
| `skills/setup/scripts/afk_native_rules.py` | Previews and writes Claude Code's own deny rules for the afk credential floor into `permissions.deny` of the settings files you name, with a digest and backup; `--remove` takes them out. |
| `skills/setup/scripts/afk_setup.py` | Previews and writes only the `## afk` section of the host config (an older `## Autopilot` section is left for the user to delete), with a digest and backup; the two guards come first, and it never writes a Mode or limit line. |
| `skills/setup/scripts/checks_setup.py` | Detects a repository's checks without running them, then previews and applies its `.finolabs/vibecode/checks.json` and approved digest after a digest-bound yes (undo: `remove`); a check is an argument array, never a shell string, and the host config is never opened. Also sets the local-receipt mode and installs or removes the optional pre-push hook (resolved hooks folder, refusal under `core.hooksPath`, backup, no silent overwrite). `ci` writes one cheaper CI workflow from the list, previewed; never commits. |
| `skills/setup/scripts/checkup.py` | Read-only setup/instruction evidence; no host commands or credentials. |
| `skills/setup/scripts/compact_stop_setup.py` | Previews/installs/removes the separately consented Antigravity size-stop hook. |
| `skills/setup/scripts/data_location.py` | Previews/copies plugin data into an empty approved folder and publishes the pointer last. |
| `skills/setup/scripts/matrix_setup.py` | Previews, validates, migrates and applies only the host config's `## Assignment matrix` after a digest-bound yes; `choices` lists the helper names setup offers as one multiple-choice question (family, presence from the scan, the coordinator), read-only; `migrate` is the only reader left of the retired `## Agent levels` and `## Agent roles`; runs no command and makes no network call. |
| `skills/setup/scripts/quota_setup.py` | Previews exact quota executable paths, and any `--weekly-floor <family>/<label>=<percent>` per recorded install, and applies only the approved digest-bound plan. |
| `skills/setup/scripts/setup_features.py` | Shows/records/clears declined features; a decline is not a consent. |
| `skills/status/scripts/refresh.py` | Rebuilds/opens local dashboard data; manages metrics consent/purge and the separately approved Antigravity metrics hook. |
| `skills/ui-review-gate/scripts/contrast.js` | Read-only page snippet: text and UI-component contrast against the computed background, with the WCAG 2.2 threshold that applies; uncertain readings marked for a check by eye. Returns JSON; no network, storage or navigation. |
| `skills/ui-review-gate/scripts/targets.js` | Read-only page snippet: interactive elements below 24 by 24 CSS px (blocking unless the 2.5.8 spacing or inline exception applies) and from 24 to 43 px (low). Returns JSON. |
| `skills/ui-review-gate/scripts/overflow.js` | Read-only page snippet: whether the page scrolls sideways at the current width, the elements that cause it, and the regions that scroll inside themselves. Returns JSON. |
| `skills/ui-review-gate/scripts/fields.js` | Read-only page snippet: the ordered form fields with name, type, `inputmode`, `autocomplete`, label and required state, never their values. Returns JSON. |

## Rules

- A skill command with a leading `/` is for the user to type; on Codex use `$`. The user-only declarations are enforced on Claude Code; equivalent invocation policy on Codex/Antigravity remains unverified. Names without `/` load on their own when the task matches, or the user can type them.
- In a Spec Kit repository, Spec Kit owns the process. Companion process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to it; companion phase tools (`grilling`, `tdd`, `diagnosing-bugs`, `prototype`, `code-review`) work inside its phases.
- Companion skills come from [mattpocock/skills](https://github.com/mattpocock/skills), [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill), [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills), [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design), [finolabs/markmap-skills](https://github.com/finolabs/markmap-skills) and [typesafe-ai/skills](https://github.com/typesafe-ai/skills) (all MIT); `codex review` is native; Claude Code review instruments may need to be installed or enabled as setup describes. When one is not installed, say so and point to that repository's install instructions; install nothing yourself. The packs are independent: neither endorses the other.
- For Route mode, name the matching skill and command in one or two sentences. When no row fits, say so and name the closest two, with the one question that would decide between them.

Project progress and work tracking are configured per repository through `/setup add project`, and stored with the parallel limit and the dashboard label in the repository's own settings file (`.finolabs/vibecode/settings.json` in the main checkout, approved in the data root); since 0.2.5 `host.md` sections and global `Ledger project:` and `Task file:` lines for them are no longer read. The instructions component writes the confirmed convention and Outcome anchors. The small host judge is the default; Jev requires the user’s own authorization and budget, and `typesafe-ai` is optional cookbook guidance outside the call path.

Parallel capacity is user-set (total 1–32, optional family caps, default 3 when absent, unknown when malformed); checks are advisory and never reserve slots. Headless hygiene is environment-only; interactive, desktop-app and in-session subagents are not covered, and private HOME remains deferred. Role/posting setup grants no rights. Relay counters are unimplemented, and navigator/judge validation remains unverified against independent cases.
