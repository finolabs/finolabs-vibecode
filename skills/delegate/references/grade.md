## Grade

Kind: `implement`, `review`, `advise` or `committee`.

Difficulty:

- **easy**: one file or seam, a known pattern, about 20 minutes of work.
- **medium**: several files in one seam, new tests, consumers known.
- **hard**: cross-cutting change, concurrency, security or permissions, migrations, subtle bugs, or a medium task that already failed once.
- **very hard**: novel design, high ambiguity, many interacting parts, or work that keeps needing judgement drawn from the coordinator's own context.
- **ultra hard**: very hard work where a wrong result is costly or hard to undo (production data, a migration, a security boundary), or very hard work that a `high` run already fell short on.

### Decision matrix

The grade fixes the rest of the plan; later sections say how to carry it out.

| Grade | Tier | Effort | Budget | Runs as | Accepted by |
| --- | --- | --- | --- | --- | --- |
| easy | fast | `medium` | 20 minutes | headless run | the coordinator |
| medium | strong | `medium` | 30–45 minutes | headless run | the coordinator |
| hard | frontier, or strong for implementation with clear acceptance tests | `medium` | 60–90 minutes; split a task that needs more | headless run | the coordinator with `verify_claim.py` |
| very hard | frontier | `high` | 90 minutes per headless sub-run | a session, not a headless run | the coordinator with `verify_claim.py` |
| ultra hard | frontier | `xhigh`, then `max` if `xhigh` falls short | 90 minutes per headless sub-run | a session, not a headless run | the coordinator with `verify_claim.py` |

A run that fell short at its level is retried one level up; the host config may set its own effort preference; `models.md` maps each level to every agent's own scale. A review, an advice or a committee seat takes its tier from the work it covers (Route, step 1) and its budget from "Budget and liveness".
