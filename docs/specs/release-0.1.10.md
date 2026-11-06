# Release 0.1.10: spec and plan

Status: in progress. Scope settled by the owner on 2026-11-06. Package status is updated in this
table as pull requests merge; the table is the record, not memory.

## Why

0.1.9 fixed the shipped bugs. Using the plugin showed the next gap: the rules it states are mostly
advice, and a user cannot see what the agents are doing. Three things follow, plus the debt carried over.

1. **Compaction nobody triggers.** A 61% session never compacted: hosts compact late, hooks cannot read
   the context or start a compaction, and the skill's "about 60%" had no enforcer.
2. **Authority that is only text.** "Merge, tag and publish need the owner" is a sentence; a host
   permission rule can make it a prompt.
3. **No view of what is running.** Agents start sub-agents of their own family, the coordinator
   delegates to other families, and the user cannot tell how many agents and background processes are
   alive.

Basis: the harness research (what Claude Code, Codex and Antigravity let a plugin or user configure and
what each enforces) in `.finolabs/research/` on the owner's machine. Principle: only hooks, host
settings and permission rules, and sandbox or approval policy enforce anything; instructions, rules and
skills are advice. Each package puts its behaviour on the strongest lever the host has, and says so
where only advice exists.

## Packages

| # | Package | Design | Status |
| --- | --- | --- | --- |
| 1 | Checked compaction threshold writer (Claude Code, Codex) | [compaction-threshold.md](compaction-threshold.md) | Merged (pull request 97) |
| 2 | Compaction steward: local handover, threshold decision, re-injection after compact, read-only agent | [compaction-steward.md](compaction-steward.md) | Merged (pull request 99) |
| 3 | Session-title reminder in the always-loaded rule and the Titles section | none (one line of text) | Merged (pull request 98) |
| 4 | Owner exception and code for an opt-in Antigravity compaction stop | [compaction-stop.md](compaction-stop.md); rule in `CLAUDE.md` (pull requests 100 and 101) | Rule merged; code in progress |
| 5 | Merge guard through host permission rules (Claude Code, Codex) | [merge-guard.md](merge-guard.md) | Spec only |
| 6 | Running agents on the dashboard (phase 1: ledger plus process snapshot) | [running-agents.md](running-agents.md) | Spec only |
| 7 | Backlog and spec corrections | below | Not started |

Order of work: 4, then 5, then 6, then 7. Packages 4 to 6 all edit `fnl-setup`, the README and the
changelog, so they run one at a time, each through its own pull request with both reviews.

## Decisions settled (owner, 2026-11-06)

- Compaction design is option B (thin steward, host thresholds, local handover, fresh sessions at story
  boundaries); a central orchestrator that every session must ask (option A) is not built.
- A second blocking hook is accepted, only as the opt-in Antigravity compaction stop, scoped by the
  second exception in `CLAUDE.md`.
- The guard against unreviewed merges goes through permission rules written by `fnl-setup` after a
  separate consent (package 5), not through a plugin hook.
- Running agents: phase 1 now; hook-reported sub-agents (phase 2) wait until phase 1 shows what users
  cannot see.
- The sync of the dev build to Codex is throttled to once per six hours (local script) because every
  change to hook content makes Codex ask the user to trust the hooks again.

## Not in this release

- A hook that forces the router to load before the first edit, and a Stop-hook review reminder: each
  needs another blocking exception, and the cost is a gate that also blocks work that needs no router.
  Alternative to measure first: inject the reminder and read the skip rate from the existing metrics.
- Session rename by a hook on Codex and Antigravity (no documented mechanism); Claude Code has a
  `sessionTitle` hook output that could set a baseline title (project and branch) without touching the
  other hosts: candidate for 0.1.11.
- Antigravity permission rules (storage unverified).
- Multi-account support (spec first), the beginner screenshot, instruction hygiene on the owner's machine.

## Package 7: backlog and spec corrections

From reviews and research; each is small and independent.

- Quota probe: a directory named `quota.json` loses a reading silently; record the 1800-second `execution`
  when the cache write fails; reject CR/LF in `configs` paths and labels; dedupe `~/.claude` and
  `~/.CLAUDE` by `samefile`; `samefile` raises `FileNotFoundError` for a missing listed folder.
  The consented executable is not constrained again at probe time (issue 88).
- `PRIVACY.md` does not say instruction lines can go to a judge (issue 87).
- Compaction writer: Claude Code stores a per-model value (`modelSettings.<model>.autoCompactWindow`,
  from `/autocompact`) that overrides the top-level key; detect it and warn. Preserve a trailing comment
  on a replaced TOML line. Same-value writes should say "No difference".
- Spec corrections found by the research: `hosts.md` (Claude "Project instructions" setting and its effect
  on `CLAUDE.local.md`; Codex `AGENTS.override.md` at user level, fallback filenames, `CODEX_HOME`;
  "dropped silently" is not documented); `usage-metrics.md` (Codex tools include `Agent`);
  `compaction-threshold.md` (Codex scope and percent keys, the writer's own range); Antigravity
  `PostToolUse` matcher `write_file` is dead (real names `write_to_file`, `replace_file_content`,
  `multi_replace_file_content`) and `suggestedPrompts` allows three, the plugin ships four.
- The keep-manual behaviour of `fnl-delegate` needs a check outside the model's wording.
- `finolabs/plugins`: the catalog check should verify the pinned ref and read manifests at it (issue 8).

## Verification and limits

Run for real on 2026-11-06: the Antigravity hook events, the transcript path and size, and ending a turn
before the model runs (throwaway workspace, one conversation). Everything else about hosts is from
documentation read through summaries, unverified until a package says otherwise. Not verified on any
host: hook output reaching the model, the effect of a new threshold on a running session, Codex trust
after a reinstall with identical content, the Antigravity stop from the user-level hooks file and in the
interactive terminal, and whether a byte limit is a usable proxy for context in long sessions.

## Release

When packages 4 to 6 are merged or explicitly deferred by the owner: release pull request (manifest
versions and changelog, low-risk lane), tag `v0.1.10`, GitHub release, catalog pin pull request in
`finolabs/plugins`, bump to the next dev version. Tag, release and catalog need the owner's go.
