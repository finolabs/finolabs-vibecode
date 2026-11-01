# Privacy

`finos-vibe-code` is a set of Agent Skills: Markdown instructions plus one small local Python script. It has no server, no analytics and no telemetry, and its maintainers receive nothing from your sessions.

## Where your data goes

The skills run inside a host agent such as Claude Code or Codex, which processes your conversation under its provider's policy. When you follow the orchestration skills and delegate work to another agent (for example Codex or Antigravity), the brief, the files that agent reads and anything it produces are processed by that agent's provider under that provider's terms. Delegate only work over files you are allowed to share with that provider.

## What the plugin stores on your machine

- `~/.claude/orchestration/ledger.jsonl` (or the path in `ORCHESTRATION_LEDGER`): one line per delegated run with a short task label, the agent, the model, timings and the outcome. It holds no prompts, code, secrets or personal data. Delete the file to clear it.
- `.orchestration/` in your repository, when you follow `fnl-orchestration` "Where files go": briefs, logs and handover notes that you or your agents write. The skill tells agents to keep this folder out of git.
- The host config file you create from `skills/fnl-orchestration/references/host-template.md`, at a path you choose.

## Reporting issues

Public issues and pull requests are visible to everyone. Remove credentials, personal data and private repository content from any transcript, brief or log before you post it. Report security problems privately as described in [SECURITY.md](SECURITY.md).
