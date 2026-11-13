# Release 0.2.6: scope

Status: in progress; the release pull request moves the changelog under 0.2.6; pull requests 270 and 272 merged before it; a real upgrade from 0.2.5 on a user's machine remains unverified.

## What shipped

| Pull request | Change |
| --- | --- |
| 263 | `afk.py check` lets an install that is the main checkout remove a merged linked worktree; `git worktree` no longer counts as changing the install's own work tree. |
| 264 | The README opens as a landing page; the banner is the new social preview. |
| 265 | `afk.py log --kind merge --pr <number> --head <sha>` is bound to an allowed `gh pr merge --match-head-commit` check of the live lease; a merge check's number takes the ASCII grammar of `log --pr`. |
| 266 | The `setup` beginner path asks only the essentials; the data root move, the agent scan, the notes read-back, hiding local files, companions, extras and the instructions offer wait for a later run or `add <feature>`. |
| 267 | Breaking: `## Agent roles` is no longer read; the assignment matrix is the only source of review roles and the judge. `/setup add delegation` converts the section with `matrix_setup.py migrate` and asks consent again. |
| 268 | `plugin-packaging` ships a README standard and checklist with `readme_check.py`; `versioning` and the release checks run it before a release. |
| 269 | `afk.py check` adds a fixed `end` line for a missing, expired, stopped or exhausted lease, telling the agent to stop its loop; spent runs or runtime answer `exhausted` instead of `limit`. Breaking for scripts that match `limit`. |
| 270 | `/setup add afk` asks first whether the rules are for the account or only this repository, then for a repository only the rules that differ. |
| 271 | `readme_check.py` blanks README comments only outside code. |
| 272 | Agents never wait for the user while an away lease is live. |

The changelog's 0.2.6 section holds the user-facing wording; `update` carries the 0.2.6 upgrade notes.

## Owner decisions (13/11/2026)

- `## Agent roles` is retired: the matrix is the only source of roles and the judge, and its consent is never inherited (`CLAUDE.md`, fourth scoped exception).
- Lease scope: direction 1 is chosen for 0.2.7.
- Under a live away lease agents never wait for the user; questions go up the decision ladder (`afk` "Decide").

Coordinator decision under the away mandate (14/11/2026, not the owner's; the owner reviews it on return): 0.2.6 stays a PATCH although it carries breaking entries, following the 0.2.5 precedent, because the upgrade notes are already keyed to 0.2.6 and 0.3.0 stays reserved for removing `## Agent levels`; the deprecation step for `## Agent roles` is waived, since the owner retired it outright on 13/11/2026.

## Breaking changes and the upgrade

A user with only `## Agent roles` loses review roles and the Jev judge until running `/setup add delegation`; the `0.2.6/agent-roles-retired` note names the step and `upgrade_state.py roles-retired` checks it. Scripts that match `limit` from `afk.py check` for spent runs or runtime must match `exhausted`. On Codex the changed session-start hook needs trust again (`0.2.6/codex-hook-trust`); the away question gate is a Claude Code hook only.

## Evidence method

The README's "Built with itself" counts come from `gh` over pull requests merged in this repository up to 13 November 2026 23:59 +07:00. A pull request counts as reviewed when it holds at least one `kind=code` and one `kind=security` review marker comment, and as sent back for rework when it holds at least one `verdict=REWORK` marker.

## Known follow-ups

- Pull requests 268 and 271 merged with no posted reviews; they count among the merged ones but not the reviewed ones.
- A lease scoped to one repository (direction 1, planned for 0.2.7).
- `post_review.py` is not an allowed wrapper in `afk.py check`.
- `skills/afk/SKILL.md` is over its size limit.
- `readme_check.py --help` is missing.
- The README's away-decision sequence and settings-scopes diagrams predate 0.2.6; their captions say so until they are redrawn.
