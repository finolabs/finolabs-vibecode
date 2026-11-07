# Feature: project (project scope)

Needs: metrics consent and project progress on (the `metrics` feature), asked there as its own consent and never bundled or assumed; a declined or missing prerequisite leaves this feature pending. Optional. In a run that covers both scopes, finish metrics consent and its `refresh.py consent` write first. Every question uses neutral Yes and No with none preselected or marked recommended; a default, timeout or auto-selected option never counts as the yes. There is no user-scope default workflow.

## Work tracking settings

Follow [project-settings.md](../project-settings.md) for this repository's ledger name and separate task file; its questions are "Save this ledger line?" and "Save this task file line?", each shown with the exact line first. Legacy global `Ledger project:` and `Task file:` lines are offered for conversion for this repository only, never automatically. Enforcers: `project_progress.py` for writes and validation; agent judgment (advisory) for the interview.

## Project label

Offer a local display label for this repository. Ask: "Set this project label?" after the user's own label is chosen. Allowed: 1 to 40 ASCII letters, digits, spaces, dots, dashes and underscores, at least one non-space. Run `python3 -I <this skill folder>/scripts/project_progress.py label --set <label>` from inside the repository, the label as one safely quoted argument.
The script validates it and changes only the entry for this repository's short code under `## Project labels` in canonical `<data root>/host.md`; a linked worktree shares the main repository's code. Running `fnl-status` inside a repository with metrics consent registers its sanitised folder name in `state/projects.json`; this label overrides it. Repositories with neither name are omitted. Hook-started refreshes never register names. Never use a ledger project name as the display label. Labels stay local and are not usage events.
The task reader keeps only the `P1` to `P9` priority number from sibling `spec.md` headings, drops their text, and skips `specs/archive`; these files share the task-reader safety and limits.
