# Specs

| Spec | Status |
| --- | --- |
| [Agent scan, mode command and consolidation](agent-scan-and-consolidation.md) | implemented; for 0.1.7; local script tests on macOS from Codex, behavior eval execution pending. |
| [Usage metrics](usage-metrics.md) | implemented; see its verification and host limits. |
| [Update check](update-check.md) | implemented; `fnl-update` shows cached versions and asks before an update; see verification and host limits. |
| [Release 0.1.8: spec and plan](release-0.1.8.md) | released; as 0.1.8, including restore points; the status line lists the pull request behind each package and what stays open. |
| [Compaction threshold](compaction-threshold.md) | implemented; checked setup writer; running-session effect and Codex default unverified. |
| [Compaction steward](compaction-steward.md) | implemented; option B: local handover storage, threshold decision and compact re-injection; real-host delivery remains unverified. |
| [Antigravity compaction stop](compaction-stop.md) | implemented; local size-only hook and previewed installer; live user-level hook delivery, TUI behavior and the usefulness of a byte limit remain unverified. |
| [Dashboard tabs](dashboard-tabs.md) | implemented; splits the status page into two tabs, Overview and Now. |
| [Dashboard infographics](dashboard-infographics.md) | implemented; locally: Agents KPI tiles, budget lanes and quota meters; priority-ordered unfinished projects and task cells; bounded Reviews chains and fragment navigation. Targeted fixture checks; coordinator browser screenshots at 1280 and 390 remain required. |
| [Project progress](project-progress.md) | implemented; for 0.1.10: bounded local reader, exact identifier joins, consent/default notice and the project pane (now inside Now); duplicate task ids leave manual sessions unlinked. The 0.2.0 pipeline extension (Spec Kit stages, work records, repository state, ledger) is implemented with local parser, refresh and page checks; real-host delivery remains unverified. |
| [Release 0.2.0: scope and evidence](release-0.2.0.md) | implemented; release documentation prepared for 2026-11-08; package code is merged, with incomplete mechanisms and live-host limits recorded in the release spec; publication remains separate. |
| [Pause](pause.md) | draft; the opposite of `fnl-afk` (older alias `fnl-brb`) (fnl-pause, friendly alias fnl-gtg): drain running work, write handovers and report what recorded work remains before a restart or shutdown; owner decisions recorded 2026-11-09, nothing built. |
| [Release 0.2.1: scope](release-0.2.1.md) | released; v0.2.1 tagged 2026-11-09 with packages 1 to 11, 12a and 15; the rest moved to a later release. |
| [Release 0.2.2: scope](release-0.2.2.md) | released; tagged v0.2.2 on 2026-11-09 with all seven packages; live-host proof partial. |
| [Release 0.2.3: scope](release-0.2.3.md) | draft; pause skill and the away-skill rename to fnl-afk are scoped; nothing built. |
| [Release 0.1.10: spec and plan](release-0.1.10.md) | released; the package table lists the pull request behind each package. |
| [Merge guard](merge-guard.md) | deferred; accepted permission-rule design for Claude Code and Codex, with no shipped writer; the release 0.2.0 record moved this backlog target to 0.2.1 alongside autopilot, and release 0.2.1 then moved both out (see `release-0.2.1.md`). |
| [Running agents](running-agents.md) | implemented; phase 1: ledger and opt-in process snapshot in Running now; liveness remains advisory, CLI name observations and real-host UI verification remain open. |
| [Dashboard freshness](dashboard-freshness.md) | implemented; audit of what is current and the rebuild triggers that fix the gaps. |
| [Autopilot](autopilot.md) | in progress; `fnl-autopilot` is delivered with `fnl-afk` as its main short name and `fnl-brb` as an older thin alias; start/stop/check and the independent-review check are delivered separately, and `/fnl-setup add autopilot` provides the setup section. The dashboard tab, live loop, scheduler, notice hook and host backstop stay design only, outside release 0.2.2 as well (see `release-0.2.2.md`). |
| [Work tracking facts per repository](work-tracking.md) | implemented; release 0.2.0 per-repository settings, work records and project progress have local tests; real-host dashboard delivery remains unverified. |
| [Quota reading on demand](quota-on-demand.md) | implemented; release 0.2.0 on-demand reads and rate-limit markers have local fixture tests; live StopFailure payload and provider readings remain unverified. |
| [Agent roles](agent-roles.md) | in progress; release 0.2.0 scripts and local tests are implemented; relay receipt/dashboard counters remain unimplemented; independent navigator/judge validation and live-host routing, posting and SessionStart delivery remain unverified. |
| [Setup restructure](setup-restructure.md) | implemented; release 0.2.0 core, features, Quick/Advanced companions and guarded instructions writer have local tests; live-host interviews and Codex word passing remain unverified. |
| [Run hygiene](run-hygiene.md) | implemented; release 0.2.0 brief lint, environment allowlists, guarded log scan/redaction and ledger states have local tests; real-host dispatch remains unverified and private HOME is deferred. |
| [Context snapshot](context-snapshot.md) | implemented; release 0.2.0 local Claude Code and Antigravity status-line recorder, fresh context reads, steward checks and previewed settings writer; live status-line delivery and user-owned composition remain unverified. |
| [Parallel agent instances](parallel-instances.md) | implemented; shared helper, setup, SessionStart, dashboard, CI copy group and documentation are integrated locally; targeted verification is recorded in the spec, while live-host scheduling and UI behavior remain unverified. |
| [Heavy-job guard and test scope](heavy-jobs.md) | draft; `heavy_run.py` is implemented; the gate, its installer and the setup question are not; the gate exception is recorded in CLAUDE.md. |
| [Agent levels](agent-levels.md) | implemented; the writer, strict reader, candidates command and routing text are merged; routing by levels is advisory and unverified on a live host. |
