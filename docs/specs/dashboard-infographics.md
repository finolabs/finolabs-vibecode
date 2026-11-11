# Dashboard infographics (running and project panes)

Status: implemented; owner decisions settled on 2026-11-06 (see "Decisions settled"). Replaces the text-line rendering of the former Agents and Project tabs (now the Now tab) that `running-agents.md` and `project-progress.md` specified. The data rules of those specs (metadata only, consent, safe reading, `textContent` only) are unchanged except where this document says so.

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

## Project pipeline decision (owner, 2026-11-06; 0.2.0)

This section supersedes the historical story-only project layout and 0.1.10 release target below.
The project pane recognises Spec Kit, repository indexes/status lines/packages, then exact-project
ledger runs, in the order and caps defined in [Project progress](project-progress.md). Only when none
yields items does it keep the simple identity row; its tooltip lists what was searched.

Beside the identity on desktop (below it on narrow screens), each item is a compact SVG chevron chain:
`spec ▸ plan ▸ design ▸ tasks ▸ verify ▸ review ▸ ship`, omitting stages without evidence. Repository items
show only known stages, with small package bricks where present. Review holds two tiny code/security chips and a final-presence mark;
file presence never implies an approved review. Tooltips show source, ordinal, state and counts, never
file text. A stale Spec Kit status keyword remains a tooltip hint; artefacts determine the item state.

Use existing tokens: solid teal (`--good`) for done, striped active, outlined todo, neutral dashed unknown
(“no status stated”), muted deferred, amber needs-attention. Tasks contain a thin segmented bar with
adjacent segments in a shared rounded clip, no gaps, and floored completion (100 only when all checked).
For one active item keep the existing story lanes and small task bricks below its chain, merging bounded
groups. Untagged tasks use a 14 px dashed tag-outline SVG with a rich “no story tag” tooltip and done/total
counts; story ids retain their text. Clip each brick to its own SVG viewport so hatch paint cannot escape
into the label column. Lego studs belong only on small task/package blocks. A ledger work strip shows
latest grouped task outcomes as done/amber/active/deferred/unknown counts; it never renders one block per run.

Newest ordinals first, at most five unfinished items, then `+n more` with a rich ordinal/state tooltip.
Finished items collapse into one count, with full tables retained. One-item rows target about 56 px,
growing with items and wrapping compactly at 375 px. Reuse the current tooltip component, tokens and
page typography in dark/light themes; no new colour family, remote resource, inline script or markup
injection. The coordinator checks both themes at 1280 and 375 with real-shaped synthetic data.

## Capacity detail (owner feedback, 2026-11-06)

Keep ledger lanes unchanged. Beside slots, show fixed host marks and distinct session counts
from existing usage events in the last 15 minutes, excluding the exact boundary and future events,
capped at 99 per host. `running.live` contains only `window_minutes: 15`, `claude`, `codex`, and
`antigravity` counts. Join host family from session-start receipts, including older starts.
The rich tooltip explains that these are sessions with activity from usage events, not processes;
sessions idle longer disappear. When the process snapshot exists, explain that both sources exist.
No event field, hook, consent or process-snapshot rule changes.

`running.quota` is three groups, in claude/codex/agy order, each `{agent, pools: [...]}`.
Read at most four cache entries per family and retain at most eight pools across them, without
collapsing to the limiting pool. A pool contains only `name`, `remaining_fraction`, `resets`,
`measured`, `unverified`; copy only the group name and validated fraction/timestamps, never other
cache text. For generic names (codex/model pools), append the validated `5h`/`weekly` window
to `name` so the closed output schema can distinguish windows and select glyphs. Preserve duplicate
group names from different entries. Each pool has a compact ten-brick meter: week pools use a calendar-week glyph, five-hour pools a clock, other names at most eight
visible characters. Tooltips retain the full group name, remaining percent, reset and measured times.
Readings older than eight hours are hollow with `?`. Missing cache families have empty pools and
one dashed placeholder with “not read; quota probe off or no reading yet; turn on in fnl-setup”.
The disclosure has one row per pool including reset/measured/state metadata. Use existing tokens,
rich tooltips and SVG helpers; keep the capacity row around two lines at 1280 and cleanly wrapped
at 375 in both themes. The coordinator performs the real-browser checks.

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

One pane, `running now`, with no KPI tiles. Each open dispatch is a flat 8 px bar with 4 px rounded outer ends, urgency first (least time left to hard cap). The neutral track has no outline, studs or brick body: `--line` in dark, very pale neutral lavender-grey in light. It ends at `max(budget * 4 / 3, budget + 10)` minutes. A shared rounded clip contains exactly two adjacent, square-ended fill rects: `--p` up to budget, `--crit` beyond. Their shared edge is half-pixel aligned with crisp edges, with no seam or rounded inner ends. Half-budget and budget ticks sit above the fill: 1 px wide, 14 px tall, `--faint`, centred on the bar. Left: family/model and task label in two short ellipsised lines with full tooltips. Right: `used/budget m`. A budget is unknown unless it is a finite positive number of at most 1,000,000 minutes. No process found gets the existing small outlined brick with a rich `no process` tooltip and accessible label `no process found`. Empty state: three ghost bricks and the muted line `No open dispatches`.

