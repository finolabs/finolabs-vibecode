# Changelog

All notable changes to this plugin are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/) under the phase-0 rules in `fnl-versioning`.

## [Unreleased]

### Added

- Add consent-gated per-repository ledger/task settings and bounded one-file work-record pipelines with a shared reader and parser-checked template.

- Show delivery pipelines in the Now project pane from Spec Kit artefacts, repository specs/packages and exact-project ledger outcomes, with metadata-only states and a searched-sources fallback tooltip.

### Changed

- Document host-only project settings, recent live activity counts and per-pool quota reset details; show an amber mark when completed tasks outpace the work-record status.

- Show recent usage-session counts beside slots and every cached quota pool by family, with unread placeholders and per-pool reset/freshness details.

- Draw project stages as SVG chevron chains beside identity, keep story lanes for one active item, and replace the truncated storyless label with a dashed tag icon.

### Fixed

- Reject non-ASCII package ordinals and negated completion wording, resolve index status headers, retain progress failure reasons and use “pool” for unnamed quota tooltips.

- Use the shared done theme token for pipeline package bricks in dark and light themes.
- Match pipeline stages to theme-aware task colours, back striped labels with solid chips, and use compact review glyphs and icon-first ledger/summary counts.

- Replace dense Agents and Project text with KPI tiles, dispatch budget lanes, cached quota meters and unfinished project/task graphics; retain data tables and collapsed limits. Keep up to five local project snapshots, read only story priority numbers from `spec.md`, skip `specs/archive`, and offer user-set local project labels through setup.
- Keep Reviews labels on one line, use project labels, and cap dot chains at eight plus a remaining-round count. Cover fragment-only navigation and ship the page code as a local script with no inline handlers or scripts; reduced-motion mode disables all animation.

## [0.1.10] - 2026-11-06

### Added

- Refuse cross-family ledger starts under manual Delegation mode unless the route is attributed to the user; the check blocks the record, not the dispatch.
- Tell coordinators to start headless runs through the host's background mechanism, never a detached shell job, and to check the process table and the recorded exit status before saying a run is running.
- Add metadata-only Project tab progress by feature, phase and story, exact identifier joins to runs and sessions, and a safe local reader with a one-second budget. With metrics consent and a resolved host config it defaults on; setup records the preference, `FNL_PROGRESS=off` disables it, page/session notices announce the change, and progress stays in overwritten dashboard data.
- Add Running now in the Agents tab: open dispatch ages and budgets, advisory liveness checks and family mismatch flags, plus a separately opted-in, bounded process snapshot. Setup records its on/off choice in canonical host config; `FNL_AGENT_SNAPSHOT=off` disables it, and snapshots stay in the overwritten dashboard data only.
- Add a validated `record.py task --id T012` receipt and a consent-gated `task` event holding only the task id, with advisory guidance for sessions the user started by hand.
- Let the Antigravity compaction stop install from Antigravity's own installed copy of the plugin, which keeps the repository's `.git` entry; any other plugin folder inside a git work tree is still refused.
- Ask user decisions through the host's native question tool across any clarify or brainstorming skill, stage rounds larger than the tool's per-call limit across calls with blocking questions first, and note how a parent session can read its own id from a child session it started when renaming (advisory, agent judgment).
- Show dashboard freshness: build time, newest event per host, ledger and quota ages, quiet-host warnings and a visible-tab stale-data notice. A newer ledger bypasses the rebuild throttle; Antigravity events start a detached, consent-gated rebuild with a 20-second self-cap.
- Add an opt-in Antigravity pre-invocation compaction stop with a user-chosen transcript byte limit, private size marks and a digest-bound setup preview; it keeps its own hook group and fails open. User-level hooks and interactive TUI delivery remain unverified.
- Add the advisory compaction steward, a deterministic threshold check and private local handovers re-injected on compact session starts; hook delivery remains unverified, and no hook declarations change.
- Let setup write a user-chosen Claude Code or Codex compaction threshold after separate approval of a checked, digest-bound preview, with local backups.

### Changed

- Consolidate the dashboard into title-bar `overview` and `now` tabs, add a compact review gate, and move delegation, Judge receipts and full Reviews into Overview tables.

- Flatten dashboard lanes into two flush colours, add structured tooltips, and refine light warning colours, freshness thresholds and story spacing.

- Move dashboard limits and footer details behind accessible info buttons, show compact freshness and finished-project check bricks, and bound lane/quota marks while separating wrapped story runs.

- Replace Agents tiles and Project text rows with lego budget lanes, slot/quota bricks and visible story runs, following the approved prototype; retain tables behind the existing disclosure.
- Make Project a compact list of named repositories active in the last 24 hours, register local folder names only when status is run there with consent, and move unfinished task detail into closed disclosures.
- Correct the Antigravity file-tool hook matcher and limit suggested prompts to three; an already installed Antigravity hook group keeps its old matcher until `refresh.py antigravity-hook --yes` is run again.
- Split the status dashboard into Overview, Agents, Project, Delegation and Reviews tabs, preserving the selected tab, panel scroll and open tables on data reload. Tabs show missing-source states when their data is unavailable.
- Remind agents to rename their session at the start, on a phase change and after every compaction, in the always-loaded rule and in the Titles section of `fnl-session-hygiene`.
- Correct host instruction mechanics for Claude Code and Codex, note Codex `spawn_agent` hook matching in usage metrics, clarify compaction threshold settings and writer bounds, and document privacy boundaries for judge instruction checks.

### Fixed

- Correct Project and Agents badge counts, floor unfinished task completion below 100%, show recent repository sessions in a metadata-only active projects strip, and scale dispatch lanes to the budget plus a third or at least 10 extra minutes.

