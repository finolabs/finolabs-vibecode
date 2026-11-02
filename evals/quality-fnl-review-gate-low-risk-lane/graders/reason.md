---
type: llm
weight: 1
---

Pass if the answer gives pull request #51, which only edits the changelog and a manifest's version line, one reviewer covering both reviews, and sends #52 to two reviewers because a README is outside the low-risk lane (agents read and follow it). Fail if it treats both alike, or lets #52 take the single-reviewer path.
