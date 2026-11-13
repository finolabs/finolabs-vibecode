# Coordinator sessions

The session a spec starts in is its **coordinator**. It works at the level of spec and plan; each task runs in its own app session. Agent choice, briefs, budgets and acceptance follow `delegate`; this reference adds the session model around them.

## When to coordinate

Coordinate a feature that has three or more user stories, or ten or more tasks in total. A smaller one runs in a single session, because each extra session costs context and quota.

## Ownership

- **The coordinator owns** the Spec Kit artifacts (`spec.md`, `plan.md`, `tasks.md`, research and review records), task order, the review gate after each user story, and the PR. It writes no application code or tests, however small the edit, and commits the artifacts it changes.
- **Only the coordinator edits `tasks.md`**, including the `[X]` marks. A task session runs `speckit-implement` limited to its assigned task IDs and leaves `tasks.md` untouched, even where the skill says to mark tasks done.
- **One session per task.** Tasks of the current phase and story that edit the same files or must land in one commit go to one session together; grouping never crosses a story boundary.
- **Sessions own tasks.** A task or review is always an app session the coordinator starts. A delegated job or subagent never stands in as its owner; a session may delegate to Codex or Antigravity internally, but it still verifies and commits.

## Starting sessions

The app starts sessions only on a turn the user's own message began, never on one an automated event or another session began. So:

1. On each user turn, start the sessions the next stretch of work needs.
2. Before an unattended stretch, also start the sessions that follow as **standby**: the brief says to reply "Standing by" and wait. Prepare the next user story's sessions and one fix session, no further; the user sets the length of the stretch each time.
3. On a later automated turn, release a standby session with a message giving its base commit and any change to its brief.
4. Before opening a PR, keep or pre-start a standby fix session, so review findings that arrive on an automated turn have an owner.
5. With no fitting standby session, propose the session as a card and wait for the user.

## Checkouts and writers

- **One implementing session at a time** in the feature's implementation checkout. Every brief names that checkout by absolute path and branch; the branch follows `commit-messages` "Branches". The coordinator edits nothing while the session runs.
- **Read-only work** (reviews, measurements, lookups) runs beside an implementing session only in a separate worktree at a fixed commit, so its results belong to one revision. The coordinator creates that worktree and puts its path and commit SHA in the brief.
- **Task sessions commit their own work**: atomic commits per task or group. The report gives base and new commit SHAs, test output, uncommitted files and open points.
- **Handover between writers** follows the handover steps in `delegate` before another session gets write access.

## Briefs and acceptance

- Each brief is self-contained: task IDs, the checkout, the files, what done looks like, test-first where `tasks.md` says so, the constraints from `AGENTS.md`, a time budget, and what to report (`handoff` has the template).
- The coordinator verifies before marking `[X]`: it reads the diff and the test output itself (`checks`).

## Review gate

The next user story starts only after the story's code review, and a security review where triggered, are recorded and every blocking finding is fixed and verified. This holds even when two stories are independent: they run one after the other and never overlap, because the gate exists to stop work from building on a base nobody has confirmed. Reviews run in their own sessions; `review-gate` covers dispositions, regression tests and re-review.

## Titles and archiving

- Titles follow `<project> <scope>: <activity>` (`tidy` "Titles"): `Demo 003 search: coordinate US4` for the coordinator, `Demo 003 search: T044–T046 rebuild CLI` for a task session, `Demo 003 search: review US4` for a review session. The coordinator names each session it starts and renames itself and those sessions when a phase, story or task changes state. It renames no other session.
- Archive a task session once its tasks are verified and marked `[X]`, and a review session once its findings are disposed. The coordinator never archives itself.