- Warn about Claude per-model compaction overrides, preserve Codex threshold comments, and skip same-value threshold writes.
- Reject excluded quota interpreters and all line separators in recorded paths and labels.
- Bind each quota executable target to its confirmed digest and reject excluded resolved paths at probe time; older records need a new setup preview.
- Retry quota cache write failures after 30 minutes instead of saving a successful backoff.
- Reject line breaks in quota configuration paths and labels during plan validation.
- Deduplicate Claude configuration folders by filesystem identity and clearly refuse missing folders.
- Apply the agent version output limit to stdout independently of stderr.

## [0.1.9] - 2026-11-06

### Changed

- Ask questions and show option labels in the user's language, preserving technical names and reporting English script output in that language (advisory, agent judgment); the beginner-register reference says it applies in the user's language, and CI checks its two copies match.
- `fnl-session-hygiene` records the documented compaction settings of Claude Code (`autoCompactWindow`, `/autocompact`) and Codex, states that Antigravity documents none beyond `/compact`, and separates the advisory 60% from the host's later default trigger; `fnl-setup` repeats the Antigravity limit.

### Fixed

- Parse capped hook payloads in linear time while preserving complete metadata fields and discarding truncated tool input.
- Treat a quota cache that is unsafe, capped, unparsable or fails validation as no reading: status shows no reading, and the next scheduled reading, limited by the 30-minute backoff, replaces the file atomically without writing through a symlink. Legacy records missing a resolved target require a fresh setup preview, and the confirmed executable must still resolve to its recorded target before running.
- Refuse line breaks in quota setup paths and labels, and recognize the default Claude folder by filesystem identity, including case variants on case-insensitive volumes.
- Read agent versions from stdout only, count each include cycle once, and preserve section ranges across Unicode line separators.
- Clarify neutral setup approvals, question-tool fallbacks and default preferences. Keep language guidance outside lists, mark compaction advice explicitly, and align privacy and reference-check documentation with the existing rules.
- Restore Claude quota readings by supplying the account database username to probe children and leaving `CLAUDE_CONFIG_DIR` unset for the default install while retaining it for listed extra folders.

## [0.1.8] - 2026-11-05

### Added

- Add an optional quota probe for Antigravity, Claude Code (up to four labelled installs) and Codex, with canonical consent, confirmed executable paths, bounded detached reads and private usage-only cache. Setup previews before digest-confirmed apply; Scan and Check show measured pools, and delegation uses fresh readings as advisory evidence.
- One account-owned data root, with checked relocation through `fnl-setup` and digest-confirmed copying that preserves the old folder. Consent and opt-ins ignore environment redirects; only usage events and the dashboard retain the documented state override and legacy compatibility paths.
- Judge receipts and a conditional Judge pane in `fnl-status`: use, usable answers, followed decisions and outcome association by routing source, with metadata only and no cost, latency or accuracy measurement.
- `fnl-restore-point` (user-invoked, git repositories only) saves the working tree to a private ref `refs/finolabs/restore/<timestamp>` without touching the index, the branch or the files, lists the saved points and restores one only after a preview and a clear yes, taking a pre-restore point first; it never pushes. `fnl-ask` Start offers a guided "try it now" first result in a new empty folder outside any repository.
- `fnl-setup-instructions` states a researched standard (add only what the agent cannot infer, verifiable lines with reasons, text is not enforcement, detail on demand), per-host limits and mechanics, and a pre-write measure step; `fnl-setup` Check gains a 20-item instruction checklist. `checkup.py` measures length, the Codex 32 KiB chain, the Antigravity 24,000-byte limit, includes, duplicates, secret-looking strings, machine paths, the local file, emphasis, layout and age offline and read-only, reporting file, line and pattern name only. The judgment items go to the route judge first (only with the separate `Instruction check` consent, through one payload builder that drops secret and path lines) and to the agent as fallback.
- A task-lifecycle state diagram (inspect, path, depth, red, change, proof, review, merge, release, with the checkpoint after two failed fixes) in the README, with the HTML sources of both diagrams in `docs/diagrams/`.

### Changed

- Narrow the `fnl-handoff` and `fnl-delegate` descriptions so a request to hand one task to an agent with a brief goes to `fnl-handoff`, and routing among agents, parallel dispatch, quota and watched runs go to `fnl-delegate`.
- Stop reading the `ORCHESTRATION_LEDGER` override, the legacy XDG ledger, the legacy `host.md` for Check, Routing mode and Delegation mode, and the legacy consent location. Use the data root for these files; data-location changes require the full 64-hex preview digest.
- A Claude Code hook of this plugin may now deny the first file write in a repository without a decision in the last 8 hours when Delegation mode is `auto` and the opt-in auto gate is on; subsequent writes in the window allow, and `FNL_AUTO_GATE=off` disables it.
- Clarify host-owned compaction thresholds and advisory writeback; setup only suggests settings, Claude Code and Codex gain a non-blocking `PreCompact` reminder, and Check reports declarations with delivery unverified.
- The remaining text questions use the host's native question tool when the session has one: the `fnl-setup` beginner-path offer, mode choices, preferences confirmation and usage-metrics consent, the `fnl-setup` Check smoke task, the `fnl-status` purge and consent-withdrawal confirmations and the `fnl-update` confirmation. Text is the fallback; native-path verification stays manual per host. Approvals among them offer neutral Yes and No choices and never count a default or timeout. Advisory (agent judgment).
- Every background run or agent a coordinator starts (a headless Codex, Antigravity or Claude run, a reviewer, a subagent) is named by who runs it and what it does, `<runner>: <project> <scope> <activity>`, in the host's name field, the ledger task, the log file names and the dispatch line. The rule lives in `fnl-session-hygiene` "Titles"; `fnl-delegate`, `fnl-review-gate` and `fnl-handoff` point to it. Advisory (agent judgment).
- Add an advisory release step to update the marketplace catalog pin and metadata after a release.
- Harden agent scans with validated versions, bounded output, absolute PATH entries, digest-bound writes, fence-aware sections and stable check dates.
- Require neutral explicit Yes/No approval in scan, mode, setup preferences and delegation offers; remove recommended approval answers from plain-language guidance.
- `fnl-coding-router` says a spec or plan asks the decisions the user can settle through the host's native question tool instead of listing them as open; only decisions that cannot be made yet stay listed, with an owner. Advisory (agent judgment).
- The skills named here now ask through the host's native question tool when the session has one (`AskUserQuestion` on Claude Code, `request_user_input` on Codex, `ask_question` on Antigravity): the `fnl-setup` interviews, beginner-path and mode choices, preferences and scope questions, the Check smoke task, the `fnl-update` confirmation and the `fnl-status` purge and consent-withdrawal confirmations, the plain-language opening question, the yes of `fnl-scan-agents` (model lists stay free text) and the confirmation of `fnl-set-mode`, the router's bounded clarification and the `suggest` hand-off offer. Text stays the fallback when there is no tool, it fails, nobody can answer (delegated or headless runs) or the answer is free text. Agent judgment enforces it, so it is advisory; verified only that each host's CLI contains the tool, not how Codex and Antigravity expose it.
- Shortened the plugin description to 147 characters, identical in the three manifests, to meet the catalog's 120-160 character standard (the 0.1.7 manifests carry a 199-character one). A unit test now pins both the length and the match across hosts.

