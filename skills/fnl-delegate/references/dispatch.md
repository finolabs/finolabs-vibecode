# Dispatch mechanics

Procedures from `SKILL.md` that only some runs reach.

## Quota fallback

When a model's quota runs out, move to the next route the rules give: another model of the same tier on the same agent, then the same tier on the next agent in the capability order. Antigravity pools are separate, so one empty pool leaves its other models usable. Moving to a weaker agent at the same tier, split the task smaller. Moving up a tier spends more quota: ask first. Moving down a tier is allowed only for easy and medium work; for hard work, wait for the reset or ask. When every reachable agent is out, report the reset times and wait. Record the fallback in the ledger as `references/ledger.md` says.

## Parallel dispatch

- Size each run small: one task or a tight pair, budget up to 90 minutes. A long run holding many tasks is slower, bloats the agent's context and loses more when it breaks.
- Give each parallel run its own git worktree on its own branch, cut from the integration branch tip. One writer per worktree.
- Merge back one branch at a time into the integration branch, rerunning the targeted tests after each merge. Resolve conflicts yourself or brief a fix run.

## Heavy-job lock

Serialise heavy jobs with an atomic `mkdir` lock at the path the host config names:

```bash
until mkdir "$LOCK" 2>/dev/null; do sleep 15; done
echo "$$ <dispatch-id> $(date)" > "$LOCK/owner"
<heavy command>; status=$?
rm -rf "$LOCK"; exit $status
```

A lock whose owner process is gone is stale: confirm with `ps -p <pid>` (the first field of `owner`) before removing it.

## Handover after an interrupted run

When a run times out, fails or stops with uncommitted work, before any other agent gets write access to that checkout:

1. Confirm the process has stopped (`ps`, the run's exit status).
2. Capture its state in the briefs folder: `git status`, the diff saved as a patch, the last lines of its log.
3. Keep the work: commit it on the run's behalf as work in progress, or name the files in the next brief.
4. Write the next brief's "Current state" and "What was tried" from that capture.

## Where files go

Sort every file that delegation produces by who will read it:

- **Shared**: documentation, design notes and briefs with lasting value for the project's community or as future usage docs. Put them in the project's normal documentation folders (`docs/`, `specs/` or whatever the project uses) and commit them under the project's rules for public content.
- **Local**: logs, working notes, handoff briefs, captured state from interrupted runs; anything that only serves development on this machine. Put them in the hidden folder `.orchestration/` at the main checkout's root (`git rev-parse --path-format=absolute --git-common-dir`, then its parent): `briefs/` for briefs and notes, `logs/` for logs and final outputs. Keep it out of git with a local `.orchestration/` line in `.git/info/exclude`; the shared `.gitignore` changes only with the user's approval. The host config may name another durable local folder. Temporary directories and session scratchpads are wiped on restart, so never keep briefs there.

When unsure, treat a file as local; promoting it to shared later is a deliberate edit and commit.
