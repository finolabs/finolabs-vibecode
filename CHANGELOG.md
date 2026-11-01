# Changelog

All notable changes to this plugin are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/) under the phase-0 rules in `fnl-versioning`.

## [Unreleased]

Target version: `0.1.0`.

### Added

- Claude Code, Codex and Antigravity manifests sharing one `skills/` folder, version `0.1.0-dev`.
- `fnl-coding-router`: Spec Kit first routing, fallback router, MIN/NORMAL/DEEP depth, the Spec Kit depth gate, the repeated-fix checkpoint, and activity selection with a semantic evaluator as a reference.
- `fnl-session-hygiene`: compaction at about 60% context, handover content, titles, one writer per scope.
- `fnl-delegate`, `fnl-handoff`, `fnl-advisor`, `fnl-committee`: grading and routing across Codex, Antigravity and Claude Code, quota fallback, at most 5 parallel dispatches, hard time caps and liveness from artifacts, heavy-job lock, verify-before-accept, handover after interrupted runs, file placement, and the dispatch ledger script; a host config template.
- `fnl-coordinator-sessions`: coordinator plus one app session per task, standby sessions, review gate per user story.
- `fnl-versioning`: SemVer, phase 0, cadence, single source of truth, immutable tags, Keep a Changelog, release authority.
- `fnl-commit-messages`: atomic commits, imperative subjects, exclusions, attribution trailer, PR descriptions.
- `fnl-review-gate`: independent review, reviewer packet, finding dispositions, regression tests, re-review, approval bound to final bytes.
- `fnl-security-review-gate`: triggers, permission-boundary review with negative tests and no existence leak.
- `fnl-verification`: targeted tests, full suites only on request, evidence statuses, proof bound to final bytes.
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
