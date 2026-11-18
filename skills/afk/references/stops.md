# Stops while the user is away

`<script>` is `afk.py` from `delegate`, as in `SKILL.md`. Blocking stays the host's job (its permission rules, auto mode and sandbox); these steps settle the places where an agent would otherwise wait for the user (docs/specs/afk-decider.md).

## Start lines

Read the start summary's Claude Code lines: add the printed allow rules with `/permissions` so the lease commands never prompt, and on a `Warning:` line tell the user before they leave that nothing on the host blocks credential reads until `/setup add afk` adds the native deny rules (advisory (agent judgment)).

## End a turn

Before ending a turn under the lease, record why: `python3 -I <script> log --kind idle --session <Session id>` when nothing is left that the lease allows, or `log --kind parked --session <Session id> --note '<brief reason>'` for what waits on the user; the Session id is the one the session start printed. On Claude Code the afk stop hook sends a turn without such a record back once (hook, `FNL_AFK_STOP=off` disables it); elsewhere recording it is advisory (agent judgment).

## Permission prompts

On Claude Code the afk permission hook denies a host permission prompt during the lease with a fixed message ending in `Request digest: <64 hex>`. Take it up "Decide" with two options (1 run it, 2 park it); "Where it must stop" parks it instead. A rung that settles on 1 records `--approve-request <digest>` on its `log --kind decision` attempt; then retry the same request once, unchanged, from the same folder (hook: the approval is used once and expires after 30 minutes or with the lease). A second denial of the same request says to park it: record `log --kind parked` and move on. `check` never uses a permission approval. Blocking stays the host's job: its permission rules, auto mode and sandbox.
