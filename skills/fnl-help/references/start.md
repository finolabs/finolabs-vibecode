# Start

Use the beginner definition and register in [plain-language.md](plain-language.md). For anyone else, name the workflow and depth (MIN, NORMAL, DEEP) when explaining what to expect.

Read the shared rules in [map.md](map.md#rules). On Codex, use `$` instead of `/` for every skill command below; Claude Code and Antigravity use `/`.

Give these steps in order, skipping any the user has done. For a beginner, instead give only the next undone step, what it does for them and what comes after it in one sentence; the rest waits until they ask. Either way, end on the single next command; offer the map for a specific situation.

1. Install the plugin for the host and open a new session; plugins load when a session starts.
2. Type `/fnl-help` to find the next step. If this skill is already running, this step is done.
3. Type `/fnl-setup`, choose user scope, project scope or both, then Quick. Quick confirms inert defaults, then asks one companion multi-select and separate offers to show install commands. Advanced interviews each companion and offers the extras. The beginner path skips companion questions. Setup writes only what the user confirms and installs nothing.
4. **Try it now** (offered once after setup, only when the user is new to coding or accepts the offer; advisory: agent judgment): guide a first result in a new empty folder the user names, never inside an existing repository. Before starting, check that the named folder is empty and not inside a git repository; if it is not empty or lies inside a repository, ask for another folder before creating anything (advisory: agent judgment). Ask for the user's own idea, build one tiny thing from it, explain what you are checking in the everyday words of [plain-language.md](plain-language.md) with no internal terms (what you are building and where to see it, that you ran it to make sure it really works, and that a second pair of eyes checks changes before they count), run it once so the user sees the result, and show the single next command to continue.
5. Describe a first real task in the user's own words. The agent starts coding work with `fnl-coding-router`; explain the checks in the user's register. Expect commits shaped by `fnl-commit-messages` and pull requests held for posted code and security reviews (one combined pass only when the adopted low-risk lane qualifies); sensitive boundaries add the full security procedure.
6. After the first result, type `/fnl-setup instructions` to set how the assistants work with the user. On Codex, type `$fnl-setup instructions` immediately after setup so coding work follows the router from the first task.
7. After a few sessions, type `/fnl-status` to open the usage dashboard, if the user consented to usage metrics in setup.

Point to the plugin README's "Getting started in detail" section for the full version.
