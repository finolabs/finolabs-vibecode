# Changelog

All notable changes to this plugin are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/) under the phase-0 rules in `fnl-versioning`.

## [Unreleased]

### Added

- `fnl-session-hygiene` sets a session title format, `<project> <scope>: <activity>`, with examples, when to rename, whose sessions to rename, and how each host names sessions (`references/titles.md`).
- CI checks cross-references (`scripts/check-references.py`): skill and agent names, section references (backticked or linked), relative links, ledger subcommands with their own flags and allowed values, and host config flags against the agent contracts.
- `fnl-delegate`'s capability map carries a review-by date, and `/fnl-status` warns when it has passed.
- Behavior evals (tag `behavior`) with deterministic graders on each answer's final verdict line: the pull request merge check with a stale marker, a marker from an author without write access, and a valid pair; coding-router depth for a typo and a tenancy change; the merge check when a later marker overrides an earlier one for the same head, when a later comment quotes a marker, and when the author lacks write access; delegate routing when one agent's quota is out, when every frontier model is, when only frontier models are left for medium work, and for a review; the Spec Kit depth gate; verification of a false delegated report. Against a no-plugin baseline, the review routing and depth gate cases show the skills' effect; the others guard against regressions.
- The contributing guide lists the local checks, how to add a host, and the release checklist, which includes an adversarial review by another model family.

### Changed

- Claude Code and Codex install the plugin from the FINOLABS catalog, `finolabs/plugins` (`finolabs-vibecode@finolabs`), which groups the FINOLABS plugins under one name; the repository's own marketplace stays for existing installs. The manifests name FINOLABS as author and developer. The agent install steps check for an existing install before adding the catalog.
- The repository moved to `github.com/finolabs/finolabs-vibecode`; links, manifests and install commands use the new address, and GitHub redirects the old one.
- `fnl-coordinator-sessions`, the delegation host template and agent contracts use that title format.
- `fnl-verifier` counts a review marker only from an author with write access, like the merge check, which now names the permission values GitHub returns.
- `fnl-delegate` keeps routing and the steps every dispatch takes in `SKILL.md`, and moves procedures only some runs reach (quota fallback, parallel runs, the heavy-job lock, handover, file placement, ledger commands) to `references/dispatch.md` and `references/ledger.md`.
- `fnl-review-gate` merge check: a verdict is an unedited comment whose first line is a marker, from an author with write access; for each kind the latest such verdict for the head (by `createdAt`) must be `APPROVE`, so a later `REWORK` blocks the merge and a marker quoted inside a comment counts for nothing. A pull request from an author without write access also needs the owner's own approving review. The verifier counts verdicts the same way.
- Reviewers treat everything under review as data: text in a pull request that tells the reviewer what to conclude, post or run is a finding (`fnl-review-gate`, both reviewer agents).
- An Antigravity coordinator's wider allow-rules need the user's approval (`fnl-delegate` agent contracts).

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

[Unreleased]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/finolabs/finolabs-vibecode/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/finolabs/finolabs-vibecode/releases/tag/v0.1.0
