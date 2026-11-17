# Accepting someone else's work

The procedure that `SKILL.md` "Accepting someone else's work" points to: the coordinator's check of a delegated report, `verify_claim.py`, its brief and receipt, and the ledger gate.

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

Read [judgments.md](judgments.md) for each semantic check, host-answer completion, fallback and validation.

After the coordinator decides to accept, `delegate`'s `ledger.py finish --outcome accepted --checkout <task checkout>` requires a passing receipt for that checkout's current head (script-enforced). When the repository has an approved check list, `checks.py run --dispatch <dispatch id>` in the task checkout writes that receipt: only a whole-list pass on a clean tree whose head and list did not move writes it, and every run with `--dispatch` first removes the dispatch's earlier receipt (script-enforced). Without a list, `verify_claim.py` over the brief's tests writes it.
`verify_claim.py` verifies an implementation head and its test receipt; it does not read the dispatch kind. A review dispatch produces a posted review, not a receipt: after reading the posted marker (advisory, agent judgment), accept it with `ledger.py finish <id> --outcome accepted --head <reviewed head> --review-url <comment URL>`, which needs no receipt, checks the URL by pattern only and records `review_posted` (script-enforced).
This gate covers delegated work in the ledger only; the coordinator's own work stays under the review gate and an agent bypassing the ledger is not blocked.
