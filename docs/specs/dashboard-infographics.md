# Dashboard infographics (running and project panes)

Status: owner decisions settled on 2026-11-06 (see "Decisions settled"). Replaces the text-line rendering of the former Agents and Project tabs (now the Now tab) that `running-agents.md` and `project-progress.md` specified. The data rules of those specs (metadata only, consent, safe reading, `textContent` only) are unchanged except where this document says so.

## Two-tab owner decision (2026-11-06)

The owner supersedes the former five-tab structure with [`dashboard-tabs.md`](dashboard-tabs.md):
`overview` and `now` buttons sit immediately after the terminal dots in the title bar, with a
2 px teal active underline and no separate tab row. `now` stacks `running now` over
`projects, last 24 h`, preserving the graphics described below. Its badge sums open dispatches
and named active projects. Move the path title to the prompt's rich tooltip; keep the theme
switch at the right and the bar on one line at 375 px with smaller tab padding.

Overview keeps its panes and first-pass KPI, adds a compact review gate beside router coverage
(floored first-pass approve rate, thin 1/2/3+ round distribution, last 12 PR dot chains in its rich
tooltip, teal approve and amber rework, no repository labels or hashes). Delegation, kept/handed-off
counts, Judge receipts and full Reviews become tables only in Overview's bottom disclosure.
Legacy fragments redirect through literal maps as specified in the tab spec. Historical references
to Agents and Project tabs below describe the unchanged panes now stacked inside `now`.

## Why

The owner reviewed the shipped tabs: both are dense text and a seven-column table, not a data visualisation. `fnl-status` exists to follow the present state so the coordinator can steer, not to manage projects. Each tab must answer one question at a glance, show it as a picture, and keep rarely needed explanations behind a small info button in the pane header.

## Design language (owner lego decision, 2026-11-06)

The approved visual reference is [`assets/dashboard-lego-prototype.html`](assets/dashboard-lego-prototype.html). Port its geometry and spacing into the real page using existing page tokens, not the prototype's copied tokens or fake data. The terminal frame, monospace type, pane titles and tab badges stay. Small bricks with two studs snap together into task runs; plain rounded bars form dispatch tracks. No KPI tiles or text-led project list. Use `--h2` for done bricks, `--p` for agent bricks, `--p` for elapsed within budget, `--warn` for unchecked completion, `--crit` for time beyond budget or quota at or below 10%, and `--line`/`--faint` for hollow marks and captions.

## Defects found on the real page (fixed in this change)

- Agents and Project show five or more lines of explanatory text above any data.
- Reviews: the repository label is the raw hash code (`repo-a5a9786d #116`), it wraps, and a long dot chain (14 rounds) runs through the label of the next column. Cap a chain at 8 dots followed by `+N`, keep the label on one line, and show the project label of the repository.
- Opening a link that only changes the fragment (`dashboard.html#overview`) in an already open tab does not switch the tab; add a `hashchange` listener that selects the tab through the same literal-name map.

## Rules for every tab

- One question per pane. Agents uses plain budget lanes and quota bricks; Project uses visible story brick runs.
- At most 6 lines of body text above the fold at 1280 by 800; explanations of limits live in a 14 px `ⓘ` info button in the pane header aside, not in disclosures or body text.
- Colour carries state, never decoration: the page's single teal ramp for progress and amount, `--warn` and `--crit` only for state, never reused for series. Every colour-coded mark also has a shape, label or tooltip (no colour-only meaning).
- Every figure has the text equivalent in the existing "show the data as tables" disclosure; the seven-column task table moves there.
- Motion is CSS only: task bricks snap from translateY(-6px) to 0 in 280 ms, staggered 10 ms per brick up to 500 ms, once on first tab view or changed data. Agent bricks breathe from opacity 1 to 0.5 over 2 s; lanes grow from the left in 0.7 s. All motion is off under `prefers-reduced-motion: reduce`; nothing animates in a hidden tab. At 375 px, task runs wrap within their available width and lane labels sit above their tracks, without horizontal page scroll.
- Rendering stays `textContent` and `setAttribute` only, no `innerHTML`, no inline script, no remote resource; hostile names are tested.

