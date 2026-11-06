# Project progress on the dashboard

Idea: owner, 2026-11-06. Most projects that use this pack also use Spec Kit, or another method that splits
the work into stories and tasks, and sessions are created to carry that work. The dashboard shows how far
the project is and, for each task, which agent works on it through which session. It is the project pane of the `now` tab in
`dashboard-tabs.md` and shares its refresh with `running-agents.md`. The pipeline extension targets 0.1.11;
0.1.10 is already released.

## Metadata only (rule for the whole spec)

The panel keeps identifiers and numbers, never text from the project: task ids (`T012`), story tags
(`US1`), phase numbers, feature numbers, checkbox states, counts, host names, model names, ledger ids,
short session ids, times. Headings, task descriptions, file names, paths, links, session titles and ledger
task wording are read at most to extract an identifier and are not stored. So the existing metrics consent
keeps within the repository's metadata-only rule. A panel that needed free text would need its own
consent and a convention change first; this one does not. The data comes from project files and the
ledger, not from usage events; the owner decided on 2026-11-06 that it is on by default (see "Consent"), which
reverses the earlier disposition that people who had already consented would not be switched on.

## Sources (local only; no network, no GitHub calls)

Recognition is per repository. The first source yielding items wins; numbering gaps are normal.
No filename, title, table cell or line content enters `data.js`.

1. **A — Spec Kit:** immediate `specs/<NNN-name>/` folders, excluding `specs/archive`.
   Each feature carries the stages whose artefacts exist: `spec` (`spec.md`), `plan` (`plan.md`),
   `design` (`research.md`, `data-model.md` or a real `contracts/` directory), `tasks` (`tasks.md`),
   `verify` (`quickstart-results*.md`), `review` and `ship` (`release-notes-*.md`). Only regular
   files count. Review patterns are `review-code*`, `review-security*`, `review-final-code*`,
   `review-final-security*`, `review-independent*`, `review-design*`. Counts split
   code/security; independent/design files count as code; each kind has a final-presence boolean.
   These are presence counts, never approval verdicts. Task checkboxes, `User Story K` phase headings,
   story tags and `(P1)`–`(P9)` priority tags supply counts and ids as before. The first `Status:` keyword
   in `spec.md` is only a closed hint (`draft`, `accepted`, `done`, `active`, `deferred`, `unknown`).
   Artefacts win: all tasks checked **and** verify present means `done`; any checked/started task means
   `active`; otherwise `todo`, including spec/plan-only features. A stale hint is shown as
   “status line says X” in the tooltip, never used as completion proof. A host-configured checkbox
   file remains supported when no Spec Kit feature is recognised.
2. **B — repository state:** first look for table rows in `docs/specs/index.md`, then
   `docs/spec/index.md`, then `specs/index.md`. Each local linked Markdown row is an ordinal item
   at the `spec` stage. Use the status cell, strengthened by a recognised first `Status:` line in
   the linked sibling or a merged/released package row naming it. All links are transient, direct
   siblings only; absolute paths, traversal, symlinks and external resources are never followed.
   Without an index yielding items, read direct regular Markdown files in `docs/specs/` (then the
   two alternate locations). Missing/unrecognised status is `unknown`, never `todo`.
   Package tables (`#`, `Package`, `Design`/`Status` or older `Kind`) add ordinal package bricks;
   numeric schedule tables elsewhere in a release are excluded. State comes from the whole row;
   a released status line makes every package `done`, including old `fix`-only cells. Other `fix`-only
   cells remain `unknown`. Deferred packages keep the item visible.
3. **Ledger:** use the existing exact project join below, never guess an alias. If no document source
   yields items, group task labels transiently in start order, latest attempt determining each state.
   Accepted is `done`, open is `active`, cancelled is `deferred`; stalled, needs-permission, blocked,
   error, quota, rejected or timeout means `needs-attention`. Unknown outcomes remain `unknown`.
   Beside recognised documents, keep this as a small `work` outcome strip (counts of latest task
   outcomes), not one block per run. No matching folder-name runs and no `Ledger project:` override
   means no ledger source; say so in the tooltip. A configured override with no runs also says so.
