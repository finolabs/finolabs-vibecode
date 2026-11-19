# Architecture checkpoint

Detail behind `SKILL.md` "Checkpoint: stop repeated local fixes". Read it when one of the stop conditions listed there fires.

Keep the implementation task open and the latest behavioral red as it is, stop product edits, and run a read-only architecture checkpoint: map each layer's owned state, whether it is authority or cache, its revision, its triggers and its stale readers. Separate safety, visibility truth, staleness, monotonicity, idempotency and coalescing. Choose one authoritative boundary or a versioned snapshot.

Resume only with a deterministic root-cause test and a coherent design. Ask "which distinct failure does this action prevent?" of every proposed step.

When the checkpoint leaves the cause open, propose a committee through `advisor` and wait for the user's yes: it spends the quota of two model families.