## Now tab, agents: who is working, is it healthy

One pane, `running now`, with no KPI tiles. Each open dispatch is a flat 8 px bar with 4 px rounded outer ends, urgency first (least time left to hard cap). The neutral track has no outline, studs or brick body: `--line` in dark, very pale neutral lavender-grey in light. It ends at `max(budget * 4 / 3, budget + 10)` minutes. A shared rounded clip contains exactly two adjacent, square-ended fill rects: `--p` up to budget, `--crit` beyond. Their shared edge is half-pixel aligned with crisp edges, with no seam or rounded inner ends. Half-budget and budget ticks sit above the fill: 1 px wide, 14 px tall, `--faint`, centred on the bar. Left: family/model and task label in two short ellipsised lines with full tooltips. Right: `used/budget m`. A budget is unknown unless it is a finite positive number of at most 1,000,000 minutes. No process found gets the existing small outlined brick with a rich `no process` tooltip and accessible label `no process found`. Empty state: three ghost bricks and the muted line `No agents running`.

Below: `slots (5)` and five small bricks, one lit per open dispatch (use a supplied parallel limit if present). Each cached agent-family quota gets a caption such as `claude quota` and ten bricks. Lit count is remaining fraction rounded to tens of percent, with a minimum of one lit brick for every positive verified fraction (including below 5%); lit bricks are teal, red at or below 10%. Zero quota has no lit bricks. An unverified reading uses dashed hollow bricks and `?`. Remaining percent is rounded with `Math.round` in its tooltip and accessible label. Slots have an accessible label giving the lit count and total. The header info tooltip gives short reading guidance; process counts, limits and mismatch flags stay in the bottom tables.

## Now tab, projects: named activity as lego runs

One block per named active project, newest activity first, at most 12; named-only selection and all activity data rules remain unchanged. Header: bold project name, host marks and faint `last 12 min ago` underneath, a 22 px tabular floored percentage at the right while unfinished (never 100). When every task is done, replace the large percentage with a small teal studded check brick with accessible label `done`; absent task lists do not imply completion. A project without a task list or unfinished work shows only this header.

Beside/below the header, each unfinished spec has a faint `spec 003` header and a rule. Each unfinished story follows priority order: a 30 px `US2` tag column, task bricks and `done/total` at the right. Each brick has a 15 x 8 px body with two studs; gaps are 2 px. Add 8 px of vertical space between story runs, 6 px at 375 px; align each story tag with the first wrapped line without sticky positioning. Done is teal, agent on it bright teal and breathing, done-not-accepted hatched amber, to do hollow. Task tooltips show the task id, story/spec, state chip, agent/model and session/host rows. Above 36 tasks, merge consecutive groups to at most 36 bricks: any agent wins, else any not-accepted, else all done, else to do. Merged tooltips give first/last ids and counts per state.

Finished stories and features are not drawn; tiny faint `+2 done` on a spec header accounts for hidden finished work. There are no project task disclosures. A single legend at the bottom of the pane shows brick swatches and `done · agent on it · done, not accepted · to do`. All old data tables remain only behind `show the data as tables` at the bottom.

Only named repositories appear: an explicit host-config label wins over a registered name. There is no short-code fallback. Empty state: `No named project active in the last 24 hours. Run fnl-status inside a repository to add it.`

## Data changes (all local, metadata only)

