# Naming sessions per host

How each host sets a session's title, as checked against each CLI's help and command list on 2026-11-02 (Claude Code 2.1.316, codex-cli 0.166.0, agy 1.4.12). Interfaces change between versions: confirm with the host's help before relying on a row, and update this file when it has drifted.

| Host | Interactive session | New or headless session | Notes |
| --- | --- | --- | --- |
| Claude Code (CLI) | `/rename <title>` | `claude -n "<title>"` (`--name`) | Resume by name or id with `claude --resume`. |
| Claude Code (desktop app) | the agent's session-title tool (`set_session_title` with session id `self`; it is often deferred, so load it through tool search first), or the app's title control | the title given when the session is started | The app may refuse to start sessions on turns another session or an automated event began. |
| Codex | `/rename` in the TUI, which asks for the name | `codex exec` takes no name: identify the run by its ledger label and log file names | `codex resume`, `archive` and `delete` accept a session name or id. Archive or delete only sessions this agent started, by id, since titles can repeat; `delete` is permanent and needs the user's explicit go. |
| Antigravity (`agy`) | no session title found in `agy --help` | group runs with `--project <name>`; identify each by its ledger label and log file names | Say that the host has no titles, and carry the name in the handover. |

Where a run's label goes (the full label that `ledger.py start` prints): Claude Code's Agent tool takes it in `description`, and a background Bash command in its `description`; a headless `claude -p` run takes `-n "<label>"`; `codex exec` takes no name, so the label is the Bash `description` and the log file names; Antigravity runs group with `--project <name>` and carry the label in the same two places. The ledger `--task` holds only the scope and activity, because `ledger.py start` adds the runner and project itself.

Log and output files for a delegated run are named `<ledger id>-<slug>`; its brief, written before the ledger records the dispatch, is `<slug>.md`. The slug is a short form of the task label the agent writes itself: lowercase `a-z`, `0-9` and `-`, at most 40 characters, never copied from an issue or pull request title. The same name works on every host, with or without titles.
