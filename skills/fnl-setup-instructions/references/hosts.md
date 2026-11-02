# User-scoped instruction files per host

Recheck each row against the host's current documentation before writing; locations and include syntax change between versions.

| Host | User-scoped file | Include another file | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/CLAUDE.md` | `@path` on its own line, home paths allowed (`@~/…`) | [memory docs](https://code.claude.com/docs/en/memory) |
| Codex | `~/.codex/AGENTS.md` (or `$CODEX_HOME/AGENTS.md`) | none documented | [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md) |
| Antigravity | `~/.gemini/GEMINI.md` or `~/.gemini/AGENTS.md`; global rules also in `~/.gemini/config/rules/*.md` | `@[label](path)` | 24,000 bytes per file after includes; [rules docs](https://antigravity.google/docs/rules) |

## Layouts with one source of truth

1. **Shared file plus includes** (recommended where every host supports includes): keep the shared body in one file the user chooses (for example `~/.agents/instructions.md`); each host file holds its host section and an include line pointing at the shared body.
2. **Symlink**: for a host without includes, link its file to a generated file that already merges the shared body and that host's section. Only after the user agrees; a symlink is easy to break when a tool rewrites the file.
3. **Managed copies**: write the merged text into each file and record in each one where its source lives. Simplest to read, but every later change must be applied to all copies.

**Default recommendation** for a user who runs Claude Code most: its file `~/.claude/CLAUDE.md` is the source. A host with an include (Antigravity) points at it with that include. A host without one (Codex today) gets a managed copy that records its source and warns that a change to the source must be applied to the copy by hand.
