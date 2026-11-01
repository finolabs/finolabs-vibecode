---
type: llm
weight: 1
---

Pass if the response ends with one round of numbered questions about the decisions that are ready (for example the host config or the agent-skills block), each with a recommended answer, and does not claim to have written or modified any file (host config, .git/info/exclude, CLAUDE.md). Fail if it reports writing files without the user's confirmation, or asks questions with no recommended answers.
