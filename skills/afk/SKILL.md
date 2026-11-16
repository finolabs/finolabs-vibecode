---
name: afk
description: Start a time-boxed standing mandate so the host agents keep working while the user is away from the keyboard, and stop it on return. Run when the user asks for afk, away mode, work while away, or to stop the mandate on returning.
disable-model-invocation: true
argument-hint: "[start|stop]"
---

# afk: start or stop an away mandate

Dependency: `delegate`. <script> is <delegate folder>/scripts/afk.py; if it is absent, report the missing dependency and stop. It classifies requests, keeps the lease and the log, executes nothing and makes no network call. What `check` allows in each mode is [references/rules.md](references/rules.md), the output of `afk.py rules`; read it, never restate it.

Talk to the user in the language they are using, options included; keep commands, flags, paths and skill names unchanged (advisory (agent judgment)).

## Start

1. Run only on the user's invocation; no argument means `start`. Run `python3 -I <script> start` and report its summary: the mode first, the guards, the lease length and the `This folder` line. It needs a recorded `## afk` section (`/setup add afk`; a `strict` one also needs a Merge answer). One lease covers every session on the machine: when one is live, `start` says when it ends and changes nothing, and this session works under it.
2. `open` (the default) lets everything run except the credential floor and the guards that are on; `strict` keeps the lists, categories, limits and gates. A repository's approved settings win in that repository; read `python3 -I <script> effective` there before choosing tasks or authors (script for `check`; following the view is advisory (agent judgment)). Never extend the lease or change setup while away: `check` denies everything after a setup change.
3. Keep the session working (advisory (agent judgment)): the lease bounds actions and starts no turn. Before the user leaves, print one goal for the host's goal command (`/goal`), worded so it can finish while they are away, such as "every listed task is merged or parked, or the lease has ended". While work waits on CI, reviews or a delegated run, start a self-paced loop where the host allows it (`/loop` on Claude Code) and stop it when `check` prints an `end` line.
4. Never ask or wait for the user while the lease is live: settle questions through "Decide". On Claude Code the away question gate denies the question tool (hook); elsewhere this is advisory (agent judgment).

## Work inside the lease

Load [references/lease-rules.md](references/lease-rules.md) when the lease starts and follow it for every action until it ends (advisory (agent judgment); `check` enforces [references/rules.md](references/rules.md)).

## Decide

Load [references/decide.md](references/decide.md) for every decision you would otherwise ask the user: the checks against "Where it must stop", the precedent packet, the ladder (a recorded rule, the evaluation table, the advisor, the host) and one `log --kind decision` record per attempt. The ladder is advisory (agent judgment); the record, the packet caps and the command forms are script-enforced. A decision grants no authority: the chosen action still passes `check`.

## Merge gate

Before any merge, load [references/merge-gate.md](references/merge-gate.md) and merge only when it holds (advisory (agent judgment), with the enforcers it names).

## Stop and return

On the user's return or `stop`, run `python3 -I <script> stop` and report it. List first every merge that used the same-family fallback, then parked work, decisions and delegated runs still waiting; record running delegates as orphaned and leave them to the user. List the decisions from your `log --kind decision` records, those with `--precedents 0` first, and ask the user to mark each `kept` or `reversed`; record each with `python3 -I <script> review --decision <id> kept|reversed` (script: the id must exist) and write each reversal back as a decision with the user's reason through `tidy` (advisory (agent judgment)).

No plugin-run loop, scheduler, notice hook or host backstop ships; following this procedure is advisory (agent judgment), backed by the script and the merge gate.
