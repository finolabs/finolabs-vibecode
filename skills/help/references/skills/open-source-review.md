# open-source-review

Typed by the user, or loaded by the agent when the task matches.

**What it does.** A read-only review of a repository's readiness to be published as open source: license, secrets and private data in the tree and history, internal leaks, clean payload, community files, repository settings, identity and versions, data flow, and plugin packages. Each item gets PASS, FAIL, N/A or BLOCKED with evidence.

**When to use it.** Before making a repository public, before a first public release, before publishing a plugin or skill package to a marketplace, or when checking a public repository's settings.

**Type:** Claude Code `/finolabs-vibecode:open-source-review` or `/open-source-review`; Codex `$open-source-review`; Antigravity `/open-source-review`.

## Tips

- It finds and reports; fixes, history rewrites, visibility changes and releases each need your explicit go.
- The verdict is **ready**, **ready after fixes** or **not ready**; an unchecked secrets, leaks or license group caps it at **not ready**.
- A tool that is not installed is BLOCKED, not PASS.
- After a repository is public, run it again before each MINOR release and when `SECURITY.md`, CI or the settings change.
