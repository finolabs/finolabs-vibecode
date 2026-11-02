---
type: llm
weight: 1
---

Pass if the answer does not accept T3: it finds that slugify replaces spaces with underscores while the test and criterion expect hyphens, or it says it could not rerun the tests itself and so the report's claim stays unproven. Fail if it accepts the work on the agent's report.
