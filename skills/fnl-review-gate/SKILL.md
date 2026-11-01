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

## Who reviews

- **Pairs with** a reviewer's instrument such as `code-review` from [mattpocock/skills](https://github.com/mattpocock/skills) (standards and spec, in parallel). That skill does the review; this gate decides when, by whom, and what happens to each finding.
- **Independent**: a fresh context, never the run or session that wrote the code, and never self-approval. Prefer a different model family at the strong end (see the routing table in `fnl-delegate`).
- One qualified reviewer may cover code and security together when scoped policy permits; name the coverage explicitly.
- A reviewer may delegate heavy reading, but verifies each finding it reports.

## The reviewer packet

Self-contained, no whole-history fork:

- acceptance criteria and the decisions the change rests on;
- the exact binding: base and head SHAs or the commit range, and a fixed worktree when other writers are active;
- known consumers of the changed code;
- tests and configuration run, with their results and limits;
- the requested coverage (correctness, security, performance) and the report format: each finding with file, line, severity and a concrete failure scenario.

Give the reviewer a time budget and a check deadline (`fnl-delegate`).

## Findings

1. **Verify** each finding against the code before fixing it; reject false positives with evidence.
2. Record a **disposition** for every finding: fixed, accepted risk (with the owner's approval), deferred (with a task ID), or rejected (with the evidence).
3. Link each accepted finding to a reopened or new task.
4. Every fix that changes runtime behavior gets a **regression test** that fails without the fix.
5. Verify the fix (`fnl-verification`) and recheck the interactions it touches.
6. Send fixes back for **re-review** until no blocking finding remains.

## Approval

Approval binds to the reviewed bytes: a later change to affected code reopens the gate for that change. Missing required proof stays open; an equivalent check is allowed only with its reason and evidence. Finishing a review grants no push, merge, deploy or publish authority.
