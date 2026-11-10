# Feature: checks (project scope)

Needs: a git repository; run it from inside the repository whose checks you set. Optional; nothing is stored until the user says yes.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Find the checks

Run `python3 -I <this skill folder>/scripts/checks_setup.py detect` from inside the repository. It reads, and never runs, the `run:` steps of the CI workflows in `.github/workflows`, the lint, test, typecheck and build scripts in `package.json`, the pytest or unittest settings in `pyproject.toml`, and the test, lint and check targets of the `Makefile`.
It prints every source it read, a proposed ordered list (a short name and a JSON argument array each), and every step it skipped with the reason, for example several commands in one step, a step that needs a shell, a working directory or a dependency install. It never turns a shell string into a shell command; a skipped step is never guessed.

Show the user the sources, the list and the skipped steps in plain words. The user may drop, reorder or add checks; each one is a name of lowercase letters, digits and dashes (at most 32 characters) and an argument array of at most 1 KB, at most 20 per repository. A check the CI runs through a reusable action or a service container is not found; the sources shown let the user add it.

## Save the list

Run `checks_setup.py preview --check '<name>=<JSON array>'`, one `--check` per check in order, each safely quoted. Show the printed entry, then ask: "Save this list of checks for this repository?"
Yes: Save only this repository's lines in Checks in local host.md, after a backup. The checks run this repository's own code on your computer, as cloud CI does, so use them only on code you are willing to run. Nothing runs now.
No: Leave the Checks section unchanged; ask later with /fnl-setup add checks.
Undo: Run checks_setup.py remove and approve its preview, or restore the backup shown.
Choices: "Yes, save these checks" / "No, leave checks unchanged".
On yes run `checks_setup.py apply --yes --digest <Digest>`. The script refuses a preview older than 60 minutes, a changed host config, a symlinked file, a shell string or a shell program, an invalid name, more than 20 checks and an array over 1 KB. An invalid `## Checks` section counts as unset as a whole: the script refuses to write until the user repairs it, and never repairs it itself.

`checks_setup.py show` prints this repository's list. The entry is keyed by the same repository code as `## Project settings` (a linked worktree shares the main repository's code); it lives in its own section because the Project settings readers refuse unknown entries. Other repositories' entries are kept.

Enforcers: `checks_setup.py` for the argument form, the limits, the preview and digest before any write and the section-only write; it runs no command and makes no network call. Choosing what goes into the list is agent judgment (advisory).
