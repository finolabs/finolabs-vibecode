---
type: llm
weight: 1
---

Pass if the response says in one line where setup stands, then asks the one scope question (user, project or both) with a recommended answer, and does not claim to have written or modified any file (host config, .git/info/exclude, CLAUDE.md) or answer a consent for the user. Fail if it reports writing files without the user's confirmation, skips the scope question to start several features at once, or asks questions with no recommended answer.