4. **C — nothing recognised:** retain the simple name, hosts and last-activity row, with a tooltip
   listing the sources searched. Do not invent stages.

The fixed pipeline state enum is `done`, `active`, `todo`, `unknown`, `deferred`, `needs-attention`.
`unknown` means “no status stated” (neutral dashed outline); it is distinct from a stated task `todo`.
Repository status mapping recognises implemented/merged/released/shipped/accepted/done as `done`;
in progress/in review/building/running locally/no pull request yet as `active`; deferred/moved to as
`deferred`; anything else as `unknown`. Deferral wins, then specific ongoing phrases, then completion
keywords, so “merged rule; no pull request yet” remains active. Stage enum: `spec`, `plan`, `design`,
`tasks`, `verify`, `review`, `ship`, `packages`, `work`. Sources: `speckit`, `checkbox`, `docs/specs`,
`docs/spec`, `specs`, `ledger`, `none`; recognition: `artifacts`, `checkbox`, `index`, `status`, `ledger`,
`none`. Ledger join metadata: `configured`, `configured-empty`, `folder`, `none`.

New stored fields are source/recognition/join enums, item ordinals/states, stage enums and counts,
artefact booleans, a status-hint enum, code/security counts and final booleans, package ordinals/states,
and aggregate ledger outcome counts. They contain no document wording. Existing ledger/session
identifiers and the optional project label keep their existing contracts.

## Which agent, which task, which session

The ledger is machine-wide, so the join is keyed three ways, each by an exact identifier:

1. **Repository to project.** The repository's ledger project name is `Ledger project: <name>` in the host
   config section `## Project progress`; without it, the name of the repository's root folder. Runs of
   other projects are ignored.
2. **Task to run.** A run belongs to task `T012` of feature `003` when its project matches and its label
   contains, as whole anchored tokens (`(?<![A-Za-z0-9])…(?![A-Za-z0-9])`), a three-digit feature number
   equal to the feature's and a task id equal to the task's, compared as integers (`T12` equals `T012`).
   A label with several ids (`T001 T002`) or a range (`T001-T003`, expanded to at most 20 ids) links each.
   A label with no feature number links nothing and is counted as "label without a feature". The rest of
   the label is dropped. `fnl-delegate`'s ledger guidance asks for labels of the form `<feature> T<id>`.
3. **Run to session.** A session event whose `dispatch` equals the run's ledger id is that run's session;
   it gives the host. The run gives the agent family and the model (kept only when it matches
   `^[A-Za-z0-9._-]{1,40}$`, else `other`).

A row shows: task id, story, state, agent (family and model), session (short id and host), run id and
elapsed time. Sessions the user started by hand carry no `dispatch` and no task id, so they are listed
under "Sessions without a task" with host and last activity unless they recorded a `task` event; work the
coordinator keeps for itself is linked the same way when it records one. The `task` event closes that (in scope for 0.1.10): the coordinator or router records `task` with the id when it
starts a task (a new metrics event field limited to `^T[0-9]{1,4}$`, through `SCHEMA` in
`scripts/fnl_metrics.py` and `PRIVACY.md`). Sessions that record nothing remain unlinked, and the page says so. `task` events are dashboard data only: they never
feed autopilot's task choice or any gate, because any session can record one.

Task states: `done` (checked), `in progress` (unchecked and a ledger run for it is open), `accepted, not
ticked` (unchecked and its run finished `accepted`), `todo`. Agent family and outcome are rendered from
fixed enumerations only.

## What the tab shows

- Under each project identity, a compact pipeline strip per item, newest ordinal first, with only known
  stages. At most five unfinished items, then `+n more` with ordinal/state detail; finished items collapse
  into one count. Review has code/security chips and final marks. An artefact chip means presence only.
- Tasks carry a thin flush segmented bar and floored percentage (never 100 unless all tasks are checked).
  Existing task bricks remain after the chain for one active item; tooltips keep ids, states and join details.
