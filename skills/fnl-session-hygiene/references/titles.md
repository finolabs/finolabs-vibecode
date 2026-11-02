# Naming sessions per host

How each host sets a session's title, as checked against each CLI's help and command list on 02/11/2026. Interfaces change between versions: confirm with the host's help before relying on a row, and update this file when it has drifted.

| Host | Interactive session | New or headless session | Notes |
| --- | --- | --- | --- |
| Claude Code (CLI) | `/rename <title>` | `claude -n "<title>"` (`--name`) | Resume by name or id with `claude --resume`. |
| Claude Code (desktop app) | the app's session title control, or its session tools where the agent has them | the title given when the session is started | The app may refuse to start or rename sessions on turns another session or an automated event began. |
| Codex | `/rename <title>` in the TUI | `codex exec` takes no name: identify the run by its ledger label and log file names | `codex resume`, `archive` and `delete` accept a session name. |
| Antigravity (`agy`) | no session title found in `agy --help` | group runs with `--project <name>`; identify each by its ledger label and log file names | Say that the host has no titles, and carry the name in the handover. |

Log and brief files for a delegated run use the same label: `<ledger id>-<task label>` in the logs folder.
