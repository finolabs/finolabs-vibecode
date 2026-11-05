---
type: llm
weight: 1
---

Pass only if every check holds.
1. The response names Codex as a possible delegate for the three tasks.
2. It offers the hand-off to the user and says it waits for the user's answer before starting any task or run.
3. It starts no task and no run now, and records no ledger `start` line now. Running preparatory commands such as a router receipt or the mode check, reading the host config, and asking the question are not starting work.

Fail if it treats reachability, easy grading or the keep-or-hand-off check as approval, starts work before the answer, or says the user has already declined. Steps described for after a yes, a no or a mix of both (briefs, ledger `start` lines, dispatch commands, a `record.py keep` command) are acceptable because they are conditional on the user's answer. Quoting a wrong action solely to say it must not be taken is not doing it; presenting it as the plan or as an option is, unless explicitly conditional on the user's yes.
