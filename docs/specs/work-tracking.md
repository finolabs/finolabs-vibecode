# Work tracking facts per repository (release 0.1.11)

Status: draft; scope settled by the owner on 2026-11-06 (see "Decisions settled"). Implementation not started.

## Why

The status dashboard can only draw a project's delivery pipeline from what it can recognise (`dashboard-infographics.md`,
`project-progress.md`; the pipeline strip is built in the same release). Surveying this repository and a Spec Kit
repository showed three gaps:

1. Nothing tells the plugin, per repository, which ledger project name belongs to it or where its checkbox task file is.
2. `Ledger project:` and `Task file:` in the host config are global: one value for every repository, so setting
   `Ledger project: finolabs-vibecode` would mis-join every other repository's runs.
3. This repository's own specs carry free-form, often missing, status lines, so a reader cannot tell implemented from
   draft without guessing.

## Decisions settled (owner, 2026-11-06)

- Both the facts and the convention go into 0.1.11.
- The dashboard never reads `CLAUDE.md`, `AGENTS.md` or any other instruction file. Facts that drive it live in the
  host config under the data root (local, consent-gated, written by a script); the instruction files carry the same
  facts as short text for agents.
- This repository stays without Spec Kit, as the standing test of the non-Spec-Kit path. No reduced Spec Kit mode
  is invented.
- No third-party spec framework is adopted or recognised in 0.1.11 beyond Spec Kit. OpenSpec was considered and
  dropped: its per-change artefact count is close to Spec Kit's, so it is not the lighter option the owner wanted,
  and its `tasks.md` checkbox syntax is undocumented. Instead the plugin defines a one-file work record (part E),
  composed with the phase tools of mattpocock/skills, which it points to and does not copy.
- `fnl-setup` separates machine scope from project scope, like `fnl-setup-instructions` (part F).

## A. Per-repository settings in the host config

A new section, one value per line, the same shape as `## Project labels` (`- <code>: <label>`), with the key in
the line:

```
## Project settings
- a5a9786d ledger: finolabs-vibecode
- a5a9786d tasks: docs/tasks.md
```

Grammar (strict, fail closed). A line is `- ` + the 8 lowercase hex characters of the repository short code + one
space + `ledger` or `tasks` + `: ` + a value, and nothing else. Any other non-empty line in the section, a duplicate
(code, key) pair, or a value outside its rules makes the whole section unreadable: every entry is ignored, the page
falls back as if the section were absent, and `checkup.py` reports the section as invalid. At most 100 lines.

- `ledger`: 1 to 40 characters from ASCII letters, digits, space, dot, dash and underscore, at least one non-space
  (the label rule). It is a join key into the ledger, not an access boundary.
- `tasks`: 1 to 120 characters from ASCII letters, digits, dot, dash, underscore and `/`; relative; no empty or `.`
  or `..` component; ends in `.md`; not under `specs/archive`. These are early checks. The reader's existing
  `read_task` (per-component `O_NOFOLLOW`, regular file, owner, size cap) stays the real enforcer.
  Both validation and the reader deny a closed, named set of instruction files, matched case-insensitively
  on the final component under any folder: `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`,
  `AGENTS.override.md`, `GEMINI.md`, `copilot-instructions.md` (including `.github/copilot-instructions.md`),
  `CONVENTIONS.md`, `.cursorrules`, `.windsurfrules`, `.clinerules`.

