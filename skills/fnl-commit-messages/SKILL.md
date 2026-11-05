---
name: fnl-commit-messages
description: Shape commits, branches and their messages. Use when staging changes, writing a commit subject or body, splitting work into commits, committing on behalf of a delegated run, creating or naming a branch, syncing a branch with its base, resolving merge conflicts, merging a pull request and cleaning up its branch, backporting a fix to a release branch, or writing a pull request description.
---

# Commit messages

## What goes in a commit

- **Atomic**: one logical change per commit, buildable on its own where the project expects that. Split unrelated edits; keep a change and its tests together. One commit holds one whole seam, not one file or one edit, so neither split a seam into fragments nor merge unrelated seams into one.
- Stage explicit paths. Leave out secrets, env files, credentials, and incidental build, cache or tool output. Generated files that the repository tracks are regenerated and verified the way the repository prescribes.
- Dependency changes pin versions and include the lockfile.
- Preserve other people's uncommitted work: commit only what this task changed.

## The message

- **Subject**: imperative and verb-led (`Add`, `Fix`, `Remove`, `Rename`), about 50 characters, no trailing period. It completes "This commit will …".
- **Attribution**: a commit holding another agent's accepted work says so in its body, for example "Written by <agent> from a coordinator brief; checked by the coordinator."
- **Body** when the why is not obvious: the reason, the consumer impact, and any follow-up, in about six lines or fewer, wrapped at about 72 columns; never a list of the files changed or a retelling of the diff. Reference task or issue IDs the project tracks.
- Follow a convention the repository already uses (for example Conventional Commits) over this default.
- End with the attribution trailer the host asks for, exactly as given, and only that one.

## Interrupted work

When committing a stopped run's work on its behalf, mark it in the subject (`WIP: <task label> …`) so the next writer sees the state.

## Branches

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged.

Trunk-based: the default branch stays releasable, and every change reaches it through a short-lived branch and a pull request. A branching scheme the repository already documents wins over this default.

- **Start**: commit on a branch of your own. Fetch, then cut it from the tip of its base: the default branch, or `release/X.Y` for a fix to an older line (`git switch -c <name> --no-track origin/<base>`). Parallel runs get one worktree and branch each (`fnl-delegate` "Parallel dispatch"); a feature has one implementing checkout (`fnl-delegate`'s `references/coordinator-sessions.md`, "Checkouts and writers").
- **Name**: `<type>/<task>` in lowercase kebab case, with a type from `feat`, `fix`, `docs`, `chore`, `refactor`, `hotfix`, and the task ID where the project tracks one (`fix/142-parser-null`). A branch the host names for its own worktree keeps that name.
- **Lifetime**: days, not weeks. Split a larger change into pull requests that each leave the base releasable.
- **Sync**: bring the base in before opening the pull request and whenever it changed the files you touch. A local branch you have not pushed yet: rebase onto `origin/<base>`. A pushed branch: merge the base into it, so its published history stays as others fetched it; rebasing it needs authority ("Authority" below) and then `git push --force-with-lease=<branch>:<sha> --force-if-includes`, where `<sha>` is the remote head you rebased from. Use the host's sync tool where it offers one for its worktrees.
- **Conflicts**: resolve them on the branch. Read both sides and keep each one's intent; where the intents contradict, stop and ask whoever owns the other change. Rerun the targeted tests (`fnl-verification`); the resolution is part of the change the reviews cover.
- **Default branch rules**: a ruleset or branch protection on the default branch is the merge path: changes arrive by pull request with its required checks and reviews, without an administrator bypass unless the owner allows one and records why (`fnl-open-source-review`). An agent never uses a bypass, even when its login holds one. A rejected direct push means: open a pull request.
- **Merge**: through the pull request, after the merge check (`fnl-review-gate` "Pull requests"), with a method the repository allows; prefer a merge commit, which keeps each commit as written. Pin the merge to the reviewed head so a later push cannot ride along: `gh pr merge <number> --merge --match-head-commit <sha>` on GitHub.
- **After merge**: whoever merged deletes the head branch on the forge (`--delete-branch`, or the repository's automatic deletion) only when that agent or its runs created it and no running session or run uses it. Remove only worktrees (`git worktree remove <path>`) and branches this agent or its runs created, and only when no running session or run uses them; delete a local branch with `git branch -d`, and use `-D` only with the owner's go.
- **Hotfix and backport**: fix on the default branch first, then for each supported older line cut a branch from `release/X.Y`, apply the fix with `git cherry-pick -x <sha>` and open its own pull request. A fix that applies only to the older line starts on that line. Create `release/X.Y` from the latest tag of that line (the highest `vX.Y.Z`) when an older line first needs a fix; tags follow `fnl-versioning` "Tags".

## Authority

Committing locally is part of the task when the task calls for it: commit when a seam is done and its targeted tests pass, always on a branch of your own and never on the default branch, and without pushing. Pushing, force-pushing, rewriting published history, merging and opening or merging pull requests need explicit authority.

## Pull request descriptions

When `pr` from [mattpocock/skills](https://github.com/mattpocock/skills) is installed, let it shape the body and keep the verification and review-status lines below.

Summary of the change, how it was verified (commands and results), what was not verified, and the review status (`fnl-review-gate`), each in one to a few lines. Do not copy the changelog entry: `CHANGELOG.md` is the one place that records a public change. End with the attribution line the host asks for.
