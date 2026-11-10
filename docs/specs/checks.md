# Checks: where a repository's checks run and what they cost (draft, scoped to release 0.2.4)

Status: draft; the owner settled the direction and the name on 2026-11-10; nothing is built.

## Why

Most people who build with coding agents keep their code on a hosted git service on a free plan, and a private repository's CI minutes run out (on a free plan GitHub gives 2,000 minutes a month and GitLab 400, by the providers' published plans as the owner's tooling recalled them; check the current plan before relying on a number). This plugin's own repository used 518 minutes in 110 runs in the 24 hours before this spec was written, every push running the whole suite of about 1,550 tests for 4 to 5 minutes, including pull requests that changed only documents. At that pace a free private plan lasts about four days.

The plugin already proves work locally (`fnl-verification`: targeted tests, `select_tests.py`, receipts, `heavy_run.py`), but a user who does not know how to set up local checks has nothing that does it for them, nothing that makes their cloud CI cheaper, and nothing that says plainly what happens when the minutes are gone.

## Owner decisions (2026-11-10)

- No CI system of our own and no runner. Running CI is what hosted CI, `act` (runs GitHub Actions workflows locally in containers) and hook managers such as `pre-commit` and `lefthook` already do; the plugin points to them and owns the decision: which checks, where they run, and what the merge gate may trust. A self-hosted runner is never set up by the plugin: on a public repository a pull request from a fork could run code on the user's machine.
- Extend the existing skill rather than add one: a new skill would put one more description into every session and compete for the same triggers ("run the tests", "CI is red", "CI minutes").
- The skill `fnl-verification` is renamed fnl-checks, the name the user meets in `/fnl-setup add checks` and `checks.py`. `fnl-verification` stays as a thin alias through 0.2.x, user-invoked only so it never competes for model triggers, and is removed in 0.3.0.

## What ships

1. **The rename.** `skills/fnl-checks` holds the content of `skills/fnl-verification`, its scripts and their copy groups; every reference in the plugin names fnl-checks; `skills/fnl-verification/SKILL.md` becomes a thin alias naming fnl-checks as its dependency, as `fnl-ask` does for `fnl-help`. The `description` gains the CI triggers and gets a trigger check. Scripts other skills copy keep their file names, so only paths and copy groups change.
2. **A check list per repository.** `/fnl-setup add checks` (a setup feature, `references/features/checks.md`) reads what the repository already has, without running it: the `run:` steps of its CI workflows, scripts in `package.json`, test settings in `pyproject.toml`, `Makefile` targets. It proposes an ordered list of checks, each a fixed command the user can read, shows it, and writes it only after a neutral yes into the repository's entry of `## Project settings` in the canonical host config (never a file the repository controls, so a pull request cannot change what runs on the user's machine). A command is stored as an argument list, never run through a shell.
3. **One command.** `checks.py run [--changed] [--base <ref>]` runs the stored list in order through `heavy_run.py`, stops at the first failure and prints which check failed. `--changed` keeps only the checks whose scope the change touches, using `select_tests.py` for Python test modules and running the rest whole. It never edits files and makes no network call. `checks.py show` prints the list.
4. **An optional pre-push hook.** Setup offers, as its own neutral question, to install a git `pre-push` hook in the repository's own `.git/hooks` that runs `checks.py run --changed`. It is the user's own git hook, not a plugin hook: it is installed and removed by a script with a preview and a backup, and an existing hook is never overwritten without a second yes. `git push --no-verify` still bypasses it, and setup says so.
5. **A cheaper cloud workflow.** `references/ci.md` in fnl-checks describes, and setup can write after a previewed yes, a workflow that runs on pull requests rather than every push, cancels a run superseded by a newer push (`concurrency` with `cancel-in-progress`), skips changes that touch only documents (`paths-ignore`), caches dependencies, and runs the whole suite on a schedule rather than on every change. Writing CI configuration is a shared repository setting, so it is never done during an away lease (a stop category in `docs/specs/away-decisions.md`).
6. **What the minutes cost.** `checks.py usage --from <file>` summarises runs, minutes and the share spent on document-only changes from a JSON file the agent produced with the host's own command (for GitHub, `gh run list --json`), so the script itself makes no network call. The plan's limit is a number the user gives in setup; the plugin never assumes one.
7. **When cloud CI cannot run.** Setup offers, per repository and as its own neutral question with what could go wrong stated, a mode where a passing `checks.py run` at the pull request's head writes a local receipt. `merge_check.py` then reports `checks: local receipt (<head>)` instead of `checks: all passed`; with the mode off, a missing cloud check still blocks as today. The receipt proves only that the user's machine ran the list at that head; it is self-reported, so the mode is meant for a repository one person works on, and setup says that it gives a reviewer nothing they can check.

## What enforces what

- Scripts: the stored list and its argument form, the preview and digest before any write, `heavy_run.py` serialising heavy checks, the receipt being bound to the head, `merge_check.py` naming a local receipt as such.
- The user's own git hook (when installed): running the checks before a push.
- Agent judgment, advisory: choosing what goes into the list, offering the cheaper workflow, running `checks.py run` before a push when no hook is installed.

## Limits

- A list built from a repository's files can miss a check the CI runs through a reusable action or a service container; the preview names every source it read so the user can add what is missing.
- A local pass on one machine does not prove the same result on another operating system.
- The plugin does not read a hosted plan's billing; it counts minutes from runs the user can already list.

## Open decisions

| Decision | Owner | What unblocks it |
| --- | --- | --- |
| Whether `--changed` should also narrow non-Python checks (for example by package in a monorepo) | owner | real use on a second language |
| Whether the local-receipt mode may also apply when the cloud check is merely slow rather than unavailable | owner | a preference |

## Evidence

None yet. A build needs a red test per behavior: the rename and the alias (counts, map, copy groups), list detection from each source without running anything, the stored argument form and its refusal of shell strings, preview and digest before any write, `checks.py run` order, stop on failure and `--changed`, the hook install and removal with backup and no silent overwrite, the workflow writer's preview, `usage` from a fixture file, the local receipt bound to the head and `merge_check.py` reporting it, and the mode off by default.
