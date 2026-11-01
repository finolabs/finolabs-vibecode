# Activity selection with a semantic evaluator

Use this only after the workflow is chosen and host rules, accepted decisions and prerequisites have not settled the next activity. It selects one activity inside that workflow; it never chooses Spec Kit versus the fallback router and grants no execution authority. Call an evaluator (for example TypeSafe Jev) only for material semantic ambiguity whose answer can change the next step; reuse an equivalent valid judgment.

## 1. Build eligible candidates

The host checks scope and authority, installed skills and callable capabilities, the current phase, accepted artifact revisions, dependencies and required gates. Each candidate has a stable activity ID, the exact installed handler, its purpose, prerequisite evidence, and a bounded output or stop condition.

- For a large or ambiguous catalog, retrieve a bounded shortlist from descriptions, then read the relevant full skill instructions before the final choice. Keep a no-match outcome possible.
- Exclude unavailable, unauthorized, blocked or duplicate-process candidates. Unknown prerequisites need evidence, not model approval.
- Zero eligible activities: resolve the blocker. One activity settled by policy: execute it without an evaluator.

## 2. Supply bounded state

Goal and acceptance, workflow and phase, relevant artifact identities, revisions and approval state, the concrete request or finding, minimal evidence, the eligible candidates and the unresolved distinction. Send only the fields the judgment needs through an existing authorized interface: no whole histories, secrets or unnecessary private material. A missing interface is not permission to use browser automation or install tooling.

## 3. Choose the smallest useful judgment set

- **Choice** compares next activities, with only the supplied candidate IDs plus `NONE_FITS` and `NEED_EVIDENCE` (host-defined choices).
- A narrow **yes/no judgment** checks absolute fit or evidence sufficiency when relative preference could mislead. One per independently useful condition.
- **Score** only for a genuinely graded criterion with an explicit rubric.

Batch independent questions over the same state. The evaluator selects or verifies; the host supplies arguments and plans execution. Keep raw answers, full distributions and the actual model binding. No fixed number of calls.

## 4. Validate before dispatch

Check the response against the evaluator schema, allowed IDs, a valid distribution, the model and state freshness. Recheck handler, prerequisites, authority and scope. A top-ranked choice alone is not acceptance; without a validated decision policy the result stays advisory. Read probabilities under the evaluator's current semantics: a yes/no judgment's probability is not a separate confidence score. A diffuse choice may mean several activities are acceptable: choose among equally suitable authorized activities by observed fit and an existing deterministic policy, or gather evidence. No universal confidence cutoff, averaged-away blocking signal or favorable reroll. Evidence of a requirement or design change may justify returning to its owning phase; a generic skill trigger cannot.

| Outcome | Host disposition |
| --- | --- |
| Activity selected and validated | Dispatch only that bounded activity; keep the workflow and gates. |
| `NONE_FITS` | Recheck candidate coverage and scope; add candidates only with observed support and authority. Never substitute a generic process workflow in a Spec Kit repository. |
| `NEED_EVIDENCE` | Name the missing fact; fetch it or ask a targeted question; pause only the dependent decision. |
| Evaluator unavailable or inconclusive | Disclose it; apply a documented owner-approved fallback policy if one settles the choice, else leave it pending and continue independent work. Never claim the evaluator ran without a validated response. |

Candidate examples, not a pipeline: a requirement gap maps to specify or clarify; a design gap to plan; decomposition to tasks; a reproducible unexplained failure to bounded debugging; ready approved tasks to implement. Analysis, convergence, verification and review need their own prerequisites. Without Spec Kit, map the same responsibilities to the fallback handlers.

Record the state binding, eligible and excluded IDs with reasons, the response, distribution and model when called (as the adapter observed them; an agent's own "the evaluator ran" is not evidence), the disposition and the next stop condition. Permission to read a private source is not permission to send it to an evaluator. The evaluator cannot consent, prove facts, accept code or waive gates.

Judge the practice by representative cases: unnecessary calls, missed useful opportunities, latency and cost, data sent. Call count alone is not a success metric.
