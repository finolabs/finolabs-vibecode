---
name: fnl-status
description: Show the state of delegated work from the dispatch ledger: runs still open, and first-pass acceptance, timeouts and fallbacks per agent, model and grade.
argument-hint: "[--since YYYY-MM-DD] [--project <name>]"
disable-model-invocation: true
---

# Delegation status

Read-only. The ledger script lives in the `fnl-delegate` skill of this plugin: `scripts/ledger.py` under the sibling folder `fnl-delegate` (one folder above this skill's base directory). It reads `ORCHESTRATION_LEDGER`, else `~/.claude/orchestration/ledger.jsonl`.

**Arguments:** $ARGUMENTS

## Steps

1. Run `python3 -I <ledger.py> open`. For each open dispatch older than its budget, check liveness from artifacts as `fnl-delegate` "Budget and liveness" says (process, log growth, new commits) and mark it **running**, **stalled** or **ended without a finish line**.
2. Run `python3 -I <ledger.py> summary` with the user's `--since` and `--project` arguments, defaulting to the last 14 days.
3. Report in three parts:
   - **Open runs**: id, agent and model, task label, age against budget, liveness verdict.
   - **Routing table**: the summary rows, then one line per agent and model whose first-pass acceptance is low or whose timeouts or fallbacks are frequent, with the count behind it.
   - **Next actions**: stalled runs to stop and hand over, and finish lines still missing (`ledger.py finish <id> …`), which the user or coordinator records.

The ledger holds only task labels and outcomes. When it is missing or empty, say so and point to `fnl-delegate` "Ledger" for how runs get recorded.
