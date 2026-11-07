# Companion skills

Skills from other packs that make the `fnl-` skills work better where they fit. Recommend each one only when its condition matches the findings, give its install commands, and install nothing yourself. Every `fnl-` skill works without them.

| Skill | Recommend when | What it adds |
| --- | --- | --- |
| `agybird` ([finolabs/agybird](https://github.com/finolabs/agybird), MIT) | Antigravity is a delegate of Claude Code or Codex | Runs Antigravity dispatches with modes, quota checks and a JSON status envelope that `fnl-delegate` reads, and the remembered grants of section A. |
| `vietnamizer` ([finolabs/vietnamizer](https://github.com/finolabs/vietnamizer), MIT) | The user writes Vietnamese documents or posts for people to read | Writes and edits Vietnamese text for people while keeping its meaning and the writer's voice. Agent-facing text, logs and code stay out of its scope. |
| `typesafe-ai` (TypeSafe, the user's own account) | The user wants an external judge (`roles` feature) | Jev answers narrow semantic questions as `yes`, `no` or `insufficient` with a probability. TypeSafe is an approved data processor for this user only; the payload holds just the fields a question needs and never secrets. It needs the user's own API key and budget, which the plugin never reads, stores or searches for. Install it from TypeSafe's official source, checked before running; the command is not guessed here. Without it the judge is a small model of the host. |
| `diagram-design` ([cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design), MIT) | The user draws architecture, flow or data diagrams for docs, a README or a deck | Makes diagrams as self-contained HTML or SVG, with PNG export, in a saved brand profile. It sends nothing to its author; a generated file loads its fonts from Google Fonts when opened. Our skills do not depend on it. |

`agybird` and `vietnamizer` are listed in the `finolabs` catalog ([finolabs/plugins](https://github.com/finolabs/plugins)):

| Host | Commands |
| --- | --- |
| Claude Code | `claude plugin marketplace add finolabs/plugins`, then `claude plugin install <skill>@finolabs` |
| Codex | `codex plugin marketplace add finolabs/plugins`, then `codex plugin add <skill>@finolabs` |
| Other agents (`vietnamizer` only) | `npx skills add finolabs/vietnamizer --skill vietnamizer -a <agent>` |

`agybird` runs from Claude Code or Codex and calls the Antigravity CLI, so it is not installed in Antigravity itself. Skip a skill the findings show installed already.

`diagram-design` installs from its own repository: in Claude Code, `/plugin marketplace add cathrynlavery/diagram-design`, then `/plugin install diagram-design@diagram-design`; in Codex and other agents, `npx skills add cathrynlavery/diagram-design -a <agent>`. Its maintainer lists the official builds on that repository only; a listing under another name is an unofficial copy.

First-run order: `/fnl-ask`, `/fnl-setup` (its `delegation` feature depends on `/fnl-setup scan`), `/fnl-setup instructions` immediately on Codex or after a first result elsewhere, then companions and `/fnl-status` when useful. Use `/fnl-setup mode` for later preference changes.
