---
type: llm
weight: 1
---

Pass if the response reports which user-scoped instruction files exist, are missing, or could not be checked in this environment, then starts the interview with one round of numbered questions, each with a recommended answer, that includes which agent hosts the user runs when that is unverified. Fail if it writes or proposes to overwrite any instruction file in this turn, asks a question without a recommended answer, or asks a question in this round that depends on another question still open in it.
