# finolabs-vibecode

Agent context for contributing to this repository. User-facing documentation is in `README.md`.

## What this repository is

One plugin with a skill set that gives AI coding agents a single engineering practice: routing of coding work, agent delegation, session hygiene, versioning, commit messages, code and security review gates, verification, and open source readiness. It ships to Claude Code (`.claude-plugin/plugin.json`), Codex (`.codex-plugin/plugin.json`) and Antigravity (`.antigravity-plugin/plugin.json`) from one `skills/` folder. Keep each host's manifest in its own folder: a root `plugin.json` would be read by both Codex and Antigravity, whose schemas conflict.

## Conventions

- Compose before you build. Before adding a capability, look for a native host command or a trusted published skill that already does it: a known organization or author, an OSI license, active maintenance, readable instructions, no hidden network or credential behavior. Point to it by name with its source and install command, keep a fallback in our skill that holds the same quality bar without it, and credit it in the README. Our skills own routing, depth, delegation, gates and conventions.
- Every skill lives in `skills/fnl-<name>/SKILL.md`; the folder name equals the `name` field, and every name starts with `fnl-`. Skills refer to each other by their `fnl-` names.
- Each skill folder is self-contained, so it works when installed alone through skills.sh: nothing in it points outside its own folder. A file two skills need is copied into both (CI checks the copies match); a skill that needs another names it as a dependency.
- Each skill stays focused, with a trigger-rich `description` that leads with what the skill does and lists the distinct cases that should fire it. Disclose reference material into `references/` and executable helpers into `scripts/`.
- Host-specific facts (paths, commands, shims, allow-rules) belong in the host config described by `fnl-delegate`, never in skill bodies.
- Content is generic: no organization, customer or personal names, and no machine paths. Examples use synthetic names.
- All content is English.

## Versions

`.claude-plugin/plugin.json` is the single source of truth for the version; `.codex-plugin/plugin.json` and `.antigravity-plugin/plugin.json` must match it. Follow `skills/fnl-versioning/SKILL.md` for bumps, the changelog and tags. Record every change to the public surface under `Unreleased` in `CHANGELOG.md`.

## Checks before committing

- `claude plugin validate .` passes.
- A changed `description` gets a trigger check: a representative prompt fires the skill, and an unrelated prompt does not.
- `skills/fnl-open-source-review/SKILL.md` stays green for this repository.

## Commits

Follow `skills/fnl-commit-messages/SKILL.md`: atomic commits, imperative subject lines, no secrets, env files or generated output.