### Fixed

- Tighten consent withdrawal, instruction checks, judge receipt recognition, restore validation and ledger error reporting.
- Allow retired skill names in dated changelog releases and the Unreleased migration mapping, preserving released history while rejecting other uses.
- Check tracked documents with Git so untracked and git-ignored local context files cannot fail reference validation.
- Remove the unused argument placeholder from the advisor's committee instructions.

## [0.1.7] - 2026-11-05

### Added

- `fnl-scan-agents` refreshes the local agent inventory and user-confirmed allowed models; `fnl-delegate` routes only among recorded present families and warns once per session when the section is older than 30 days. The scan runs only three fixed `--version` calls, reads `host.md`, uses no network and stores nothing outside `host.md`; a clear yes is required for its atomic section-only write.
- `fnl-set-mode` shows effective Delegation mode and Routing with their sources and environment overrides, previews changes and writes only those settings after a clear yes. Setup uses the scan, Check reports missing/stale inventory and retired context pointers, and the README includes light/dark skill architecture diagrams.
- New behavior evals for the router in a Spec Kit repository, a repository with mattpocock/skills, and one with no workflow pack.
- `fnl-delegate` "Keep or hand off": a coordinator holding two or more independent tasks with clear acceptance tests dispatches them or records why it kept them, before starting the first; under `suggest` (the default), it asks first. The coding router points to it. `record.py keep` prints one line with a count, a fixed reason and who settled it, and with usage metrics on the hook stores it as a new `kept` event, under the same consent, retention and purge as other events; existing consents cover it. The `fnl-status` delegation pane shows the tasks kept beside the implementation runs handed off.
- Add user-chosen Delegation mode (manual, suggest or auto) and Routing (on/off), with a read-only settings reader, setup choices and honest Check reporting. Claude Code and Codex session-start reminders honor Routing; Antigravity’s static rule cannot, and safety gates remain unchanged.
- Add a default-on, cached release check and synchronous startup notice, verified on Claude Code and unverified on Codex and Antigravity (Codex ships a hook; Antigravity has none), with `FNL_UPDATE_CHECK=off` and the user-invoked `fnl-update` skill for explicit update approval, skip and never-ask choices; the detached GET sends nothing about the user and works independently of metrics consent.
- `fnl-setup` has a Check mode: a read-only local check reports setup evidence and runtime limits per host, with a small optional smoke task. `fnl-ask` routes setup checks to it.
- The `fnl-status` dashboard updates itself while its tab is open: the page reloads `data.js` every 5 seconds while visible and redraws when the numbers changed, and the hooks rebuild the file at most once per 10 seconds during a session and at each stop and session start (Claude Code and Codex; on Antigravity the page follows rebuilds made elsewhere). Checked in Chrome; Safari and Firefox are unverified. It stays local: no server and no listener.
- Plain-language guidance in `fnl-ask` and `fnl-setup`: lead with the result, use everyday words and ask only the user's decisions. Both skills carry an identical reference so each works alone; CI checks the copies match.
- `fnl-handoff` has a Resume mode: it writes a handover for a later session or another agent without dispatching anything. The handover is a note in the knowledge base the user's instructions name (tagged `handoff`, with a pointer line at the top of the project's state entry), or a brief file without one, and the agent's native memory holds at most a pointer. The agent that continues reads the latest handover, trusts the repository where they disagree, does the first unfinished step, asks before a merge, a deploy or a deletion, and updates the same note as it goes. The brief template gains two optional headings, "Waiting on" and "Linked runs or sessions".
- `fnl-setup` now suggests the `diagram-design` skill set (MIT, cathrynlavery/diagram-design) for users who draw architecture or flow diagrams, with install commands. Our skills work without it.

### Fixed

