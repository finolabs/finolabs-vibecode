# The map

## Skills

The 19 skill folders and their purposes match the README.

| Skill | Use it when |
| --- | --- |
| `fnl-coding-router` | Starting or resuming any coding work, in any repository: depth (MIN, NORMAL, DEEP), review and security gates, proof, the stop-before-a-third-fix checkpoint, and a workflow path for Spec Kit (with its depth gate), mattpocock/skills, obra/superpowers, or none. |
| `fnl-session-hygiene` | Keeping sessions healthy: context pressure, phase changes, stale titles, handovers, and remembering or recalling decisions, lessons and project state in one shared knowledge base (Orrery or an Obsidian vault); code facts stay in the repository. Opt-in Claude Code/Antigravity context snapshots feed the compaction steward; Codex is not covered by the recorder. |
| `fnl-delegate` | Handing work to other agents (Claude Code, Codex, Antigravity) and running it, coordinated from whichever one you run in: grading on five levels with one decision matrix (tier, effort, budget, who accepts), routing by agent and model through a dated capability map, the configured judge, quota fallback, parallel runs up to the limit you set for each project, across any mix of agent families, time budgets, liveness from artifacts, the heavy-job lock, verify-before-accept, handover and the dispatch ledger; running a spec as a coordinator with one app session per task, standby sessions and review gates. |
| `fnl-handoff` | Writing a self-contained brief and dispatching one task, or saving a handover through session hygiene so a later session or another agent continues the work. |
| `fnl-advisor` | Getting one second opinion from another model family, or convening two contrasting families for root-cause analysis and a plan when stuck or looping; both are read-only and spend quota, with approval governed by their procedure. |
| `fnl-versioning` | Bumping a version, tagging a release, or writing the changelog and release notes: SemVer, `0.y.z` until a stable release is declared, immutable `vX.Y.Z` tags, Keep a Changelog. |
| `fnl-commit-messages` | Committing, writing a pull request description, or working with branches: atomic commits, imperative subjects, no secrets or build output, the host attribution trailer, and the branch flow (naming, base, sync, conflicts, merge, cleanup, backports). |
| `fnl-restore-point` | Saving the working tree to a private git ref before the agent edits, listing restore points and restoring one after a preview and a yes. User-invoked, git repositories only. |
| `fnl-autopilot` | Starting a time-boxed standing mandate while you are away, checking each action against its lease and tiers, and stopping on return. User-invoked; requires recorded setup. The setup feature follows separately; the live loop, dashboard tab, scheduler and hooks are deferred. |
| `fnl-brb` | Short name for `fnl-autopilot` (be right back); follows the same procedure and arguments. |
| `fnl-review-gate` | A user story is done or a pull request is about to merge: an independent code review, a disposition for every finding, a regression test per runtime fix. |
| `fnl-security-review-gate` | A change touches auth, permissions, private data, untrusted input or payments: a permission-boundary review, with negative tests proving that not even a record's existence leaks. |
| `fnl-verification` | Choosing targeted tests, checking current-head verification receipts, completing host/judge criterion checks and deciding whether to accept reported work; the coordinator keeps the verdict. |
| `fnl-plugin-packaging` | Packaging skills as a plugin for Claude Code, Codex and Antigravity from one repository: layout, manifests, icon, marketplaces, checks. |
| `fnl-setup` | Configure user scope, project scope or both: Quick confirms inert defaults and asks companion choices; Advanced interviews each companion and offers widening features. `add <feature>` opens one feature, `check` is read-only, `scan` refreshes inventory, `mode` manages Delegation mode and Routing, and `instructions` drafts instruction files with approval per file; setup installs nothing. |
| `fnl-status` | Opening the usage dashboard: router coverage, skill and agent use, load cost, depth against review outcome, delegation and the review gate, from the usage events (after you consent in setup) and the dispatch ledger. Overview holds activity and reviews; Now shows repository-labelled running lanes, advisory slots, per-install quota and named repositories active in the last 24 hours. It also lists this repository's delegated runs still open. |
| `fnl-update` | Showing installed and cached available versions, updating through the host after a clear yes, skipping a release, or stopping update notices. |
| `fnl-ask` | You are new and do not know where to start, want to know what the plugin holds, or have a question about a skill, agent or script: it gives the first steps, lists the contents, explains the piece you name, or maps your situation to the next command, including companion skills from other packs. |
| `fnl-open-source-review` | Before a repository goes public, and after: license, secrets in tree and history, internal leaks, clean payload, community files, repository settings, identity, data flow, plugin checks. |

