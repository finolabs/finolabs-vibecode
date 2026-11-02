---
name: fnl-coding-router
description: Route coding work before the first substantive change. Use when starting, resuming or redirecting an implementation, bug fix, refactor or feature: choosing Spec Kit or the fallback process, picking depth (MIN, NORMAL, DEEP), deciding between speckit-tasks and direct implementation, or when fixes keep failing on the same invariant.
---

# Coding router

The entry point for coding work. It picks the workflow, the depth and the gates; the other skills in this plugin own the details it points to.

## 1. Inspect before acting

Read the goal and acceptance criteria, the scoped instructions (`AGENTS.md`, `CLAUDE.md`, a constitution), ownership and the current diff, accepted artifacts and decisions, open failures and findings, and the proof already gathered. Expose conflicts between sources; a newer source does not win by being newer. A missing source pauses only the work that depends on it.

Keep a short receipt: source, task, depth, gaps, evidence limits. A receipt is a record, not proof.

Done when the workflow below can be chosen without guessing.

## 2. Choose the workflow

Choose the workflow here before loading or invoking any generic process skill, including one that another skill asks for.

**Spec Kit first.** When the repository uses Spec Kit, its installed `speckit-*` skills own the development workflow: specify, clarify, plan, tasks, implement, converge. Check the setup and the skill files; a `.specify` folder is a signal, not proof of a working integration. Use the invocation the current agent exposes (Codex: `$speckit-<command>`). Resume from accepted artifacts and the current phase; never restart a completed phase to satisfy a generic skill trigger. Use clarify, checklist and analyze for real ambiguity or where the installed workflow or repository requires them; use convergence only where the installed version supports it, after implementation on the tasks path. Evidence of a requirement or design change can send work back to its owning phase; a generic skill trigger cannot. References: [Spec Kit](https://github.com/github/spec-kit).

Spec Kit replaces the overlapping generic process skills (brainstorming, writing-plans, executing-plans, subagent-driven-development, finishing-a-development-branch). Domain skills, debugging, testing, verification, review and security work still apply inside the active phase, each limited to its own responsibility; any nested instruction that duplicates Spec Kit planning, artifacts or execution yields to this rule.

A Spec Kit repository with a missing or broken required skill has an integration gap: report it and pause that step. Installing, migrating or substituting another workflow needs explicit authority.

**Spec Kit depth gate** (tasks and implement only). Specify, clarify and plan are never skipped. After a plan or user story is accepted and before `speckit-tasks`, implement the story directly when all of these hold:

- it fits one implementation pass over one coherent seam, with known consumers;
- it needs no task ordering or parallel split;
- it hits none of `fnl-security-review-gate` "Triggers" beyond the contract change below, and crosses no migration, dependency or irreversible boundary; accepting new input, or exposing data to anyone who could not see it before, counts as a trigger;
- any contract change is small and contained: every consumer is known and updated in the same change, and `fnl-security-review-gate` reviews it before merge;
- the constitution and scoped rules do not require tasks.

Otherwise run `speckit-tasks`, then `speckit-implement`. When fit stays ambiguous after these rules, run `speckit-tasks`: ambiguity is not evidence that the change is one seam. With the `typesafe-ai` skill installed, read [references/activity-selection.md](references/activity-selection.md) "Depth gate questions" first.

A direct path records the chosen path and its reason in the feature's `plan.md` and meets every acceptance criterion and gate. Its acceptance is `fnl-verification` against each acceptance criterion with fresh targeted tests, plus the two posted reviews of `fnl-review-gate`, whose packet carries the story's acceptance criteria and `plan.md`; it runs no separate analyze or converge step.

A request that is only a review, with no change to make, goes to `fnl-review-gate`, plus `fnl-security-review-gate` when its triggers hit, in any repository.

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

The process skills brainstorming, writing-plans, systematic-debugging and test-driven-development come from [obra/superpowers](https://github.com/obra/superpowers) (MIT); without them, do the same step by hand.

Companion phase tools from other packs fit these rows, for example `grilling`, `prototype`, `tdd` and `diagnosing-bugs` from [mattpocock/skills](https://github.com/mattpocock/skills). They also work inside Spec Kit phases; that pack's process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to Spec Kit where it is in use.

When a semantic choice between eligible activities remains after these rules and the `typesafe-ai` skill is installed, follow [references/activity-selection.md](references/activity-selection.md). Without it, choose by observed fit and the table above, or ask the user the one question that decides it.

Done when you can name the workflow, the phase and the next activity.

## 3. Choose the depth

- **MIN**: a bounded, reversible seam with known consumers and no unexplained failure, blocking finding, or contract, security, privacy, permission, runtime, dependency or migration risk. Work serially: no optional new spec, plan or interview, no implementation children, no broad reruns. Required acceptance, checks and specialist gates still apply. A no-runtime-impact text edit needs its applicable checks, not a new reviewer per edit; text that changes instructions, executable configuration, auth or data is not automatically harmless.
- **NORMAL**: understood behavior and integration.
- **DEEP**: consequential uncertainty, unknown consumers, sensitive boundaries or irreversible effects.

Depth sets effort inside the chosen workflow; in a Spec Kit repository it bypasses nothing except through the depth gate. Upgrade before dependent work. Downgrade only future ceremony when evidence allows, never acceptance, gates, findings or failure counters. File count alone does not set depth.

Done when the depth and its reason are in the receipt.

## 4. Work, then gate

- Delegation to other agents follows the `fnl-delegate` skill. Within one task, budget root and children before spawning: MIN has no implementation children (handing a whole task to another agent under `fnl-delegate` is a delegation, not a child); otherwise at most two lightweight children, one nesting level and one heavy job at a time, unless a stricter cap applies. Independent tasks run in parallel up to `fnl-delegate`'s limit (5 runs), each under these per-task caps.
- Commits follow `fnl-commit-messages`, and so does every branch: creating, syncing, merging and deleting it (`fnl-commit-messages` "Branches"). Versions, tags and changelogs follow `fnl-versioning`.
- Proof follows `fnl-verification`.
- Every pull request needs a posted code review and a posted security review before merge (`fnl-review-gate` "Pull requests").
- Long sessions, handovers and titles follow `fnl-session-hygiene`.

## Checkpoint: stop repeated local fixes

After two failed corrections of the same invariant, stop before a third. Also stop when:

- the next fix reaches a third layer;
- each fix's targeted test is green while the end-to-end gate stays red;
- the proposed fix adds another flag, retry, debounce, timeout or state copy;
- no shared authority, revision or epoch can prove the invariant.

Then keep the implementation task open and the latest behavioral red as it is, stop product edits, and run a read-only architecture checkpoint: map each layer's owned state, whether it is authority or cache, its revision, its triggers and its stale readers. Separate safety, visibility truth, staleness, monotonicity, idempotency and coalescing. Choose one authoritative boundary or a versioned snapshot. Resume only with a deterministic root-cause test and a coherent design. Ask "which distinct failure does this action prevent?" of every proposed step.
