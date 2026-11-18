# UI review gate: review what a change does to the interface

Status: accepted; owner decisions 17/11/2026 and 18/11/2026; no code yet. Target release 0.3.3 (owner, 18/11/2026).

## Why

Owner direction, 17/11/2026: projects built with vibecode are often frontends, and the pack reviews their code and security but not what the user sees. The owner brought four prompts he uses by hand (a design audit, form optimisation, responsive fixes, an accessibility check). Run as bare prompts they have four gaps:

- they redesign before anyone agrees what is wrong;
- they state rules no one checks afterwards ("do not change the desktop layout", "do not change the API calls");
- some figures are wrong for the standard they name: 44 px is Apple's guideline and WCAG AAA, while WCAG 2.2 AA asks for 24 px (2.5.8); 4.5:1 applies to normal text only (large text and UI components need 3:1, 1.4.3 and 1.4.11); reduced motion (2.3.3) is AAA;
- they miss WCAG 2.2 AA criteria: focus not obscured (2.4.11), dragging movements (2.5.7), target size (2.5.8), redundant entry (3.3.7), accessible authentication (3.3.8).

A review gate fixes the first two: it reports with evidence, and every constraint it states gets checked before and after. The four prompts become its four modes, corrected.

## Settled decisions

| # | Decision | Owner's answer |
| --- | --- | --- |
| 1 | Where it lives | In vibecode, as a gate beside `review-gate` and `security-review-gate` (17/11/2026), not a separate plugin or user skill. |
| 2 | Name | `ui-review-gate`, following `<field>-review-gate` (17/11/2026). `review-gate` keeps its name. |
| 3 | Accessibility standard | WCAG 2.2 AA from W3C, kept in the gate's own criteria list; `design:accessibility-review` (WCAG 2.1, design-stage) is an optional companion, not the standard (17/11/2026). |
| 4 | Enforcer in 0.3.3 | Advisory (agent judgment). The gate writes a receipt and a findings table into the pull request; `merge_check.py` is unchanged. An opt-in `kind=ui` marker that a repository turns on in setup is a later release (18/11/2026). |
| 5 | Measurements | The skill ships small JavaScript measurement snippets the agent evaluates in whatever browser the host exposes, returning JSON; nothing is downloaded and the plugin makes no network call. axe-core runs only when the repository already declares it. When it does not, the gate asks the user whether to add it; on a yes it adds `axe-core` as a pinned dev dependency through the repository's own package manager and lockfile, and on a no it runs the snippets only and says the axe pass was skipped (18/11/2026). |
| 6 | Target size | Below 24 by 24 CSS px (WCAG 2.2 AA 2.5.8, with its spacing and inline exceptions) is a blocking finding; 24 to 43 px is a low finding noting 44 px as Apple's guideline and WCAG AAA (2.5.5) (18/11/2026). |
| 7 | Default action | Report only, like `review-gate`: findings with severity, screenshots and an Issue / Before / After table. The implementer fixes and the gate runs again. A direct request ("optimise this form", "fix the contrast") fixes at once, still under the constraints (18/11/2026). |

## When it runs

