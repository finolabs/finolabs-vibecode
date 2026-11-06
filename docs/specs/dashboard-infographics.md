# Dashboard infographics (Agents and Project tabs)

Status: owner decisions settled on 2026-11-06 (see "Decisions settled"). Replaces the text-line rendering of the Agents and Project tabs that `running-agents.md` and `project-progress.md` specified. The data rules of those specs (metadata only, consent, safe reading, `textContent` only) are unchanged except where this document says so.

## Why

The owner reviewed the shipped tabs: both are dense text and a seven-column table, not a data visualisation. `fnl-status` exists to follow the present state so the coordinator can steer, not to manage projects. Each tab must answer one question at a glance, show it as a picture, and keep text for hover and for a collapsed "limits" note.

## Design language (observed on the real page, 2026-11-06)

New marks must look like the existing ones, not like a generic card UI: a terminal window frame with monospace type throughout; panes with a small teal bar before a lowercase title and a muted aside at the right; big monospace KPI figures with a dashed baseline sparkline; horizontal bars with the value printed at the bar end; lollipop rows on a 0 to 60 percent scale with a vertical threshold rule (Delegation); a calendar heat grid (Overview); dot chains per pull request (Reviews). Radius stays small (4 px marks, 8 px panes), no filled "cards on cards", no sans-serif face, numbers right-aligned in tabular figures, the tab badges (`Agents 0`) stay and show the live count.

## Defects found on the real page (fixed in this change)

- Agents and Project show five or more lines of explanatory text above any data.
- Reviews: the repository label is the raw hash code (`repo-a5a9786d #116`), it wraps, and a long dot chain (14 rounds) runs through the label of the next column. Cap a chain at 8 dots followed by `+N`, keep the label on one line, and show the project label of the repository.
- Opening a link that only changes the fragment (`dashboard.html#overview`) in an already open tab does not switch the tab; add a `hashchange` listener that selects the tab through the same literal-name map.

## Rules for every tab

- One question per tab, answered by one hero figure plus at most two supporting visuals.
- At most 6 lines of body text above the fold at 1280 by 800; explanations of limits live in one collapsed "limits" disclosure, not in the body.
- Colour carries state, never decoration: the page's single teal ramp for progress and amount, `--warn` and `--crit` only for state, never reused for series. Every colour-coded mark also has a shape, label or tooltip (no colour-only meaning).
- Every figure has the text equivalent in the existing "show the data as tables" disclosure; the seven-column task table moves there.
- Motion is CSS only, subtle and optional: bars grow from the left once on first view of a tab and on data change (0.7 s ease-out); a running lane has a slow light sweep at its leading edge (2.4 s); active task cells breathe (opacity 1 to 0.45, 2 s); numbers change without tweening if the value is unchanged. Under `prefers-reduced-motion: reduce` all of it is off. No motion runs in a hidden tab, and none loops on a finished item.
- Rendering stays `textContent` and `setAttribute` only, no `innerHTML`, no inline script, no remote resource; hostile names are tested.

## Agents tab: who is working, is it healthy

1. KPI row of three stat tiles: running now, past the check time, processes not started by the coordinator. Zero shows as `0`, in the neutral ink.
2. Lanes, one per open dispatch, sorted by urgency (closest to its hard cap first): label `agent model · task label`, a track showing elapsed against budget, a tick at half budget (the check deadline), amber past the tick, red past the budget, `elapsed/budget` text on the right. The track ends at the hard cap, `max(budget * 4 / 3, budget + 10)` minutes (a third over budget, at least 10 minutes over). A lane with no process found shows a small outlined marker, not a sentence.
3. Quota meters, one per agent family from the local quota cache (the probe already stores remaining fractions): a thin meter and the percent; below 10 percent uses `--crit`; unverified (older than 8 hours) shows hollow. If the cache is absent the block is omitted.
4. The process snapshot is shown only as small counts on the KPI tiles and as a dot per root process inside the lane list when the snapshot is on; machine-wide caveats go in the "limits" disclosure.
5. Empty state: one calm line ("No agents running") and three ghost lanes.

## Project tab: what is in flight, in priority order

The Project badge counts repositories in the active projects strip; the Agents badge counts open dispatches. Task completion percentages on projects, spec lines and story rows use `floor(done / total * 100)`, capped at 99 while any task remains unfinished; only all-done work reads 100 percent.

Above the cards, an active projects strip lists repositories with at least one recorded session in the last 24 hours, newest first, at most 12. Each row shows the user-set label or `repo <first four characters>`, one distinct host shape per host with its name in the tooltip, `n sessions` today, relative last activity, and a thin floored-percentage bar when a progress card exists. Repositories without a task list have no bar and say `no task list` only in the tooltip. With no recent sessions, show one muted line. Cards still require a task list and unfinished work; finished projects may appear in the activity strip but have no completion bar.

