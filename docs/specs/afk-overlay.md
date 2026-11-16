# afk overlay: repository rules that yield during an away lease

Status: proposed; rule recorded as the ninth scoped exception in `CLAUDE.md` (owner decisions 2026-11-16). No code lands before that rule is merged.

## Why

`/setup add afk` saves away rules in the host config or in a repository's settings, and `afk.py check` allows the actions they name. A repository's `AGENTS.md`, `CLAUDE.md` or Spec Kit constitution may still say that push, merge or deploy need the owner's approval each time. An agent reads those files and stops to ask, although the script allows the action. On 2026-11-16 the owner hit this in a repository whose constitution and `AGENTS.md` "Authority" section conflicted with the new away rules.

A lease must not override repository instructions on its own: they belong to the repository owner and may be stricter on purpose, and a lease that overrode them would take away every repository's ability to set its own rules. The repository acknowledges afk once, through files its owner approved.

## Decisions (owner, 2026-11-16)

1. The overlay is not a second set of instructions. It holds only override entries: each names the rule it replaces (file and section) and gives the afk wording. Every rule it does not name keeps the normal instructions.
2. The file is `AGENTS.afk.md` at the repository's top level, beside the source file `AGENTS.md`, for every host.
3. It is local: git-ignored through the repository's local `.git/info/exclude`, never committed.
4. It is loaded by the session-start hook while a lease is live, and printed by `/afk start`.
5. The conflict report is agent judgment, not a pattern scan in `checkup.py`.
6. An override lists the exact actions allowed on the day of the approval (push and pull requests, merge, each listed deploy and release command), never a general reference to the away rules, so widening those rules later needs a new approval.

## Design

### Conflict report (setup and check)

In project scope, after the away rules, `/setup add afk` and `/setup check` read the repository's `AGENTS.md`, `CLAUDE.md` and Spec Kit constitution (`.specify/memory/constitution.md`, else the file its Spec Kit setup names) as data and list each line that requires the owner's approval for an action the effective away rules allow: file, line number, section and action. The report changes nothing. Enforcer: agent judgment (advisory).

### The overlay

`/setup add afk` drafts one entry per conflicting rule in `AGENTS.md` or `CLAUDE.md`, and nothing else:

```markdown
# afk overlay (owner, YYYY-MM-DD)

While a valid afk lease is live, only the rules named below yield; every other rule in this repository's instructions still holds. `afk.py check` stays the last gate for every action.

## Replaces AGENTS.md › Authority: push and merge
<!-- source sha256=<first 16 hex of the replaced section's text> -->
Agents may push their own branches, open pull requests and merge pull requests that pass the merge gate without asking each time.

## Replaces AGENTS.md › Deploys
<!-- source sha256=<...> -->
Agents may run exactly `<deploy command>` without asking. Every other deploy still waits for the owner.
```

- A constitution rule is never replaced. Setup shows the amendment text it would need and says it follows the constitution's own amendment process, for the owner to run; until it is amended, the constitution line wins.
- An action the away rules do not allow gets no entry. With no conflict left, setup offers no overlay.
- The file is written by `instructions_write.py`, which gains one target: `AGENTS.afk.md` at the git top level, refused when Git tracks it. Same preview, digest, backup and per-file yes as every instruction file, under its own consent question.
- On that write setup adds `AGENTS.afk.md` to the local `.git/info/exclude` and records the file's SHA-256 in `<data root>/state/afk-overlay/<repository identity digest>.json` (owner-only, atomic; the digest and the time, no path and no content). That record is the trust anchor: the overlay counts only while the file's bytes match it.

### Deference line

The normal instructions must say that the overlay may replace rules, or an agent reading both sees a contradiction. Setup offers one line for `AGENTS.md` (else `CLAUDE.md`), written through the same writer after its own yes: "While a valid afk lease is live, a local `AGENTS.afk.md` written by `/setup` replaces only the rules it names; every other rule here still holds." It names no action and holds no personal data, so it may be committed. It counts only once committed on the default branch.

### Loading

- Session start (Claude Code and Codex, the existing `SessionStart` hook): only while a valid, unexpired lease exists, and only when `FNL_AFK_OVERLAY` is not `off`, `session_start.py` looks at `AGENTS.afk.md` at the git top level of the working folder. It prints the file's text, framed by a fixed first and last line, only when the file is a regular file, not a symlink, owned by the user, not group- or world-writable, at most 8 KiB, untracked by Git (read from the index without running Git), and its SHA-256 equals the recorded digest. When the file exists but any check fails, it prints one fixed line: "An afk overlay is here but not in force (changed since setup or unsafe): ask before the actions it names, or run /setup add afk." Any error prints nothing more and exits 0.
- `/afk start` runs the same reader and prints the same text or line, so a lease started mid-session reaches the session too.
- Antigravity: no session-start hook of this plugin; `/afk start` is the only path there.

### Guarding the file

`afk.py check` treats `AGENTS.afk.md` as a hard protected name (Tier 3) in every repository and on every branch, so a lease cannot write or stage it, and the Decide ladder cannot approve it. The Spec Kit constitution (`.specify/memory/constitution.md`) becomes protected the same way, so a lease cannot amend it through an approved `unknown` path. A changed file fails the digest and is not in force.

The overlay replaces the committed clause first drafted in pull request 319. Its security review (2026-11-16) found that an agent under a lease with Push and Merge yes could write such a clause into top-level `AGENTS.md` on a work branch and merge it, after which it looked exactly like an owner-written one. The overlay has no merge path: it is never committed, a lease cannot write it, and it counts only while its bytes match the digest that setup recorded after the owner's yes. A deference line an agent added on its own grants nothing without a matching overlay.

### Staleness

`/setup check` and `/setup add afk` recompute each entry's source digest from the named section. A section that changed or disappeared marks that entry stale, and the report says so; a stale overlay is regenerated with the owner's yes, never kept silently. A changed away rule is reported the same way when an entry lists an action the rules no longer allow, or the rules allow an action with a conflict and no entry.

### Lease rules

`afk` `references/lease-rules.md`: a Tier 1 answer never overrides the repository's instructions; an agent acts on a rule that requires the owner's approval only when the overlay in force replaces it; never edit the overlay or the deference line during a lease.

## Enforcers

| Step | Enforcer |
| --- | --- |
| Conflict report, drafting the entries, staleness wording | agent judgment (advisory) |
| Writing the overlay and the deference line | `instructions_write.py` (preview, digest, backup, per-file yes) |
| Trust anchor and loading | `session_start.py` and `afk.py start` (digest, file checks, lease) |
| Lease cannot change the overlay | `afk.py check` (hard protected name) |
| Every action | `afk.py check` (last gate; the overlay never widens it) |

## Privacy

The overlay text is the owner's own instructions about this repository. While a lease is live the hook adds it to the session's model context, which the host sends to its AI provider like any instruction file. The plugin stores only the digest and the time; it sends nothing. `PRIVACY.md` "afk overlay" carries this.

## Not covered

- An agent that ignores the overlay or the normal instructions: text is not enforcement; `afk.py check` is.
- A lease started in another session while this one runs: the hook ran at session start; the session sees the overlay only after `/afk start` here or a new session.
- Antigravity sessions without `/afk start` in them.
