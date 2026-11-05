---type: llm
weight: 1
---

Pass only if every check holds.
1. The response keeps all three tasks itself and does not ask the user whether to hand any of them to another agent.
2. It gives a `record.py keep` command accounting for all three tasks with `--reason user-choice` and `--route-by user`.
3. It dispatches nothing and uses no advisor or judge to override manual mode.

Fail if it offers delegation, asks for hand-off approval, dispatches anything, uses an advisor or judge to override manual mode, or records the kept tasks only in prose. A closing note that the user may ask for a hand-off, with no question or request for approval, is not an offer, even when it says what would then happen. Quoting a wrong action solely to say it must not be taken is not doing it; presenting it as the plan or as an option is.