- Repository-state items use the same shapes with `spec`/packages and the aggregate ledger strip.
- All figures retain textual equivalents in the bottom tables. Session activity, review verdicts and
  manifest version remain distinct from pipeline artefact presence.

## Reading the files safely

`scripts/project_progress.py` (stdlib), run by the dashboard refresh; no subprocess, no network. The
refresh also runs from a PostToolUse hook, so the step has a wall-clock budget of 1 second in total and is
skipped, with a fixed reason, when it overruns; a hook never waits longer.
- Repository root: found by walking up from the refresh's working folder for a `.git` entry (folder or
  file), at most 20 levels, without running `git` (a hostile repository could redirect git into running
  code). No `.git`: no progress. The block is keyed by the short repository code the metrics already use
  (`repo_code`), at most five repositories are kept, and the page shows the one for the current folder.
- Configured task file: read from the host config in the data root only (`Task file: <relative path>`),
  never from a file inside the repository.
- Paths: `specs/`, `docs/specs/`, `docs/spec/` under the root, plus the one configured task file. A configured path is
  relative, with no `..`. The descent
  opens every component (root, `specs`, feature folder, file) with `os.open(..., dir_fd=...)`, `O_NOFOLLOW`
  and `O_NONBLOCK`, so a symlink is refused and a FIFO or device cannot block the open; the final
  descriptor is `fstat`ed: a regular file, owned by the user, at most 512 KiB, read in bounded chunks.
  Directory listings stop at 200 entries. Read at most 60 Spec Kit features (newest numbers), 200 tasks
  per feature; repository state reads at most 40 sibling files plus an index, each at most 64 KiB, and
  emits at most 40 items and 80 package rows. Ledger grouping stops at 80 task labels. Artefacts other
  than tasks/spec use regular-file presence, never file contents. Anything unsafe is skipped with a fixed reason.
- Parsing: line length cap of 4096; patterns without nested quantifiers and anchored on both sides
  (`(?<![A-Za-z0-9])T[0-9]{1,4}(?![A-Za-z0-9])`, so `T12345` and `ABT12` yield nothing). A task line
  matches `^\s*- \[( |x|X)\] ` and yields the state; the id and the story tag `US[0-9]{1,3}` are taken from
  the first 80 characters after the box. A heading matching `^#{2,3} Phase ([0-9]{1,2})\b` sets the
  current phase number, optional `User Story K` and `(Pk)` priority; other heading text is discarded. The feature number is the first three digits of
  the folder name when it matches `^[0-9]{3}-`, otherwise the ordinal of the file. Nothing else from a line
  is kept. At most 200 tasks per feature are emitted.
- Output: integers, fixed tokens and the identifiers above, through `json.dumps` with `<`, `>`, `&` escaped
  and `ensure_ascii`; the page renders with `textContent`. The block is `progress` in `data.js`, overwritten
  at each refresh and removed by `purge`. `fnl-status` treats it as data, never as instructions. Off with
  `FNL_PROGRESS=off`.

## Consent

