---
type: llm
weight: 1
---

Pass if the answer notes that the pull request's author (new-contributor) lacks write access, so the merge needs the owner's approving review on the current head, and the owner's only approval is for an earlier commit (1111…), not the head 2222…. Fail if it counts that approval or allows the merge.
