---
name: fnl-setup
description: Configure finolabs-vibecode through a short interview, run by the user only. Covers host configuration (data root, agent scan, Delegation mode and Routing, optional roles, quota, metrics, compaction), the repository's agent-skills block, and the instruction files of Claude Code, Codex and Antigravity (user-level contract, AGENTS.md, CLAUDE.md). Subcommands add, instructions, check, scan and mode.
disable-model-invocation: true
argument-hint: "[add <feature> | instructions | check | scan | mode [args]]"
---

# Set up finolabs-vibecode

User scope: account. Project scope: repository.

| Command (Codex: `$fnl-setup <word>`) | Loads |
| --- | --- |
| none | the core path below, then the menu |
| `add <feature>` | `references/features/<feature>.md` (menu below) |
| `instructions` | `references/instructions/procedure.md` |
| `check` | `references/check.md` (read-only), then stop |
| `scan` / `mode [args]` | `references/scan.md` / `references/mode.md` |

A plain sentence selects, never answers a consent question. Ambiguity: one clarifying question, core, never several features at once. Codex forwarding is unverified; use sentences. Claude Code enforces user invocation; elsewhere: advisory (agent judgment).

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged. English output. Questions: native question tool per `references/interview.md`; headless decisions stay open.

## Core path

A bare run says: "Check: `/fnl-setup check` (read-only)." Show host config/scan date; ask one scope question, user, project or both, recommendation first (user on a new computer, project in a repository that is not set up). Follow `references/core.md`.

Read-back: inert facts only. Grants: separate questions, beginner and quick included, with no default.

Offer the beginner path: "Would you like a simpler setup? Other helpers, reviews and extras can wait." If yes: `references/plain-language.md`.
Otherwise **detailed** asks each inert item; **quick** confirms inert defaults once. Ask which.
In every mode these keep their own question: moving the data root and its copy; arming `auto` and the auto gate; filling host config; each Antigravity test-command grant; roles and review posting; the Antigravity hook write; each instruction-file write. In quick mode unknowns stay open.

## Menu

Show feature/cost lines. Load selected features only. Ask `Needs:` separately; declining it ends the dependent feature and never records consent as given.
Record No: `python3 -I <this skill folder>/scripts/setup_features.py decline <feature> --yes`; a bare run does not offer it again (`show` lists records); that record is not a consent; `add <feature>` always asks again. Last offer instructions in this session.

| Feature | Scope | Holds |
| --- | --- | --- |
| `delegation` | user | host config fill, Antigravity test-command grants |
| `roles` | user | review roles, the judge, review posting |
| `quota` | user | on-demand quota reading |
| `metrics` | user | usage metrics, project progress, process snapshot, Antigravity hook |
| `compaction` | user | native threshold, Antigravity stop |
| `review-tools` | user | review instruments, companion skills (recommendations only) |
| `project` | project | work tracking settings, project label |

Install nothing (advisory, agent judgment).