- **Active projects.** Each refresh rebuilds `progress.active` from the events already read, deduplicating session ids per repository and counting distinct sessions with at least one recorded event in the last 24 hours. Session activity exactly 24 hours old and future events are excluded; host names are joined from session-start receipts. Only named repositories are kept. Rows contain only `repo` (existing code), `label`, `hosts` (closed host-name set), `sessions` (integer), `last` (ISO time), and `percent` (integer or null). No new event fields or session identifiers are retained. Never carry active rows over: keep validated repository snapshots as before, reconstruct the closed activity schema from validated events each refresh and remove it on purge. Render text with `textContent` only.
- **Several projects.** `refresh.py` already keeps up to five repositories in the `progress` block; the page draws their unfinished detail inside named activity rows. Each refresh updates the repository it runs in and keeps the others as last written.
- **Project label and registration.** Running `fnl-status` inside a repository is the act that names it: step 1 invokes `python3 -I <refresh.py> run --open --register-here`. Only this explicit flag, recorded metrics consent and a current working directory inside a git work tree permit registration; hook-started refreshes never register. Find the repository root with the existing no-git-command reader. Store its existing 8-hex repository code and root folder basename locally in `<data root>/state/projects.json`, a closed object of at most 50 entries, in a private folder, atomically with mode 0600 and flock. Replace characters outside `[A-Za-z0-9 ._-]` with `-`, trim, truncate to 40 characters; skip empty names. An existing code can be updated at the cap; new entries beyond 50 are skipped. The existing `label --set` host `## Project labels` value always wins. Without either name, a repository is not a project of this plugin and is not shown. Purge or deleting this file removes registered names; host labels remain independently configured. `PRIVACY.md` states the kept folder name and this explicit naming act plainly.
- **Story priority.** The reader also reads the story headings of the `spec.md` beside each `tasks.md` and keeps only the tag `P1` to `P9` of a heading of the form `User Story N (Pk)`; the heading text is dropped. A story with no tag sorts last. This extends the metadata kept in `project-progress.md` by one value (a priority number) and `PRIVACY.md` says so.
- **Reading safety** is as in `project-progress.md` "Reading the files safely"; `spec.md` follows the same rules and counts toward the same file and byte limits.

## Not in scope

Editing anything from the page, dependencies between tasks, estimates. The two-tab owner decision above governs the review gate and bottom tables.

## Acceptance

1. A rich fixture (`tests/fixtures/status-sample.json`) holds four open dispatches including one past its check time and one without a process, quota for three families, three named active projects (unfinished with a 45-task story and a separate four-state story, no tasks, and done), two unnamed repositories, one finished story and one finished feature, and a hostile name in each free field.
2. Page tests also cover both badges, active rows with and without task lists, host tooltips, recency, empty state, and completion values 408/410, 56/57, 1/3, 2/3, 0/5, 5/5. Reader/refresh tests cover deduplication, the 24-hour boundary, ordering, the 12-row cap, labels, closed schema, carry-over validation and purge. Track scale tests cover both branches of the hard-cap formula. Page tests (fake DOM): the lane order, the tick position, the two flush lane colours, the empty states, the project order by latest activity, hidden finished detail, the tooltip content, the quota brick lit counts, slots, merged brick states/counts, the info tooltip content; no `innerHTML` anywhere in the file; the hostile names stay inert.
3. Reader tests: the `P1` to `P9` tag only, a heading with markup or control characters yields no text, an `archive` folder is skipped, a label with a disallowed character is refused, a missing name hides the repository, a project with 100 percent is flagged done.
4. Motion: a test asserts the reduced-motion media query disables every animation and no animation name is applied to an element in a hidden tab.
5. Visual check (owner rule, not skippable): the coordinator serves the page from a localhost server with the rich fixture, screenshots the Overview and Now tabs at 1280 wide and at 390 wide, and attaches them to the pull request.
6. `PRIVACY.md` (priority tag, labels), README row, CHANGELOG, `docs/specs/index.md`, `fnl-setup` and `fnl-status` text updated; `check-references.py`, `claude plugin validate .` and targeted tests pass under a world-writable `/tmp`; no hook declaration and no `CLAUDE.md` change.

## Decisions settled (owner, 2026-11-06)

- The owner delegates the visual design to the coordinator; reviews are the repository's gate, not a design approval.
- Complete and archived work is not shown; the tab follows the present state, not project management.
- The redesign ships as a hotfix in the 0.1.10 line.
- Owner review supersedes strip/cards and short-code fallback: only explicitly registered or labelled repositories appear, as visible lego story runs following the approved prototype. Unnamed repositories are excluded from Project tables too; all table types remain reachable for named repositories. Priority tags and archived-folder exclusion remain unchanged.

