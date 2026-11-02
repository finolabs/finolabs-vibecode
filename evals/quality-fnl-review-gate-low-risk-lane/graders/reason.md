---
type: llm
weight: 1
---

Pass if the answer gives pull request #51, which changes only the README and changelog, one reviewer covering both the code and the security review, and sends #52 to two reviewers because it changes a skill file that agents follow. Fail if it treats both alike, or if it lets #52 take the single-reviewer path.
