# Feature: checks (project scope)

Needs: a git repository; run it from inside the repository whose checks you set. Optional; nothing is stored until the user says yes.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Find the checks

Run `python3 -I <this skill folder>/scripts/checks_setup.py detect` from inside the repository. It reads, and never runs, the lint, test, typecheck and build scripts in `package.json`, the Python test runner and the test, lint and check targets of the `Makefile`, and proposes checks only from those.
It chooses pytest only when it is declared: in `[project] dependencies`, `[project.optional-dependencies]`, `[dependency-groups]`, `[tool.poetry.dependencies]`, `[tool.poetry.group.*.dependencies]`, a `[tool.pytest]` table such as `[tool.pytest.ini_options]`, a `pytest.ini` `[pytest]` section or a `setup.cfg` `[tool:pytest]` section. It chooses unittest only when a test module in `tests/` imports `unittest`; with neither it lists the Python project as skipped with "test runner not declared".
The CI workflows in `.github/workflows` are evidence, not checks: under the heading `found in CI, add with --check if you want it` it lists the first line of each `run:` key it finds under a job (at most 120 characters, control characters replaced), with the job name when it is plainly readable, and converts none of them. These are lexical candidates, not verified steps: one may be an action's input rather than a run step, so the user reads them as hints.
It prints every source it read, a proposed ordered list (a short name and a JSON argument array each), every source or check it skipped with the reason, and the CI evidence. It never turns a shell string into a command.

Show the user the sources, the list, the skipped items and the CI evidence in plain words. The user may drop, reorder or add checks; to keep a step found in CI, propose it as a `--check "<name>=<JSON array>"` item the user can read, never as a shell string. Each check is a name of lowercase letters, digits and dashes (at most 32 characters) and an argument array of at most 1 KB, at most 20 per repository. A check the CI runs through a reusable action or a service container is not listed; the sources shown let the user add it.

As a best-effort guard, not a sandbox, the script refuses an argument array whose program is a shell or a known launcher of another program (env, xargs, sudo, timeout and the like), or an interpreter given inline code, at detection, preview and when reading the stored section (one such entry makes the whole section unset).
Say plainly that this list cannot be complete: a program may start a shell by itself (npm run, find -exec), and every check runs the repository's own code. The real protection is that the user reads and approves each array, and that a repository cannot change the stored list.

## Save the list

Run `checks_setup.py preview --check '<name>=<JSON array>'`, one `--check` per check in order, each safely quoted. Show the printed entry, then ask: "Save this list of checks for this repository?"
Yes: Save only this repository's lines in Checks in local host.md, after a backup. The checks run this repository's own code on your computer, as cloud CI does, so use them only on code you are willing to run. Nothing runs now.
No: Leave the Checks section unchanged; ask later with /fnl-setup add checks.
Undo: Run checks_setup.py remove and approve its preview, or restore the backup shown.
Choices: "Yes, save these checks" / "No, leave checks unchanged".
On yes run `checks_setup.py apply --yes --digest <Digest>`. The script refuses a preview older than 60 minutes, a changed host config, a symlinked file, a shell string, a shell, launcher or inline-code program, an invalid name, more than 20 checks and an array over 1 KB. An invalid `## Checks` section counts as unset as a whole: the script refuses to write until the user repairs it, and never repairs it itself.

`checks_setup.py show` prints this repository's list. The entry is keyed by the same repository code as `## Project settings` (a linked worktree shares the main repository's code); it lives in its own section because the Project settings readers refuse unknown entries. Other repositories' entries are kept.

## Local receipt (optional, its own question)

Offer this only after a list is saved, and only for a repository whose cloud CI cannot run. Run `checks_setup.py receipt on`, show the printed preview, then ask: "Turn on the local receipt for this repository?"
Yes: When the whole list passes with `fnl-checks`' `checks.py run` (never from a `--changed` run), on a clean working tree whose head did not move, a receipt is written, and `merge_check.py` accepts it in place of missing or failing cloud checks for that head and this list only. What could go wrong: the receipt is self-reported. It proves only that this computer ran the list at that head, and it gives a reviewer nothing they can check. It suits a repository one person works on.
No: Leave the mode off; a missing cloud check keeps blocking the merge as before.
Undo: Run `checks_setup.py receipt off` and approve its preview. Removing the list also turns the mode off.
Choices: "Yes, turn on the local receipt" / "No, keep it off".
On yes run `checks_setup.py apply --yes --digest <Digest>`. The mode is the line `- <repository code>: local-receipt = on` in `## Checks`, written only by this script; `local-receipt` is never a check name.

## Pre-push hook (optional, its own question)

Run `checks_setup.py hook install --checks-script <fnl-checks skill folder>/scripts/checks.py [--base <ref>]` from inside the repository. It asks git where hooks are read (`git rev-parse --git-path hooks`), so a linked worktree gets the main repository's hooks folder. It refuses when `core.hooksPath` is set and never changes that setting. Show the preview, which names the hooks folder, says the hook applies to every worktree of the repository, names any existing `pre-push` hook and shows the hook script. Then ask: "Install this pre-push hook?"
Yes: Before every push, git runs `checks.py run --changed`: the stored checks the change touches. A failing check stops the push. `git push --no-verify` skips the hook. It is your own git hook, not a plugin hook.
No: Install no hook; run `checks.py run` yourself before a push.
Undo: Run `checks_setup.py hook remove` and approve its preview; it removes only this plugin's hook and keeps a backup.
Choices: "Yes, install the hook" / "No, no hook".
On yes run `checks_setup.py hook apply --yes --digest <Digest>`. When the preview names a different existing hook, the script refuses unless the user also says yes to replacing it (a second, separate question: "Replace the existing pre-push hook? A backup is kept."), and then `--replace-existing` is added. A hook that changed after the preview, a link in place of the hook, or a hooks folder that is not yours is refused.

When no hook existed at the preview, the new hook is published with a hard link that fails if a hook has appeared since, so a concurrent hook is never overwritten.
When replacing or removing, the script reads the hook again right before the replace or removal and refuses if its bytes differ from the preview. A writer that ignores this and changes the hook between that last read and the replace or removal remains a residual race.

Enforcers: `checks_setup.py` for the argument form, the limits, the preview and digest before any write, the section-only write, the mode line, and the hook folder resolution, `core.hooksPath` refusal, backup and no silent overwrite. Detection, the list and the mode run no command; the hook commands run only fixed git queries. Nothing makes a network call. Choosing what goes into the list is agent judgment (advisory).
