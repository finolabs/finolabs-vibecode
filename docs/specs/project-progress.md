# Project progress on the dashboard

Idea: owner, 2026-11-06. Most projects that use this pack also use Spec Kit, or another method that splits
the work into stories and tasks, and sessions are created to carry that work. The dashboard shows how far
the project is and, for each task, which agent works on it through which session. It is the "Project" tab of
`dashboard-tabs.md` and shares its refresh with `running-agents.md`. Design only; code follows those two.

## Metadata only (rule for the whole spec)

The panel keeps identifiers and numbers, never text from the project: task ids (`T012`), story tags
(`US1`), phase numbers, feature numbers, checkbox states, counts, host names, model names, ledger ids,
short session ids, times. Headings, task descriptions, file names, paths, links, session titles and ledger
task wording are read at most to extract an identifier and are not stored. So the existing metrics consent
covers it and `CLAUDE.md`'s "metadata only" holds. A panel that needed free text would need its own
consent and a convention change first; this one does not.

## Sources (local only; no network, no GitHub calls)

| Source | Gives |
| --- | --- |
| `specs/<NNN-name>/tasks.md` (Spec Kit) | per task: checkbox state, task id, story tag, phase number |
| A configured task file (other methods) | the same, from one Markdown checkbox list; set in the host config as `## Project progress` / `Task file: <relative path>` |
| Ledger | per delegated run: id, agent family, model, project, start, finish, outcome, rework rounds, and whether its task label contains a task id |
| Usage events (consented) | per session: id, host, first and last seen, the `dispatch` id when the session was started by the coordinator |

## Which agent, which task, which session

A task row is joined to work in three steps, each by an exact identifier:

1. **Task to run.** A ledger run belongs to task `T012` when its task label contains the token `T012` as a
   whole token (not `T0123`). The match is exact; the rest of the label is dropped.
2. **Run to session.** A session event whose `dispatch` equals the run's ledger id is that run's session
   (the coordinator exports the id to the run). The session gives the host.
3. **Run to agent.** The ledger run gives the agent family and model.

A row shows: task id, story, state, agent (family and model), session (short id and host), run id and
elapsed time. Sessions the user started by hand carry no `dispatch` and no task id, so they are listed
under "Sessions without a task" with host and last activity; work the coordinator keeps for itself is
likewise not linked. Phase 2 can close that: the coordinator or router records `task` with the id
when it starts a task (a new metrics event field limited to `^T[0-9]{1,4}$`, through `SCHEMA` and
`PRIVACY.md`). Until then the page says "linked through delegated runs only".

Task states: `done` (checked), `in progress` (unchecked and a ledger run for it is open), `accepted, not
ticked` (unchecked and its run finished `accepted`), `todo`.

## What the tab shows

- Per feature (`feature 003`): total `done / total`, and per phase and story the same with a bar.
- A table of tasks in progress and recently finished: the join above.
- Counts of sessions by state: running now (a process in the Agents tab, once shipped), active in the last
  24 hours, idle; delegated runs by outcome.
- Last review verdicts per kind and the manifest version, from existing records.
- States its limits plainly: derived from files and local records, not from a tracker; "done" means the box
  is ticked; linked through delegated runs only.

## Reading the files safely

`scripts/project_progress.py` (stdlib), run by the dashboard refresh; no command, no network.
- Paths: `specs/` under the repository root, plus the one configured task file. A configured path must be
  relative, with no `..`; its real path must be under the real repository root (`commonpath`); no path
  component (root, `specs`, feature folder, file) may be a symlink; the descent opens each component with
  `O_NOFOLLOW` and `fstat`s the descriptor (regular file, owned by the user, at most 512 KiB). At most 20
  files per refresh. Anything else is skipped with a fixed reason.
- Parsing: line length cap of 4096; patterns without nested quantifiers. A task line matches
  `^\s*- \[( |x|X)\] ` and yields the state; the id is `T[0-9]{1,4}` and the story `\[US[0-9]{1,3}\]` when
  present, anywhere in the first 80 characters after the box. A heading matching `^#{2,3} Phase ([0-9]{1,2})\b`
  sets the current phase number; every other heading is ignored. The feature number is the first three
  digits of the folder name when it matches `^[0-9]{3}-`, otherwise the ordinal of the file. Nothing else
  from a line is kept.
- Output: integers, fixed tokens and the identifiers above, through `json.dumps` with `<`, `>`, `&` escaped
  and `ensure_ascii`; the page renders with `textContent`. The block is `progress` in `data.js`,
  overwritten at each refresh and removed by `purge`. `fnl-status` treats it as data, never as
  instructions. Built only with recorded metrics consent; `FNL_PROGRESS=off` stops it.

## Not in scope

Writing to `tasks.md` or any project file; trackers (GitHub, Huly); dates or velocity; per-person
assignment; free text of any kind; linking sessions without a `dispatch` or a recorded task id.

## Acceptance

1. Parser fixtures: counts per phase and story; ids, story tags and phase numbers extracted; every other
   text dropped (a hostile line with HTML, bidi and control characters, a `.env`-like `# SECRET=` line, a
   400-character line, a near-miss `T0123` or `US` tag leaves no trace in the output); the folder with a
   symlink in any component, an absolute or `..` task path, an oversize file, a file of another owner and a
   21st file are skipped.
2. Join: `T1` does not match `T12`; a run with no task id stays unlinked; session to run by `dispatch` only;
   the four task states, including `accepted, not ticked`, from a fake ledger and fake events.
3. `refresh.py` writes `progress`, leaves the events files untouched, does nothing without recorded consent
   or with `FNL_PROGRESS=off`, and `purge` removes it.
4. The Project tab renders with `textContent`, the empty state (no `tasks.md`) and the limits line; page
   tests with fake timers.
5. `PRIVACY.md`, README, CHANGELOG, `docs/specs/index.md` updated; `check-references.py`,
   `claude plugin validate .` and targeted tests pass under a world-writable `/tmp`; no hook file changed.

## Open

- Real `tasks.md` shapes across Spec Kit versions: check against the repository's own specs and one
  external project before fixing the grammar.
- Whether phase 2 (`task` event) is worth its schema change after a few weeks of the delegated-only view.
- Whether the owner's tracker connectors should feed the same tab later.
