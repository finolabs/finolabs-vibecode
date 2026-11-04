---
name: fnl-setup-instructions
description: Interview the user and write user-scoped working contracts, project-scoped agent context, or both for Claude Code, Codex and Antigravity. Use to set up global preferences, repository build and test commands, conventions and skill pointers, or consolidate instruction files into one source. Run only when the user asks for it.
disable-model-invocation: true
---

# Set up agent instructions

User-scoped instructions load in every session the user starts, in every repository. Write them as a short **working contract**: who the user is, how to work with them, what needs their approval, and where the detailed practice lives. Detailed engineering rules stay in the `fnl-` skills; the contract points to them instead of restating them.

Project-scoped instructions hold only repository-specific build and test commands, conventions, adopted gates and pointers to the `fnl-` skills. Never repeat the user-scoped contract in them.

Start with one question: "Which scope: user, project, or both?" Add one concrete recommendation: user for a bare invocation or preferences across repositories, project for repository context, both when the request covers both. Wait for the answer before scope-dependent exploration.

The user-contract skeleton and question bank are in [references/contract-template.md](references/contract-template.md). File locations and include syntax per host are in [references/hosts.md](references/hosts.md); recheck them against each host's docs before writing.

## 1. Explore

- Which hosts the user runs (`claude`, `codex`, `agy` on `PATH`) and which instruction files already exist in the chosen scope (see `hosts.md`). Read them as the starting draft; read the user contract for comparison when available, without changing it in project-only mode.
- Whether the same text is copied into several files (a drift risk this skill will offer to remove).
- For project scope: the repository root, its documented build and test commands and conventions, existing context files and overrides, and the `## Agent skills` block and review-gate adoption line written by `fnl-setup`. Read and preserve those entries; never duplicate or author them. If either is missing, point to `/fnl-setup` and leave adoption pending.

A file or command that cannot be checked here is listed as **unverified** in one line, with a request that the user paste its contents if it exists. Missing permissions are not a reason to stop: the interview needs only the user's answers.

Done when the message lists the files found, their sizes, any duplication and what is unverified, and it ends with the first round of questions, each with a concrete recommended answer. When the hosts are unverified, the round includes which hosts the user runs ("Recommended: Claude Code first, the others later."), and questions that depend on the answer (file locations, host sections, delegation between hosts) wait for the next round.

## 2. Grill

For user scope, interview section by section through the template. For project scope, settle repository commands, conventions, adopted gates, skill pointers and any migration of existing context into `AGENTS.md`; do not repeat the user interview. For both, settle each decision once in its own scope. Prefer existing files: ask only about gaps, conflicts and stale lines, and skip optional sections the user does not need.

Interview by the rules in [references/interview.md](references/interview.md): map the decisions, look up facts yourself, ask every ready decision in one numbered round with a recommended answer, and finish with a read-back and a yes.

Done when the chosen scope's decisions are confirmed or explicitly left pending, and each optional section is confirmed or skipped. Record unresolved decisions before dependent drafting.

## 3. Draft

- **User scope:** one shared body with the host-neutral sections, plus a short host section per host (session naming, compaction, tool quirks).
- **Project scope:** `AGENTS.md` is the source; `CLAUDE.md` holds an `@AGENTS.md` include line plus only Claude-specific lines. Antigravity reads `AGENTS.md` directly where its docs confirm support. Consolidate existing repository rules without losing them; move the setup-owned block and adoption line intact into the source only in the confirmed migration, never leaving a second copy. Resolve conflicts with the user first.
- Point to skills by name for practice the plugin already covers: coding entry (`fnl-coding-router`), delegation (`fnl-delegate`), commits (`fnl-commit-messages`), versions (`fnl-versioning`), proof (`fnl-verification`).
- Keep it short: every line loads on every turn of every session. Cut any line the agent would follow by default. Treat about 150 lines in the shared body as a soft limit: beyond it, offer to move detail into a skill or a reference the contract points to, rather than cut lines blindly.
- Committed context contains no personal, customer or organization names or machine paths. Personal project context goes in Claude Code's untracked `CLAUDE.local.md`; tell the user to keep it out of git. Do not copy it into other hosts' tracked files or commit backups; unverified local-file support is listed in `hosts.md`.

## 4. Confirm and write

1. Show the full draft, then a diff for every proposed file (against empty content for a new file), including any migration or local file.
2. For user scope, recommend a layout with one source of truth (`hosts.md` lists supported includes); for project scope, confirm the `AGENTS.md` source and Claude include layout above.
3. After an explicit yes for each file: back up the existing file beside it (`<file>.bak-YYYYMMDD`), write, then read it back.

Never write an instruction file in either scope without that file's explicit yes; these files steer future sessions.

## 5. Report

Files written by scope, backups made, files left unchanged and why, pending `/fnl-setup` items and anything unverified. Remind the user to keep local context and backups out of git. To check the result, start a fresh session on each host in the repository and ask the agent to summarize its instruction sources and rules; docs checks alone do not prove runtime loading.
