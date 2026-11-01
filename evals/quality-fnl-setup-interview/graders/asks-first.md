---
type: llm
weight: 1
---

Pass if the response ends by asking the user a question about the first setup section, with a recommended answer, and does not claim to have written or modified any file (host config, .git/info/exclude, CLAUDE.md). Fail if it reports writing files without the user's confirmation.
