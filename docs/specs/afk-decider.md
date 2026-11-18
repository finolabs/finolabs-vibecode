# afk decider: settle the stops, leave the blocking to the host

Status: in progress; owner direction and decisions 18/11/2026; code for A to D and decisions 1 to 4 and 6 lands in 0.3.3, decision 5 (dropping the syntax allowlist and the general argv classification) is parked and left out of 0.3.3 (19/11/2026), because it redefines `strict` mode and the rules a live lease runs on. It changes [afk-autonomy.md](afk-autonomy.md), [afk-per-project.md](afk-per-project.md) and [away-decisions.md](away-decisions.md) where they say who blocks and when an agent may stop; where they disagree, this document wins from the release that ships its code.

## Why

Owner direction, 18/11/2026: blocking is the native harness's job, and afk's job is autonomy. Claude Code already blocks through permission rules and auto mode, and Codex through its sandbox and approval policy. Agents in auto mode do most of the work themselves, but they still stop to wait for the user to decide or approve something. While the user is away, afk must be the decider that settles those stops in the user's place, within what the user authorized.

Evidence from 18/11/2026:

- The afk check hook (a second blocking layer) produced about 100 false denials in one night, and five review rounds of a replacement tokenizer (PR 358, closed unmerged) kept finding forms where it read a command differently from the shells. Blocking by imitating the shell has no end; the host already blocks.
- One coordinator session ended more than ten turns with a question to the user ("Merge PR 357?", "Post the security review?") that the existing "Decide" ladder could have settled. The ladder exists (`skills/afk/references/decide.md`); nothing makes an agent use it instead of stopping.

The afk check hook is removed in its own pull request (owner decision, 18/11/2026). This spec covers what afk does instead.

## The stops and who settles them

| Where an agent stops for the user | Today | This design |
| --- | --- | --- |
| A question through the host's question tool | The away question gate denies it and points to "Decide" | Unchanged |
| The turn ends with a question or approval in text | Nothing; the agent waits | A. The stop hook sends the agent back to "Decide" |
| A host permission prompt the host does not settle itself | The host waits for a click | B. The permission hook answers from the lease's recorded approvals |
| A merge | The merge gate, under a lease with Merge yes or `open` | C. The decider merges on the evidence when the user's authority covers it |
| Posting a security review by another family | The standing relay under a lease | Unchanged |
| An action that could reach credentials, production or real people | `check` and "Where it must stop" | D. The host blocks; afk parks the decision and never answers it |

### A. The stop hook (Claude Code)

One `Stop` hook in its own group, active only while a valid, unexpired lease exists and `FNL_AFK_STOP` is not `off`. When the agent ends a turn, the hook returns `decision: block` with one fixed reason: settle any pending decision through `afk` "Decide" and continue; to end the turn, first record why with `afk.py log --kind idle` (nothing left that the lease allows) or `--kind parked`.

- It lets the stop through when the host marks the turn as already continued by a stop hook (`stop_hook_active`), so it blocks at most once in a row; when a `log --kind idle` or `parked` record for this session is younger than the turn; when the lease's runtime or action limit is reached; and on any error.
- It never blocks the user's own stop or interrupt, a prompt, a tool call or a session start. It reads only the lease and the lease log, keeps no content and sends nothing.
- It needs a new scoped exception in `CLAUDE.md`: today no hook may block an agent's stop.

### B. The permission hook (Claude Code)

One `PermissionRequest` hook in its own group, active only under a live lease and when `FNL_AFK_PERMIT` is not `off`.

- **What it matches.** A *permission approval*, a record separate from today's `--approve-argv-json` approvals: it binds the exact host request, a digest of the tool name, the canonical JSON of `tool_input` as the host sends it (for Bash, the command string as written) and the working folder. The hook compares digests only; it never splits or rebuilds a shell command.
- **Who records one.** When the host denies a request through this hook, the agent takes it up the "Decide" ladder with two options (1 run it, 2 park it). Any action the lease allows is eligible, ordinary `open`-mode actions included; "Where it must stop" (section D) parks it instead. A rung that settles on 1 records the permission approval for that exact request (`afk.py log --kind decision ... --approve-request <digest>`).
- **Use and expiry.** `afk.py check` never consumes a permission approval; the permission hook consumes it once, when it allows that exact request. It expires after 30 minutes or when the lease ends.
- **Its own lease commands.** The hook always allows this install's own `afk.py` lease commands (`log`, `stop`, `review`, `effective`, `rules`, `check`, `packet-check`), named by their resolved path, with every argument made only of letters, digits, spaces and `._,:=/@+%-` (the exemption the removed afk check hook used), so recording an approval or a park never needs an approval itself. `afk start` also offers a native allow rule for those commands, so the host does not prompt for them in the first place.
- **Every other request** gets `deny` with one fixed message: away, settle it through "Decide" or park it, followed by the request's digest (64 hex characters, nothing else from the request), which the agent passes to `--approve-request`. The digest is all the agent needs; it computes nothing itself. A request denied a second time with no approval recorded in between is parked: the agent records `log --kind parked` for it and moves on, so the same prompt never loops.
- It never answers a prompt the host does not route through this event, keeps only digests and sends nothing. It needs a new scoped exception in `CLAUDE.md`.

