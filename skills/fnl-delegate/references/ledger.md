# Ledger

Record every dispatch with `scripts/ledger.py` in this skill's base directory. It appends to `~/.finolabs/vibecode/ledger.jsonl` (override with `ORCHESTRATION_LEDGER`; a machine whose ledger is still in `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` keeps using it until a new one exists). The ledger measures whether this routing works, so write each line at the moment it happens:

```bash
L="<this skill's base directory>/scripts/ledger.py"
python3 -I "$L" start --project demo-app --task "T101 isolation check" \
  --kind implement --grade medium --coordinator claude --agent codex \
  --model gpt-6.1-sol --route-by table --budget 45
python3 -I "$L" finish <id> --outcome accepted --rework-rounds 1 --tests passed
python3 -I "$L" open                     # dispatches with no finish line
python3 -I "$L" summary --since 2026-11-01
python3 -I "$L" summary --json           # the same rows as JSON, with quota and error counts
```

`--grade` is one of `easy`, `medium`, `hard`, `very-hard` and `ultra-hard` (`SKILL.md` "Grade" defines them); lines written before `ultra-hard` existed still read.

Record why a route was taken: `--reason fallback-quota` for a quota fallback, `--reason fallback-failure` for a reroute after a failed run, `--reason user-choice --route-by user` for a route the user named, and `--route-by judge` when the route judge settled it.

`--agent claude-session` records a Claude Code app or interactive session, `claude` a headless `claude -p` run, `subagent` an in-session subagent. Task labels are short names; the ledger holds no task data, secrets or personal data. `summary` reports, per agent, model, kind and grade, the first-pass acceptance rate, timeouts and stalls, fallbacks and median duration.
