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
  is invented. An optional OpenSpec adapter is a separate, later decision.

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
  `read_task` (per-component `O_NOFOLLOW`, regular file, owner, size cap) stays the real enforcer and is unchanged.

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
  first (`.specify/` and `specs/NNN-*`, `docs/specs`, a `tasks.md`, ledger runs whose project resembles the folder
  name) and recommends an answer. Questions: the workflow (Spec Kit, the repository's own spec documents, none); where
  specs live; how tasks are tracked (Spec Kit `tasks.md`, a checkbox file, the ledger, the forge's issues); the ledger
  project name. Its only output is a short `## Work tracking` block in the project's agent context file after the
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
git remotes or plugin names; the OpenSpec adapter.

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

## Open decisions

None blocking. Later: reading `Status:` from release-spec package tables of other repositories that do not use the
vocabulary; an OpenSpec adapter and recognition.
