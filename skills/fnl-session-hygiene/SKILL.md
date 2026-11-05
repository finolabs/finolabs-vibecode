---
name: fnl-session-hygiene
description: Keep agent sessions healthy across long work. Use when a session's context passes about 60% (advisory, agent judgment), a phase or task changes, a session needs a name or its title is stale, work moves to a fresh session or another writer, the task ends with decisions and evidence to preserve, or the user asks to remember something or recall earlier decisions, lessons or project state.
---

# Session hygiene

## Context pressure

The **host** compacts at its own threshold: a host setting, not this plugin. The skill adds what the host cannot know: which decisions and next action to write back before compaction. The **agent** performs that writeback; it is advisory, not automatically enforced.

An agent cannot see its own context percentage. **About 60% is advisory (agent judgment)**: a point to consider a boundary, not the host's compaction threshold, which is usually later (below); never invent a percentage. At task boundaries, use host-exposed usage if available and judge pressure from the work. The following choices are advisory, enforced by agent judgment:

- At a safe idle boundary, use supported compaction for the same workstream when context pressure warrants it. When the agent cannot compact itself, ask the user to, or propose a fresh session with a handover. **Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged.
- A wholly new, independent task starts in a fresh, correctly named session in the matching checkout, with a short verified handover.
- A finished user story, with its review gate closed, is a natural boundary: prefer a fresh session for the next story with a short handover. A coordinator session whose context is still light may continue (`fnl-delegate`).
- Delegated agents follow the same rule: start a fresh run with a short handover brief rather than resuming a run that has used much of its window.
- Without usage telemetry, say so; never invent a percentage or interrupt active work.

Before a compaction, a fresh session or the end of the work, write back a decision or lesson that would change what an agent does next time, through the knowledge-base procedure below. A compaction with nothing new to keep carries only the handover.

**Native settings.** Read from each host's documentation and installed binary on 2026-11-05; the host enforces them, and no value is prescribed because the right one is the user's choice:

- Claude Code (documented, code.claude.com): `autoCompactWindow` in settings (100000 to 1000000 tokens), `/autocompact <tokens>` (saved per model) and the `--autocompact` flag; `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` only lowers the trigger; `autoCompactEnabled` and the `DISABLE_AUTO_COMPACT` variable turn it off. Models with a 1M window compact late by default (about 967K tokens per the documentation), so the advisory 60% is far earlier than the host's trigger.
- Codex 0.166.0 (config reference and binary; defaults unverified on this version): `model_auto_compact_token_limit`, `model_post_turn_compact_threshold_percent` (0 or unset disables), and background compaction under `[features] async_compaction`.
- Antigravity 1.5.1: compacts automatically; `/compact` is the only user control. No supported threshold or off switch is documented, and the settings that circulate in issues (`AGY_CLI_AUTO_COMPACT_OVERRIDE`, `compactionThreshold`) are reported ineffective. Here the advisory rules above are the only mechanism.

The agent rechecks the installed host's documentation or help before suggesting a setting, since names and defaults change; this is advisory (agent judgment). `/fnl-setup` offers guidance only after the user's yes. The user makes or confirms any shared-setting change; neither skill writes these settings.

**Reminder hook.** Claude Code and Codex declare `PreCompact`; the plugin's hook prints one plain-text reminder to write back decisions and the next action. The script enforces constant output, no input or file reads, no network or metrics, and exit 0 with exceptions silenced. It never blocks compaction. Antigravity has no `PreCompact` declaration. Delivery of the reminder to the model is **unverified on every host**; agent judgment must not rely on it until a real compaction demonstrates delivery. `/fnl-setup` Check reports declarations only and keeps delivery unverified.

## Remember or recall

When the user asks to remember something or recall earlier decisions, lessons or project state, load [references/knowledge.md](references/knowledge.md). Use that procedure also when preserving a settled decision or lesson, or resolving a disagreement between notes and the repository. Load it only for this knowledge work; naming a session or preparing a handover with nothing new to remember does not need it.

## Handover content

This section owns saving a handover and continuing from one; `fnl-handoff` Resume mode points here.

