---
name: fnl-review-gate
description: Gate work on an independent code review. Use when a user story or increment is committed, before a pull request merges, when briefing a reviewer, when review findings arrive and need a disposition, or when deciding whether a fix needs re-review.
---

# Review gate

## When the gate applies

- **After each user story** or increment: review it, dispose every finding, fix and verify, then review the next story. The next story's implementation starts only after the previous gate is closed.
- **Before merge**: a pull request needs a clean code review, and a security review when `fnl-security-review-gate` triggers, bound to the final bytes.
- Major features and work produced by delegated agents always get one.
- A no-runtime-impact text edit needs its checks, not a reviewer per edit.

## Instruments

This gate decides when, by whom, and what happens to each finding; an instrument does the reading. The reviewer uses its own host's native review and adds companions:

- **Claude Code**: `/code-review` on the diff at a chosen effort, `/security-review` for pending changes that hit a security trigger, `claude ultrareview` for a cloud multi-agent pass before merging large work (the code goes to a cloud run, so the owner approves it). Posting comments or applying fixes needs an explicit ask.
- **Codex**: `codex review --base <branch>` (or `--uncommitted`, `--commit <sha>`), or `/review` in a session.
- **Antigravity**: no native AI review; `/diff` and the review pane are for the human. Route the review to Claude Code or Codex.
- **Companions**: `code-review` from [mattpocock/skills](https://github.com/mattpocock/skills) for standards and spec, and `security-audit` from [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) for audits (`fnl-security-review-gate` says when).

When an instrument is missing, the reviewer applies the packet and findings rules below directly and names the missing instrument in its report.

## Who reviews

- **Independent**: a fresh context, never the run or session that wrote the code, and never self-approval. With the plugin installed, the `fnl-reviewer` and `fnl-security-reviewer` agents are ready-made fresh-context reviewers; a reviewer from another model family (`fnl-delegate`) adds contrast. Prefer a different model family at the strong end (see the routing table in `fnl-delegate`).
- One qualified reviewer may cover code and security together when scoped policy permits; name the coverage explicitly.
- A reviewer may delegate heavy reading, but verifies each finding it reports.

## The reviewer packet

Self-contained, no whole-history fork:

- acceptance criteria and the decisions the change rests on;
- the exact binding: base and head SHAs or the commit range, and a fixed worktree when other writers are active;
- known consumers of the changed code, as a starting list the reviewer extends;
- tests and configuration run, with their results and limits;
- the requested coverage (correctness, security, performance) and the report format: each finding with file, line, severity and a concrete failure scenario.

Give the reviewer a time budget and a check deadline (`fnl-delegate`).

## Review scope

A review covers two rings, in order: the change itself, then what the change can break. The rest of the repository stays out of scope.

1. **The change**: every hunk of the diff read in its full context, meaning the whole function, class or block it sits in, and new files whole. Tests, configuration, migrations and build files in the diff count as change. Done when every changed file has been read; a file judged by its name has not been read.
2. **The impact set**, traced from the changed symbols rather than guessed:
   - consumers of each changed function, type, endpoint, event, command, configuration key, schema or column (name search, language-server references, route and handler tables);
   - what the change now depends on: functions called with new arguments or new assumptions, new packages, environment;
   - contracts: public APIs, serialized formats, database schema and migrations, permissions;
   - the tests covering the changed code, and whether they still exercise the new behavior.

   Follow one hop from each changed symbol. Go further only where the hop passes the change on (a changed return shape handed to the next caller, a widened permission reused elsewhere).

Defects seen outside both rings are listed separately as **outside the change**, non-blocking. A diff over about 1,000 changed lines or 30 files is split by seam, one reviewer per seam, each with its own rings.

The report states the coverage: the impact set as "symbol → consumers checked", and anything not traced with the reason. The gate reads it to know what the approval covers.

## Findings

1. **Verify** each finding against the code before fixing it; reject false positives with evidence.
2. Record a **disposition** for every finding: fixed, accepted risk (with the owner's approval), deferred (with a task ID), or rejected (with the evidence).
3. Link each accepted finding to a reopened or new task.
4. Every fix that changes runtime behavior gets a **regression test** that fails without the fix.
5. Verify the fix (`fnl-verification`) and recheck the interactions it touches.
6. Send fixes back for **re-review** until no blocking finding remains.

## Approval

Approval binds to the reviewed bytes: a later change to affected code reopens the gate for that change. Missing required proof stays open; an equivalent check is allowed only with its reason and evidence. Finishing a review grants no push, merge, deploy or publish authority.