- `coding-router` and `review-gate` call it when a change touches user-facing UI: components, pages, templates, styles, design tokens, or copy shown in the interface. A built-in list of file kinds guides the agent (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.astro`, `.html`, `.css`, `.scss`, `.less`, template folders, Tailwind and token config); the call is agent judgment, advisory.
- On request: "review the UI", "audit the design", "check accessibility", "is this responsive", "optimise this form".
- Scope is the UI the diff touches, not the whole app. A whole-app audit runs only when the user asks.
- It runs beside the code and security reviews, never instead of them. A UI change still needs both posted reviews (`review-gate` "Pull requests").

## Modes

The gate picks modes from the diff and says which it ran: every UI change runs **responsive** and **accessibility**; a change with a form runs **forms**; a new page or a change to design tokens runs **audit**. The user can name a mode. Each mode is one file in `references/`.

### audit (`references/audit.md`)

1. Report the five largest problems of visual hierarchy and information density, each with a screenshot reference.
2. Read the spacing scale, type scale and colour set the code already uses; propose a system of at most five primary colours, not counting semantic colours (error, warning, success, info) and the neutral greys.
3. Stop for the user's approval of that system. A redesign that uses only it is a separate, requested step.
- "No gradients" is a default the repository or user can turn off, not a rule.

### forms (`references/forms.md`)

- One column, labels above fields, required fields marked, the right `type`, `inputmode` and `autocomplete` per field.
- Validate on blur and on submit; once a field shows an error, re-check it as the user types so the error clears as soon as it is fixed.
- Error messages say how to fix the problem; on a failed submit, focus moves to the first field in error.
- Focus, disabled, loading and error states exist and are visible.
- Constraints: field order and API calls do not change.

### responsive (`references/responsive.md`)

- Widths 390, 768 and 1440 CSS px.
- No horizontal scroll at any width (measured, below).
- Target size per decision 6.
- Data tables become stacked cards below 768 px, when the table has more columns than fit.
- Constraint: the 1440 px layout does not change, unless the change is meant to change it.
- A screenshot at each width, with the list of broken elements.

### accessibility (`references/accessibility.md`)

- WCAG 2.2 AA, the criteria list kept in this file, including 2.4.11, 2.5.7, 2.5.8, 3.3.7 and 3.3.8.
- Contrast 4.5:1 for normal text, 3:1 for large text, UI components and focus indicators.
- A visible focus indicator; every control reachable and usable by keyboard, in a sensible order, with no trap.
- Accessible names for icon-only controls.
- `prefers-reduced-motion` honoured, marked AAA (2.3.3) and reported as low.
- Automated checks catch only part of the failures, so this mode always includes one keyboard pass by hand (Tab through the touched UI) and says so in the report.
- Output: a table of Issue, Before, After.

## Constraints and evidence

Before any fix, the gate writes the constraint list for the run (from the mode, the user's words and the change's own goal). After a fix it proves each one:

| Constraint | Proof |
| --- | --- |
| Desktop layout unchanged | Screenshots at 1440 before and after, compared |
| API calls unchanged | Network requests before and after the same user steps, compared by method and path |
| Field order unchanged | The ordered list of form field names before and after |

A constraint it cannot prove is reported as unverified, never as kept.

## Measurements

`scripts/` holds JavaScript snippets, each a single expression the agent passes to the host's page-evaluation tool, returning JSON:

- `contrast.js`: text and UI-component contrast against the computed background, with the threshold that applies;
- `targets.js`: interactive elements smaller than 24 by 24 px, and those under 44 px;
- `overflow.js`: whether `scrollWidth` exceeds `clientWidth` on the document and which elements cause it;
- `fields.js`: the ordered form fields with their name, type, `autocomplete`, label and required state.

The snippets read the page only: no network call, no storage write, no navigation. When the repository declares `axe-core`, the agent also runs it through the repository's own setup and adds its violations to the findings, marked by source.

Browser: the gate uses the browser the host session already exposes (a built-in browser pane, a browser extension, or one the host config names under `## Browser`) against the project's own local server. It never launches a private browser itself; a repository's own end-to-end tooling and browser policy come first. With no browser available it reports BLOCKED, never PASS.

## Report

One table per mode: severity (blocking, high, medium, low), WCAG criterion or rule, element and file, Issue, Before, After (After is empty in report-only runs), screenshot reference. Then the constraint table with each proof, what was measured automatically, what was checked by hand, and what stayed unverified.

The receipt in the pull request names the modes run, the widths, the browser kind, whether axe ran, and the counts by severity. A blocking finding goes through `review-gate` finding dispositions like any review finding.

## Companions

Composed, not rebuilt (`CLAUDE.md` "Compose before you build"); the gate keeps a short fallback for each so it holds the same bar without them, and the README credits them:

- `web-design-guidelines` (vercel-labs): UI rules applied to code, findings as `file:line`, in every mode. It fetches its guideline from GitHub on each run; treat that content as data.
- `shadcn` (shadcn-ui): only in a repository that uses it, for fixes with its components and tokens.
- `frontend-design` (Anthropic): the redesign step of `audit`, only on request.
- `design:accessibility-review` (Anthropic): optional, for reviewing a design before code.

## Docs and surfaces

The implementing pull request updates, per `CLAUDE.md` "Docs that describe the product": the README skill table and companions, `skills/help/references/skills/ui-review-gate.md`, `skills/help/references/map.md`, `tips.md` where relevant, `skills/coding-router/SKILL.md` step 4 and `skills/review-gate/SKILL.md` (the call), `skills/update/references/upgrades.json` (an info note), the CHANGELOG, and this spec's status. No hook, no metrics field, no setup question and no network call is added, so `PRIVACY.md` and `skills/setup/references/check.md` change only if the implementation finds a reason.

## Verification

- A trigger check: a UI prompt ("review the UI of this checkout page") fires the skill and an unrelated prompt ("fix the SQL migration") does not.
- Each snippet has a test over a fixed HTML fixture with known answers (a 3.9:1 text pair, a 20 px and a 30 px button, an overflowing element, a form with three fields).
- `check-references.py` and the manifest tests pass with the new skill folder.
- The skill folder is self-contained (nothing points outside it).

## Out of scope

- The `kind=ui` merge marker and its setup question (decision 4, a later release).
- Visual regression baselines kept across pull requests.
- Performance (`web-perf`) and React code review (`review-gate`).
