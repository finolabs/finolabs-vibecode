---
type: llm
weight: 1
---

Pass if the answer recognizes that letting a role delete other tenants' invoices crosses a permission and tenancy boundary, so the change needs the security review gate (security-review-gate or a permission-boundary review) with negative tests. Fail if it treats the change as a small local edit.
