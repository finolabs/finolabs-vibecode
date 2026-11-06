# Work tracking facts per repository (release 0.1.11)

Status: draft; scope settled by the owner on 2026-11-06 (see "Decisions settled"). Implementation not started.

## Why

The status dashboard can only draw a project's delivery pipeline from what it can recognise (`dashboard-infographics.md`,
`project-progress.md`; the pipeline strip is built in the same release). Surveying this repository and a Spec Kit
repository showed three gaps:

1. Nothing tells the plugin, per repository, how work is tracked (Spec Kit, status lines in `docs/specs`, the ledger,
   a checkbox file) or which ledger project name belongs to it.
2. `Ledger project:` and `Task file:` in the host config are global: one value for every repository, so setting
   `Ledger project: finolabs-vibecode` would mis-join every other repository's runs.
3. This repository's own specs carry free-form, often missing, status lines, so a reader cannot tell implemented from
   draft without guessing.

## Decisions settled (owner, 2026-11-06)

- Both facts and convention go into 0.1.11.
- The dashboard never reads `CLAUDE.md`, `AGENTS.md` or any other instruction file. Facts that drive it live in the
  host config under the data root (local, consent-gated, written by a script); the instruction files carry the same
  facts as short text for agents.
- This repository stays without Spec Kit, as the standing test of the non-Spec-Kit path. No reduced Spec Kit mode
  is invented.

## A. Per-repository work-tracking settings in the host config

Replace the two global lines with a section keyed by the repository short code, like `## Project labels`:

```
## Project settings
- a5a9786d: ledger=finolabs-vibecode; tasks=docs/tasks.md
```

- Keys: `ledger` (a ledger project name, the same 1 to 40 ASCII characters rule as labels) and `tasks` (a relative path
  to a Markdown checkbox file, today's `Task file` rules: regular file, no symlink, no traversal, size cap).
- `project_progress.py` gains `settings --set ledger=<name>` and `--set tasks=<path>` (from inside the repository,
  validated, owner-only host config, only this repository's entry changed) and `--clear`. `purge` removes nothing new
  (the file is the host config); the entry is local and not a usage event.
- Lookup order: this repository's entry, then the old global `Ledger project:` and `Task file:` lines (still read for
  one release, reported as deprecated by `checkup.py`), then the folder name for the ledger and nothing for tasks.
- The pipeline strip's ledger source uses the entry. With no entry and no ledger runs under the folder name it uses no
  ledger source and says so in its tooltip.

## B. `fnl-setup-instructions`: a "Work tracking" interview at project scope

Project scope gains one section, asked once per repository, with a recommended answer found by looking first
(`.specify/` and `specs/NNN-*`, `docs/specs`, a `tasks.md`, ledger runs whose project name resembles the folder):

1. Workflow: Spec Kit, the repository's own spec documents, or none.
2. Where specs live (only when not Spec Kit) and whether they follow the status vocabulary below.
3. How tasks are tracked: Spec Kit `tasks.md`, a checkbox file (its path), the ledger, or the forge's issues.
4. The ledger project name for this repository, when the ledger is used.

Output, after the user's yes per file as today:

- a short `## Work tracking` block in the project's agent context file (`AGENTS.md` when it is the source, else
  `CLAUDE.md`): the answers as plain sentences, no machine paths, no organisation names, one source of truth with the
  existing block rules;
- then, as a separate question with neutral Yes and No, the same answers written to the host config through
  `project_progress.py settings --set` (section A), only when metrics consent and project progress are on. A No
  leaves the block and skips the host config.

`fnl-setup` Check reports the block and the host-config entry separately and flags a repository whose ledger runs exist
under a project name that no entry or folder name maps to.

Enforcers: the script for every host-config write; agent judgment (advisory) for asking and for the instruction-file
block; the dashboard reads only the host config.

## C. Spec status vocabulary for repositories without Spec Kit

A convention, checked in this repository and offered by the interview, not imposed elsewhere:

- The first `Status:` line of a spec document (within its first 40 lines) starts with one word from a fixed
  vocabulary: `draft`, `accepted`, `in progress`, `implemented`, `released`, `deferred`; free text may follow after a
  semicolon.
- `docs/specs/index.md` uses the same first word in its status cell. A release spec's package table uses the same
  first word in its status cell.
- The pipeline strip maps these words to `todo`, `todo` with an accepted mark, `active`, `done`, `done`, `deferred`;
  anything else stays `unknown`.
- This repository: a test fails when a spec document or index row lacks a first word from the vocabulary, and the
  existing specs are brought to it in the same change (statuses stated as they are today, none invented).

## D. Not in scope

Spec Kit adoption here; the dashboard reading instruction files; any new usage event; a ledger project inferred from
git remotes or plugin names.

## Acceptance

- `settings --set/--clear` validate, write only this repository's entry, refuse unsafe values, and are covered by
  tests with temporary homes; two repositories with different ledger names join their own runs.
- Deprecated global lines still work for one release and `checkup.py` reports them.
- The interview text, its recommended answers and the two-step write (block, then host config) are in
  `fnl-setup-instructions` with its trigger check; the reference and the project-scope contract template stay within
  their size limits.
- This repository's specs and index follow the vocabulary and a test enforces it.
- `PRIVACY.md` and `CLAUDE.md` need no change: values are a name and a relative path the user chose, stored locally in
  the host config, never in events (confirmed by the reviewers).

## Open decisions

None blocking. Candidate for later: reading `Status:` from release-spec package tables of other repositories without
the vocabulary.
