# setup

Typed by the user only.

**What it does.** Configures the plugin for your user account, a project repository, or both, and drafts instruction files. A bare run asks the scope and offers the beginner path, Quick (confirm inert defaults once) or Advanced (ask each item). It writes only what you confirm and installs nothing.

**When to use it.** The first time on a machine or in a repository, to turn on one feature, to check what is set up, or to change Delegation mode.

**Type:** Claude Code `/finolabs-vibecode:setup` or `/setup`; Codex `$setup`; Antigravity `/setup`. Arguments: `[add <feature> | instructions | check | scan | mode [args]]`.

## Tips

- `/setup check` is read-only: run it to see what is set up and what happens automatically.
- `/setup add <feature>` opens one feature, for example `afk`, `checks` or `metrics`.
- A plain sentence such as "install everything" never answers a consent question; each grant keeps its own question.
- `/setup add delegation` asks which helpers to use as one multiple-choice question built from the scan, then one picker per role.
- `/setup scan` refreshes which agents and models are present; `/setup instructions` drafts instruction files with approval per file.