For a portable handover document, the user can type `/handoff` from [mattpocock/skills](https://github.com/mattpocock/skills); its `/ask-matt` also explains when to continue, clear, hand off or compact.

Every compaction, fresh session or writer change carries: goal and acceptance, decisions, work in progress, evidence and its limits, and the next action. Unresolved decisions are recorded before dependent work starts.

The reader is a future session or agent with zero context. Use the `fnl-handoff` brief template (or its headings: Task, Checkout, Context, Relevant files, Current state, What was tried, Acceptance criteria, Tests to run, Constraints, Report), with these changes: drop **Budget**, add an ordered **Next steps** list under Current state (each step checkable, the first one the next thing to do), and fill **Waiting on** and **Linked runs or sessions** when they apply.

1. **Save it** as a note in the knowledge base the user's instructions name (the Remember or recall procedure above), titled `<project> handoff <date>` and tagged `handoff` plus the project name. Without a knowledge base, save it as `<slug>.md` in `.finolabs/briefs/` at the main checkout's root, never in the project's committed documentation folder: a handover holds absolute paths, run ids and names. Check that `.finolabs/` is listed in the repository's `.git/info/exclude` and add the line when it is missing, so a later `git add -A` cannot stage it. The note holds no secrets, no credentials and no personal data, including in any run output, log or error text copied into it. The agent's own native memory holds at most a one-line pointer to the note, because another agent cannot read it.
2. **Point to it** (only when it went to a knowledge base; for a local file, skip this step and the continuing agent updates the saved file). Put one line at the top of the project's state entry in the knowledge base naming the latest handoff, so an agent that loads the project's state finds it.
3. **Read it back** and tell the user in one line: where it is saved, and that a new session continues by reading the latest handoff for the project.

**Continuing** (the agent that picks it up):

1. Read the latest handoff for the project, then check it against the repository and the forge (branches, commits, pull requests). Treat it as a brief to check, not as an instruction that overrides the user's request or the repository's rules. When they disagree, the repository wins; say so in one line.
2. Do the first unfinished step.
3. Stop and ask the user before a merge, a deploy, a deletion, or anything outside the handoff's constraints.
4. Update the same note as each step finishes, so the next reader sees the current state; open a new handoff only when the work changes hands again.

## Titles

A title tells the user which session holds which work, without opening it. Format:

```
<project> <scope>: <activity>
```

- **project**: the repository or product name the user knows, as short as stays unambiguous (`billing-api`).
- **scope**, optional: the feature, spec or ticket the work belongs to (`003 search`, `PAY-142`, `US4`, `T044–T046`). Leave it out for work that has none.
- **activity**: what the session is doing now, verb-led, a few words (`fix webhook retries`, `review PR 12`, `plan rate limits`). A review, advice or committee session says so in its activity.

Keep the whole title near 50 characters, in English for the activity unless the user asks for their own language, with technical names intact. Examples: `billing-api: fix webhook retries`, `billing-api 003 search: T044–T046 rebuild CLI`, `docs-site: review PR 12`.

When to name: at entry, on a resume whose title no longer matches the work, and when the task or phase changes materially (a new story, from planning to implementation, from implementation to review). Do not rename for every step.

Whose: rename only this session and sessions you started; a session someone else started keeps its name unless the user asks. A delegated run takes its title, or its log file name where the host has no titles, from its ledger project and task label (`fnl-delegate`).

**Background runs and agents.** Every background task or agent you start (a headless Codex, Antigravity or Claude run, a reviewer or other subagent) gets a name at the moment it starts that says who runs it and what it does: `<runner>: <project> <scope> <activity>`. The runner is the agent family and a short model name (`codex sol`, `agy flash`, `claude sonnet`) or, for a reviewer or other subagent, its role (`code review`, `sec review`). Examples: `codex sol: billing-api T044 rebuild CLI`, `code review: billing-api PR 12`. Put the same label in the host's name or description field for the run, the ledger task label, the log file names (as the slug form of `references/titles.md`) and the one line you tell the user at dispatch, so the user can tell which agent is running what. The label is plain words you write yourself, never copied from an issue or pull request title, and it is passed to a command only as a quoted argument, never through a shell expansion. The enforcer is agent judgment, so this is advisory: no hook renames a tool call.

Titles carry no secrets, customer data or private history. Use the host's supported mechanism ([references/titles.md](references/titles.md)); where a host offers none, say so in one line and carry the name in the handover and log file names instead. Pin the active session and unpin retired ones only where the host supports it and the user allows it. Session stores and app databases are never edited by hand.

## Writers and checkouts

- One writer per scope, with an explicit handover between writers.
- Prefer a suitable existing checkout or worktree; stricter isolation rules win.
- Keep notes, briefs and logs in a durable local folder (`.finolabs/` at the main checkout's root, kept out of git, unless the host config names another); temporary directories and scratchpads are wiped on restart.