## Lego Project acceptance (owner review, 2026-11-06)

Registration tests cover consent, hooks, sanitisation, closed schema, 50-entry cap, label precedence, purge and 0600. Reader tests count sessions over the rolling 24-hour window, including across midnight. The fixture has three named active projects (unfinished with a 45-task story and a separate four-state story, no task list, and done), plus two unnamed repositories excluded from the page, retaining hostile free-field values. Page tests cover one row per named project, badge count, SVG bricks and their states/tooltips, bounded merging, hidden finished stories, one bottom legend, header-only absent/done task lists, and the named-project empty state.

## Info buttons and compact footer (owner polish, 2026-11-06)

- Use one reusable helper for a real `button` with `type="button"`, an aria label summarising the tooltip facts (`About this data` for legacy strings), and `tabindex="0"`, drawing a 14 px circled `ⓘ`. Agents and Project header asides use it for the former limits text, at most five short items. Remove `details.limits` and its CSS. Other explanatory pane asides (including Overview, Delegation and Reviews) stay unchanged.
- Reuse `#tip`; accept legacy strings or structured specs held in a `WeakMap` keyed by the element, never content attributes. Render with `createElement` and `textContent` only. Structured specs support `{title, sub, rows: [[label, value]], items: [text], chips: [{label, state}], bar: {value, max, marks}}`. Use a bold 12 px title, optional muted subtitle, divider, label/value grid (muted labels, right-aligned tabular values), short items with 4 px teal bullets, state-dot pills, and an optional 4 px mini bar. Maximum width 260 px, padding 10 px, radius 8 px, `--raised` surface, 1 px `--line` border; 120 ms CSS fade disabled under reduced motion. Limit height to 60vh and scroll internally. Task/merged bricks, lanes, quota, slots, host marks and no-process markers use structured specs; Project and Agents info buttons use title `How to read this` with at most five short items. Aria labels preserve the same facts as one plain sentence. Open on hover and focus; tap/click toggles a pinned tooltip. Escape and outside tap close it. Provide `role="tooltip"` and the button's tooltip relationship; keyboard users can focus the button and dismiss it.
- Replace footer body text with one compact line: a freshness dot, `updated 3 min ago` (relative to `D.generated`, advancing with the existing clock), and the same info button. Teal means data is at most 10 minutes old with no previously active host quiet beyond 15 minutes. Amber means data is older than 10 minutes through 6 hours, or a host with recorded events is quiet beyond 15 minutes. Red is reserved for data older than 6 hours; missing generation time is amber. Hosts without recorded events do not make the dot amber. Preserve former source names/notes, session counts, generated/build times, per-host last events and trust warnings, ledger and quota ages, and visible-page stale notice as lines in its tooltip. Missing generation time reads `updated time unknown`; future generation times clamp to zero age.
- Keep `show the data as tables` after the status line as the last element for the selected tab. Refreshes preserve selected tab, scroll and open tables; refresh the footer tooltip even when chart data has not changed.
- Page tests cover info-button semantics, per-tab text, hover/focus/tap, Escape/outside dismissal, absence of limits disclosures, all footer dot states and relative time, finished check bricks, stud-free lanes and unknown huge/non-finite budgets, quota boundaries, accessible values, merged-tooltip state rows and narrow story spacing/alignment. The coordinator checks the real browser at 375 px.

## Light-theme polish (owner review, 2026-11-06)

Light `--warn` is golden `#d19a00` for fills/hatch; `--warn-text: #8a6400` is reserved for warning text on light surfaces. `--crit` remains `#cf222e`. Accepted bricks hatch `--warn` on transparent ground. Small task, quota, slot and check brick geometry stays unchanged. Dark theme tokens stay unchanged. Browser verification uses the theme toggle on both Agents and Project; coordinator also checks the delivered page in a real browser.
