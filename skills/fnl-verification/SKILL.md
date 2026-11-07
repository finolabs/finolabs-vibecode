---
name: fnl-verification
description: Verify before claiming or accepting work. Use when an agent or session reports a task done or tests passing, when choosing which tests to run after a change, when deciding whether a full suite is needed, before heavy container-backed or end-to-end runs, and before saying anything is done, fixed or passing.
---

# Verification

A report is a claim. The diff and the test output you read yourself are the evidence.

Pairs with `tdd` and `diagnosing-bugs` from [mattpocock/skills](https://github.com/mattpocock/skills), which produce the red and green evidence this skill reads.

## Choose the tests

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged.

- Run the **targeted tests** at checkpoints, not after every edit: those covering the changed code and its traced consumers, plus the project's lint and unit checks for those packages. Pick them from the diff (packages, test name patterns, the end-to-end suite only when the user-facing path changed). Say when no test covers the change; when that change alters runtime behavior, name the gap and propose a test rather than skip it.
- Run a **full suite** only when the owner asks. Gates and pull requests use targeted tests; CI runs the rest after an authorized push. When the change touches widely shared code whose consumers you cannot trace in full, propose a full suite and wait for the owner's yes.
- Keep local fixtures small (about 1,000 items) unless the owner asks for larger stages.
- **Heavy jobs** (container-backed suites, scale measurements, end-to-end runs) run one at a time per machine under an atomic `mkdir` lock (`fnl-delegate` "Heavy jobs" points to the snippet; without it, `until mkdir "$LOCK"; do sleep 15; done`, then remove the lock when the job ends); light targeted runs may overlap. Keep the machine awake for long runs.

## Read the evidence

- Read the output, not the exit code alone: count what ran, what skipped and what was filtered out. A skipped or partially green run is not a pass.
- Missing setup, a missing API or credential is not a behavioral pass: report it as blocked.
- Enabled configuration, a tool's DONE, a tick in a task list or a moved HEAD is not proof of behavior.
- For queries, reports, infrastructure changes and forecasts, a run that completed is not proof the result is right: see `fnl-coding-router` `references/non-code-work.md`.

## Bind proof to final bytes

Evidence belongs to the exact revision, contracts, dependencies, configuration and environment it ran on. A later change invalidates only the evidence it affects; rerun those checks and keep the required final ones.

Report each check as **PASS**, **FAIL**, **PENDING**, **SKIP**, **WAIVED** (with who waived it and why) or **N/A**. Only the owner waives a check; an agent proposes the waiver with its reason and leaves the check **PENDING** until the owner agrees, unless the project's rules already waive it.

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

`verify_claim.py` checks the reported head, ancestor base, clean checkout before and after testing, changed-file scope and test exits. It prints `PASS`/`FAIL` plus the evidence, then writes a metadata-only `verify` receipt through `record.py` (script-enforced). Exits: 0 for passing mechanics, 1 for failed mechanics, 2 for invalid input or unavailable evidence/storage. Exit 0 grants no acceptance. The receipt holds head, checkout hash, test/mechanical results, an evidence-packet digest and each criterion's identifier, answer, source and fallback flag; no criterion text, commands, output or paths.

For a criterion comparing two documents, use `{"id":"C2","documents":[{"path":"docs/first.md","question":"The document states the reset interval is fifteen minutes."},{"path":"docs/second.md","question":"The document states the reset interval is fifteen minutes."}]}`. The coordinator splits the criterion into equivalent positive statements per document (advisory, agent judgment); the script reads each independently at the reported head, asks once per document and compares answers in code. Both must be `yes` for support; either `no` is reported as `no`, otherwise `insufficient`. Two `no` answers never prove agreement.

Every semantic check uses [scripts/judge.py](scripts/judge.py). Canonical `## Agent roles` chooses `judge: jev` or `judge: host`; absent or unreadable means `host` (script-enforced). Only choose Jev after the user's setup authorization and API budget; keep spend guards on and send only the fields needed (advisory, agent judgment). `TYPESAFE_API_KEY` is read only from the environment, never from a file. `judge.py ask --question <English statement> --evidence-file <file> [--judge jev|host]` prints exactly one JSON answer line: `answer`, `source`, `p`, `quote_ok`. `--dry-run` prints payload field names and sizes and sends nothing. Jev uses Noul probabilities: at least 0.7 gives `yes`, at most 0.3 gives `no`, otherwise `insufficient` (script-enforced; these inherited experimental thresholds do not establish validation).

The host judge is a small model on the host's fast tier; the script never calls it. Give it the same question and evidence, treated as data, and ask for `answer: yes|no|insufficient` plus a verbatim supporting `quote` for `yes` (advisory, agent judgment). `judge.py check-host --answers <json file> --evidence-file <file>` changes an unquoted or misquoted `yes` into `insufficient` (script-enforced). A quote's presence alone cannot prove support. `judge.py` exit 3 reports `unavailable`; if Jev fails, the coordinator supplies the small host answer with the same payload and reports the fallback (advisory, agent judgment); verification preserves that fallback in the receipt.

The first verification run saves the question/evidence packet with owner-only permissions when `--requests-out` is given; this is a private local work artifact, never plugin state or an event. Produce a host answers JSON object keyed by criterion identifier, each containing `answer`, `quote`, `question` and `evidence_sha256` copied from that packet. Then run:

```text
python3 -I <this skill folder>/scripts/verify_claim.py --complete-host <saved request packet> --host-answers <answers json> --head <same head> --ledger-id <same dispatch id> --checkout <task checkout>
```

This attaches checked answers to the exact test run without rerunning tests with potentially different timing output; packet digest, question, evidence, checkout and head must match (script-enforced). Keep both the original criterion and its English restatement in the coordinator report for criteria in another language (advisory, agent judgment); receipts store neither. For an agreement measurement, `judge.py validate --cases <json> --judge <jev|host> [--answers <host json>]` runs one harness over the same supplied cases and prints counts and per-case answers; it stores nothing. Cases contain `id`, `question`, `evidence`, `expected`; host answers are keyed by case id. Use known outcomes from merged pull requests by independent authors before trusting a judge (advisory, agent judgment). The current experiment and synthetic tests do not establish that validation: reports stay labelled `unvalidated`. Read every `no` and `insufficient`; neither judge grants acceptance, and `yes` never replaces mechanics (advisory, agent judgment).

After the coordinator decides to accept, `fnl-delegate`'s `ledger.py finish --outcome accepted --checkout <task checkout>` requires a passing receipt for that checkout's current head (script-enforced). Work with nothing to check may use the logged, counted `--accept-unverified --reason <text>` escape hatch; keep the full reason in the coordinator report, as the ledger stores only its digest. This gate covers delegated work in the ledger only; the coordinator's own work stays under the review gate and an agent bypassing the ledger is not blocked.

## Claims

State what was run and what it showed. Distinguish drafted, verified, integrated, delivered and parked. Verification grants no publication, push or deploy authority.
