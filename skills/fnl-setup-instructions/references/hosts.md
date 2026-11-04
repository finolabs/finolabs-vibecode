# Instruction files per host

Recheck each row against the host's current documentation before writing; locations and include syntax change between versions.

## User scope

| Host | User-scoped file | Include another file | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/CLAUDE.md` | `@path` on its own line, home paths allowed (`@~/…`) | [memory docs](https://code.claude.com/docs/en/memory) |
| Codex | `~/.codex/AGENTS.md` (or `$CODEX_HOME/AGENTS.md`) | none documented | [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md) |
| Antigravity | `~/.gemini/GEMINI.md` or `~/.gemini/AGENTS.md`; global rules also in `~/.gemini/config/rules/*.md` | `@[label](path)` | 24,000 bytes per file after includes; [rules docs](https://antigravity.google/docs/rules#global-rules) |

## Project scope

Docs checked 2026-11-04. These are documented mechanisms, not runtime validation of the user's installed hosts. List any row or behavior that cannot be rechecked as **unverified** before drafting.

| Host | Repository file | Include mechanism | Tracked versus local | Source / limits |
| --- | --- | --- | --- | --- |
| Claude Code | `CLAUDE.md` imports the source `AGENTS.md` | `@AGENTS.md` on its own line, outside a code block | Track both; personal context in untracked `CLAUDE.local.md`, kept out of git | [Memory docs](https://code.claude.com/docs/en/memory#import-additional-files) document imports and local instructions. |
| Codex | `AGENTS.md` | None documented; reads the source directly | Track `AGENTS.md`; a private local companion is **unverified**, so do not create one | [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md#how-codex-discovers-guidance); an existing `AGENTS.override.md` takes precedence in its directory: report it, do not overwrite it. |
| Antigravity (App, CLI, IDE and extensions) | `AGENTS.md` in the workspace or parents up to the repository root | Reads it directly; optional `@[label](path)` inlines another rule file, while `@filename` is only a reference | Track `AGENTS.md`; a private local companion is **unverified**, so do not create one | [Rules docs](https://antigravity.google/docs/rules#directory-scoped-rules), including configuration by surface; 24,000 bytes per file after includes. |

Use `AGENTS.md` as the sole repository source, with only the include and Claude-specific lines in `CLAUDE.md`; do not generate a parallel `GEMINI.md`. Keep committed content generic: no personal, customer or organization names or machine paths. Tell the user to keep `CLAUDE.local.md` and backups out of git. The `## Agent skills` block and review-gate adoption line belong to `fnl-setup`; preserve them once in the source, and point to `/fnl-setup` for missing entries.

## User layouts with one source of truth

1. **Shared file plus includes** (recommended where every host supports includes): keep the shared body in one file the user chooses (for example `~/.agents/instructions.md`); each host file holds its host section and an include line pointing at the shared body.
2. **Symlink**: for a host without includes, link its file to a generated file that already merges the shared body and that host's section. Only after the user agrees; a symlink is easy to break when a tool rewrites the file.
3. **Managed copies**: write the merged text into each file and record in each one where its source lives. Simplest to read, but every later change must be applied to all copies.

**Default recommendation** for a user who runs Claude Code most: its file `~/.claude/CLAUDE.md` is the source. A host with an include (Antigravity) points at it with that include. A host without one (Codex today) gets a managed copy that records its source and warns that a change to the source must be applied to the copy by hand.
