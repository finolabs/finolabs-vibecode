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
- `/setup add compaction` recommends an auto-compact threshold (300-500K for a coordinator on a 1M model, 600-800K for one task) and, on Claude Code, can write it for one repository only. The threshold is when the conversation is shortened, not the model's window. Settings cannot tell a coordinator from a task session, so the saved value is for task sessions, and setup shows a line to open a coordinator with its own value: `CLAUDE_CODE_AUTO_COMPACT_WINDOW=500000 claude` (hooks cannot see `--autocompact`, so the reminder before compaction would stay silent). It can also remove per-model values that would override the one you save.
- On Claude Code, `/setup add compaction` can save the threshold for one model only, as `/autocompact` does, instead of for every model.
- `/setup add quota` can record a weekly floor for one install, such as `claude/work=15`: routing then stops handing it work once less than 15% of its week is left, instead of the default 10%.
- `/setup add roles` also asks the Rework limit (2 to 4 review rounds) and whether a same-family security review may count when no other family can review.
- `/setup scan` refreshes which agents and models are present; `/setup instructions` drafts instruction files with approval per file, and first lists lines in your existing files that would stop `afk` or `delegate` (for example a merge allowed only where you approved it), with a proposed replacement for each.
