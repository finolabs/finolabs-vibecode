---
name: fnl-status
description: Show the state of delegated work from the dispatch ledger: runs still open, and first-pass acceptance, timeouts and fallbacks per agent, model and grade. Run only when the user asks for it.
argument-hint: "[--since YYYY-MM-DD] [--project <name>]"
disable-model-invocation: true
---

# Delegation status

Read-only. Requires the `fnl-delegate` skill installed beside this one. When it is missing, tell the user to add it (`npx skills add fioenix/finolabs-vibecode --skill fnl-delegate`, or install the whole plugin) and stop.

The ledger script is `scripts/ledger.py` in the `fnl-delegate` skill's folder, a sibling of this skill's base directory. It reads `ORCHESTRATION_LEDGER`, else `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode/ledger.jsonl`.

**Arguments:** $ARGUMENTS

## Steps

1. Run `python3 -I <ledger.py> open`; it prints each open dispatch's age against its budget. For each one past its check deadline (half the budget), check liveness from artifacts as `fnl-delegate` "Budget and liveness" says (process, log growth, new commits) and mark it **running**, **stalled** or **ended without a finish line**.
2. Run `python3 -I <ledger.py> summary` with the user's `--since` and `--project` arguments, defaulting to the last 14 days.
3. Read the `Review by` date (ISO, `YYYY-MM-DD`) at the top of `references/models.md` in the `fnl-delegate` folder. When today is past it, the capability map is stale: say so first, with the date, since routing still reads it.
4. Report in three parts:
   - **Open runs**: id, agent and model, task label, age against budget, liveness verdict.
   - **Routing table**: the summary rows, then one line per agent and model whose first-pass acceptance is low or whose timeouts or fallbacks are frequent, with the count behind it.
   - **Next actions**: stalled runs to stop and hand over, finish lines still missing (`ledger.py finish <id> …`), which the user or coordinator records, and a stale capability map to recheck.

The ledger holds only task labels and outcomes. When it is missing or empty, say so and point to `fnl-delegate` "Ledger" for how runs get recorded.
