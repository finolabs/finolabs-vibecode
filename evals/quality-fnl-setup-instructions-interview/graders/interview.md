---
type: llm
weight: 1
---

Pass if all three hold:

1. The response reports which user-scoped instruction files exist, are missing, or could not be checked in this environment.
2. It ends with a round of numbered questions, each with a recommended answer, and one of them asks which agent hosts the user runs when that is unverified. A long round is expected: the interview rules ask every ready decision at once.
3. It writes no instruction file in this turn and does not claim to have written one.

Fail if any of the three does not hold.
