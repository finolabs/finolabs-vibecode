# Keep receipt

`scripts/record.py keep` is `SKILL.md` "Keep or hand off" for tasks you keep. It writes nothing to the ledger: it prints one line, and with usage metrics on the hook stores the count, the reason and who settled it as a `kept` event, under the same consent, retention and purge as other events. `--tasks` is how many tasks you kept for this reason, and `--reason` is one of:

- `needs-context`: finishing needs this conversation's context.
- `brief-costs-more`: writing and checking the brief would cost more than the work.
- `hard-grade`: graded hard or above, which load sharing leaves on its route, and the route landed here.
- `no-delegate`: no delegate is reachable, allowed by the project rules, left with quota, or allowed to receive these files.
- `never-delegated`: the work is on the "Never delegated" list.
- `user-choice`: the user said to keep it, declined the offer, or set the delegation mode to `manual`, with `--route-by user`.

`--route-by` says who settled it, as on `start`: `table` on a host whose config names a route judge shows the judge was not asked.
