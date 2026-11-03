# Companion skills

Skills from other packs that make the `fnl-` skills work better where they fit. Recommend each one only when its condition matches the findings, give its install commands, and install nothing yourself. Every `fnl-` skill works without them.

| Skill | Recommend when | What it adds |
| --- | --- | --- |
| `agybird` ([finolabs/agybird](https://github.com/finolabs/agybird), MIT) | Antigravity is a delegate of Claude Code or Codex | Runs Antigravity dispatches with modes, quota checks and a JSON status envelope that `fnl-delegate` reads, and the remembered grants of section A. |
| `vietnamizer` ([finolabs/vietnamizer](https://github.com/finolabs/vietnamizer), MIT) | The user writes Vietnamese documents or posts for people to read | Writes and edits Vietnamese text for people while keeping its meaning and the writer's voice. Agent-facing text, logs and code stay out of its scope. |

Both are listed in the `finolabs` catalog ([finolabs/plugins](https://github.com/finolabs/plugins)):

| Host | Commands |
| --- | --- |
| Claude Code | `claude plugin marketplace add finolabs/plugins`, then `claude plugin install <skill>@finolabs` |
| Codex | `codex plugin marketplace add finolabs/plugins`, then `codex plugin add <skill>@finolabs` |
| Other agents (`vietnamizer` only) | `npx skills add finolabs/vietnamizer --skill vietnamizer -a <agent>` |

`agybird` runs from Claude Code or Codex and calls the Antigravity CLI, so it is not installed in Antigravity itself. Skip a skill the findings show installed already.
