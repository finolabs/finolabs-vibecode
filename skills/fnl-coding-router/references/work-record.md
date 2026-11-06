# Work record

Use this template under the existing spec-or-plan trigger in [workflows/none.md](workflows/none.md),
not as another trigger. MIN depth creates no work record. In a Spec Kit repository, Spec Kit owns the
process and no work record is created. Enforcer: agent judgment (advisory); the coding router sets depth.

## Template

Copy the block into one Markdown file in the repository's spec folder: `docs/specs/`, else `docs/spec/`,
else flat `specs/`. Replace the placeholders as the work proceeds; do not treat sample Evidence as proof.
Enforcer: agent judgment (advisory).

```markdown
# <title>
Status: draft

## Goal and acceptance
- [ ] AC1 <a checkable criterion>

## Plan
<decisions and steps>

## Tasks
### US1
- [ ] T1 <one observable task>

## Evidence
<commands run, pull requests and review verdicts; pending until recorded>
```

## Field rules

The project progress reader enforces recognition and metadata extraction:

- The first `Status:` line is within the first 40 physical lines, outside fenced code. Its leading value
  is `draft`, `accepted`, `in progress`, `implemented`, `released` or `deferred`; commentary follows a
  semicolon. The reader maps an unknown value to `unknown` and never echoes it.
- At least two exact second-level headings from the template, plus a Status line, identify a record.
  Otherwise the file remains a plain spec document. Fenced headings are ignored.
- Goal and acceptance checkboxes supply the `spec` stage and its done/total counts. A non-empty Plan
  line supplies `plan`; Tasks checkboxes supply `tasks` counts. Optional `### US1` subheadings group
  tasks by numeric story tag. A non-empty Evidence line supplies `verify`, as presence only.
- Whole-line `<...>` placeholders do not supply Plan or Evidence content. Checkboxes whose text
  is only a placeholder, optionally after an AC or T numeric tag, do not count.
- Status sets item state: draft and accepted are `todo` (accepted has a mark), in progress is `active`,
  implemented and released are `done`, deferred is `deferred`. All Tasks checked with Status still
  in progress adds an amber “status not updated” mark; it does not change the item state.
- A record's Tasks section takes precedence over a separate configured checkbox file for that record.
  Titles, heading text, Evidence content and file names never enter dashboard data. Only counts,
  numeric tags, task ids and closed state/mark tokens leave the reader.

Keep criteria checkable, update Status from observed evidence and tick Tasks only when their checks
pass. This is advisory, enforced by agent judgment; the reader cannot establish implementation or
review quality from prose or checkbox state. No command or slash-command framework is required.

## Composition

The steps remain those of [workflows/none.md](workflows/none.md); the phase tools of
[mattpocock/skills](https://github.com/mattpocock/skills) contribute output when installed. Nothing is
copied from that pack. Tool selection and where output is recorded are advisory (agent judgment).

| Step | Phase tools when available | Output in the record |
| --- | --- | --- |
| 1. Clarify | `grilling` | Goal and acceptance |
| 2. Plan | `to-spec`; `to-tickets` when the repository also uses an issue tracker | Plan and Tasks; link issue references in the record |
| 3–4. Red, implement | `tdd`, `implement` | Tick Tasks as their checks pass |
| 5–6. Prove, review | `code-review`, `pr` | Evidence: checks, review verdicts and pull requests |

Where a tool is unavailable, perform the step as none.md describes. The router's verification and
review gates still apply; a filled Evidence section does not satisfy them by itself. Enforcer:
agent judgment (advisory), with the relevant gate's own checks.
