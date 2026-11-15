# plugin-packaging

Typed by the user, or loaded by the agent when the task matches.

**What it does.** Packages agent skills as one plugin that installs on Claude Code, Codex and Antigravity from one repository: layout, manifests, skill frontmatter across hosts, the icon, distribution (marketplaces, catalogs, single-skill installs), the README standard and checklist, and the checks before a release.

**When to use it.** Creating or restructuring a plugin or skill repository, fixing a manifest or catalog, reviewing a plugin README, designing an icon, preparing listing metadata, adding a host, or validating before a release.

**Type:** Claude Code `/finolabs-vibecode:plugin-packaging` or `/plugin-packaging`; Codex `$plugin-packaging`; Antigravity `/plugin-packaging`.

## Tips

- One manifest holds the version and the others copy it; CI fails when they differ.
- Single skills install with `npx skills add owner/repo --skill <name>`; pick one install path per agent, since both list every skill.
- A validator pass shows the package loads; only the trigger suite and real use show the skills help.
- Creating a marketplace repository, directory portal steps, tagging and publishing need your explicit approval.
