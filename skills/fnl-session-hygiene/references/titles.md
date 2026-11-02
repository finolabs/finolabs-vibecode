# Naming sessions per host

How each host sets a session's title, as checked against each CLI's help and command list on 2026-11-02 (Claude Code 2.1.316, codex-cli 0.166.0, agy 1.4.12). Interfaces change between versions: confirm with the host's help before relying on a row, and update this file when it has drifted.

| Host | Interactive session | New or headless session | Notes |
| --- | --- | --- | --- |
| Claude Code (CLI) | `/rename <title>` | `claude -n "<title>"` (`--name`) | Resume by name or id with `claude --resume`. |
| Claude Code (desktop app) | the app's session title control, or its session tools where the agent has them | the title given when the session is started | The app may refuse to start sessions on turns another session or an automated event began. |
| Codex | `/rename` in the TUI, which asks for the name | `codex exec` takes no name: identify the run by its ledger label and log file names | `codex resume`, `archive` and `delete` accept a session name or id. Archive or delete only sessions this agent started, by id, since titles can repeat; `delete` is permanent and needs the user's explicit go. |
| Antigravity (`agy`) | no session title found in `agy --help` | group runs with `--project <name>`; identify each by its ledger label and log file names | Say that the host has no titles, and carry the name in the handover. |

Log and brief files for a delegated run are named `<ledger id>-<slug>`, where the slug is a short form of the task label the agent writes itself: lowercase `a-z`, `0-9` and `-`, at most 40 characters, never copied from an issue or pull request title. The same name works on every host, with or without titles.
