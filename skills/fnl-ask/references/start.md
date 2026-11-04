# Start

Use the beginner definition and register in [plain-language.md](plain-language.md). For anyone else, name the workflow and depth (MIN, NORMAL, DEEP) when explaining what to expect.

Read the shared rules in [map.md](map.md#rules). On Codex, use `$` instead of `/` for every skill command below; Claude Code and Antigravity use `/`.

Give these steps in order, skipping any the user has done. For a beginner, instead give only the next undone step, what it does for them and what comes after it in one sentence; the rest waits until they ask. Either way, end on the single next command; offer the map for a specific situation.

1. Install the plugin for the host and open a new session; plugins load when a session starts.
2. Type `/fnl-ask` to find the next step. If this skill is already running, this step is done.
3. Type `/fnl-setup` and choose Quick. It asks a few questions, writes only what the user confirms and installs nothing.
4. Describe a first real task in the user's own words. The agent starts coding work with `fnl-coding-router`; explain the checks in the user's register. Expect commits shaped by `fnl-commit-messages` and pull requests held for a posted code review, plus a security review at sensitive boundaries.
5. After the first result, type `/fnl-setup-instructions` to set how the assistants work with the user. On Codex, type `$fnl-setup-instructions` immediately after setup so coding work follows the router from the first task.
6. After a few sessions, type `/fnl-status` to open the usage dashboard, if the user consented to usage metrics in setup.

Point to the plugin README's "Getting started in detail" section for the full version.