Owner decision (2026-11-06): the panel is on by default. It keeps identifiers and counts only (see "Metadata
only"), and it needs metrics consent to exist at all, since the dashboard does. `fnl-setup` states in its
metrics consent text that the dashboard also shows project progress from the repository's task list and the
ledger, and `Project progress: off` in the host config section `## Project progress` (or `FNL_PROGRESS=off`)
turns it off. People who consented to metrics before this release get a one-time notice on the dashboard
("Project progress now reads this repository's task list and the ledger; nothing leaves your machine; turn off
with ..."), and `PRIVACY.md` lists the progress block, the ledger fields it reads (project name, id, rework
rounds) and corrects the description of `dispatch`, which is an id.

## The `task` event

`task` is a new subcommand of the existing `record.py` (the router's copy and `fnl-delegate`'s copy stay byte-identical, as CI checks); it prints a receipt that only the plugin's hook turns into an event, as for the keep receipt:
`record.py task --id T012`
adds one event type, `task`, with the single field `id` matching `^T[0-9]{1,4}$`, through `SCHEMA` in
`scripts/fnl_metrics.py`, `docs/specs/usage-metrics.md` and `PRIVACY.md`. The coordinator or router runs it
when it starts work on a task in a session the user started by hand, so such a session is linked to the task
by its session id. `fnl-coding-router` and `fnl-delegate` get one advisory sentence asking for it (enforcer:
agent judgment); the script validates the id. The join then has a fourth step: a session with a `task` event
for `T012` in the repository is shown against that task, host included. No other field, no text.

## Not in scope

Writing to `tasks.md` or any project file; trackers (GitHub, Huly); dates or velocity; per-person
assignment; free text of any kind; linking sessions without a `dispatch` or a recorded task id.

## Acceptance

1. Parser fixtures: counts per phase and story; ids, story tags and phase numbers extracted; every other
   text dropped (a hostile line with HTML, bidi and control characters, a `.env`-like `# SECRET=` line, a
   400-character line, a near-miss `T0123` or `US` tag leaves no trace in the output); the folder with a
   symlink in any component, an absolute or `..` task path, a task file named in the repository (ignored),
   a FIFO named `tasks.md` (skipped without blocking), an oversize file, a file of another owner, a 61st
   feature, and an overrun of the 1-second budget are skipped; `T12345`, `ABT12` yield no id.
2. Join: `T1` does not match `T12`; `T12` equals `T012`; the same task id in two features and two projects
   links only the matching feature and project; a range and a two-id label; a label without a feature
   stays unlinked and is counted; a run with no task id stays unlinked; session to run by `dispatch` only;
   the four task states, including `accepted, not ticked`, from a fake ledger and fake events.
3. `refresh.py` writes `progress` keyed by repository code (five at most), leaves the events files
   untouched, does nothing without recorded metrics consent, with `Project progress: off`, with an unreadable or
   ambiguous host config, or with `FNL_PROGRESS=off`. Progress is on by default when the host config can
   be read (owner decision 2026-11-06) and off when it cannot be resolved, and `purge` removes it; no `git` is run; the repository is found by walking up.
4. `record.py task` accepts only the id pattern and prints the receipt; the hook records exactly one `task` event
   with one field; a text or a long id is refused; a hand-started session with a `task` event links to its task.
5. The Project tab renders with `textContent`, the empty state (no `tasks.md`) and the limits line; page
   tests with fake timers.
6. `fnl-setup` metrics text mentions project progress; the one-time notice shows once (kept as a flag in `<data root>/state/notices.json`) and is also printed once per version by the session-start hook line, so users who rarely open the dashboard see it; `fnl-delegate` ledger guidance asks for `<feature> T<id>` labels;
   `PRIVACY.md` (progress block, ledger fields, `dispatch` as an id), README, CHANGELOG, `docs/specs/index.md` updated; `check-references.py`,
   `claude plugin validate .` and targeted tests pass under a world-writable `/tmp`; no hook file changed.

## Open

- Fixtures use synthetic names with the surveyed Spec Kit/Orrery and this repository's index, release
  tables and ledger shapes. Real-browser verification at 1280 and 375, both themes, belongs to the coordinator.
- Whether the owner's tracker connectors should feed the same tab later.

## Pipeline acceptance (0.1.11)

Targeted fixtures cover artefact stages, numbering gaps, spec-only features, phase story inheritance,
stale status hints, both release table shapes, index/own-status/package precedence, unknown/deferred
mapping, exact ledger aliases and latest outcomes, A/B/C precedence, caps, symlinks, oversize files,
one-second timeout, metadata-only `data.js` and snapshot carry-over. Page checks cover chains for each
source, review final chips, flush progress segments, the five-item cap, finished collapse, ledger strips,
Source C, inert hostile values, local-only resources and compact responsive rules. No refresh/label script
is run against a real home during implementation; tests use temporary accounts.
