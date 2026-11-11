# Release 0.2.5: scope

Status: in progress; all three packages are built on the main line or a branch for review; a real upgrade from 0.2.4 on a user's machine remains unverified.

## Rule (owner decisions, 2026-11-11)

User-scope data lives in the data root, `~/.finolabs/vibecode/` by default. Project-scope data lives at the same relative path inside the project, `<main checkout>/.finolabs/vibecode/`, shared by linked worktrees. Per-repository data does not belong in the shared `host.md`, which every agent reads before dispatching. A file inside the repository counts only while its exact bytes match a SHA-256 approved in the data root's private state folder, so a branch or a pull request cannot change what it says.

## Scope

| # | Package | What it covers |
| --- | --- | --- |
| 1 | The check list moves | A repository's check list moves from `## Checks` in `host.md` to `checks.json` in its project folder, with an approved digest and no legacy fallback. Spec: `checks.md` ("Storage"). |
| 2 | Validated identity | `project_store.layout` accepts a linked worktree only in the canonical layout `<main>/.git/worktrees/<name>` outside the checkout, its `commondir` resolving to that `.git`, its `gitdir` pointing back to this checkout's `.git`, and every metadata file and folder walked owned and not group- or world-writable, as `git_metadata.git_dirs` does; anything else resolves to the checkout's own root, and the exclude line is written only to `<main>/.git/info/exclude`. `project_progress.repository_code`, `parallel_slots.repository_code` and `checks_list.layout` share it, so a checkout cannot borrow another repository's code, check list or settings. Codes of real repositories and real linked worktrees are unchanged. |
| 3 | Project settings move | `ledger`, `tasks`, `parallel`, `parallel-caps` and the dashboard `label` move from `## Project settings` and `## Project labels` in `host.md` to `settings.json` in the project folder, closed schema, approved digest in `<data root>/state/settings-approved/`. The host sections and the global `Ledger project:`/`Task file:` lines are no longer read, with no fallback and no migration command. Spec: `project-progress.md` ("Project settings file"), `parallel-instances.md`. |

## What enforces what

- Scripts: `project_store.py` (shared copies registered in CI) for the identity, the project folder's no-follow, owner-checked reads, the closed schema, the approval and the exclude line; `project_progress.py` for the setters, the consent rule for `ledger` and `tasks`, and the readers; `parallel_slots.py` for the capacity reader; `checks_list.py` and `checks_setup.py` for the check list.
- Agent judgment, advisory: telling the user to set settings and labels again after the upgrade, and deleting the old `host.md` sections by hand.

## Breaking changes and the upgrade

Settings, labels and check lists saved in `host.md` with 0.2.4 or earlier are no longer read. The 0.2.5 upgrade notes in `fnl-update` ask the user to run `/fnl-setup add checks`, `/fnl-setup add project` or `/fnl-setup add delegation` again in each repository where they changed something, then delete `## Checks`, `## Project settings`, `## Project labels` and the global `Ledger project:` and `Task file:` lines from `host.md` by hand. Unset means the safe defaults: no checks with the receipt mode off, `parallel` 3 with no caps, the folder name as ledger name, no task file and the registered folder name as label.

## Limits

- The dashboard shows a user label only for the repository it runs in; other repositories show their registered folder name, because their settings live in their own folders.
- `fnl_metrics.repo_code`, the metrics identity, is not changed by this release; for a real repository and a real linked worktree it gives the same code. It still accepts nonreciprocal worktree metadata, so a crafted `.git` file can attribute metrics events to another repository's code; validating it like `project_store.layout` is deferred to a later release (security review finding 4 on the 0.2.5 pull request). It selects no settings, checks or limits.

## Evidence

Built test first. Package 2: a real `git worktree add` keeps the main checkout's code; a reciprocal layout without git keeps it; a mismatched back-pointer and fake metadata folders (inside the checkout, beside it, or naming another repository's common folder) fall back to the own root; such a checkout cannot read another repository's approved check list; a reciprocal pair under a common folder not named `.git` keeps its own code, settings, check list, receipt mode off and writes no exclude line elsewhere; group- or world-writable metadata files and folders fall back to the own root. Package 3: two repositories keep separate files; a linked worktree uses the main checkout's file; `## Project settings`, `## Project labels` and the global lines left in `host.md` are never read; an unapproved or branch-supplied file cannot raise `parallel` or redirect `tasks`; an approved file that gains a byte, is deleted, unreadable, unsafe or approved but malformed makes capacity unknown (exit 3, never available) and the ledger join unknown, never joined under the folder name; `host.md` stays byte-identical after every setter; the defaults hold when nothing is set; the session-start line and the dashboard work with no repository root and with an unset file. Covered by `tests/test_project_progress.py`, `tests/test_parallel_slots.py`, `tests/test_checks_setup.py`, `tests/test_refresh.py`, `tests/test_session_start.py` and `tests/test_checkup.py`.
