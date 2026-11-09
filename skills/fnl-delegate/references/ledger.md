# Ledger

Record every dispatch with `scripts/ledger.py` in this skill's base directory. It appends to `ledger.jsonl` under the resolved data root, ignoring environment overrides and legacy folders. The ledger measures whether this routing works, so write each line at the moment it happens:

```bash
L="<this skill's base directory>/scripts/ledger.py"
python3 -I "$L" start --project demo-app --task "003 T101" \
  --kind implement --grade medium --coordinator claude --agent codex \
  --model gpt-6.1-sol --route-by table --budget 45
python3 -I "$L" finish <id> --outcome accepted --rework-rounds 1 --tests passed
python3 -I "$L" open                     # dispatches with no finish line
python3 -I "$L" summary --since 2026-11-01
python3 -I "$L" summary --json           # the same rows as JSON, with quota and error counts
```

**Project label.** Choose one short, stable `--project` label per repository and use it from every worktree of that repository; never use a customer, personal or machine name. The dashboard joins dispatches to a repository by the repository's `ledger` project setting (the legacy `Ledger project:` line, then the folder name), not by its display label, so use that name; a different label joins nothing on the dashboard until `/fnl-setup add project` records it as the repository's `ledger` entry.

For review routing, the coordinator adds `--head <implementation head SHA>` to `finish`. This validates a forty-character lowercase SHA and copies the agent from the dispatch's start record; legacy records without a head cannot establish authorship. Commit trailers alone are insufficient. When acceptance uses a verification receipt, this head must also match the verified head.

`start` prints the dispatch id on stdout and, on stderr, the run's name as `label: <runner>: <project> <task>`, where the runner is the family plus the short model name (`codex sol`, `agy flash`, `claude opus`); `--task` holds only scope and activity. `start` records optional `coord_session`: the first 12 hex characters of the SHA-256 of the `CLAUDE_CODE_SESSION_ID` environment value, never the raw id and never from a command-line option (an argument would show in process listings and parser errors). It is `null` when the variable is unset or unusable, and older lines without it remain readable. It is a correlation identifier, not protection: a predictable id can be guessed from its hash, so treat the ledger as private.

Before `finish --outcome accepted`, run the self-contained `verify_claim.py` from `fnl-verification` "Accepting someone else's work" and read its evidence. Pass `--checkout <task checkout>` to both `start` and `finish` when the task runs elsewhere: the gate requires a passing receipt for that checkout and its current head. For work with nothing to check, the coordinator can use `--accept-unverified --reason <text>`; keep the full reason in the coordinator report because the ledger stores only its SHA-256 digest and counts the exception in `summary`.

`--grade` is one of `easy`, `medium`, `hard`, `very-hard` and `ultra-hard` (`SKILL.md` "Grade" defines them); lines written before `ultra-hard` existed still read.

Record why a route was taken: `--reason fallback-quota` for a quota fallback, `--reason fallback-failure` for a reroute after a failed run, `--reason user-choice --route-by user` for a route the user named, and `--route-by judge` when a validated configured-judge response informed it.

Under Delegation mode `manual`, `start` refuses a cross-family record without `--route-by user`, writes nothing and exits 1. Claude, `claude-session` and `subagent` are the Claude family; own-family records remain allowed. This check blocks the record, not the dispatch itself; an unavailable or invalid mode leaves the previous behavior unchanged.

`--agent claude-session` records a Claude Code app or interactive session, `claude` a headless `claude -p` run, `subagent` an in-session subagent. Task labels are short names; the ledger holds no task data, secrets or personal data. `summary` reports, per agent, model, kind and grade, the first-pass acceptance rate, timeouts and stalls, fallbacks and median duration.

For task progress, use labels of the form `<feature> T<id>` (for example `003 T012`); include the exact three-digit feature number. Multiple ids or ranges of at most 20 ids link each task; labels without a feature remain unlinked. The rest of the label is discarded by the dashboard.

`finish` accepts `--log-path <log>` inside the private `.finolabs/logs/` folder of the current checkout; it scans before recording and stores only `log_scan: no_findings|findings|not_scanned`. Omit the path to record `not_scanned`. The `--head` and verification-receipt gate still apply.
