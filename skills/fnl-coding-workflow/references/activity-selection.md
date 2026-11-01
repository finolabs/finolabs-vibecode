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

Batch independent questions over the same state. Keep raw answers, full distributions and the actual model binding. No fixed number of calls.

## 4. Validate before dispatch

Check the response against the evaluator schema, allowed IDs, a valid distribution, the model and state freshness. Recheck handler, prerequisites, authority and scope. A top-ranked choice alone is not acceptance; without a validated decision policy the result stays advisory. A diffuse choice may mean several activities are acceptable. No universal confidence cutoff and no favorable reroll.

| Outcome | Host disposition |
| --- | --- |
| Activity selected and validated | Dispatch only that bounded activity; keep the workflow and gates. |
| `NONE_FITS` | Recheck candidate coverage and scope; add candidates only with observed support and authority. Never substitute a generic process workflow in a Spec Kit repository. |
| `NEED_EVIDENCE` | Name the missing fact; fetch it or ask a targeted question; pause only the dependent decision. |
| Evaluator unavailable or inconclusive | Disclose it; apply a documented owner-approved fallback policy if one settles the choice, else leave it pending and continue independent work. Never claim the evaluator ran without a validated response. |

Record the state binding, eligible and excluded IDs with reasons, the response, distribution and model when called, the disposition and the next stop condition. The evaluator cannot consent, prove facts, accept code or waive gates.
