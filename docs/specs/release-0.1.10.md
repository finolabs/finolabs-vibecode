# Release 0.1.10: spec and plan

Status: implemented; merged; release pull request open. Scope settled by the owner on 2026-11-06. Package status is updated in this
table as pull requests merge; the table is the record, not memory.

## Why

0.1.9 fixed the shipped bugs. Using the plugin showed the next gap: the rules it states are mostly
advice, and a user cannot see what the agents are doing. Three things follow, plus the debt carried over.

1. **Compaction nobody triggers.** A 61% session never compacted: hosts compact late, hooks cannot read
   the context or start a compaction, and the skill's "about 60%" had no enforcer.
2. **Authority that is only text.** "Merge, tag and publish need the owner" is a sentence; a host
   permission rule can add a prompt on the common commands (not a complete guard).
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
| 1 | Checked compaction threshold writer (Claude Code, Codex) | [compaction-threshold.md](compaction-threshold.md) | implemented; Merged (pull request 97) |
| 2 | Compaction steward: local handover, threshold decision, re-injection after compact, read-only agent | [compaction-steward.md](compaction-steward.md) | implemented; Merged (pull request 99) |
| 3 | Session-title reminder in the always-loaded rule and the Titles section | none (one line of text) | implemented; Merged (pull request 98) |
| 4 | Owner exception and code for an opt-in Antigravity compaction stop | [compaction-stop.md](compaction-stop.md); rule in `CLAUDE.md` (pull requests 100 and 101) | implemented; Merged (pull requests 100, 101, 105, 109) |
| 5 | Merge prompt through host permission rules | [merge-guard.md](merge-guard.md) | deferred; Moved to 0.2.0 with autopilot (owner, 2026-11-06): hosts already ask in their default modes |
| 6 | Running agents on the dashboard (phase 1: ledger plus a `ps` snapshot); the page becomes tabs (see package 8) | [running-agents.md](running-agents.md); needs its own `CLAUDE.md` exception for the `ps` command first | implemented; Merged (pull requests 113 and 117) |
| 7 | Backlog and spec corrections | below | implemented; Merged (pull requests 107, 111, 114, 115, 118); the `finolabs/plugins` catalog ref check and the keep-manual outside check move to the next release |
| 8 | Project progress panel on the dashboard, with the `task` event that links hand-started sessions to tasks | [project-progress.md](project-progress.md) and [dashboard-tabs.md](dashboard-tabs.md); builds on package 6 | implemented; Merged (pull requests 110, 112, 119) |
| 9 | Dashboard freshness: ledger and Antigravity trigger a rebuild, a freshness line per host | [dashboard-freshness.md](dashboard-freshness.md) | implemented; Merged (pull request 108) |
| 10 | Ask in the host's native question form: always-loaded rule, interview rules for rounds larger than the tool allows, router and map wording | none (text only; see "Package 10") | implemented; Merged (pull request 106) |

Order of work: 4, then 9 (small, and the other dashboard packages rely on it), then 6, then 8 (it shares the page and the refresh with 6), then 10 (text only, any time), then 7. Package 5 is not in this release. Packages 4 to 6 all edit `fnl-setup`, the README and the
changelog, so they run one at a time, each through its own pull request with both reviews.

## Decisions settled (owner, 2026-11-06)

- Audit correction: a ledger write by a hooked coordinator already triggers a rebuild (see `dashboard-freshness.md`); the real gaps are Antigravity, writes outside a hooked session, idle periods, and untrusted Codex hooks.
- All four dashboard packages (tabs and progress in 8, running agents in 6, freshness in 9) ship in 0.1.10: a release should carry features users notice, and time is not the constraint.
- The `ps` exception for the process snapshot is approved. The snapshot is the last piece of package 6 and is
  off until `fnl-setup` turns it on; the exception text merges into `CLAUDE.md` only when that code is about to land.
