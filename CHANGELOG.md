# Changelog

All notable changes to this plugin are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/) under the phase-0 rules in `fnl-versioning`.

## [Unreleased]

### Changed

- `fnl-verifier` counts a review marker only from an author with write access, like the merge check, which now names the permission values GitHub returns.

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

[Unreleased]: https://github.com/fioenix/finolabs-vibecode/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/fioenix/finolabs-vibecode/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/fioenix/finolabs-vibecode/releases/tag/v0.1.0
