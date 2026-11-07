---
name: fnl-setup
description: Configure finolabs-vibecode through a short interview, run by the user only. Covers host configuration (data root, agent scan, Delegation mode and Routing, optional roles, quota, metrics, compaction), the repository's agent-skills block, and the instruction files of Claude Code, Codex and Antigravity (user-level contract, AGENTS.md, CLAUDE.md). Subcommands add, instructions, check, scan and mode.
disable-model-invocation: true
argument-hint: "[add <feature> | instructions | check | scan | mode [args]]"
---

# Set up finolabs-vibecode

User scope is everything under the user's account (host config, consent, user-level instruction files); project scope is one repository. Explore, settle the user's choices, confirm, then write.

| Command (Codex: `$fnl-setup <word>`) | Loads |
| --- | --- |
| none | the core path below, then the menu |
| `add <feature>` | `references/features/<feature>.md`; features: `delegation`, `roles`, `quota`, `metrics`, `compaction`, `review-tools` (user scope), `project` (project scope) |
| `instructions` | `references/instructions/procedure.md` |
| `check` | `references/check.md` (read-only), then stop |
| `scan` / `mode [args]` | `references/scan.md` / `references/mode.md` |

A plain sentence ("add quota", "set up my instruction files") only selects what to present and never answers a consent question. A sweeping or ambiguous sentence ("set up everything") gets one clarifying question and opens the core path, never several features at once. Whether Codex passes a word after `$fnl-setup` is unverified, so the sentence path is the contract. Enforcer: agent judgment (advisory); the host flag `disable-model-invocation: true` keeps the skill user-invoked on Claude Code.

Talk in the user's language (questions and option labels too); keep commands, flags, paths and skill names unchanged. Script output stays English. Ask through the host's native question tool as `references/interview.md` says. A delegated or headless run records an open decision and never assumes an answer. All advisory (agent judgment).

## Core path

A bare run says in one line where setup stands (the host config present or missing, the scan date), then asks one scope question, user, project or both, recommendation first (user on a new computer, project in a repository that is not set up). Then follow `references/core.md`:

- **User scope**: data root, `scan`, `mode`, knowledge-base write-back, read-back, report.
- **Project scope**: repository facts, `.finolabs/` exclude line, `## Agent skills` block, workflow detection, read-back, report.

The read-back covers inert facts only: what will be shown or written that grants nothing. A step that grants something keeps its own question in every mode, beginner and quick included, with no default.

Offer the beginner path once in plain words: "Would you like a simpler setup? It leaves settings for other AI helpers, review tools and extra skills until later." Start it only when the user says they are new to coding or accepts; follow `references/plain-language.md`. Otherwise **detailed** asks each inert item and **quick** takes the recommended default for inert items and writes after one confirmation. Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes.
In every mode these keep their own question: moving the data root and its copy, arming `auto` and the auto gate, filling host config and each Antigravity test-command grant, roles and review posting, the Antigravity hook write, and each instruction-file write. In quick mode an item the findings cannot fill stays unsettled and is named in the report.

## Menu

The core ends with one menu: each feature with one line on what it does and costs, a neutral Yes and No per item, none preselected. Load a feature file only when the user picks it. A feature names what it needs from another feature (`Needs:`) and asks that prerequisite as its own consent; declining it ends the dependent feature and never records consent as given.
A No on a feature is recorded with `python3 -I <this skill folder>/scripts/setup_features.py decline <feature> --yes`, so a bare run does not offer it again (`show` lists them); that record is not a consent, and `add <feature>` always asks again and clears it. Last, offer the instructions component in this session (neutral Yes and No).

| Feature | Scope | Holds |
| --- | --- | --- |
| `delegation` | user | host config fill, Antigravity test-command grants |
| `roles` | user | review roles, the judge, review posting |
| `quota` | user | on-demand quota reading |
| `metrics` | user | usage metrics, project progress, process snapshot, Antigravity hook |
| `compaction` | user | native threshold, Antigravity stop |
| `review-tools` | user | review instruments, companion skills (recommendations only) |
| `project` | project | work tracking settings, project label |

Install nothing; shared-setting writes are limited to the separately confirmed steps in the feature files (advisory, agent judgment).