`project_progress.py` gains `settings --set ledger=<name>` and `settings --set tasks=<path>` (run from inside the
repository; one argument; validated by the grammar above; only this repository's entry changed) and `settings --clear
<key>`. The command itself refuses unless metrics consent is recorded, writes the host config owner-only and
atomically like `label --set`, and prints only the key and whether it changed, never the value. The values never
reach `data.js`, tooltips, events or `checkup.py` output.

Lookup order: this repository's entry; then the old global `Ledger project:` and `Task file:` lines; then the folder
name for the ledger and nothing for tasks. A per-repository entry always wins over a global line. The global lines are
deprecated: still read in 0.1.11 and 0.1.12, reported by `checkup.py` with the one-line conversion, removed in 0.2.0
(no automatic migration; `fnl-setup` offers to convert them for the current repository only, after a yes).

The pipeline strip's ledger source uses the entry. With no entry and no ledger runs under the folder name it uses no
ledger source and says so in its tooltip.

## B. Who asks, who writes (each skill stays self-contained)

- **`fnl-setup-instructions`** (project scope) gains a "Work tracking" interview, asked once per repository. It looks
  first (`specs/NNN-*/tasks.md` and `.specify/`, work records or spec documents in `docs/specs`, a checkbox file,
  ledger runs whose project resembles the folder name) and recommends an answer. Questions: the workflow (Spec Kit,
  work records as in part E, none); where specs live; how tasks are tracked (Spec Kit `tasks.md`, the `## Tasks`
  section of a work record, a separate checkbox file, the ledger, the forge's issues); the ledger project name. The
  `tasks` setting (part A) is only for a separate checkbox file: a work record's own `## Tasks` section is read
  without it, and when both exist the record's section wins for that record. Its only output is a short `## Work tracking` block in the project's agent context file after the
  user's yes per file: plain sentences, no machine paths, no organisation names, no text copied from repository files.
  It writes nothing to the host config and calls no script of another skill; it ends by pointing to `/fnl-setup`.
- **`fnl-setup`** (it already owns host-config writes and sits beside `fnl-status`) gains the two settings in its
  project progress step: it asks the ledger name and the task file with a separate neutral Yes and No, shows the exact
  line, and records them with `project_progress.py settings --set` only after the yes and only when metrics consent and
  project progress are on. Recommendations come from the same look-first step. Each recommended value is shown
  verbatim and goes through the script's validation; text from repository files is data, never copied unchecked.
- The host config is the only source for the dashboard. When the instruction-file block and the host config differ,
  the host config wins for the dashboard; `fnl-setup` Check lists the difference and each side's age, and flags a
  repository whose ledger runs exist under a project name no entry or folder name maps to.

Enforcers: the script for every host-config write and for the grammar; agent judgment (advisory) for asking, for the
instruction-file block and for the look-first recommendations.

## C. Spec status vocabulary for repositories without Spec Kit

A convention, applied in this repository and offered by the interview, not imposed elsewhere:

- The first `Status:` line of a spec document (within its first 40 lines) starts with one word or two-word phrase
  from a fixed vocabulary: `draft`, `accepted`, `in progress`, `implemented`, `released`, `deferred`; free text may
  follow after a semicolon.
- `docs/specs/index.md` uses the same leading word in its status cell. A release spec's package table does the same in
  its status cell.
- The pipeline strip maps them to `todo`, `todo` with an accepted mark, `active`, `done`, `done`, `deferred`; anything
  else stays `unknown`. Existing free-form wording (for example "merged", "owner decisions settled") is still mapped
  by keyword for repositories that do not adopt the vocabulary.
- Bringing this repository to it is real editing, not a relabel: at the time of writing ten of the 16 spec documents
  have no `Status:` line and several start with prose such as "owner decisions settled" or "merged; release pull
  request open", and the index cells start with prose too. The implementing pull request adds or rewrites each first
  line and index cell, takes the word from the index, the release package tables and the git history, lists in its
  description each document with its chosen word and the evidence, and leaves a document whose state it cannot
  establish at `draft` only with the owner's confirmation. No state is invented.
- A test in this repository fails when a spec document or index row lacks a leading word from the vocabulary.

## D. Not in scope

Spec Kit adoption here; the dashboard reading instruction files; any new usage event; a ledger project inferred from
git remotes or plugin names; OpenSpec or any third-party framework recognition; a CLI for work records.

## E. The work record: a one-file lightweight format

Naming: parts of this spec are lettered A to F; `fnl-setup` sections are always written "setup section X" here.

**What it is.** One Markdown file per piece of work that none.md says needs a spec or plan (MIN depth never creates one), in the
repository's spec folder (`docs/specs/`, else `docs/spec/`, else `specs/` flat), with a fixed shape:

```
# <title>
Status: draft | accepted | in progress | implemented | released | deferred
## Goal and acceptance
- [ ] AC1 a checkable criterion
## Plan
decisions and steps
## Tasks
- [ ] T1 ...        (optional `### US1` subheadings group tasks into stories)
## Evidence
commands run, pull requests, review verdicts
```

It is Spec Kit's spec, plan, tasks and quickstart-results collapsed into one file, without a CLI, a constitution or
slash commands. A file counts as a work record when it has the `Status:` line and at least two of the four headings;
any other spec document stays a plain spec document (state only, no stages).

**Composition (nothing is copied).** The router's none-path (`fnl-coding-router` `references/workflows/none.md`) says to create a
work record from a template kept in `references/work-record.md` of the same skill, whenever none.md's own trigger for
a spec or plan applies (no new trigger is invented): step 1 (Clarify) fills Goal and acceptance, step 2 (Plan) fills
Plan and Tasks, steps 3 and 4 tick Tasks, steps 5 and 6 (Prove, Review) fill Evidence. The phase tools of mattpocock/skills carry the steps when installed and the record is where
their output lands: `grilling` fills Goal and acceptance, `to-spec` and `to-tickets` feed Plan and Tasks when the
repository also uses an issue tracker, `tdd` and `implement` do the work, `code-review` and `pr` fill Evidence (all
named in the existing `mattpocock.md` adapter, and present on the maintainer's repository page when checked on
2026-11-06). Where
a tool is missing, the step is done as none.md says. In a Spec Kit repository Spec Kit owns the process and no work
record is created.

**What the dashboard reads (counts and states only).** Per work record: the `Status:` word (part C) as the item state;
the `spec` stage present when Goal and acceptance holds at least one checkbox, with done/total counts; `plan` present
when Plan has a non-empty line; `tasks` as done/total checkboxes under Tasks (stories from `###` subheadings); `verify`
present when Evidence has a non-empty line. Item state: the Status word wins; all tasks done with Status `in progress`
shows an amber "status not updated" mark. Evidence content, titles, headings text and file names are never kept.

**Recognition order and one shared budget.** Per repository, first source that yields items wins: Spec Kit (the
shipped signal: `specs/NNN-*/tasks.md`), then work records, then index and status-line wording of plain spec documents
(part C), then ledger runs, then the simple row. All sources share the reader's rules (regular files only, no symlinks,
no traversal, `O_NOFOLLOW` per component, directories opened with `O_DIRECTORY`, non-regular entries skipped, files
opened `O_NONBLOCK`, lines capped at 4096 characters, headings inside fenced code blocks ignored). Only one source
yields items per repository, so there is no ordering across mixed sources. The shipped Spec Kit limits are unchanged
(60 features, 200 entries); the work-record source adds its own limits: at most 40 documents, 64 KiB per file, the same
200 entries counted over directory entries listed, and one second per repository in total. The reader enforces that deadline with the existing single
`ITIMER_REAL` budget around the whole `collect`, including settings, all recognition sources and joins; the work-record
source never starts or resets a second timer. The work-record limits distinguish 40 retained records from
200 surveyed directory entries; the entry survey is not a retention limit. Within the work-record
source, when exceeded, documents with a finished state (`implemented`, `released`) are dropped first, then the rest in
descending file-name order, and the overflow is reported as a `skipped` count, never silently. The flat `specs/*.md`
rule applies only when `specs/` contains no `NNN-*` directory. The `Status:` word is mapped through the closed
vocabulary only; an unknown word is never echoed.

