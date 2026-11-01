---
name: fnl-verification
description: Verify before claiming or accepting work. Use when an agent or session reports a task done or tests passing, when choosing which tests to run after a change, when deciding whether a full suite is needed, before heavy container-backed or end-to-end runs, and before saying anything is done, fixed or passing.
---

# Verification

A report is a claim. The diff and the test output you read yourself are the evidence.

## Choose the tests

- Run the **targeted tests**: those covering the changed code and its traced consumers, plus the project's lint and unit checks for those packages. Pick them from the diff (packages, test name patterns, the end-to-end suite only when the user-facing path changed). Say when no test covers the change.
- Run a **full suite** only when the owner asks. Gates and pull requests use targeted tests; CI runs the rest after an authorized push.
- Keep local fixtures small (about 1,000 items) unless the owner asks for larger stages.
- **Heavy jobs** (container-backed suites, scale measurements, end-to-end runs) run one at a time per machine under the lock in `fnl-orchestration`; light targeted runs may overlap. Keep the machine awake for long runs.

## Read the evidence

- Read the output, not the exit code alone: count what ran, what skipped and what was filtered out. A skipped or partially green run is not a pass.
- Missing setup, a missing API or credential is not a behavioral pass: report it as blocked.
- Enabled configuration, a tool's DONE, a tick in a task list or a moved HEAD is not proof of behavior.

## Bind proof to final bytes

Evidence belongs to the exact revision, contracts, dependencies, configuration and environment it ran on. A later change invalidates only the evidence it affects; rerun those checks and keep the required final ones.

Report each check as **PASS**, **FAIL**, **PENDING**, **SKIP**, **WAIVED** (with who waived it and why) or **N/A**.

## Accepting someone else's work

Before accepting a delegated run or a session's report, check all three:

- the commits sit on the branch and base the brief named, and nothing that belongs in them is left uncommitted;
- the whole diff is in scope, with no unrelated edits, secrets, env files or stray generated output;
- the brief's targeted tests, rerun by you, pass, and you have read their output.

A task is marked done only on this evidence.

## Claims

State what was run and what it showed. Distinguish drafted, verified, integrated, delivered and parked. Verification grants no publication, push or deploy authority.
