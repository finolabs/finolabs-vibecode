---
name: fnl-checks
description: Verify before claiming or accepting work. Use when an agent or session reports a task done or tests passing, when choosing which tests to run after a change, when deciding whether a full suite is needed, before heavy container-backed or end-to-end runs, before saying anything is done, fixed or passing, and when CI is red or slow, CI minutes or quota run out, or a repository needs checks set up to run locally or in CI.
---

# Checks

A report is a claim. The diff and the test output you read yourself are the evidence.

Pairs with `tdd` and `diagnosing-bugs` from [mattpocock/skills](https://github.com/mattpocock/skills), which produce the red and green evidence this skill reads.

## Choose the tests

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged.

- Run the **targeted tests** at checkpoints, not after every edit: those covering the changed code and its traced consumers, plus the project's lint and unit checks for those packages. Pick them from the diff (packages, test name patterns, the end-to-end suite only when the user-facing path changed). Say when no test covers the change; when that change alters runtime behavior, name the gap and propose a test rather than skip it. Advisory (agent judgment): `<this skill folder>/scripts/select_tests.py [--base <ref>]` lists the test modules that name a changed file.
- Run a **full suite** only when the owner asks. Gates and pull requests use targeted tests; CI runs the rest after an authorized push. When the change touches widely shared code whose consumers you cannot trace in full, propose a full suite and wait for the owner's yes.
- Keep local fixtures small (about 1,000 items) unless the owner asks for larger stages.
- **Heavy jobs** (container-backed suites, scale measurements, end-to-end runs) run one at a time per machine through `fnl-delegate`'s `heavy_run.py` (it also waits for load and free memory); without it, run one at a time yourself and start only when the one-minute load average is below 12. Run at most two test modules per command. Light targeted runs may overlap. Keep the machine awake for long runs.

## Read the evidence

- Read the output, not the exit code alone: count what ran, what skipped and what was filtered out. A skipped or partially green run is not a pass.
- Missing setup, a missing API or credential is not a behavioral pass: report it as blocked.
- Enabled configuration, a tool's DONE, a tick in a task list or a moved HEAD is not proof of behavior.
- For queries, reports, infrastructure changes and forecasts, a run that completed is not proof the result is right: see `fnl-coding-router` `references/non-code-work.md`.

## Bind proof to final bytes

Evidence belongs to the exact revision, contracts, dependencies, configuration and environment it ran on. A later change invalidates only the evidence it affects; rerun those checks and keep the required final ones.

Report each check as **PASS**, **FAIL**, **PENDING**, **SKIP**, **WAIVED** (with who waived it and why) or **N/A**. Only the owner waives a check; an agent proposes the waiver with its reason and leaves the check **PENDING** until the owner agrees, unless the project's rules already waive it.

`run_env.py` is the only way the plugin starts a delegate or test command: it builds an allowlisted
child environment, shared with `delegate_env.py` and `verify_claim.py` (script-enforced).
For a manual targeted test: `python3 -I <this skill folder>/scripts/run_env.py -- <test argv>`.
The quota probe and `ps` snapshot keep their own scoped allowlists under the `CLAUDE.md` exceptions.
Never print, dump, log or assert on the process environment; test synthetic mappings and key names only.

## Accepting someone else's work

The coordinator checks the branch and base, every hunk's acceptance-criterion trace, and the targeted test output before accepting a delegated report (advisory, agent judgment). Run the self-contained command:

```text
python3 -I <this skill folder>/scripts/verify_claim.py --brief <json> --base <full commit id> --head <reported full commit id> --ledger-id <dispatch id> --checkout <task checkout> --requests-out <new private local file>
```

The JSON brief is an explicit execution contract approved by the coordinator (advisory, agent judgment): `scope` is a list of relative file names or glob patterns; `tests` is a nonempty list of argv arrays, never shell command strings; `criteria` is a list of objects with identifiers `C1` through `C9999` and an English `question`. For example:

```json
{"scope":["src/parser.py","tests/test_parser.py"],"tests":[["python3","-I","tests/test_parser.py"]],"criteria":[{"id":"C1","question":"The supplied evidence shows the parser rejects empty input."}]}
```

List whole test modules and their traced consumers; never list a full suite (advisory, agent judgment). The script refuses shells and full-suite discovery, runs exactly the listed argv arrays with no shell, limits each command to 300 seconds and 64 KiB combined output, and kills the process group when it ends. The coordinator confirms that any custom test command is targeted; a script cannot infer its coverage (advisory, agent judgment).

`verify_claim.py` checks the reported head, ancestor base, clean checkout before and after testing, changed-file scope and test exits. It prints `PASS`/`FAIL` plus the evidence, then writes a metadata-only `verify` receipt through `record.py` (script-enforced). Exits: 0 for passing mechanics, 1 for failed mechanics, 2 for invalid input or unavailable evidence/storage. Exit 0 grants no acceptance. The receipt holds head, checkout hash, test/mechanical results, an evidence-packet digest and each criterion's identifier, answer, source and fallback flag; no criterion text,
commands, output or paths.

For a criterion comparing two documents, use `{"id":"C2","documents":[{"path":"docs/first.md","question":"The document states the reset interval is fifteen minutes."},{"path":"docs/second.md","question":"The document states the reset interval is fifteen minutes."}]}`. The coordinator splits the criterion into equivalent positive statements per document (advisory, agent judgment); the script reads each independently at the reported head, asks once per document and compares answers in code. Both must be `yes` for support; either `no` is reported as `no`, otherwise
`insufficient`. Two `no` answers never prove agreement.

Read [references/judgments.md](references/judgments.md) for each semantic check, host-answer completion, fallback and validation.

After the coordinator decides to accept, `fnl-delegate`'s `ledger.py finish --outcome accepted --checkout <task checkout>` requires a passing receipt for that checkout's current head (script-enforced).
`verify_claim.py` verifies an implementation head and its test receipt; it does not read the dispatch kind. A review dispatch has no implementation head to verify, so `ledger.py finish` refuses `--head` for it and refuses `accepted` without a passing receipt (script-enforced); that refusal is expected, not a defect. After reading the posted marker, accept the review dispatch with `--accept-unverified --reason <text>` (advisory, agent judgment). The ledger logs and counts this escape hatch, storing only the reason's digest; keep the full reason in the coordinator report.
This gate covers delegated work in the ledger only; the coordinator's own work stays under the review gate and an agent bypassing the ledger is not blocked.

## Claims

State what was run and what it showed. Distinguish drafted, verified, integrated, delivered and parked. Verification grants no publication, push or deploy authority.
