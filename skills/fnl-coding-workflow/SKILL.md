---
name: fnl-coding-workflow
description: Route coding work before the first substantive change. Use when starting, resuming or redirecting an implementation, bug fix, refactor or feature: choosing Spec Kit or the fallback process, picking depth (MIN, NORMAL, DEEP), deciding between speckit-tasks and direct implementation, or when fixes keep failing on the same invariant.
---

# Coding workflow

The entry point for coding work. It picks the workflow, the depth and the gates; the other skills in this plugin own the details it points to.

## 1. Inspect before acting

Read the goal and acceptance criteria, the scoped instructions (`AGENTS.md`, `CLAUDE.md`, a constitution), ownership and the current diff, accepted artifacts and decisions, open failures and findings, and the proof already gathered. Expose conflicts between sources; a newer source does not win by being newer. A missing source pauses only the work that depends on it.

Keep a short receipt: source, task, depth, gaps, evidence limits. A receipt is a record, not proof.

Done when the workflow below can be chosen without guessing.

## 2. Choose the workflow

**Spec Kit first.** When the repository uses Spec Kit, its installed `speckit-*` skills own the development workflow: specify, clarify, plan, tasks, implement, converge. Check the setup and the skill files; a `.specify` folder is a signal, not proof of a working integration. Use the invocation the current agent exposes (Codex: `$speckit-<command>`). Resume from accepted artifacts and the current phase; never restart a completed phase to satisfy a generic skill trigger.

Spec Kit replaces the overlapping generic process skills (brainstorming, writing-plans, executing-plans, subagent-driven-development, finishing-a-development-branch). Domain skills, debugging, testing, verification, review and security work still apply inside the active phase, each limited to its own responsibility.

A Spec Kit repository with a missing or broken required skill has an integration gap: report it and pause that step. Installing, migrating or substituting another workflow needs explicit authority.

**Spec Kit depth gate** (tasks and implement only). After a plan or user story is accepted and before `speckit-tasks`, implement directly when all of these hold:

- the change is one coherent seam with known consumers;
- it needs no task ordering or parallel split;
- it touches no contract, security, privacy, permission, migration, dependency or irreversible boundary;
- the constitution and scoped rules do not require tasks.

Otherwise run `speckit-tasks`, then `speckit-implement`. When fit stays ambiguous after these rules, judge it with two narrow questions over the plan or story summary, acceptance criteria and touched areas: "fits one implementation pass" and "hides a cross-cutting risk" (a semantic evaluator may answer them; see [references/activity-selection.md](references/activity-selection.md)). A direct path still meets every acceptance criterion and gate, runs targeted tests, and records the chosen path and its reason in the feature's `plan.md`. Specify, clarify and plan are never skipped.

**Fallback router**, only in repositories without Spec Kit. Fill only the missing artifacts and keep accepted decisions:

| Gap | Next action |
| --- | --- |
| Unclear intent or acceptance | Bounded clarification (grilling when triggered); persist decisions before dependent code. |
| Missing agreement, design or plan | Fill only what is missing (brainstorming, writing-plans when triggered). |
| Bug, CI failure, unexplained finding | systematic-debugging; keep the reproducer and establish the cause. |
| Ready seam | Smallest sufficient change; test-driven-development with a genuine behavioral red. |
| Missing or stale proof | The `fnl-verification` skill. |
| Required review absent | The `fnl-review-gate` skill, plus `fnl-security-review-gate` when its triggers hit. |
| Outcome evidenced | Report the actual disposition. |

When a semantic choice between eligible activities remains after these rules, follow [references/activity-selection.md](references/activity-selection.md).

Done when you can name the workflow, the phase and the next activity.

## 3. Choose the depth

- **MIN**: a bounded, reversible seam with known consumers and no unexplained failure, blocking finding, or contract, security, privacy, permission, runtime, dependency or migration risk. Work serially: no optional new spec, plan or interview, no implementation children, no broad reruns. Required acceptance, checks and specialist gates still apply. A no-runtime-impact text edit needs its applicable checks, not a new reviewer per edit; text that changes instructions, executable configuration, auth or data is not automatically harmless.
- **NORMAL**: understood behavior and integration.
- **DEEP**: consequential uncertainty, unknown consumers, sensitive boundaries or irreversible effects.

Depth sets effort inside the chosen workflow; in a Spec Kit repository it bypasses nothing except through the depth gate. Upgrade before dependent work. Downgrade only future ceremony when evidence allows, never acceptance, gates, findings or failure counters. File count alone does not set depth.

Done when the depth and its reason are in the receipt.

## 4. Work, then gate

- Delegation to other agents follows the `fnl-orchestration` skill. Budget root and children before spawning: MIN has no implementation children; otherwise at most two lightweight children, one nesting level and one heavy job at a time, unless a stricter cap applies.
- Commits follow `fnl-commit-messages`; versions, tags and changelogs follow `fnl-versioning`.
- Proof follows `fnl-verification`.
- Pull requests need a clean code review and, when triggered, a security review before merge (`fnl-review-gate`, `fnl-security-review-gate`).
- Long sessions, handovers and titles follow `fnl-session-hygiene`.

## Checkpoint: stop repeated local fixes

After two failed corrections of the same invariant, stop before a third. Also stop when:

- the next fix reaches a third layer;
- each fix's targeted test is green while the end-to-end gate stays red;
- the proposed fix adds another flag, retry, debounce, timeout or state copy;
- no shared authority, revision or epoch can prove the invariant.

Then keep the implementation task open and the latest behavioral red as it is, stop product edits, and run a read-only architecture checkpoint: map each layer's owned state, whether it is authority or cache, its revision, its triggers and its stale readers. Separate safety, visibility truth, staleness, monotonicity, idempotency and coalescing. Choose one authoritative boundary or a versioned snapshot. Resume only with a deterministic root-cause test and a coherent design. Ask "which distinct failure does this action prevent?" of every proposed step.