## Situations

| Situation | Skill | Companion skills and native commands |
| --- | --- | --- |
| New to the plugin, or not sure what it holds | `fnl-ask`, "Start" or "Contents" | |
| "Is it set up right?" or what happens automatically on this host | `/fnl-setup check` | |
| First time in this repository or on this machine | `/fnl-setup` | `/setup-matt-pocock-skills` if that pack is installed |
| Writing or revising your own instructions for every agent and repository | `/fnl-setup instructions` | |
| Adding or removing an agent, or refreshing allowed models | `/fnl-setup scan` | |
| Saving the working tree before the agent edits, or going back to a saved point | `/fnl-restore-point` | |
| Working while away, or stopping the mandate on return | `/fnl-autopilot start` or `/fnl-autopilot stop`; `/fnl-brb` is the short name | Recorded setup required; setup feature follows separately |
| Showing or changing Delegation mode or Routing, including environment overrides | `/fnl-setup mode` | |
| Starting, resuming or redirecting coding work | `fnl-coding-router` | |
| Requirements unclear | `fnl-coding-router` (workflow adapter's clarification step, with questions put through the host's native question tool; advisory, agent judgment) | `/grill-me`, or `/grill-with-docs` to keep a glossary and ADRs |
| A design question only code can answer | `fnl-coding-router` | `prototype` |
| Ready to implement one seam | `fnl-coding-router` (depth, gates) | `tdd` for the red-green loop |
| Bug, failing CI, unexplained behavior | `fnl-coding-router` (workflow adapter's debug path, router checkpoint) | `diagnosing-bugs` |
| Handing one task to another agent (Claude Code, Codex, Antigravity) with a brief, or restarting a timed-out run | `fnl-handoff`, which loads `fnl-delegate` for the route and gates | `/handoff` for a portable handoff document |
| Giving work to another agent, splitting work across agents, choosing an agent and model, parallel dispatch, quota, a watched run that stalls | `fnl-delegate` | |
| Stopping or switching and wanting the work continued later by a new session or another agent | `fnl-handoff` (Resume mode: writes a handover note and launches nothing) | |
| How the practice is working for you: router coverage, skill use, load cost, delegated runs, review outcomes | `/fnl-status` (opens the usage dashboard) | |
| Deleting the recorded usage data, or stopping the recording | `/fnl-status purge` (asks before deleting) | |
| Checking for a plugin update, skipping a release, or stopping update notices | `/fnl-update` (shows versions and asks before updating) | |
| Want a second opinion | `fnl-advisor` (proposed first and waits for your yes; spends quota) | |
| Stuck or looping on fixes | `fnl-advisor` committee procedure (proposed first and waits for your yes; spends two families' quota) | |
| A query on live data, an infrastructure change, a dashboard or a forecast | `fnl-coding-router`, which reads `references/non-code-work.md` | |
| Coordinating a spec across desktop app sessions | `fnl-delegate` | |
| Remembering a decision or lesson, or finding what was decided before | `fnl-session-hygiene` | `obsidian-cli` from kepano/obsidian-skills for an Obsidian vault |
| Project drift or a milestone course check | `fnl-delegate`, then the `fnl-navigator` agent | |
| Confirm outcome anchors, work records or dashboard project settings | `/fnl-setup instructions` for conventions/anchors; `/fnl-setup add project` for settings | |
| Assign review families, judge or posting setup | `/fnl-setup add roles` | |
| Set concurrent-run total and optional family caps | `/fnl-setup add delegation` | |
| Read context counts for compaction | `/fnl-setup add compaction`, then `fnl-session-hygiene` | Claude Code/Antigravity status line only; live delivery unverified |
| Long session, phase change, compaction | `fnl-session-hygiene` | `/ask-matt` covers its phase-boundary choices |
| A story is done, or before merge | `fnl-review-gate` | `/code-review` (Claude Code), `codex review`, or `code-review` from Matt's pack |
| Change touches auth, permissions, private data, untrusted input | `fnl-security-review-gate` | `/security-review` (Claude Code); `security-audit` from Cloudflare for a full audit |
| "Is it done?" or accepting someone else's work | `fnl-verification` | |
| Writing a commit | `fnl-commit-messages` | `pr` for the pull request body |
| Creating, syncing or merging a branch, or a backport | `fnl-commit-messages` "Branches" | |
| Release, tag, changelog | `fnl-versioning` | |
| Making a repository public, or checking a public repository's settings | `fnl-open-source-review` | `security-audit` from Cloudflare |
| Packaging skills as a plugin | `fnl-plugin-packaging` | |

## Agents and scripts

Paths below are relative to the full plugin root. There are three agent definitions and 47 distinct script names: 37 in root `scripts/` and 10 available only under a skill. Shared root scripts also have byte-identical copies in consuming skill folders. A standalone skill has only its own helpers; find the installed folder before giving a command. Explaining these pieces runs nothing.

| Agent | Purpose | Procedure |
| --- | --- | --- |
| `fnl-reviewer` | Reads changed hunks and their impact set, or reports native-engine coverage; no project edits. Authorized posting uses a private draft. | `fnl-review-gate` |
| `fnl-security-reviewer` | Traces the change and trust paths; no project edits. Authorized posting uses a private draft. | `fnl-security-review-gate` |
| `fnl-navigator` | Compares confirmed anchors with bounded evidence and proposes up to three corrections without editing; independent validation remains pending. | `fnl-delegate` |

### Shared and repository scripts

| Path | Purpose |
| --- | --- |
| `scripts/agent_processes.py` | Opt-in bounded process-name/elapsed-time snapshot for the dashboard; no repository attribution. |
| `scripts/auto_gate.py` | Stores local repository-window handoff/keep decisions for the opt-in auto gate. |
| `scripts/auto_gate_hook.py` | Claude Code first-write nudge; allows on errors, never covers shell writes. |
| `scripts/brief_check.py` | Lints brief headings, the environment rule and secret patterns without quoting matches; standalone copy in `fnl-handoff`. |
| `scripts/build-parity-plugins.sh` | Builds local evaluation plugins from this checkout and a supplied upstream skill checkout. |
| `scripts/check-references.py` | Checks local links, headings, names, inventories, ledger flags and shared mode copies. |
| `scripts/compact_setup.py` | Previews/applies an approved documented native compaction threshold. |
| `scripts/compact_stop_hook.py` | Opt-in Antigravity transcript-size stop; no content read, live delivery unverified. |
| `scripts/context_snapshot.py` | Records/reads Claude Code or Antigravity status-line context counts and feeds the steward; Codex is out of scope. |
| `scripts/context_steward.py` | Applies the deterministic action table to supplied counts, threshold and boundary; never compacts. |
| `scripts/data_root.py` | Resolves account-owned canonical storage and checks safe paths; environment overrides cannot select trusted state. |
| `scripts/delegate_env.py` | Starts headless forms with approved environment names; HOME remains reachable. |
| `scripts/fnl_metrics.py` | Shared consent, metadata schema, storage, retention and event helpers. |
| `scripts/git_metadata.py` | Reads bounded local Git metadata without starting Git. |
| `scripts/handover_state.py` | Stores/reads private bounded handovers; compact SessionStart can re-inject them on Claude Code/Codex. |
| `scripts/instructions_write.py` | Previews and writes one approved instruction file/block with digest and backups. |
| `scripts/judge.py` | Screens bounded questions, validates supplied host answers or calls optional Jev, and discloses fallback; neither judge accepts work. |
| `scripts/log_scan.py` | Scans logs, shows redacted views and applies digest-bound local redaction; never reads a raw log into a receipt. |
| `scripts/metrics_hook.py` | Records consented usage metadata and triggers local dashboard refreshes. |
| `scripts/mode.py` | Shows effective settings/sources and writes previewed confirmed changes for `/fnl-setup mode`. |
| `scripts/nav_state.py` | Collects bounded current anchors/metadata, screens payloads and checks report references; it does not prove drift. |
| `scripts/parallel_slots.py` | Reads user-set total/per-family capacity; advisory snapshots, not reservations or a ledger-start gate. |
| `scripts/post_review.py` | Posts a bounded marker-checked private draft to the checkout's repository only when authorized. |
| `scripts/precompact.py` | Prints a nonblocking reminder; Claude stdout feeds summary instructions, Codex plain stdout does not reach the model. |
| `scripts/project_progress.py` | Reads bounded task/work-record/repository facts and manages consented per-repository settings, labels and registration. |
| `scripts/quota_limit_hook.py` | Records only Claude family/time on opt-in StopFailure `rate_limit`; starts no reading. |
| `scripts/quota_probe.py` | Reads quota on demand before routing and reports cached per-install pools and advisory markers. |
| `scripts/record.py` | Router, keep, task and judge metadata receipts; persists current-head verification metadata. |
| `scripts/review_config.py` | Reads canonical role/posting settings; writes nothing. |
| `scripts/review_route.py` | Chooses review families before a run, prefers independence and discloses same-family fallbacks; builds an in-memory review packet. |
| `scripts/route_task.py` | Prints matrix tier, effort, budget and family order for a kind/grade; the coordinator chooses the model. |
| `scripts/run_env.py` | Builds the allowlisted child environment for headless delegates and verification commands. |
| `scripts/secret_patterns.py` | Shared secret-pattern and environment-dump detection for briefs and logs. |
| `scripts/session_start.py` | Read-only Claude Code/Codex reminder and fixed state summary, with advisory slots and optional context/handover. |
| `scripts/statusline_setup.py` | Previews/applies/removes the opt-in context recorder; existing status lines get a manual recipe. |
| `scripts/update_check.py` | Cached update status, skip/never preferences and the detached fixed-endpoint release check. |
| `scripts/verify_claim.py` | Checks head, scope and targeted tests, writes verification metadata and prepares host-judge evidence; grants no acceptance. |

### Skill-only scripts

| Path | Purpose |
| --- | --- |
| `skills/fnl-delegate/scripts/ledger.py` | Records runs; accepted finishes need a current-head receipt or explicit reason-digested exception. |
| `skills/fnl-restore-point/scripts/restore_point.py` | Saves/lists/previews/restores private git snapshots; captures non-ignored untracked files and keeps extra current files on restore. |
| `skills/fnl-review-gate/scripts/merge_check.py` | Checks posted reviews, the low-risk lane and router marker when the base adopted the gate. |
| `skills/fnl-setup/scripts/agent_scan.py` | Previews fixed local `--version` inventory; writes only after confirmation. |
| `skills/fnl-setup/scripts/checkup.py` | Read-only setup/instruction evidence; no host commands or credentials. |
| `skills/fnl-setup/scripts/compact_stop_setup.py` | Previews/installs/removes the separately consented Antigravity size-stop hook. |
| `skills/fnl-setup/scripts/data_location.py` | Previews/copies plugin data into an empty approved folder and publishes the pointer last. |
| `skills/fnl-setup/scripts/quota_setup.py` | Previews exact quota executable paths and applies only the approved digest-bound plan. |
| `skills/fnl-setup/scripts/setup_features.py` | Shows/records/clears declined features; a decline is not a consent. |
| `skills/fnl-status/scripts/refresh.py` | Rebuilds/opens local dashboard data; manages metrics consent/purge and the separately approved Antigravity metrics hook. |

## Rules

- A skill command with a leading `/` is for the user to type; on Codex use `$`. The seven user-only declarations are enforced on Claude Code; equivalent invocation policy on Codex/Antigravity remains unverified. Names without `/` load on their own when the task matches, or the user can type them.
- In a Spec Kit repository, Spec Kit owns the process. Companion process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to it; companion phase tools (`grilling`, `tdd`, `diagnosing-bugs`, `prototype`, `code-review`) work inside its phases.
- Companion skills come from [mattpocock/skills](https://github.com/mattpocock/skills), [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill), [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills), [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design), [finolabs/markmap-skills](https://github.com/finolabs/markmap-skills) and [typesafe-ai/skills](https://github.com/typesafe-ai/skills) (all MIT); `codex review` is native; Claude Code review instruments may need to be installed or enabled as setup describes. When one is not installed, say so and point to that repository's install instructions; install nothing yourself. The packs are independent: neither endorses the other.
- For Route mode, name the matching skill and command in one or two sentences. When no row fits, say so and name the closest two, with the one question that would decide between them.

Project progress and work tracking are configured per repository through `/fnl-setup add project`; global `Ledger project:` and `Task file:` lines remain readable in 0.2.0 and 0.2.1 and are removed in 0.3.0. The instructions component writes the confirmed convention and Outcome anchors. The small host judge is the default; Jev requires the user’s own authorization and budget, and `typesafe-ai` is optional cookbook guidance outside the call path.

Parallel capacity is user-set (total 1–32, optional family caps, default 3 when absent, unknown when malformed); checks are advisory and never reserve slots. Headless hygiene is environment-only; interactive, desktop-app and in-session subagents are not covered, and private HOME remains deferred. Role/posting setup grants no rights. Relay counters are unimplemented, and navigator/judge validation remains unverified against independent cases.