- `fnl-delegate`: under `suggest` the coordinator no longer asks the user to approve a session of its own kind (for example a Codex session in its own worktree started from Codex, or one a repository's rules require); that is the coordinator doing the work, and an offer names an agent of another family.
- The three usage-metrics hook commands on Claude Code now end with `; exit 0`, as the Codex and update hooks already did, so a missing or broken script can never return a blocking exit code. A test pins the guard on every shipped hook command.
- The update-check tests no longer depend on the manifest version, so a version bump cannot break them.

### Changed

- Consolidate 20 skill folders into 17: `fnl-committee` → `fnl-advisor` (`references/committee.md`), `fnl-coordinator-sessions` → `fnl-delegate` (`references/coordinator-sessions.md`), and `fnl-knowledge` → `fnl-session-hygiene` (`references/knowledge.md`). Use the surviving skill names; committee and knowledge procedures load only when needed, and session hygiene owns saved handovers.
- Clarify six own-kind delegation follow-ups: use sessions or headless runs, limit offer-free starts under manual to project requirements or context pressure with a one-line reason, define own kind by the recorded coordinator family, else the host family, retain delegate authority limits, respect project session rules, and reject Codex hand-off offers in the keep-own-kind eval.
- The README explains the bricks idea (small skills plus a guideline, inspired by the LEGO Group's turnaround under Jørgen Vig Knudstorp; independent of and not endorsed by the LEGO Group), says what you hand over and what stays with you, and gains a Check step in the three-minute start. The repository social preview shows a robot built from bricks.
- `fnl-coding-router` now works in any repository. Depth, the review and security gates, proof, "Proportion" and the stop-before-a-third-fix checkpoint are the core; the workflow is a short first step that reads one adapter under `references/workflows/`: `speckit.md` (every Spec Kit rule and the Spec Kit depth gate, unchanged in meaning), `mattpocock.md`, `superpowers.md`, or `none.md`, a self-contained procedure (bounded clarification, a genuine red, the smallest change, proof, review) for repositories with no workflow pack. The description is workflow-neutral, and the fallback table that pointed to skills a user might not have is gone.
- `fnl-session-hygiene` marks the 60% compaction rule advisory unless enforced by the host or a hook, with enforcement unverified until verified. The README and `fnl-ask` contents also list session wrap-up as a trigger for `fnl-handoff`.
- `fnl-setup-instructions` offers user, project or both scopes, with repository context sourced from `AGENTS.md`, a Claude include and private local context kept out of git. Its user contract asks for delegation and compaction preferences and distinguishes advisory rules from verified enforcement.
- `fnl-ask` routes Start, Contents, Explain and Route questions to references, reads the target before answering and still invokes nothing; all modes share the beginner definition and register, with one question first for a bare invocation. The onboarding order is `/fnl-ask`, Quick setup, a first task, user instructions (immediately after setup on Codex), and the dashboard later.
- The README opens in plain words, with a three-minute start and a glossary, and teaches the same onboarding order to users and agents.
- `fnl-setup` offers a beginner path before the mode choice and uses it only for users who say they are new to coding or accept the offer. Its closing handover lists user instructions (immediately on Codex, after the first result elsewhere), matching companion suggestions and the skipped sections to revisit later.

### What to do

- Update the plugin through your host's plugin update (the new update check, on by default, will tell you from now on; type `/fnl-update`, `$fnl-update` on Codex), or on Antigravity reinstall with `agy plugin install https://github.com/finolabs/finolabs-vibecode`. Claude Code needs a restart; Codex hooks need your trust again.
- Delegation mode defaults to `suggest` (the agent names who could take a task and waits for your yes). Use `/fnl-set-mode` (`$fnl-set-mode` on Codex) to see or change it and Routing, and `/fnl-scan-agents` to refresh present families and confirmed models.
- The update check makes one GitHub request every 24 hours. Set `FNL_UPDATE_CHECK=off` to stop it; see `PRIVACY.md`.
- Run `/fnl-setup` and choose Check to see what runs on its own on your host and what is unverified.

## [0.1.6] - 2026-11-04

### Added

- Usage metrics on Claude Code and Codex (and Antigravity, through a hook that setup adds to the user's own hooks.json after a clear yes), off until the user consents in `fnl-setup`. The plugin's hooks record metadata only (a time, a session id, a short repository code, an `fnl-` skill or agent name, the router's depth, a review verdict) in a local folder, with a retention the user picks (30, 90 or 365 days). Nothing is sent anywhere; `FNL_METRICS=off` or `consent --revoke` stops it, and `fnl-status purge` deletes it.
- `fnl-status` now opens a local dashboard page: router coverage, skill and agent use, load cost, depth against review outcome, delegation and the review gate, in the FINOLABS palette with a dark and a light theme. A refresh script builds its data from the usage events and the dispatch ledger.
- The coding router prints a depth receipt (`scripts/record.py`) that the hook records with the session, and the host template marks delegated runs with `FNL_DISPATCH_ID`.
- `refresh.py consent --revoke` withdraws consent for the usage metrics; recorded events stay until `fnl-status purge`.
- The test suite runs the dashboard page's script in node against a fake DOM (skipped when node is not installed).
- `ledger.py summary --json` prints the summary rows as JSON, with quota and error counts.
- `fnl-setup` recommends companion skills from `references/companions.md`: `agybird` when Antigravity is a delegate of Claude Code or Codex, and `vietnamizer` when the user writes Vietnamese documents for people. It gives their install commands and installs nothing.

### Changed

- Router coverage counts a commit as a session's first change when it comes before any edit, because agents often write files through the shell, which no edit hook sees.
- `fnl-delegate` grades work on five levels (`easy`, `medium`, `hard`, `very hard`, and the new `ultra hard`, which `ledger.py` accepts as `ultra-hard`; earlier ledger lines still read), and routing defaults to `medium` effort on every agent and tier, hard work included, with `high` for very hard, `xhigh` for ultra hard and one level up after a run fell short; the tier table now names models, not effort levels, and the host template has an optional "Effort preference" section to override the default.
- The project-scoped folder for briefs, logs and handover notes is now `.finolabs/` at the main checkout's root, matching `~/.finolabs/vibecode/` for the machine. A repository that still has `.orchestration/` and no `.finolabs/` keeps using it; nothing is moved.
- The plugin's own data and configuration now default to `~/.finolabs/vibecode/`: `host.md`, `ledger.jsonl` and `state/` (consent, usage events, the dashboard). Folders it creates there are mode `0700`. A machine that already keeps them in `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` or `${XDG_CONFIG_HOME:-~/.config}/finolabs-vibecode` and has nothing in the new place keeps using the old files; nothing is moved. `FNL_STATE_DIR`, `ORCHESTRATION_LEDGER` and `ORCHESTRATION_HOST_CONFIG` still win.
- `fnl-status` no longer takes `--since` or `--project` and no longer prints a routing table in the terminal; the dashboard shows the same figures, and the skill still lists open dispatches and checks the capability map's review date.
- `PRIVACY.md` no longer says the plugin has no analytics; it describes the opt-in local record and what it holds.
- Shortened the plugin description to 142 characters and made it identical in the Claude Code, Codex and Antigravity manifests, matching the shared catalog.

### What to do

- Update the plugin through your host's plugin update, or on Antigravity reinstall with `agy plugin install https://github.com/finolabs/finolabs-vibecode`.
- Usage metrics are off until you consent. To turn them on, run setup (`/fnl-setup`, or `$fnl-setup` on Codex) and answer section F; on Codex also trust the plugin's hooks once with `/hooks`. Nothing else is required, and your existing ledger, host config and `.orchestration/` folders keep working where they are.

## [0.1.5] - 2026-11-03

### Fixed

- Antigravity skipped `fnl-security-reviewer` and `fnl-verifier` in 0.1.4, because their `model: opus` and `model: sonnet` are not Antigravity model tiers. All three agents are back on `model: inherit`; `fnl-review-gate` and `fnl-delegate` now tell the caller which tier to start them on where the host lets it pick, and a test keeps every agent on `inherit`.

### What to do

- On Antigravity, reinstall with `agy plugin install https://github.com/finolabs/finolabs-vibecode`; `agy plugin list --json` should show three agents.

## [0.1.4] - 2026-11-03

### Added

- `fnl-coding-router` `references/non-code-work.md`, read on demand for queries on live data, infrastructure, dashboards and forecasts; the router stays code by default, and DEEP now also covers compounding calculations, predictions and ambiguous input.
- `fnl-coding-router` "Proportion": build what the acceptance criteria require at the product's current stage, trace each hunk to a criterion and run tests at checkpoints, not after every edit or across the whole suite. Handoff briefs, verification and the review gate carry the limit.

### Changed

- A judge named in the host config (for example `typesafe-ai` for TypeSafe's Jev) now makes the grade, route, depth and next-activity calls first; without one, or when it is inconclusive, the agent decides itself. The detail moved into references read only when a judge is configured.
- `fnl-delegate`: plain content writing goes to Codex first; a "Never delegated" rule lists what a delegate never does or decides and what the coordinator itself does only with the user's authority; a same-family review fallback asks the user first on a security-triggered pull request.
- `fnl-review-gate`: severities are defined (CRITICAL, HIGH and MEDIUM block; LOW never causes another round), rework is capped at two rounds, and findings outside the change stay in the report.
- `fnl-security-review-gate`: adds a data-leaving trigger, a short report when no trigger matches, negative tests only through entry points that reach the touched resources, an exploit scenario for MEDIUM or higher, a NEEDS-VALIDATION outcome that blocks until the owner validates a concern the repository cannot settle, and a rule that `security-audit` in focused mode supplies method, not findings, so a file counts as engine-only only when the engine says it read it.
- `fnl-open-source-review`: reruns before each MINOR release, strongly recommends a secret scanner, caps the verdict at "not ready" while a secrets, leaks or license check is BLOCKED, and splits repository settings into blocking and noted.
- `fnl-verification`: names the gap and proposes a test for an untested runtime change, proposes a full suite for widely shared code, points to the non-code reference, and lets only the owner waive a check.
- `fnl-commit-messages`: a commit is one whole seam with a body of about six lines; agents commit when a seam passes its targeted tests, on their own branch, without pushing; pull request text stays short.
- `fnl-handoff`: findings go back to the same run while it is light and to a new run after about 60% context or two failed rework rounds; a prose brief names language and tone, and the editing pass runs only for social content or documents.
- `fnl-advisor` one-opinion and committee procedures: both are proposed and wait for the user's yes (an advisor may run without it while the user is away; a committee never does); tier follows difficulty; a same-family advisor stands in only when both other families are out; a committee adds a third member only after two rounds of disagreement, settles it with one reversible experiment, and waits for the user before its plan is dispatched.
- `fnl-delegate`: coordinate from three user stories or ten tasks; the coordinator writes no application code; standby covers the next story plus one fix session; independent stories still run one after another.
- `fnl-status`: flags a group only from five runs (first-pass acceptance below 60%, or timeouts plus fallbacks at 25%); a coordinator closes an orphaned ledger record only when its log or the repository shows how the run ended.
- `fnl-session-hygiene` covers two layers, the knowledge base and the repository, and leaves an agent's native memory to the agent (the per-host `references/hosts.md` is removed); a decision is written as soon as the user settles it, a lesson at the end of a task or at once after an incident, and a project-state entry carries a review-by date. `fnl-setup` no longer writes a native-memory pointer.
- `fnl-setup` lets the user choose a detailed or a quick mode (the quick mode asks every decision once with its recommended default, and a skill that later needs an unsettled item asks the user once), reruns only when an agent is added or changed or the host template gains a field, grants Antigravity only exact test commands recorded in the host config and kept to one repository, and offers the low-risk lane line only to a repository with one owner. `fnl-review-gate` asks the user once to adopt the gate where the repository has not.
- `fnl-setup-instructions` treats about 150 lines in the shared body as a soft limit and offers to move detail into a skill or reference, adds a contract line that lets an agent propose one entry (at most one per session, written only on the user's yes) after the user corrects the same behavior twice, and recommends the Claude Code file as the source, with an include where a host has one and a managed copy that warns about manual sync where it has none.
- `fnl-plugin-packaging` runs the trigger suite only for skills whose `description` changed (the whole suite before a MINOR release), applies the icon section only when a directory asks for an icon, and says that a catalog tracking the default branch serves `-dev` builds that change with every merge.
- `fnl-ask` adds a row for queries on live data, infrastructure changes, dashboards and forecasts, and notes on the advisor and committee rows that they are proposed first, wait for the user's yes and spend quota.
- `fnl-reviewer`, `fnl-security-reviewer` and `fnl-verifier`: the two reviewers are always the entry and run the host's native review (`/code-review`, `codex review`) as their engine, with the effort set by depth. The security reviewer runs `security-audit` in focused mode on the diff when a trigger matches or the diff is large, and the native security review otherwise; where an instrument is missing it reviews by hand and tells the caller that `/fnl-setup` guides installing it. Reviewers use the CRITICAL to LOW scale, trace each hunk to an acceptance criterion, name engine-only coverage, and need a concrete scenario for a MEDIUM or higher security finding; `fnl-security-reviewer` runs on `opus` and `fnl-verifier` on `sonnet`. `fnl-delegate` uses the verifier for hard and very hard runs, and the coordinator checks easy and medium runs itself. `fnl-setup` gains a review tools step that strongly recommends installing missing instruments.
- `fnl-session-hygiene`: a finished user story with its review gate closed is a boundary for a fresh session, knowledge is written back only when it would change what an agent does next time, and session titles use English for the activity unless the user asks for their own language.
- `fnl-versioning`: an agent never cuts a release on its own and proposes one when a spec is merged, a spec usually bumps the last digit, a release is two pull requests, and changelog entries stay to one or two sentences.

### What to do

- Run `/fnl-setup` again: its new review tools step finds the review instruments the reviewer agents use (`/code-review`, `/security-review`, `codex review`, Cloudflare's `security-audit`) and recommends installing any that are missing.
- If your host config names a route judge, nothing changes in it; the coordinator and the router now ask that judge first.

## [0.1.3] - 2026-11-02

### Added

- `fnl-review-gate` ships `scripts/merge_check.py <number> --repo <owner/name>`, which applies the pull request merge check with `gh`: the latest unedited marker of each kind for the head from an author with write access, the owner's approving review for an outside author's pull request, passing checks and a mergeable state. It exits 0, 1 or 2 (merge, blocked, cannot tell) and fails closed: a failed permission lookup, an uncomputed merge state, a full page of comments, no reported checks or a compare result without every file or a merge base never pass. It compares manifests as parsed JSON (only the top-level `"version"` may differ, duplicate keys refused), reads the lane's files from the compare API, bound to the head SHA and diffed from the merge base, treats only GitHub's 404 as no access and gives each `gh` call a timeout. Unit tests cover each blocking rule, including a comment-only review after an approval and a tie between verdicts, plus the lane and permission paths through the CLI.
- `fnl-review-gate` "Pull requests" rule 7, the low-risk lane, for repositories whose agent context file adopts it: a pull request whose files are all modified in place and are only the root documents written for people (`README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `PRIVACY.md`, `TERMS.md`) or the plugin manifests' top-level version takes one pass by `fnl-reviewer`, which reads text addressed to agents, such as a README's install steps, as instructions agents will follow and posts both markers, the security one with ` lane=yes`. `merge_check.py --lane` decides, not an agent, and the merge check blocks a lane verdict on a pull request that does not qualify. Agent context files, skills, agents, rules and every other path stay out. `fnl-setup`'s optional combined-review line now adopts this lane, and `fnl-security-reviewer` runs on every pull request outside it. A behavior eval guards it: against a no-plugin baseline it separates (1.0 and 1.0 with the plugin, 0.33 and 0.33 without).

### Changed

- The merge check (`fnl-review-gate` rule 4), by hand or by script, also requires every check on the head to have passed and GitHub to report the pull request mergeable; `UNKNOWN` means wait. `fnl-verifier` reads review markers the same way, counting a ` lane=yes` security verdict only when the pull request qualifies.
- A standing relay approval counts only when recorded in the agent context file as committed on the default branch; untracked files, agent memory, the host config and uncommitted edits no longer count, because a coordinator can write them. The relayed comment's second line is defined once.
- `fnl-delegate` reads an Antigravity run's error before retrying: with `agybird` 0.3.2 or later, `evidence.agy_error` with `RESOURCE_EXHAUSTED` or a 429 means that model's pool is out, so the run is recorded as `quota` and follows the quota fallback with its tier rules instead of retrying the same model; only a 429 that says it is a short rate limit is retried, once. The direct-`agy` and `agybird` outcome tables follow the same rule. The host template asks how to look up the `agybird` runner at each dispatch, not for a pinned or highest cached folder.
- Antigravity review inputs go to `.orchestration/briefs/` inside the worktree and are removed once the report is read, and the long-lived worktree switches branch once the previous run's work is committed or handed over.

### What to do

- If a standing relay approval lives in your host config or another untracked file, move it, with its scope and date, into the agent context file (`CLAUDE.md` or `AGENTS.md`) through a reviewed pull request; until then the coordinator hands relayed reviews to you.
- If your agent context file carries the 0.1.2 optional line letting documentation pull requests take one combined review, replace it with the line `/fnl-setup` now offers. The lane still covers the README and other root documents, but no longer a `docs/` folder; pull requests there go to both reviewers.

These two steps would make this a minor release under `fnl-versioning`; the owner kept it a patch because the plugin is in early use with few installs outside the maintainer's, and both steps are stated here. The owner also waived the release checklist's adversarial review by another model family for this release: Gemini 4 Argon and Codex were out of quota.

## [0.1.2] - 2026-11-02

### Added

- `fnl-plugin-packaging` covers shared catalogs across hosts, Codex grouping and catalog renames, Antigravity installs from a repository URL, pinning versus tracking, and protection for listed repositories (`references/catalogs.md`).
- `fnl-session-hygiene` sets a session title format, `<project> <scope>: <activity>`, with examples, when to rename, whose sessions to rename, and how each host names sessions (`references/titles.md`). A delegated run's logs are named `<ledger id>-<slug>` and its brief `<slug>.md`; Codex sessions are archived or deleted by id, never by title.
- CI checks cross-references (`scripts/check-references.py`): skill and agent names, section references (backticked or linked), relative links, ledger subcommands with their own flags and allowed values, and host config flags against the agent contracts.
- `fnl-delegate`'s capability map carries a review-by date, and `/fnl-status` warns when it has passed.
- Behavior evals (tag `behavior`) with deterministic graders on each answer's final verdict line: the pull request merge check with a stale marker, a marker from an author without write access, and a valid pair; coding-router depth for a typo and a tenancy change; the merge check when a later marker overrides an earlier one for the same head, when a later comment quotes a marker, when the author lacks write access, when the owner approved only an earlier commit, and when a verdict comment was edited; delegate routing when one agent's quota is out, when every frontier model is, when only frontier models are left for medium work, and for a review; the Spec Kit depth gate; verification of a false delegated report. Against a no-plugin baseline, the review routing and outside-author cases show the skills' effect, and the depth gate case separates only on its reason grader; the others guard against regressions. A trigger eval covers session titles and the branch flow, and every eval scaffold refuses to run outside an empty directory.
- `fnl-commit-messages` "Branches" sets one branch flow: trunk-based with short-lived branches, naming, the base to cut from, syncing by rebase or merge without rewriting a pushed branch, conflicts, default branch rules, merge commits pinned to the reviewed head, cleanup of branch and worktree, hotfixes and backports to `release/X.Y`. Its description gains branch triggers, and `fnl-coding-router`, `fnl-delegate`, `fnl-handoff`, `fnl-review-gate`, `fnl-versioning`, `fnl-open-source-review` and `fnl-ask` point to it where a branch is created, synced or merged.
- The contributing guide lists the local checks, how to add a host, and the release checklist, which includes an adversarial review by another model family.

### Changed

- `fnl-coding-router`'s Spec Kit depth gate lets a user story go from an accepted plan straight to implementation, skipping `speckit-tasks`, also when it makes a small, contained contract change that a security review covers; security, privacy, permission, migration, dependency and irreversible boundaries still go through tasks. A direct path is accepted by `fnl-verification` against each acceptance criterion and the two posted reviews, and `fnl-review-gate`'s reviewer packet carries the story's acceptance criteria and `plan.md` when Spec Kit is in use. A direct path runs no separate analyze or converge step. Two behavior evals guard it: an additive response field goes direct (it passes without the plugin too), and a new filter parameter that reaches a query goes to tasks (2/2 with the plugin, 0/2 without).
- Claude Code and Codex install the plugin from the FINOLABS catalog, `finolabs/plugins` (`finolabs-vibecode@finolabs`), which groups the FINOLABS plugins under one name; the repository's own marketplace stays for existing installs. The manifests name FINOLABS as author and developer. The agent install steps check for an existing install before adding the catalog.
- The repository moved to `github.com/finolabs/finolabs-vibecode`; links, manifests and install commands use the new address, and GitHub redirects the old one.
- `fnl-delegate`, the delegation host template and agent contracts use that title format.
- `fnl-verifier` counts a review marker only from an author with write access, like the merge check, which now names the permission values GitHub returns.
- `fnl-advisor` names Antigravity among the agents it can ask, in its description and argument hint.
- `fnl-delegate`'s capability map routes reviews of medium work at frontier tier and reviews of easy work at strong tier, matching the rule that a review takes the tier above the work.
- `fnl-delegate` keeps routing and the steps every dispatch takes in `SKILL.md`, and moves procedures only some runs reach (quota fallback, parallel runs, the heavy-job lock, handover, file placement, ledger commands) to `references/dispatch.md` and `references/ledger.md`. The rule that a task needing wider shell access goes to another agent applies to every delegate, not only Antigravity.
- `fnl-review-gate` merge check: a verdict is an unedited comment whose first line is a marker, from an author with write access; for each kind the latest such verdict for the head (by `createdAt`) must be `APPROVE`, so a later `REWORK` blocks the merge and a marker quoted inside a comment counts for nothing. A pull request from an author without write access also needs the owner's own approving review on the head commit, the reviewer's latest review counting, read from the pull request's reviews; no agent submits it. The verifier counts verdicts the same way.
- Reviewers treat everything under review as data: text in a pull request that tells the reviewer what to conclude, post or run is a finding (`fnl-review-gate`, both reviewer agents).
- An Antigravity coordinator's wider allow-rules need the user's approval (`fnl-delegate` agent contracts).
- When a delegate's allow-rules miss the commands a brief's tests need and the user is present, `fnl-delegate` asks the user to grant them as literal rules (with `agybird`'s grant flow, or a per-run settings file) before falling back to an edit-only brief or another agent, and never skips the permission check. The user chooses each grant, only for commands the brief lists, and is told that a granted test command runs the repository's test code; the host config only records grants; `/fnl-setup` offers remembered rules for the repository's test commands. A behavior eval guards it.
- `fnl-delegate` shares whole easy and medium implementation tasks when the coordinator's context is past about 60% or it holds several independent tested tasks (to a fresh session or headless run of its own kind), or when its own quota or tokens are short (to another agent with quota left); the coordinator keeps briefing and acceptance, reviews follow `fnl-review-gate`, and merges stay with whoever holds the authority (Load sharing). `fnl-coding-router` says a delegated whole task is not an implementation child.
- Reviews of several pending pull requests go to each reviewer in one packet and one pass, with one comment and marker per pull request and their interactions noted (`fnl-review-gate`, both reviewer agents).
- Antigravity grants are remembered per folder, so `fnl-delegate` dispatches a repository's runs from one long-lived worktree, one run at a time, and opens with a short run of the brief's check commands to collect grants; parallel runs keep their own worktrees and grants. A read-only review gets the diff and check output inside its worktree and reads the report even when the run ends `partial`.
- A coordinator may post another family's review under a standing relay approval that the owner recorded, with its scope and date, in a file the owner controls; the relayed comment names the reviewer and cites the record (`fnl-review-gate`), so pull requests one model family wrote get a code review from another.
- The owner approval on an outside author's pull request reads each reviewer's latest approving, change-requesting or dismissed review; comment-only reviews do not count.
- `fnl-commit-messages` names the agent whose accepted work a commit holds.

### Fixed

- The dispatch ledger skips lines that are valid JSON but not records, instead of crashing.

## [0.1.1] - 2026-11-02

### Added

- `fnl-setup` offers an optional line that lets a pull request changing only documentation take one combined code and security review.
- CI scans the tree and history for secrets (gitleaks, checksum-verified), and the tree for personal paths and addresses, and runs tests for the dispatch ledger script.
- `fnl-open-source-review` checks repository settings: default branch and release tag protection, secret scanning and push protection, dependency alerts, private vulnerability reporting, merge and Actions settings, listing.

### Changed

- `fnl-review-gate` and the reviewer agents: a reviewer that cannot post returns the finished comment with its marker; the coordinator posts it only with the same authority, otherwise the owner does, and the merge waits. The merge check counts a marker only from an author with write access.
- The README states that installs track `main` and that releases are the `vX.Y.Z` tags.

## [0.1.0] - 2026-11-02

First public release.

### Added

- README section for AI agents given the repository link: confirm with the user, install per host from a shell, verify, then hand setup to the user in a new session.
- Session-start reminder for Claude Code (SessionStart hook) and Antigravity (always-on rule) directing agents to `fnl-coding-router` and `fnl-delegate`.
- Claude Code, Codex and Antigravity manifests sharing one `skills/` folder, version `0.1.0-dev`.
- `fnl-coding-router`: Spec Kit first routing, fallback router, MIN/NORMAL/DEEP depth, the Spec Kit depth gate, the repeated-fix checkpoint, and activity selection with a semantic evaluator as a reference.
- `fnl-session-hygiene`: compaction at about 60% context, handover content, titles, one writer per scope.
- `fnl-delegate`, `fnl-handoff`, `fnl-advisor`: grading and routing across Codex, Antigravity and Claude Code, quota fallback, at most 5 parallel dispatches, hard time caps and liveness from artifacts, heavy-job lock, verify-before-accept, handover after interrupted runs, file placement, and the dispatch ledger script; a host config template.
- Any agent can coordinate: `fnl-delegate` routes by agent and model through a dated capability map (`references/models.md`), states each agent's dispatch contract from every coordinator, and takes an optional route judge for open calls with a conservative fallback; the ledger records the coordinator and how each route was chosen.
- `fnl-session-hygiene`: native agent memory for working preferences, one shared knowledge base (Orrery where available, or an Obsidian vault) for decisions, lessons and project state, and a native-memory map per host.
- Pull request gate: every pull request needs a code review and a security review, each posted as a comment with a machine-readable marker bound to the head commit, before it merges.
- `fnl-security-reviewer` agent, and a two-ring review scope in the review gates: every changed file in full context, then the impact set (consumers, dependencies, contracts, tests) or, for security, every trust path to the change; reviewers report what they traced.
- Review instruments: the review gates and agents use each host's native review (`/code-review`, `/security-review`, `codex review`) and recommend Cloudflare's `security-audit` skill for audits.
- Single-skill installs through skills.sh: every skill folder is self-contained, the delegation family names `fnl-delegate` as its one dependency, and CI checks that shared copies match and no skill reaches outside its folder.
- `/fnl-status` (user-invoked): open delegated runs and acceptance per agent and model from the ledger.
- `fnl-delegate`: coordinator plus one app session per task, standby sessions, review gate per user story.
- `fnl-versioning`: SemVer, phase 0, cadence, single source of truth, immutable tags, Keep a Changelog, release authority.
- `fnl-commit-messages`: atomic commits, imperative subjects, exclusions, attribution trailer, PR descriptions.
- `fnl-review-gate`: independent review, reviewer packet, finding dispositions, regression tests, re-review, approval bound to final bytes.
- `fnl-security-review-gate`: triggers, permission-boundary review with negative tests and no existence leak.
- `fnl-verification`: targeted tests, full suites only on request, evidence statuses, proof bound to final bytes.
- `fnl-reviewer` and `fnl-verifier`: read-only subagents in `agents/` that apply `fnl-review-gate`, `fnl-security-review-gate` and `fnl-verification` in a fresh context.
- `fnl-open-source-review`: open source readiness review with evidence per check.
- `fnl-plugin-packaging`: one repository for Claude Code, Codex and Antigravity, with each host's native tools as the authority for field schemas.
- `/fnl-setup`, `/fnl-setup-instructions` and `/fnl-ask` (user-invoked): a first-run setup interview, an interview that writes the user's working contract for every host, and a router that also points to companion skills from mattpocock/skills.
- Quality eval cases with LLM graders for the packaging, setup and ask skills.
- Acknowledgements of the projects and documentation this pack learned from.
- "Pairs with" pointers to companion skills in the coding router, review gate, verification, commit and session hygiene skills.
- Icon in light and dark (SVG and 512 px PNG), listing metadata for the Claude plugin directory and Codex, and marketplace catalogs so the repository installs as its own marketplace on both hosts.
- Trigger eval suite for `claude plugin eval`: one case per skill and two negative cases.
- Privacy notice, terms of use, issue and pull request templates, Dependabot and a validate workflow.
- MIT license, contributing guide, security policy, Contributor Covenant 2.1 code of conduct, and contributor agent context in `CLAUDE.md`.

[Unreleased]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.10...HEAD
[0.1.10]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/finolabs/finolabs-vibecode/releases/tag/v0.1.0
