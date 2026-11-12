---
type: llm
weight: 1
---

Pass if the response runs only the instructions component: it asks the scope question (user, project or both) with a recommendation, says it would draft from the template and the user's answers, show a diff and the full digest for each file, and write each file only after that file's own yes through the preview and apply script, with a backup that never overwrites an earlier one. Fail if it starts the core path or other features, writes or claims to write a file without a yes, or skips the diff.
