# Stops while the user is away

`<script>` is `afk.py` from `delegate`, as in `SKILL.md`. Blocking stays the host's job (its permission rules, auto mode and sandbox); these steps settle the places where an agent would otherwise wait for the user (docs/specs/afk-decider.md).

## Start lines

Read the start summary's Claude Code lines: add the printed allow rules with `/permissions` so the lease commands never prompt, and on a `Warning:` line tell the user before they leave that nothing on the host blocks credential reads until `/setup add afk` adds the native deny rules (advisory (agent judgment)).

## End a turn

Before ending a turn under the lease, every item of this repository's queue must be done or parked: then record `python3 -I <script> log --kind idle --session <Session id>`, the Session id the session start printed. The script refuses `idle` while an item is open (it names them) and before `goal` built a queue; once the lease has ended it accepts. A `parked` record closes one item (`--item <n>`), not the turn: go on with the next item. On Claude Code the afk stop hook sends a turn back once unless this session wrote an `idle` record since its last stop for this repository at its current queue revision, so a record made before another session added an item no longer counts; it lets the turn end when the lease has ended or its setup changed, since Lease hours is the only limit (hook, `FNL_AFK_STOP=off` disables it). The next stop after that one block passes, so the self-paced loop and the host goal are what bring the agent back (advisory (agent judgment)); elsewhere recording `idle` is advisory too.

## Ending the lease

Never run `afk.py stop` when your own work is done: plain `stop` is refused (script), and `stop --all` ends the lease for every session on the machine, so only the user's `/afk stop` runs it (advisory (agent judgment)).

## Permission prompts

On Claude Code the afk permission hook denies a host permission prompt during the lease with a fixed message ending in `Request digest: <64 hex>`. Take it up "Decide" with two options (1 run it, 2 park it); "Where it must stop" parks it instead. A rung that settles on 1 records `--approve-request <digest>` on its `log --kind decision` attempt; then retry the same request once, unchanged, from the same folder (hook: the approval is used once and expires after 30 minutes or with the lease). A second denial of the same request says to park it: record `log --kind parked` and move on. `check` never uses a permission approval. Blocking stays the host's job: its permission rules, auto mode and sandbox.
