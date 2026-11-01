---
name: fnl-commit-messages
description: Shape commits and their messages. Use when staging changes, writing a commit subject or body, splitting work into commits, committing on behalf of a delegated run, or writing a pull request description.
---

# Commit messages

## What goes in a commit

- **Atomic**: one logical change per commit, buildable on its own where the project expects that. Split unrelated edits; keep a change and its tests together.
- Stage explicit paths. Leave out secrets, env files, credentials, and incidental build, cache or tool output. Generated files that the repository tracks are regenerated and verified the way the repository prescribes.
- Dependency changes pin versions and include the lockfile.
- Preserve other people's uncommitted work: commit only what this task changed.

## The message

- **Subject**: imperative and verb-led (`Add`, `Fix`, `Remove`, `Rename`), about 50 characters, no trailing period. It completes "This commit will …".
- **Body** when the why is not obvious: the reason, the consumer impact, and any follow-up, wrapped at about 72 columns. Reference task or issue IDs the project tracks.
- Follow a convention the repository already uses (for example Conventional Commits) over this default.
- End with the attribution trailer the host asks for, exactly as given, and only that one.

## Delegated and interrupted work

- Task sessions and delegated agents commit their own work, one commit per task or tight group, and report base and new SHAs.
- When committing a stopped run's work on its behalf, say so in the subject or body (`WIP: …` with the run's task label) so the next writer sees the state.

## Authority

Committing locally is part of the task when the task calls for it. Pushing, force-pushing, rewriting published history, merging and opening or merging pull requests need explicit authority. Work on a branch when the current branch is the default branch.

## Pull request descriptions

Summary of the change, how it was verified (commands and results), what was not verified, and the review status (`fnl-review-gate`). End with the attribution line the host asks for.
