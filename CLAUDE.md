# finos-vibe-code

Agent context for contributing to this repository. User-facing documentation is in `README.md`.

## What this repository is

One plugin with a skill set that gives AI coding agents a single engineering practice: coding workflow routing, agent orchestration, session hygiene, versioning, commit messages, code and security review gates, verification, and open source readiness. It ships to Claude Code (`.claude-plugin/plugin.json`) and Codex (`.codex-plugin/plugin.json`) from one `skills/` folder.

## Conventions

- Every skill lives in `skills/fnl-<name>/SKILL.md`; the folder name equals the `name` field, and every name starts with `fnl-`. Skills refer to each other by their `fnl-` names.
- Each skill stays focused, with a trigger-rich `description` that leads with what the skill does and lists the distinct cases that should fire it. Disclose reference material into `references/` and executable helpers into `scripts/`.
- Host-specific facts (paths, commands, shims, allow-rules) belong in the host config described by `fnl-orchestration`, never in skill bodies.
- Content is generic: no organization, customer or personal names, and no machine paths. Examples use synthetic names.
- All content is English.

## Versions

`.claude-plugin/plugin.json` is the single source of truth for the version; `.codex-plugin/plugin.json` must match it. Follow `skills/fnl-versioning/SKILL.md` for bumps, the changelog and tags. Record every change to the public surface under `Unreleased` in `CHANGELOG.md`.

## Checks before committing

- `claude plugin validate .` passes.
- A changed `description` gets a trigger check: a representative prompt fires the skill, and an unrelated prompt does not.
- `skills/fnl-open-source-review/SKILL.md` stays green for this repository.

## Commits

Follow `skills/fnl-commit-messages/SKILL.md`: atomic commits, imperative subject lines, no secrets, env files or generated output.
