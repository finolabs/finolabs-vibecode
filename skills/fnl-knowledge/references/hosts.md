# Native memory per host

Checked 01/11/2026. Recheck against each host's documentation and `--help` before relying on a row; memory features change between versions.

| Host | Native memory | How it loads | Notes |
| --- | --- | --- | --- |
| Claude Code | Auto memory: one file per memory in the project's memory folder under `~/.claude/projects/`, indexed by `MEMORY.md`; plus `CLAUDE.md` files | The index loads every session; entries load when relevant | [memory docs](https://code.claude.com/docs/en/memory). Keep the index one line per entry. |
| Codex | The `memories` feature (stable, on by default in CLI 0.166), stored under `$CODEX_HOME/memories`; plus `AGENTS.md` | Codex selects memories by relevance | Check `codex features list` for its state. |
| Antigravity | Knowledge items in the Antigravity app; the CLI documents no memory store, so durable preferences go in `GEMINI.md` or `AGENTS.md` rules | Rules load every session (24 KB per file) | Recheck the CLI changelog for a memory feature. |

Native memory stays inside one agent product. A fact two agents need belongs in the knowledge base, with each agent's native memory holding at most a pointer.