1. One card per project that still has unfinished work, at most five, ordered by the highest-priority unfinished story, then most recent activity. A project with all tasks done is not shown; the tab shows a single muted count ("2 projects done, hidden").
2. Card header: project label, the percentage of tasks done as a hero figure, and a segmented bar of done, an agent is on it, and to do (2 px gaps).
3. Under the header, the unfinished stories of each feature (spec) in order: label `US2 · P1`, a row of task cells (one 14 px square per task, in phase order: done, an agent is on it, done but not accepted, to do), and `done/total`. A completed story is not drawn; a muted "n stories done" chip stands for them. A feature folder with every task done is not drawn at all.
4. A cell shows its task id, state, agent family and model, session and host only in its tooltip and in the data tables. Sessions without a task become one chip with a count.
5. "Archived": a feature folder under `specs/archive` is not read or counted; a feature with every task done is hidden as above. No other state is called archived.
6. Empty state: one line naming what to do ("No tasks.md found for this repository"), no ghost.

## Data changes (all local, metadata only)

- **Active projects.** Each refresh rebuilds `progress.active` from the events already read, deduplicating session ids per repository and counting distinct sessions with a recorded event today (machine-local date). Session activity exactly 24 hours old and future events are excluded; host names are joined from session-start receipts. Rows contain only `repo` (existing code), `label`, `hosts` (closed host-name set), `sessions` (integer), `last` (ISO time), and `percent` (integer or null). No new event fields or session identifiers are retained. Never carry active rows over: keep validated repository snapshots as before, reconstruct the closed strip schema from validated events each refresh and remove it on purge. Render text with `textContent` only.
- **Several projects.** `refresh.py` already keeps up to five repositories in the `progress` block; the page now draws all with unfinished work instead of only the current one. Each refresh updates the repository it runs in and keeps the others as last written.
- **Project label.** A repository code is a hash and is not shown as a name. `fnl-setup` offers an optional label per repository, written by a script run from inside that repository (`project_progress.py label --set <label>`), stored in the canonical host config under `## Project labels`. A label is 1 to 40 characters of letters, digits, space, dot, dash and underscore, chosen by the user, local, never sent anywhere; without a label the tab shows `repo <first four characters of the code>`. The ledger's project name is not reused.
- **Story priority.** The reader also reads the story headings of the `spec.md` beside each `tasks.md` and keeps only the tag `P1` to `P9` of a heading of the form `User Story N (Pk)`; the heading text is dropped. A story with no tag sorts last. This extends the metadata kept in `project-progress.md` by one value (a priority number) and `PRIVACY.md` says so.
- **Reading safety** is as in `project-progress.md` "Reading the files safely"; `spec.md` follows the same rules and counts toward the same file and byte limits.

## Not in scope

The Delegation tab (its lollipop and threshold view already fits the page) and any Reviews redesign beyond the defects above; editing anything from the page, dependencies between tasks, estimates.

## Acceptance

1. A rich fixture (`tests/fixtures/status-sample.json`) holds three open dispatches including one past its check time and one without a process, quota for three families, two projects with several stories, one finished story and one finished feature, and a hostile name in each free field.
2. Page tests also cover both badges, active rows with and without task lists, host tooltips, recency, empty state, and completion values 408/410, 56/57, 1/3, 2/3, 0/5, 5/5. Reader/refresh tests cover deduplication, the 24-hour boundary, ordering, the 12-row cap, labels, closed schema, carry-over validation and purge. Track scale tests cover both branches of the hard-cap formula. Page tests (fake DOM): the lane order, the tick position, the three lane colours, the empty states, the project order by priority, the hidden finished items and the "done, hidden" chip, the tooltip content, the quota meter states, the disclosure content; no `innerHTML` anywhere in the file; the hostile names stay inert.
3. Reader tests: the `P1` to `P9` tag only, a heading with markup or control characters yields no text, an `archive` folder is skipped, a label with a disallowed character is refused, a missing label falls back, a project with 100 percent is flagged done.
4. Motion: a test asserts the reduced-motion media query disables every animation and no animation name is applied to an element in a hidden tab.
5. Visual check (owner rule, not skippable): the coordinator serves the page from a localhost server with the rich fixture, screenshots the Agents and Project tabs at 1280 wide and at 390 wide, and attaches them to the pull request.
6. `PRIVACY.md` (priority tag, labels), README row, CHANGELOG, `docs/specs/index.md`, `fnl-setup` and `fnl-status` text updated; `check-references.py`, `claude plugin validate .` and targeted tests pass under a world-writable `/tmp`; no hook declaration and no `CLAUDE.md` change.

## Decisions settled (owner, 2026-11-06)

- The owner delegates the visual design to the coordinator; reviews are the repository's gate, not a design approval.
- Complete and archived work is not shown; the tab follows the present state, not project management.
- The redesign ships as a hotfix in the 0.1.10 line.
- Defaults for project label (user-set, fallback short code), priority (tag only) and archived (done or under `specs/archive`) stand unless the owner objects.
