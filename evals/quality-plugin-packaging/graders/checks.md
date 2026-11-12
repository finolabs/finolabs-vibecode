---
type: llm
weight: 1
---

Pass if the answer names one version source of truth with the other manifests checked against it (for example in CI), AND names host validators such as `claude plugin validate` and `agy plugin validate`, AND mentions testing that skills trigger (for example an eval suite). Fail if two of these three are missing.
