---
type: llm
weight: 1
---

Pass only if the response keeps all three tasks without dispatching or offering a hand-off, and gives a `record.py keep` command accounting for all three with `--reason user-choice` and `--route-by user`. A closing note that the user may ask for a hand-off, with no question or request for approval, is not an offer. Fail if it offers delegation, asks for hand-off approval, dispatches anything, uses an advisor or judge to override manual mode, or records the kept tasks only in prose.
