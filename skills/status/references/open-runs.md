# Open and stale runs

Detail behind `SKILL.md` step 3. Read it when step 3 reports open dispatches or `stale` lists records.

## Running block

In the `running` block of the generated `data.js` (the `now` tab), the script produces each open dispatch's age against its budget, the half-budget check deadline, an `unverified` liveness marker and family-level snapshot mismatch flags.

## Stale records

`python3 -I <ledger.py> stale` flags by default an open record past twice its budget and at least 24 hours; `--older-than-hours <n>` sets another threshold, never inside a budget.

It writes nothing to the ledger and lists each stale record with its id, age, label, what its run log's last line says and the outcome it would get; it covers only this repository's ledger project and refuses when none resolves (script-enforced); do not widen it with `--all-projects` to close other repositories' runs.

When it lists records, show the list and offer the one `stale --close --digest <digest>` command it prints; only after the user's yes run it (closing stays the user's step; the digest check is script-enforced, asking is advisory, agent judgment).

The session-start open count and `open` drop the closed records.
