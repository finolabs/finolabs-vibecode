---
name: fnl-setup-instructions
description: Interview the user and write their user-scoped agent instructions (global CLAUDE.md, Codex AGENTS.md, Antigravity GEMINI.md) from one shared source, pointing coding practice at the finolabs-vibecode skills.
disable-model-invocation: true
---

# Set up user-scoped instructions

User-scoped instructions load in every session the user starts, in every repository. Write them as a short **working contract**: who the user is, how to work with them, what needs their approval, and where the detailed practice lives. Detailed engineering rules stay in the `fnl-` skills; the contract points to them instead of restating them.

The section skeleton and its question bank are in [references/contract-template.md](references/contract-template.md). File locations and include syntax per host are in [references/hosts.md](references/hosts.md); recheck them against each host's docs before writing.

## 1. Explore

- Which hosts the user runs (`claude`, `codex`, `agy` on `PATH`) and which instruction files already exist for them (see `hosts.md`). Read the existing files: they are the user's current contract and the starting draft.
- Whether the same text is copied into several files (a drift risk this skill will offer to remove).

A file or command that cannot be checked here is listed as **unverified** in one line, with a request that the user paste its contents if it exists. Missing permissions are not a reason to stop: the interview needs only the user's answers.

Done when the message lists the files found, their sizes, any duplication and what is unverified, and it ends with the first round of questions, each with a concrete recommended answer. When the hosts are unverified, the round includes which hosts the user runs ("Recommended: Claude Code first, the others later.").

## 2. Grill

Interview the user section by section through the template. Prefer what the existing files already say: ask only about gaps, conflicts and stale lines, and skip optional sections the user does not need.

Interview by the plugin's shared rules in `references/interview.md` (two folders above this skill's base directory): map the decisions, look up facts yourself, ask every ready decision in one numbered round with a recommended answer, and finish with a read-back and a yes.

Done when every required section has confirmed rules and every optional section is confirmed or skipped.

## 3. Draft

- One **shared body** with the host-neutral sections, plus a short **host section** per host (session naming, compaction, tool quirks).
- Point to skills by name for practice the plugin already covers: coding entry (`fnl-coding-router`), delegation (`fnl-delegate`), commits (`fnl-commit-messages`), versions (`fnl-versioning`), proof (`fnl-verification`).
- Keep it short: every line loads on every turn of every session. Cut any line the agent would follow by default.
- Content the user marks private (employer, customers, personal paths) stays in their own files only.

## 4. Confirm and write

1. Show the full draft, then a diff against each existing file.
2. Recommend a layout with one source of truth (`hosts.md` lists the include mechanism each host supports) and let the user choose.
3. After an explicit yes for each file: back up the existing file beside it (`<file>.bak-YYYYMMDD`), write, then read it back.

Never write a user's instruction file without that yes; these files steer every future session.

## 5. Report

Files written, backups made, files left unchanged and why, and how to check the result: start a fresh session on each host and ask the agent to summarize its instructions.
