# Contents

The user asks what is in the plugin, or what exists for a purpose. Read [map.md](map.md) and list the skills, agents and scripts grouped by purpose, in three groups: typed by the user only (`restore-point`, `afk` and its older alias `brb`, `session-hygiene` (the older name of `tidy`), `pause` and its short name `gtg`, `setup` (including `add <feature>`, `instructions`, `check`, `scan` and `mode`), `status`, `update`, `help` and its older name `ask`); typed by the user or loaded by the agent (`handoff`, loaded by `delegate` or on session wrap-up; `advisor` (one opinion or a committee), proposed first and waiting for the user's yes; `shape`, the interview for brainstorming, discussing or stress-testing an idea, plan or design); and loaded by the agent when the task matches (the rest). When the installed folder differs from the map, trust the folder: list the skill folders beside this one (skip the `fnl-` folders, which are only older-name aliases) and the plugin root's `agents/fnl-*.md` with each file's one-line description, and fall back to the map when neither can be listed. State a count only after counting it in the folder; when the folder cannot be listed, say the list comes from the map and give no totals.

The current agent set is `fnl-reviewer`, `fnl-security-reviewer` and `fnl-navigator`. When explaining automation, distinguish fixed session-start state from observed live-host behavior, optional on-demand quota from a background timer, and verification receipts from the coordinator’s acceptance decision.

The map lists every distinct script with its full-plugin path, including skill-only helpers. The map describes files shipped, not host capabilities: Claude Code user-only flags do not prove invocation-policy parity on Codex or Antigravity. Review agents forbid project edits by instruction; an authorized post uses a private draft.

## Skill pages

One short page per skill: what it does, when to use it, the command on each host and a few tips. Read the skill's own `SKILL.md` before answering in detail; the page is a summary and the skill file wins where they differ.

- [`advisor`](skills/advisor.md)
- [`afk`](skills/afk.md)
- [`ask`](skills/ask.md)
- [`brb`](skills/brb.md)
- [`checks`](skills/checks.md)
- [`coding-router`](skills/coding-router.md)
- [`commit-messages`](skills/commit-messages.md)
- [`delegate`](skills/delegate.md)
- [`gtg`](skills/gtg.md)
- [`handoff`](skills/handoff.md)
- [`help`](skills/help.md)
- [`open-source-review`](skills/open-source-review.md)
- [`pause`](skills/pause.md)
- [`plugin-packaging`](skills/plugin-packaging.md)
- [`restore-point`](skills/restore-point.md)
- [`review-gate`](skills/review-gate.md)
- [`security-review-gate`](skills/security-review-gate.md)
- [`session-hygiene`](skills/session-hygiene.md)
- [`setup`](skills/setup.md)
- [`shape`](skills/shape.md)
- [`status`](skills/status.md)
- [`tidy`](skills/tidy.md)
- [`update`](skills/update.md)
- [`versioning`](skills/versioning.md)
