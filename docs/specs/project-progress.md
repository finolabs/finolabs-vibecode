# Project progress on the dashboard

Idea: owner, 2026-11-06. Most projects that use this pack also use Spec Kit, or another method that
splits the work into stories and tasks. The sessions that carry that work are created, run and finish.
The dashboard can show that as project progress next to "Running now" (`running-agents.md`), so a user
sees how far the project is without opening each session. This spec is the design; the code follows
`running-agents.md` phase 1, because both feed the same page.

## Sources (local only; no network, no GitHub calls)

| Source | Gives | Limit |
| --- | --- | --- |
| Spec Kit task lists: `specs/<feature>/tasks.md` in the repository | Tasks as Markdown checkboxes (`- [ ]` / `- [x]`), usually with a task id (`T012`), a parallel flag and a story tag (`[US1]`), under phase headings | Only repositories that use Spec Kit; format drift between versions; the file is the repository's own text |
| Ledger (`ledger.py`) | Delegated runs: project, task label (often the task id), start, finish, outcome, rework rounds | Only coordinator-started runs; labels are the coordinator's words |
| Usage events (`events-*.jsonl`, consented) | Sessions per repository code: started, last seen; review verdicts, commits | Metadata only; no titles, no task ids |
| A configured task file (other methods) | Any Markdown with checkbox lists the user names in the host config (`## Project progress`, `Task file: <relative path>`) | One file per repository in phase 1; checkbox format only |

Not sources: GitHub issues and pull requests (network), session titles or transcripts (content), Huly or
other trackers (separate connectors, out of scope).

## What the panel shows

- **Progress by story/phase**: for each `tasks.md` (feature), the phase and story headings with
  `done / total` task counts and a bar; the feature total; the count of tasks with no story tag.
- **Task state**: `done` (checked), `in progress` (unchecked, with an open ledger dispatch whose task
  label contains the task id), `delegated and finished` (unchecked, ledger run finished with outcome
  `accepted` but the box not ticked: flagged "accepted, not ticked"), `todo`.
- **Sessions of the project**: from usage events, per repository code: running now (a process in the
  snapshot, when `running-agents.md` ships), recently active (last 24 h), idle; completed delegated runs
  from the ledger with outcome. Counts only; no titles.
- **Review and release state when recorded**: last review verdicts per kind (existing events), the
  version in the manifest.
- States its limits plainly: derived from files and local records, not from the tracker; a task is "done"
  because the box is ticked.

## Reading `tasks.md` safely

`scripts/project_progress.py` (stdlib) runs inside the dashboard refresh, reads only:
- `specs/*/tasks.md` (and the one configured task file) under the repository root of the current
  directory, each a regular file, not a symlink, owned by the user, at most 512 KiB, the root not a
  symlink; at most 20 files per refresh.
- It extracts per line: the checkbox state, a task id matching `^T[0-9]{1,4}$` if present, a story tag
  matching `^US[0-9]{1,3}$` if present, and the nearest heading text truncated to 80 characters with
  control characters removed. It keeps no other task text: descriptions, file paths and links in the
  line are dropped.
- Heading text and ids reach the page through `json.dumps` with `<`, `>`, `&` escaped and are rendered
  with `textContent`.
- It runs no command and makes no network call.

## Data and privacy

The result is a `progress` block in `data.js` (overwritten at each refresh, removed by `purge`). It holds
counts, ids and truncated headings of the repository's own files; `PRIVACY.md` says so and that the page
is local. It is built only when metrics consent is recorded; `FNL_PROGRESS=off` stops it. Headings are
user content, not metadata only, so the first build asks no new consent but the panel is off until
`fnl-setup` section F (usage metrics) has been answered and states this in its consent text.

## Not in scope

- Writing to `tasks.md` or any project file; syncing with a tracker; estimating dates or velocity.
- Parsing task text beyond id, story tag and heading; parsing methods other than checkbox lists.
- Per-person assignment; session titles.

## Acceptance

1. `project_progress.py` with fixture `tasks.md` files: counts per phase and story, ids and story tags
   extracted, descriptions dropped, hostile headings (HTML, control characters, very long) neutralised,
   a symlink, oversize file, other-owner file and a 21st file are skipped.
2. State derivation: the four task states and the "accepted, not ticked" flag from a fake ledger.
3. `refresh.py` writes the `progress` block, leaves the events files untouched, does nothing without
   recorded consent or with `FNL_PROGRESS=off`, `purge` removes it.
4. The page renders the panel with `textContent`, an empty state (no `tasks.md`) and the limits line;
   page tests with fake timers.
5. `PRIVACY.md`, README, CHANGELOG, `docs/specs/index.md` updated; `check-references.py`,
   `claude plugin validate .` and targeted tests pass under a world-writable `/tmp`; no hook file changed.

## Open

- Real `tasks.md` shapes across Spec Kit versions: check against the repository's own specs and at least
  one external Spec Kit project before fixing the grammar.
- Whether a second task format (a numbered list or a table) is worth supporting after phase 1.
- Whether the tracker connectors the owner uses (Huly) should feed the same panel later.
