# Workflow: Spec Kit

Read this when the repository uses [Spec Kit](https://github.com/github/spec-kit). The router's depth, gates, proof, "Proportion" and checkpoint still apply.

## Detect

The repository has installed `speckit-*` skills that work. Check the setup and the skill files; a `.specify` folder is a signal, not proof of a working integration. Use the invocation the current agent exposes (Codex: `$speckit-<command>`).

## Steps

Spec Kit's installed `speckit-*` skills own the development workflow: specify, clarify, plan, tasks, implement, converge. Resume from accepted artifacts and the current phase; never restart a completed phase to satisfy a generic skill trigger. Use clarify, checklist and analyze for real ambiguity or where the installed workflow or repository requires them; use convergence only where the installed version supports it, after implementation on the tasks path. When clarify runs, run that skill's interview, but put its questions through the host's native question tool (advisory, agent judgment). Evidence of a requirement or design change can send work back to its owning phase; a generic skill trigger cannot.

## Spec Kit depth gate

Tasks and implement only. Specify, clarify and plan are never skipped. After a plan or user story is accepted and before `speckit-tasks`, implement the story directly when all of these hold:

- it fits one implementation pass over one coherent seam, with known consumers;
- it needs no task ordering or parallel split;
- it hits none of `security-review-gate` "Triggers" beyond the contract change below, and crosses no migration, dependency or irreversible boundary; accepting new input, or exposing data to anyone who could not see it before, counts as a trigger;
- any contract change is small and contained: every consumer is known and updated in the same change, and `security-review-gate` reviews it before merge;
- the constitution and scoped rules do not require tasks.

Otherwise run `speckit-tasks`, then `speckit-implement`. When these conditions leave the fit unclear, take it from the judge if the host config names one (read [../activity-selection.md](../activity-selection.md) "Depth gate questions"); otherwise decide it yourself, and run `speckit-tasks` when you still cannot tell: ambiguity is not evidence that the change is one seam.

A direct path records the chosen path and its reason in the feature's `plan.md` and meets every acceptance criterion and gate. Its acceptance is `checks` against each acceptance criterion with fresh targeted tests, plus the two posted reviews of `review-gate`, whose packet carries the story's acceptance criteria and `plan.md`; it runs no separate analyze or converge step.

Spec Kit owns the process and artifacts; no work record is created in a Spec Kit repository (advisory, agent judgment).

## What yields

Spec Kit replaces the overlapping generic process skills (brainstorming, writing-plans, executing-plans, subagent-driven-development, finishing-a-development-branch, and mattpocock/skills' `to-spec`, `to-tickets`, `implement`, `implement-spec`). Domain skills, debugging, testing, verification, review and security work still apply inside the active phase, each limited to its own responsibility: phase tools such as `grilling`, `shape`, `prototype`, `tdd` and `diagnosing-bugs` work inside Spec Kit phases, and `grilling` and `shape` yield to Spec Kit's own clarify step. Any nested instruction that duplicates Spec Kit planning, artifacts or execution yields to this rule.

## Gaps

A Spec Kit repository with a missing or broken required skill has an integration gap: report it and pause that step. Installing, migrating or substituting another workflow needs explicit authority.
