# Instruction files per host

Recheck each row against the host's current documentation before writing; locations and include syntax change between versions.

## User scope

| Host | User-scoped file | Include another file | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/CLAUDE.md` | `@path` on its own line, home paths allowed (`@~/…`) | [memory docs](https://code.claude.com/docs/en/memory) |
| Codex | `~/.codex/AGENTS.override.md`, else `~/.codex/AGENTS.md` (or under `$CODEX_HOME`) | none documented | [AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md) (the older developers.openai.com address redirects here) |
| Antigravity | `~/.gemini/GEMINI.md` or `~/.gemini/AGENTS.md`; global rules also in `~/.gemini/config/rules/*.md` | `@[label](path)` | [rules docs](https://antigravity.google/docs/rules#global-rules); limits in the next section |

## Project scope

Docs checked 2026-11-04. These are documented mechanisms, not runtime validation of the user's installed hosts. List any row or behavior that cannot be rechecked as **unverified** before drafting.

| Host | Repository file | Include mechanism | Tracked versus local | Source / limits |
| --- | --- | --- | --- | --- |
| Claude Code | `CLAUDE.md` imports the source `AGENTS.md` | `@AGENTS.md` on its own line, outside a code block | Track both; personal context in untracked `CLAUDE.local.md`, kept out of git | [Memory docs](https://code.claude.com/docs/en/memory#import-additional-files) document imports and local instructions. |
| Codex | `AGENTS.md` | None documented; reads the source directly | Track `AGENTS.md`; a private local companion is **unverified**, so do not create one | [AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md); an existing `AGENTS.override.md` takes precedence in its directory: report it, do not overwrite it. |
| Antigravity (App, CLI, IDE and extensions) | `AGENTS.md` in the workspace or parents up to the repository root | Reads it directly; optional `@[label](path)` inlines another rule file, while `@filename` is only a reference | Track `AGENTS.md`; a private local companion is **unverified**, so do not create one | [Rules docs](https://antigravity.google/docs/rules#directory-scoped-rules), including configuration by surface; 24,000 bytes per file after includes. |

## Limits, precedence and mechanics

Documented on 2026-11-05, read through a page summarizer and not run on any host: treat each figure as unverified until a host shows it.

| Host | Size limit | What happens past it | Precedence | Mechanics worth knowing |
| --- | --- | --- | --- | --- |
| Claude Code | Target under 200 lines per file; imports load with their parent and do not reduce the cost | Longer files cost context and reduce adherence | Files are concatenated, none overrides another; on a conflict the model may pick either | Imports go four hops deep and are skipped inside code spans and blocks. Version 2.1.277 and later also reads `AGENTS.md` natively, but only when no `CLAUDE.md` or `CLAUDE.local.md` exists, so a `CLAUDE.local.md` suppresses it; a `CLAUDE.md` that imports `AGENTS.md` avoids a double read. HTML block comments are stripped before loading. Rules with exactly zero exceptions belong in a hook or a deny permission, not in text. |
| Codex | 32 KiB for the whole chain (`project_doc_max_bytes`) | Later files are dropped silently | Closer files come later and override; `AGENTS.override.md` wins in its directory, one file per directory | Rebuilt on every run; no include syntax. |
| Antigravity | 24,000 bytes per file after includes; about 20,000 tokens shared by global and always-on rules | The file is truncated; past the token budget the largest rule files are replaced by pointers | Rules are cumulative with no stated order | No rules load from subfolders below the workspace folder. A file in `.agents/rules/` needs a valid `trigger` in its frontmatter or it is ignored, and files nested in its subfolders are ignored unless registered. |
| Gemini CLI | none stated | | Hierarchical, `@file.md` imports | Superseded by the Antigravity CLI on 2026-06-18 per its own page; treat its paths as legacy. |

The 150-line figure in `SKILL.md` is a house rule with no vendor source; 200 lines is Anthropic's documented target for Claude Code. `/fnl-setup` Check measures these limits after a write.

Use `AGENTS.md` as the sole repository source, with only the include and Claude-specific lines in `CLAUDE.md`; do not generate a parallel `GEMINI.md`. Keep committed content generic: no personal, customer or organization names or machine paths. Tell the user to keep `CLAUDE.local.md` and backups out of git. The `## Agent skills` block and review-gate adoption line belong to `fnl-setup`; preserve them once in the source, and point to `/fnl-setup` for missing entries.

## User layouts with one source of truth

1. **Shared file plus includes** (recommended where every host supports includes): keep the shared body in one file the user chooses (for example `~/.agents/instructions.md`); each host file holds its host section and an include line pointing at the shared body.
2. **Symlink**: for a host without includes, link its file to a generated file that already merges the shared body and that host's section. Only after the user agrees; a symlink is easy to break when a tool rewrites the file.
3. **Managed copies**: write the merged text into each file and record in each one where its source lives. Simplest to read, but every later change must be applied to all copies.

**Default recommendation** for a user who runs Claude Code most: its file `~/.claude/CLAUDE.md` is the source. A host with an include (Antigravity) points at it with that include. A host without one (Codex today) gets a managed copy that records its source and warns that a change to the source must be applied to the copy by hand.

Keep machine inventory and settings out of instruction files: `/fnl-scan-agents` refreshes the local agent section, and `/fnl-set-mode` shows or changes Delegation mode and Routing with environment overrides explained. Both ask before writing host config.