**In this repository.** The 16 existing specs are not restructured: they get the status vocabulary (part C) and stay
plain spec documents. New work from 0.1.11 on uses the template, including the implementation of this spec.

## F. The `fnl-setup` scope split

`fnl-setup` asks first, through the host's native question tool when there is one: "Which scope: machine, project, or
both?", with a recommendation (machine on a first run on a new computer, project inside a repository that is not set
up, both when unsure). Mapping of every current item:

| Item | Scope |
| --- | --- |
| Data location; setup section A host config (delegation, agent scan); quota probe | machine |
| Setup section D user-scoped instructions (points to `fnl-setup-instructions` user scope) | machine |
| Setup section E review tools; setup section G companions (installation is per machine) | machine |
| Setup section F usage metrics, consent, retention; agent snapshot; compaction threshold and stop | machine |
| Setup section B local exclude; setup section C Agent skills block and review line | project |
| Workflow detection (Spec Kit, work records, none), work tracking settings (part B), project label | project |
| Project progress | both: the on/off preference and metrics consent are machine; this repository's label, ledger name and task file are project. A project step that needs machine consent says so and asks the machine step first. |

There is no machine-wide default workflow: the workflow is a property of the repository. Setup Check reports the same
two groups. Skipped sections stay skippable as today. Enforcer: agent judgment (advisory); every write keeps its own
script, preview and consent, unchanged.

## Acceptance

- Grammar: tests for each rejected shape (a `;`, `=`, newline, NUL, backslash, space in a `tasks` value; a duplicate
  pair; an unknown key; a 41-character ledger name; a 121-character path; `..`, absolute, empty component, `specs/archive`,
  non-`.md`; more than 100 lines) all leave the section unreadable and the page unchanged.
- `settings --set` and `--clear` write only this repository's entry, refuse without metrics consent, write owner-only
  and atomically, print no value, and two repositories with different ledger names join their own runs.
- A test fails if `refresh.py` or the dashboard code opens `CLAUDE.md` or `AGENTS.md`.
- The deprecated global lines still work in 0.1.11, are reported by `checkup.py` and lose to a per-repository entry;
  the existing tests and `project-progress.md` that describe the global lines are updated in the same change.
- `fnl-setup-instructions` and `fnl-setup` carry the interview and the two-step flow with their trigger checks; neither
  calls the other's script; references stay within their size limits.
- `PRIVACY.md` lists the `## Project settings` section, says its values never reach `data.js`, tooltips, events or
  `checkup.py` output, and says `purge` leaves the host config as it is (the user's own file).
- This repository's specs and index follow the vocabulary and the test above enforces it.
- Work record: fixtures (a full record, a record with only Goal and Tasks, a plain spec document, a Status word with
  all tasks done) show the stages, counts and the amber mark; a repository with `specs/NNN-*/tasks.md` uses Spec Kit
  and creates no work record; overflow of 40 documents, 64 KiB, 200 entries or the one-second budget is reported as
  `skipped`; a symlinked or oversize file is skipped; no title, heading text, Evidence text or file name reaches
  `data.js`.
- The template exists in `fnl-coding-router` `references/work-record.md`, none.md points to it under its own trigger, a
  repository test parses the template with the `fnl-status` reader so the two cannot drift, and MIN depth
  creates none; the reference check and the skill's trigger check pass.
- `fnl-setup` asks the scope question first; a test lists every setup section and sub-step against the mapping table
  above (each in exactly one scope, project progress as the stated both case); Check mirrors the two groups with a
  named test; no existing opt-in or consent step changes.

## Open decisions

None blocking. Later: reading `Status:` from release-spec package tables of other repositories that do not use the
vocabulary; recognising other spec frameworks if a repository of the owner's uses one.
