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
keeps within the repository's metadata-only rule. A panel that needed free text would need its own
consent and a convention change first; this one does not. The data comes from project files and the
ledger, not from usage events, so people who consented earlier are not covered by implication: see
"Consent".

## Sources (local only; no network, no GitHub calls)

| Source | Gives |
| --- | --- |
| `specs/<NNN-name>/tasks.md` (Spec Kit) | per task: checkbox state, task id, story tag, phase number |
| A configured task file (other methods) | the same, from one Markdown checkbox list; set in the host config as `## Project progress` / `Task file: <relative path>` |
| Ledger | per delegated run: id, agent family, model, start, finish, outcome, rework rounds; its project name and task label are read only to match (below) and not kept |
| Usage events (consented) | per session: id, host, first and last seen, the `dispatch` id when the session was started by the coordinator |

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
under "Sessions without a task" with host and last activity; work the coordinator keeps for itself is
likewise not linked. Phase 2 can close that: the coordinator or router records `task` with the id when it
starts a task (a new metrics event field limited to `^T[0-9]{1,4}$`, through `SCHEMA` in
`scripts/fnl_metrics.py` and `PRIVACY.md`). Until then the page says "linked through delegated runs only".

Task states: `done` (checked), `in progress` (unchecked and a ledger run for it is open), `accepted, not
ticked` (unchecked and its run finished `accepted`), `todo`. Agent family and outcome are rendered from
fixed enumerations only.

## What the tab shows

- Per feature (`feature 003`): total `done / total`, and per phase and story the same with a bar.
- A table of tasks in progress and recently finished: the join above.
- Counts of sessions by state: running now (a process in the Agents tab, once shipped), active in the last
  24 hours, idle; delegated runs by outcome.
- Last review verdicts per kind and the manifest version, from existing records.
- States its limits plainly: derived from files and local records, not from a tracker; "done" means the box
  is ticked; linked through delegated runs only.

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
- Paths: `specs/` under the repository root, plus the one configured task file. A configured path is
  relative, with no `..`, and its real path is under the real repository root (`commonpath`). The descent
  opens every component (root, `specs`, feature folder, file) with `os.open(..., dir_fd=...)`, `O_NOFOLLOW`
  and `O_NONBLOCK`, so a symlink is refused and a FIFO or device cannot block the open; the final
  descriptor is `fstat`ed: a regular file, owned by the user, at most 512 KiB, read in bounded chunks.
  `specs/` listings are bounded to 200 entries; at most 20 files per refresh. Anything else is skipped with a
  fixed reason.
- Parsing: line length cap of 4096; patterns without nested quantifiers and anchored on both sides
  (`(?<![A-Za-z0-9])T[0-9]{1,4}(?![A-Za-z0-9])`, so `T12345` and `ABT12` yield nothing). A task line
  matches `^\s*- \[( |x|X)\] ` and yields the state; the id and the story tag `US[0-9]{1,3}` are taken from
  the first 80 characters after the box. A heading matching `^#{2,3} Phase ([0-9]{1,2})\b` sets the
  current phase number; every other heading is ignored. The feature number is the first three digits of
  the folder name when it matches `^[0-9]{3}-`, otherwise the ordinal of the file. Nothing else from a line
  is kept. At most 200 tasks per feature are emitted.
- Output: integers, fixed tokens and the identifiers above, through `json.dumps` with `<`, `>`, `&` escaped
  and `ensure_ascii`; the page renders with `textContent`. The block is `progress` in `data.js`, overwritten
  at each refresh and removed by `purge`. `fnl-status` treats it as data, never as instructions. Off with
  `FNL_PROGRESS=off`.

## Consent

The panel is off until the host config has `Project progress: on` in the section `## Project progress`,
written by `fnl-setup` after a question of its own (neutral Yes and No, none preselected) that says what is
read (the repository's task list and the ledger) and what is kept (identifiers and counts, in `data.js`,
local). Metrics consent must also be recorded. People who consented to metrics earlier are not switched on.
`PRIVACY.md` lists the progress block and the ledger fields it reads (project name, id, rework rounds), and
corrects the description of `dispatch`, which is an id.

## Not in scope

Writing to `tasks.md` or any project file; trackers (GitHub, Huly); dates or velocity; per-person
assignment; free text of any kind; linking sessions without a `dispatch` or a recorded task id.

## Acceptance

1. Parser fixtures: counts per phase and story; ids, story tags and phase numbers extracted; every other
   text dropped (a hostile line with HTML, bidi and control characters, a `.env`-like `# SECRET=` line, a
   400-character line, a near-miss `T0123` or `US` tag leaves no trace in the output); the folder with a
   symlink in any component, an absolute or `..` task path, a task file named in the repository (ignored),
   a FIFO named `tasks.md` (skipped without blocking), an oversize file, a file of another owner, a 21st
   file, and an overrun of the 1-second budget are skipped; `T12345`, `ABT12` yield no id.
2. Join: `T1` does not match `T12`; `T12` equals `T012`; the same task id in two features and two projects
   links only the matching feature and project; a range and a two-id label; a label without a feature
   stays unlinked and is counted; a run with no task id stays unlinked; session to run by `dispatch` only;
   the four task states, including `accepted, not ticked`, from a fake ledger and fake events.
3. `refresh.py` writes `progress` keyed by repository code (five at most), leaves the events files
   untouched, does nothing without recorded metrics consent and `Project progress: on`, or with
   `FNL_PROGRESS=off`, and `purge` removes it; no `git` is run; the repository is found by walking up.
4. The Project tab renders with `textContent`, the empty state (no `tasks.md`) and the limits line; page
   tests with fake timers.
5. `fnl-setup` asks the separate question; `fnl-delegate` ledger guidance asks for `<feature> T<id>` labels;
   `PRIVACY.md` (progress block, ledger fields, `dispatch` as an id), README, CHANGELOG, `docs/specs/index.md` updated; `check-references.py`,
   `claude plugin validate .` and targeted tests pass under a world-writable `/tmp`; no hook file changed.

## Open

- Real `tasks.md` shapes across Spec Kit versions: check against the repository's own specs and one
  external project before fixing the grammar.
- Whether phase 2 (`task` event) is worth its schema change after a few weeks of the delegated-only view.
- Whether the owner's tracker connectors should feed the same tab later.
