# The map

## Skills

The 17 skill folders and their purposes match the README.

| Skill | Use it when |
| --- | --- |
| `fnl-coding-router` | Starting or resuming any coding work, in any repository: depth (MIN, NORMAL, DEEP), review and security gates, proof, the stop-before-a-third-fix checkpoint, and a workflow path for Spec Kit (with its depth gate), mattpocock/skills, obra/superpowers, or none. |
| `fnl-session-hygiene` | Keeping sessions healthy: context pressure, phase changes, stale titles, handovers, and remembering or recalling decisions, lessons and project state in one shared knowledge base (Orrery or an Obsidian vault); code facts stay in the repository. |
| `fnl-delegate` | Coordinating Claude Code, Codex and Antigravity from whichever one you run in: grading on five levels with one decision matrix (tier, effort, budget, who accepts), routing by agent and model through a dated capability map, an optional route judge, quota fallback, at most 5 parallel runs, time budgets, liveness from artifacts, the heavy-job lock, verify-before-accept, handover and the dispatch ledger; running a spec as a coordinator with one app session per task, standby sessions and review gates. |
| `fnl-handoff` | Writing a self-contained brief and dispatching one task, or saving a handover through session hygiene so a later session or another agent continues the work. |
| `fnl-advisor` | Getting one second opinion from another model family, or convening two contrasting families for root-cause analysis and a plan when stuck or looping; both are read-only and spend quota, with approval governed by their procedure. |
| `fnl-versioning` | Bumping a version, tagging a release, or writing the changelog and release notes: SemVer, `0.y.z` until a stable release is declared, immutable `vX.Y.Z` tags, Keep a Changelog. |
| `fnl-commit-messages` | Committing, writing a pull request description, or working with branches: atomic commits, imperative subjects, no secrets or build output, the host attribution trailer, and the branch flow (naming, base, sync, conflicts, merge, cleanup, backports). |
| `fnl-restore-point` | Saving the working tree to a private git ref before the agent edits, listing restore points and restoring one after a preview and a yes. User-invoked, git repositories only. |
| `fnl-review-gate` | A user story is done or a pull request is about to merge: an independent code review, a disposition for every finding, a regression test per runtime fix. |
| `fnl-security-review-gate` | A change touches auth, permissions, private data, untrusted input or payments: a permission-boundary review, with negative tests proving that not even a record's existence leaks. |
| `fnl-verification` | Choosing targeted tests, reading the evidence, accepting someone else's work, claiming done. |
| `fnl-plugin-packaging` | Packaging skills as a plugin for Claude Code, Codex and Antigravity from one repository: layout, manifests, icon, marketplaces, checks. |
| `fnl-setup` | Configure user scope, project scope or both through a short core and optional features; `scan` refreshes the agent inventory, `mode` manages Delegation mode and Routing, and `instructions` interviews for user contracts and project context with approval per file. |
| `fnl-status` | Opening the usage dashboard: router coverage, skill and agent use, load cost, depth against review outcome, delegation and the review gate, from the usage events (after you consent in setup) and the dispatch ledger. It also lists delegated runs still open. |
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
| Showing or changing Delegation mode or Routing, including environment overrides | `/fnl-setup mode` | |
| Starting, resuming or redirecting coding work | `fnl-coding-router` | |
| Requirements unclear | `fnl-coding-router` (workflow adapter's clarification step, with questions put through the host's native question tool; advisory, agent judgment) | `/grill-me`, or `/grill-with-docs` to keep a glossary and ADRs |
| A design question only code can answer | `fnl-coding-router` | `prototype` |
| Ready to implement one seam | `fnl-coding-router` (depth, gates) | `tdd` for the red-green loop |
| Bug, failing CI, unexplained behavior | `fnl-coding-router` (workflow adapter's debug path, router checkpoint) | `diagnosing-bugs` |
| Handing one task to another agent (Claude Code, Codex, Antigravity) with a brief, or restarting a timed-out run | `fnl-handoff`, which loads `fnl-delegate` for the route and gates | `/handoff` for a portable handoff document |
| Splitting work across agents, choosing an agent and model, parallel dispatch, quota, a watched run that stalls | `fnl-delegate` | |
| Stopping or switching and wanting the work continued later by a new session or another agent | `fnl-handoff` (Resume mode: writes a handover note and launches nothing) | |
| How the practice is working for you: router coverage, skill use, load cost, delegated runs, review outcomes | `/fnl-status` (opens the usage dashboard) | |
| Deleting the recorded usage data, or stopping the recording | `/fnl-status purge` (asks before deleting) | |
| Checking for a plugin update, skipping a release, or stopping update notices | `/fnl-update` (shows versions and asks before updating) | |
| Want a second opinion | `fnl-advisor` (proposed first and waits for your yes; spends quota) | |
| Stuck or looping on fixes | `fnl-advisor` committee procedure (proposed first and waits for your yes; spends two families' quota) | |
| A query on live data, an infrastructure change, a dashboard or a forecast | `fnl-coding-router`, which reads `references/non-code-work.md` | |
| Coordinating a spec across desktop app sessions | `fnl-delegate` | |
| Remembering a decision or lesson, or finding what was decided before | `fnl-session-hygiene` | `obsidian-cli` from kepano/obsidian-skills for an Obsidian vault |
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

| Piece | What it answers or does | Where it comes from |
| --- | --- | --- |
| `scripts/verify_claim.py` | Checks the reported head, changed-file scope and targeted tests, then records verification metadata. | `fnl-verification` (accepting delegated work) |
| `scripts/context_steward.py` | Checks supplied usage against the chosen threshold; the working agent handles the safe boundary and handover. | `fnl-session-hygiene` |
| `fnl-reviewer` agent | Is the change good? Reads the diff, then its callers, contracts and tests. | `fnl-review-gate` |
| `fnl-security-reviewer` agent | Is the change safe? Reads the diff, then every trust path that reaches it. | `fnl-security-review-gate` |
| `scripts/agent_scan.py` | Previews the local agent inventory; writes only after a yes. | `/fnl-setup scan` |
| `scripts/mode.py` | Shows effective settings and sources; previews or writes confirmed changes. | `/fnl-setup mode` |
| `scripts/ledger.py` | Records delegated runs and lists the open ones. | `fnl-delegate` |
| `scripts/merge_check.py` | Checks a pull request's posted reviews before merge, and the low-risk lane. | `fnl-review-gate` |
| `scripts/refresh.py` | Rebuilds the dashboard data; also consent and purge for usage metrics. | `fnl-status` |
| `scripts/record.py` | Prints the router's depth receipt. | `fnl-coding-router` |
| `scripts/record.py` | Prints a coordinator's keep receipt. | `fnl-delegate` |

## Rules

- A command with a leading `/` is user-invoked: tell the user to type it. Names without `/` load on their own when the task matches, or the user can type them.
- In a Spec Kit repository, Spec Kit owns the process. Companion process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to it; companion phase tools (`grilling`, `tdd`, `diagnosing-bugs`, `prototype`, `code-review`) work inside its phases.
- Companion skills come from [mattpocock/skills](https://github.com/mattpocock/skills), [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill), [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) and [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) (all MIT); commands such as `/code-review` and `codex review` are built into their hosts. When one is not installed, say so and point to that repository's install instructions; install nothing yourself. The packs are independent: neither endorses the other.
- For Route mode, name the matching skill and command in one or two sentences. When no row fits, say so and name the closest two, with the one question that would decide between them.
