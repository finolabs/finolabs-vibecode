# Feature: checks (project scope)

Needs: a git repository; run it from inside the repository whose checks you set. Optional; nothing is stored before a yes.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Find the checks

Run `python3 -I <this skill folder>/scripts/checks_setup.py detect` from inside the repository. It reads, and never runs, the lint, test, typecheck and build scripts in `package.json`, the Python test runner and the test, lint and check targets of the `Makefile`, and proposes checks only from those.
It chooses pytest only when declared: as a dependency in `pyproject.toml` (project, optional, dependency-group or Poetry tables), a `[tool.pytest]` table, a `pytest.ini` `[pytest]` or a `setup.cfg` `[tool:pytest]` section. It chooses unittest only when a test module in `tests/` imports `unittest`; with neither it lists the Python project as skipped with "test runner not declared".
CI workflows in `.github/workflows` are evidence, not checks: under `found in CI, add with --check if you want it` it lists the first line of each job's `run:` keys (at most 120 characters, control characters replaced, with the job name when plainly readable) and converts none. They are hints: one may be an action's input.
It prints the sources read, a proposed ordered list (a name and a JSON argument array each), skipped items with reasons, and the CI evidence; it never turns a shell string into a command.

Show all of it in plain words. The user may drop, reorder or add checks; to keep a step found in CI, propose it as a `--check "<name>=<JSON array>"` item, never a shell string. Each check is a name of lowercase letters, digits and dashes (at most 32 characters) and an argument array of at most 1 KB, at most 20 per repository. A check the CI runs through a reusable action or a service container is not listed; the sources shown let the user add it.

As a best-effort guard, not a sandbox, the script refuses a program that is a shell, a launcher (env, xargs, sudo, timeout and the like) or an interpreter given inline code, at detection, preview and when reading the stored list (one such entry unsets the whole list).
Say plainly that this cannot be complete: a program may start a shell itself (npm run, find -exec), and every check runs the repository's own code. The real protection: the user approves each array, and only the approved bytes count.

## Save the list

Run `checks_setup.py preview --check '<name>=<JSON array>'`, one `--check` per check in order, each safely quoted. Show it, then ask: "Save this list of checks for this repository?"
Yes: Save the list in this repository's .finolabs/vibecode/checks.json and record its approval in your private state folder. The checks run this repository's own code on your computer, as cloud CI does, so use them only on code you are willing to run. Nothing runs now.
No: Leave the checks unchanged; ask later with /setup add checks.
Undo: Run checks_setup.py remove for this repository and approve its preview.
Choices: "Yes, save these checks" / "No, leave checks unchanged".
On yes run `checks_setup.py apply --yes --digest <Digest>`. It refuses a preview older than 60 minutes, a file changed since the preview, a link on the path and anything the limits above refuse.

The file sits in the main checkout (linked worktrees share it); apply adds `.finolabs/` to `.git/info/exclude` once, never to `.gitignore`, and keeps a replaced file as `checks.json.bak-<date>`. A file edited or supplied by a branch no longer matches its approval: nothing runs and the receipt is off until setup runs again. An invalid file is unset for that repository only, never repaired. A list in `## Checks` of host.md (0.2.4) is never read: save it again, then delete that section by hand.

## Local receipt (optional, its own question)

Offer this only after a list is saved, and only for a repository whose cloud CI cannot run. Run `checks_setup.py receipt on`, show the printed preview, then ask: "Turn on the local receipt for this repository?"
Yes: When the whole list passes with `checks`' `checks.py run` (never `--changed`) on a clean tree whose head did not move, a receipt is written; `merge_check.py` accepts it in place of missing or failing cloud checks for that head and list only. What could go wrong: the receipt is self-reported. It proves only that this computer ran the list at that head, and it gives a reviewer nothing they can check. It suits a repository one person works on.
No: Leave the mode off; a missing cloud check keeps blocking the merge.
Undo: Run `checks_setup.py receipt off` and approve its preview. Removing the list also turns the mode off.
Choices: "Yes, turn on the local receipt" / "No, keep it off".
On yes run `checks_setup.py apply --yes --digest <Digest>`. The mode is `local_receipt` in the check file, written only by this script.

## Pre-push hook (optional, its own question)

Run `checks_setup.py hook install --checks-script <checks skill folder>/scripts/checks.py [--base <ref>]` from inside the repository. It asks git where hooks are read (`git rev-parse --git-path hooks`), so a linked worktree gets the main repository's folder, and refuses when `core.hooksPath` is set, never changing it. Show the preview (the hooks folder, that it applies to every worktree, any existing `pre-push` hook, the script), then ask: "Install this pre-push hook?"
Yes: Before every push, git runs `checks.py run --changed`: the stored checks the change touches. A failing check stops the push. `git push --no-verify` skips the hook. It is your own git hook, not a plugin hook.
No: Install no hook; run `checks.py run` yourself before a push.
Undo: Run `checks_setup.py hook remove` and approve its preview; it removes only this plugin's hook and keeps a backup.
Choices: "Yes, install the hook" / "No, no hook".
On yes run `checks_setup.py hook apply --yes --digest <Digest>`. A different existing hook needs a second yes ("Replace the existing pre-push hook? A backup is kept.") and `--replace-existing`. A hook changed after the preview, a link in its place, or a hooks folder not yours is refused.

A new hook is published with a hard link that fails if a hook appeared since the preview. A replace or removal re-reads the hook and refuses if it differs; a change between that read and the write is a residual race.

## Cloud workflow (optional, its own question)

Only after a list is saved, for a GitHub repository; never during an away lease, as CI configuration is a shared setting (advisory). Run `checks_setup.py ci preview [--branch <default branch>]`, show it, then ask: "Write this workflow file to the repository?"
Yes: A new file in `.github/workflows` runs the checks on pull requests, default-branch pushes and weekly, skipping document-only changes. What could go wrong: it runs the repository's code in the cloud; a required check on a skipped document-only pull request may stay pending. You review and commit it.
No: Write no workflow.
Undo: Delete the file, or restore the backup shown.
Choices: "Yes, write the workflow" / "No, leave CI unchanged".
On yes run `checks_setup.py ci apply --yes --digest <Digest>`; an existing file needs a second yes ("Replace the existing workflow file? A backup is kept.") and `--replace-existing`. Limits and `checks.py usage`: `checks`' `references/ci.md`.

Enforcers: `checks_setup.py` for the argument form, the limits, the preview and digest before any write, the approved digest, the mode, the hook folder resolution, `core.hooksPath` refusal, and backup and no silent overwrite for the hook and the workflow. Detection, the list, the mode and the workflow writer run no command; the hook commands run only fixed git queries. Nothing makes a network call. Choosing what goes into the list is agent judgment (advisory).
