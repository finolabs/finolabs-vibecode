# Feature: project (project scope)

Needs: metrics consent and project progress on (the `metrics` feature), asked there as its own consent and never bundled or assumed; a declined or missing prerequisite leaves this feature pending. Optional. In a run that covers both scopes, finish metrics consent and its `refresh.py consent` write first. Every question uses neutral Yes and No with none preselected or marked recommended; a default, timeout or auto-selected option never counts as the yes. There is no user-scope default workflow.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Work tracking settings

Follow [project-settings.md](../project-settings.md) for the implementation and validation. Show each exact line first, then ask separately: "Link this repository’s dashboard progress to the task records named here?"
Yes: Save the shown ledger line, the name joining local work-run records to this repository, in Project settings in local host.md. Nothing is sent.
No: Leave that key unchanged; ask later.
Undo: Restore its previous value through project settings.
Choices: "Yes, save this work-run name" / "No, keep the current setting".
Ask: "Use this checkbox file to count this repository’s tasks on the dashboard?"
Yes: Save the shown task-file line in Project settings in local host.md. The dashboard reads that local file; nothing is sent.
No: Leave that key unchanged; ask later.
Undo: Restore its previous value through project settings.
Choices: "Yes, save this task file" / "No, keep the current setting".
Legacy global `Ledger project:` and `Task file:` lines are offered for conversion for this repository only, never automatically. Enforcers: `project_progress.py` for writes and validation; agent judgment (advisory) for the interview.

## Project label

After the user chooses a local display label, ask: "Show this name for the repository on your private dashboard?"
Yes: Save only this repository’s Project labels entry in local host.md. It replaces the displayed folder name; nothing is sent.
No: Leave its label unchanged; ask later.
Undo: Set the previous label again through this step.
Choices: "Yes, save this display name" / "No, keep the current name".
Allowed: 1 to 40 ASCII letters, digits, spaces, dots, dashes and underscores, at least one non-space. Run `python3 -I <this skill folder>/scripts/project_progress.py label --set <label>` from inside the repository, the label as one safely quoted argument.
The script validates it and changes only the entry for this repository's short code under `## Project labels` in canonical `<data root>/host.md`; a linked worktree shares the main repository's code. Running `fnl-status` inside a repository with metrics consent registers its sanitised folder name in `state/projects.json`; this label overrides it. Repositories with neither name are omitted. Hook-started refreshes never register names. Never use a ledger project name as the display label. Labels stay local and are not usage events.
The task reader keeps only the `P1` to `P9` priority number from sibling `spec.md` headings, drops their text, and skips `specs/archive`; these files share the task-reader safety and limits.