Below: `slots (N)` and N small bricks against the canonical user-configured total (1 to 32), one lit per open dispatch; missing/invalid total defaults to 5 with source stated, unreadable state shows unknown. The slots tooltip shows each family's open count and optional cap; see [parallel instances](parallel-instances.md). Live usage-session counts sit beside slots, as described in Capacity detail above. Each agent-family quota group gets a caption such as `claude quota` and one ten-brick meter per pool; unread families get a dashed placeholder. Lit count is remaining fraction rounded to tens of percent, with a minimum of one lit brick for every positive verified fraction (including below 5%); lit bricks are teal, red at or below 10%. Zero quota has no lit bricks. An unverified reading uses dashed hollow bricks and `?`. Remaining percent is rounded with `Math.round` in its tooltip and accessible label. Slots have an accessible label giving the lit count and total. The header info tooltip gives short reading guidance; process counts, limits and mismatch flags stay in the bottom tables.

## Now tab, projects: named activity as lego runs

One block per named active project, newest activity first, at most 12; named-only selection and all activity data rules remain unchanged. Header: bold project name, host marks and faint `last 12 min ago` underneath, a 22 px tabular floored percentage at the right while unfinished (never 100). When every task is done, replace the large percentage with a small teal studded check brick with accessible label `done`; absent task lists do not imply completion. A project without a task list or unfinished work shows only this header.

Beside/below the header, each unfinished spec has a faint `spec 003` header and a rule. Each unfinished story follows priority order: a 30 px `US2` tag column, task bricks and `done/total` at the right. Each brick has a 15 x 8 px body with two studs; gaps are 2 px. Add 8 px of vertical space between story runs, 6 px at 375 px; align each story tag with the first wrapped line without sticky positioning. Done is teal, agent on it bright teal and breathing, done-not-accepted hatched amber, to do hollow. Task tooltips show the task id, story/spec, state chip, agent/model and session/host rows. Above 36 tasks, merge consecutive groups to at most 36 bricks: any agent wins, else any not-accepted, else all done, else to do. Merged tooltips give first/last ids and counts per state.

Finished stories and features are not drawn; tiny faint `+2 done` on a spec header accounts for hidden finished work. There are no project task disclosures. A single legend at the bottom of the pane shows brick swatches and `done · agent on it · done, not accepted · to do`. All old data tables remain only behind `show the data as tables` at the bottom.

Only named repositories appear: an explicit host-config label wins over a registered name. There is no short-code fallback. Empty state: `No named project active in the last 24 hours. Run fnl-status inside a repository to add it.`

## Data changes (all local, metadata only)

- **Active projects.** Each refresh rebuilds `progress.active` from the events already read, deduplicating session ids per repository and counting distinct sessions with at least one recorded event in the last 24 hours. Session activity exactly 24 hours old and future events are excluded; host names are joined from session-start receipts. Only named repositories are kept. Rows contain only `repo` (existing code), `label`, `hosts` (closed host-name set), `sessions` (integer), `last` (ISO time), and `percent` (integer or null). No new event fields or session identifiers are retained. Never carry active rows over: keep validated repository snapshots as before, reconstruct the closed activity schema from validated events each refresh and remove it on purge. Render text with `textContent` only.
- **Several projects.** `refresh.py` already keeps up to five repositories in the `progress` block; the page draws their unfinished detail inside named activity rows. Each refresh updates the repository it runs in and keeps the others as last written.
- **Project label and registration.** Running `fnl-status` inside a repository is the act that names it: step 1 invokes `python3 -I <refresh.py> run --open --register-here`. Only this explicit flag, recorded metrics consent and a current working directory inside a git work tree permit registration; hook-started refreshes never register. Find the repository root with the existing no-git-command reader. Store its existing 8-hex repository code and root folder basename locally in `<data root>/state/projects.json`, a closed object of at most 50 entries, in a private folder, atomically with mode 0600 and flock. Replace characters outside `[A-Za-z0-9 ._-]` with `-`, trim, truncate to 40 characters; skip empty names. An existing code can be updated at the cap; new entries beyond 50 are skipped. The `label --set` value always wins; since 0.2.5 it lives in the repository's own settings file (the `## Project labels` section of `host.md` is no longer read), so the dashboard shows it for the repository it runs in. Without either name, a repository is not a project of this plugin and is not shown. Purge or deleting this file removes registered names. `PRIVACY.md` states the kept folder name and this explicit naming act plainly.
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