- Project progress is on by default (it keeps identifiers and counts only, and needs metrics consent); the
  dashboard shows a one-time notice of what it reads and how to switch it off. The `task` event is in this
  release.
- Codex no longer follows `main` on this machine: it installs from the `finolabs` catalog and is refreshed on
  purpose after a release; Claude Code and Antigravity follow `main`. Cause: any reinstall (remove and add)
  of Codex makes it ask to trust the hooks again, tested on 2026-11-06.
- The release procedure (release pull request, tag, GitHub release, catalog pin) runs as one package after every
  package is merged, stopping at the tag and the release for the owner's go.

- Compaction design is option B (thin steward, host thresholds, local handover, fresh sessions at story
  boundaries); a central orchestrator that every session must ask (option A) is not built.
- A second blocking hook is accepted, only as the opt-in Antigravity compaction stop, scoped by the
  second exception in `CLAUDE.md`.
- A prompt on the common merge and publish commands goes through permission rules written by
  `fnl-setup` after a separate consent (package 5), not through a plugin hook. It is not a complete guard.
- The dashboard also becomes a project view (package 8): task progress from Spec Kit `tasks.md` or a
  configured task file, joined with delegated runs and sessions; local files and records only.
- Running agents: phase 1 now; hook-reported sub-agents (phase 2) wait until phase 1 shows what users
  cannot see.
- The sync of the dev build to Codex is throttled to once per six hours (local script) because every
  change to hook content makes Codex ask the user to trust the hooks again.

## Not in this release

- Autopilot, live dashboard mode, and the merge prompt (package 5) are release 0.2.0: [autopilot.md](autopilot.md).
- A hook that forces the router to load before the first edit, and a Stop-hook review reminder: each
  needs another blocking exception, and the cost is a gate that also blocks work that needs no router.
  Alternative to measure first: inject the reminder and read the skip rate from the existing metrics.
- Session rename by a hook on Codex and Antigravity (no documented mechanism); Claude Code has a
  `sessionTitle` hook output that could set a baseline title (project and branch) without touching the
  other hosts: candidate for 0.1.11.
- Antigravity permission rules (storage unverified).
- Multi-account support (spec first), the beginner screenshot, instruction hygiene on the owner's machine.

## Package 10: ask in the native question form

Owner request, 2026-11-06, clarified: whichever skill an agent uses to brainstorm or clarify with the user
(`grilling` from mattpocock/skills, `brainstorming` from superpowers, Spec Kit's clarify step, or the pack's own
interview rules), the agent should put the user's decisions through the host's native question tool, not plain text.
The pack already does this for its own skills (0.1.8, package 1) and for specs and plans (`fnl-coding-router`
section 4). Gaps: an agent that needs a decision outside those skills asks in text, a third-party skill's own
instructions may say "ask the user" without naming the tool, and a round larger than the tool takes (four on Claude
Code) falls back to a numbered text list.

Changes, all text and advisory (agent judgment; no host mechanism can force an agent to use a tool):

- One line in the always-loaded rule (`rules/AGENTS.md`), which applies on top of any skill: ask the user's decisions
  through the native tool (`AskUserQuestion` on Claude Code, `request_user_input` on Codex, `ask_question` on
  Antigravity), the recommended option first, even when another skill's text only says "ask"; use free text only
  when there is no tool, it fails, nobody can answer, or the answer is free text.
- Each router workflow adapter that points to a clarify skill (Matt Pocock's, superpowers, Spec Kit) gets one
  sentence: run that skill's interview, but put its questions through the native tool.
- The shared `interview.md` copies say how to stage a larger round: blocking questions first, at most the tool's
  limit per call, the rest in the next call, a numbered text list only as the last resort.
- `fnl-ask` map names the behaviour in its "Requirements unclear" row.

The pack has no brainstorming skill of its own and builds none (compose before build); it composes with whichever the
repository adopts, and the interview rules stay the fallback.

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
