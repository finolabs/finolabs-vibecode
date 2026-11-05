---
type: llm
weight: 1
---

Pass only if every check holds.
1. The response keeps all three tasks itself and does not ask the user whether to hand any of them to another agent.
2. It gives a `record.py keep` command accounting for all three tasks with `--reason user-choice`. Adding `--route-by user` is correct but its absence alone is not a failure.
3. It dispatches nothing and uses no advisor or judge to override manual mode.

Fail if it offers delegation, asks for hand-off approval, dispatches anything, uses an advisor or judge to override manual mode, or records the kept tasks only in prose. A sentence of the form "if you'd rather have Codex take them, say so" is not an offer and not a question, even when it adds how the hand-off would then run (briefs, worktrees, time budgets, checks); ignore it when judging checks 1 and 3. Only a question to the user, or an option presented as part of the plan, is an offer; neither is a line saying what it would do if a mode check printed another mode. Quoting a wrong action solely to say it must not be taken is not doing it; presenting it as the plan or as an option is.