### C. Merge by the decider

A merge is a decision like any other. The decider merges without the user when the user's authority covers it and the evidence holds:

- **Authority:** the lease's Merge answer, or `open` mode, for that repository (today's rule), or a standing per-repository record that the decider may merge (decision 3).
- **Evidence (unchanged, script-enforced where it is today):** `merge_check.py --independent` prints `MERGE OK` at the current head: two posted reviews by a family other than the author's, or, when no other family is reachable, the same-family fallback of `skills/afk/references/merge-gate.md` with its existing conditions and `--fallback-family`; CI green; the router marker; the rework limit respected. The merge argv pins the full head SHA. No answer of the ladder replaces `MERGE OK`.
- **Gray cases** (a rework round past the limit, whether to use the same-family fallback, a review that approves with findings) go up the "Decide" ladder; its answer chooses what to do next and never stands in for the evidence above: a recorded rule, the evaluation table, the advisor of another family, the host. The answer is final for the lease and is listed for the user's return with `kept` or `reversed`.
- A pull request that changes the lease, setup, hooks or instruction files is merged like any other when the review gate passes; it does not park (decision 4).

### D. What afk still refuses

afk no longer imitates the shell. `afk.py check` keeps what is not syntax:

- the lease's counters, limits and merge pins, and the approval records the permission hook reads;
- "Where it must stop" as decision rules: credentials, production, real users or customer data, and release targets park instead of entering the ladder;
- the guards the user kept in setup (`afk-autonomy.md` section C: no direct push to the default branch, no force push, and the others listed there). They are authorization limits, not syntax, so `check` keeps the narrow reading of the `git` commands they name; the user's server-side branch protection, which `setup` recommends, enforces the same limits outside the agent.

Its word-level syntax allowlist and its general classification of argv go away with the hook (decision 5); the guards above keep their own narrow reading. Blocking credential reads becomes the host's job: `setup` offers native deny rules for the credential floor (for example `Read(~/.netrc)` and `Bash(printenv:*)` on Claude Code), and `afk start` warns when the host has neither those rules nor an approval mode that asks.

## Owner decisions

Settled by the owner on 18/11/2026. Decisions 1, 2, 3, 5 and 6 took their recommendation; decision 4 took the alternative. The declined option stays recorded.

1. **Stop hook (A).** Settled (owner, 18/11/2026): yes, as a new scoped exception that may block an agent's stop once in a row under a lease, never the user's stop. Alternative: keep "never end a turn with a question" advisory, as today.
2. **Permission hook (B).** Settled (owner, 18/11/2026): yes, allow only exact recorded approvals and deny the rest under a lease. Alternative: leave host prompts waiting for the user.
3. **Merge authority (C).** Settled (owner, 18/11/2026): the lease's Merge answer or `open` mode, as today, plus an optional per-repository `merge: decide` record made in `setup` with its own consent question, so a repository the user names can be merged by the decider under any lease. Alternative: lease only.
4. **Self-protection (C).** Settled (owner, 18/11/2026): the review gate decides; such a pull request merges like any other when `MERGE OK` holds. Declined: a pull request that changes the lease, setup, hook manifests or instruction files (`CLAUDE.md`, `AGENTS.md`, `AGENTS.afk.md`, a constitution) would have parked instead of being merged by the decider.
5. **`check` (D).** Settled (owner, 18/11/2026): keep accounting, approvals and "Where it must stop", with the setup guards counted among those limits (review of 18/11/2026); drop the syntax allowlist and the general argv classification. Alternative: drop `check` entirely and keep only the ledger.
6. **Native floor (D).** Settled (owner, 18/11/2026): `setup` offers native deny rules for the credential floor with a preview and a neutral yes; `afk start` warns when the host has none. Alternative: document it only.

## Open, not the owner's

- Codex and Antigravity: whether their hook systems offer a stop event and a permission event a hook may answer is unverified; until it is, the agent follows "Decide" by judgment there (advisory).
- The stop hook's continuation reads `stop_hook_active` from the hook input as Claude Code documents it; verify on the installed version.

## Verification

- Stop hook: a turn that ends with a pending question under a lease is sent back once; a second stop in a row, an idle or parked record, a reached limit, no lease, `FNL_AFK_STOP=off` and every error let it through; the user's interrupt is never blocked.
- Permission hook: with no Bash allow rule on the host, a denied request's message carries its digest, and recording that digest through the exempt `log` command lets the same request through once; the install's own lease commands with plain arguments are always allowed, and any other form of them is not; an exact recorded permission approval is allowed once; the same request a second time, a request differing by one byte, tool or working folder, an expired approval and every request without a lease are not allowed; a second denial without an approval ends in a parked record; `check` never consumes a permission approval; `FNL_AFK_PERMIT=off` and errors fall back to the host's prompt.
- Guards: a direct push to the default branch and a force push stay refused under a lease in both modes when the user kept those guards.
- Merge: under each authority source, `MERGE OK` merges and anything else parks, a pull request that changes hooks or instruction files included.
- The `PRIVACY.md` sections and `CLAUDE.md` exceptions match the code before release.

## Not covered

Blocking itself (the host's), the content of the "Decide" ladder (unchanged), and what an agent does inside an approved action.
