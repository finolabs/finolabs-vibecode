# Changelog

All notable changes to this plugin are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/) under the phase-0 rules in `fnl-versioning`.

## [Unreleased]

### Added

- `fnl-coding-router` `references/non-code-work.md`, read on demand for queries on live data, infrastructure, dashboards and forecasts; the router stays code by default, and DEEP now also covers compounding calculations, predictions and ambiguous input.
- `fnl-coding-router` "Proportion": build what the acceptance criteria require at the product's current stage, trace each hunk to a criterion and run tests at checkpoints, not after every edit or across the whole suite. Handoff briefs, verification and the review gate carry the limit.

### Changed

- A judge named in the host config (for example `typesafe-ai` for TypeSafe's Jev) now makes the grade, route, depth and next-activity calls first; without one, or when it is inconclusive, the agent decides itself. The detail moved into references read only when a judge is configured.
- `fnl-delegate`: plain content writing goes to Codex first; a "Stays with the coordinator" rule lists what a delegate never does or decides; a same-family review fallback asks the user first on a security-triggered pull request.
- `fnl-review-gate`: severities are defined (CRITICAL, HIGH and MEDIUM block; LOW never causes another round), rework is capped at two rounds, and findings outside the change stay in the report.
- `fnl-security-review-gate`: adds a data-leaving trigger, a short report when no trigger matches, negative tests only through entry points that reach the touched resources, and an exploit scenario for MEDIUM or higher.
- `fnl-open-source-review`: reruns before each MINOR release, strongly recommends a secret scanner, caps the verdict at "not ready" while a secrets, leaks or license check is BLOCKED, and splits repository settings into blocking and noted.
- `fnl-verification`: names the gap and proposes a test for an untested runtime change, proposes a full suite for widely shared code, points to the non-code reference, and lets only the owner waive a check.
- `fnl-commit-messages`: a commit is one whole seam with a body of about six lines; agents commit when a seam passes its targeted tests, on their own branch, without pushing; pull request text stays short.
- `fnl-handoff`: findings go back to the same run while it is light and to a new run after about 60% context or two failed rework rounds; a prose brief names language and tone, and the editing pass runs only for social content or documents.
- `fnl-advisor` and `fnl-committee`: both are proposed and wait for the user's yes; tier follows difficulty; a same-family advisor stands in only when both other families are out; a committee adds a third member only after two rounds of disagreement, settles it with one reversible experiment, and waits for the user before its plan is dispatched.
- `fnl-coordinator-sessions`: coordinate from three user stories or ten tasks; the coordinator writes no application code; standby covers the next story plus one fix session; independent stories still run one after another.
- `fnl-status`: flags a group only from five runs (first-pass acceptance below 60%, or timeouts plus fallbacks at 25%); a coordinator closes the orphaned ledger records its own session created.
- `fnl-session-hygiene`: a finished user story with its review gate closed is a boundary for a fresh session, knowledge is written back only when it would change what an agent does next time, and session titles use English for the activity unless the user asks for their own language.
- `fnl-versioning`: an agent never cuts a release on its own and proposes one when a spec is merged, a spec usually bumps the last digit, a release is two pull requests, and changelog entries stay to one or two sentences.

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
- `fnl-commit-messages` "Branches" sets one branch flow: trunk-based with short-lived branches, naming, the base to cut from, syncing by rebase or merge without rewriting a pushed branch, conflicts, default branch rules, merge commits pinned to the reviewed head, cleanup of branch and worktree, hotfixes and backports to `release/X.Y`. Its description gains branch triggers, and `fnl-coding-router`, `fnl-delegate`, `fnl-handoff`, `fnl-coordinator-sessions`, `fnl-review-gate`, `fnl-versioning`, `fnl-open-source-review` and `fnl-ask` point to it where a branch is created, synced or merged.
- The contributing guide lists the local checks, how to add a host, and the release checklist, which includes an adversarial review by another model family.

### Changed

- `fnl-coding-router`'s Spec Kit depth gate lets a user story go from an accepted plan straight to implementation, skipping `speckit-tasks`, also when it makes a small, contained contract change that a security review covers; security, privacy, permission, migration, dependency and irreversible boundaries still go through tasks. A direct path is accepted by `fnl-verification` against each acceptance criterion and the two posted reviews, and `fnl-review-gate`'s reviewer packet carries the story's acceptance criteria and `plan.md` when Spec Kit is in use. A direct path runs no separate analyze or converge step. Two behavior evals guard it: an additive response field goes direct (it passes without the plugin too), and a new filter parameter that reaches a query goes to tasks (2/2 with the plugin, 0/2 without).
- Claude Code and Codex install the plugin from the FINOLABS catalog, `finolabs/plugins` (`finolabs-vibecode@finolabs`), which groups the FINOLABS plugins under one name; the repository's own marketplace stays for existing installs. The manifests name FINOLABS as author and developer. The agent install steps check for an existing install before adding the catalog.
- The repository moved to `github.com/finolabs/finolabs-vibecode`; links, manifests and install commands use the new address, and GitHub redirects the old one.
- `fnl-coordinator-sessions`, the delegation host template and agent contracts use that title format.
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
- `fnl-delegate`, `fnl-handoff`, `fnl-advisor`, `fnl-committee`: grading and routing across Codex, Antigravity and Claude Code, quota fallback, at most 5 parallel dispatches, hard time caps and liveness from artifacts, heavy-job lock, verify-before-accept, handover after interrupted runs, file placement, and the dispatch ledger script; a host config template.
- Any agent can coordinate: `fnl-delegate` routes by agent and model through a dated capability map (`references/models.md`), states each agent's dispatch contract from every coordinator, and takes an optional route judge for open calls with a conservative fallback; the ledger records the coordinator and how each route was chosen.
- `fnl-knowledge`: native agent memory for working preferences, one shared knowledge base (Orrery where available, or an Obsidian vault) for decisions, lessons and project state, and a native-memory map per host.
- Pull request gate: every pull request needs a code review and a security review, each posted as a comment with a machine-readable marker bound to the head commit, before it merges.
- `fnl-security-reviewer` agent, and a two-ring review scope in the review gates: every changed file in full context, then the impact set (consumers, dependencies, contracts, tests) or, for security, every trust path to the change; reviewers report what they traced.
- Review instruments: the review gates and agents use each host's native review (`/code-review`, `/security-review`, `codex review`) and recommend Cloudflare's `security-audit` skill for audits.
- Single-skill installs through skills.sh: every skill folder is self-contained, the delegation family names `fnl-delegate` as its one dependency, and CI checks that shared copies match and no skill reaches outside its folder.
- `/fnl-status` (user-invoked): open delegated runs and acceptance per agent and model from the ledger.
- `fnl-coordinator-sessions`: coordinator plus one app session per task, standby sessions, review gate per user story.
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

[Unreleased]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/finolabs/finolabs-vibecode/releases/tag/v0.1.0
