# finolabs-vibecode

Agent context for contributing to this repository. User-facing documentation is in `README.md`.

## What this repository is

One plugin with a skill set that gives AI coding agents a single engineering practice: routing of coding work, agent delegation, session hygiene, versioning, commit messages, code and security review gates, verification, and open source readiness. It also carries optional, consent-based usage metrics (hooks that record metadata only, and a local dashboard that `fnl-status` opens). It ships to Claude Code (`.claude-plugin/plugin.json`), Codex (`.codex-plugin/plugin.json`) and Antigravity (`.antigravity-plugin/plugin.json`) from one `skills/` folder. Keep each host's manifest in its own folder: a root `plugin.json` would be read by both Codex and Antigravity, whose schemas conflict.

## Conventions

- Every rule a skill states names its enforcer: a host setting, a hook, the review gate, or agent judgment. A rule enforced only by agent judgment is marked advisory and never promised as automatic.
- Compose before you build. Before adding a capability, look for a native host command or a trusted published skill that already does it: a known organization or author, an OSI license, active maintenance, readable instructions, no hidden network or credential behavior. Point to it by name with its source and install command, keep a fallback in our skill that holds the same quality bar without it, and credit it in the README. Our skills own routing, depth, delegation, gates and conventions.
- Every skill lives in `skills/fnl-<name>/SKILL.md`; the folder name equals the `name` field, and every name starts with `fnl-`. Skills refer to each other by their `fnl-` names.
- Each skill folder is self-contained, so it works when installed alone through skills.sh: nothing in it points outside its own folder. A file two skills need is copied into both (CI checks the copies match); a skill that needs another names it as a dependency.
- Each skill stays focused, with a trigger-rich `description` that leads with what the skill does and lists the distinct cases that should fire it. Disclose reference material into `references/` and executable helpers into `scripts/`.
- Host-specific facts (paths, commands, shims, allow-rules) belong in the host config described by `fnl-delegate`, never in skill bodies.
- Content is generic: no organization, customer or personal names, and no machine paths. Examples use synthetic names.
- All content is English.
- Usage metrics hold metadata only and stay off until the user consents. A new event field goes through `SCHEMA` in `scripts/fnl_metrics.py` and `docs/specs/usage-metrics.md`, never carries prompt, code, command text or paths, and updates `PRIVACY.md`. A hook never blocks a session: it exits 0 and fails closed.
- The update check is the one allowed network call: a detached worker makes a GET to the fixed public GitHub latest-release endpoint, sends nothing about the user, and stores only a timestamp and validated stable tag. It is on by default, separate from metrics consent; `FNL_UPDATE_CHECK=off` stops it. The session-start hook reads local state only, never waits for the worker, exits 0 and fails closed. See `docs/specs/update-check.md`.
- The plugin's own data and config live under `~/.finolabs/vibecode/` (see `README.md`); a skill never hard-codes another location.

## Reviews

Pull requests follow `fnl-review-gate` "Pull requests"; reviewers may post their review comments on them. Pull requests may take the low-risk lane of `fnl-review-gate`.

Standing relay (owner, 02/11/2026): when one model family wrote a pull request, a code review by another model family that cannot post may be posted unchanged by the coordinator, with a second line naming the reviewer, who relayed it and this record. Security reviews and every other relay still need the owner's approval per pull request.

## Versions

`.claude-plugin/plugin.json` is the single source of truth for the version; `.codex-plugin/plugin.json` and `.antigravity-plugin/plugin.json` must match it. Follow `skills/fnl-versioning/SKILL.md` for bumps, the changelog and tags. Record every change to the public surface under `Unreleased` in `CHANGELOG.md`.

## Checks before committing

- `claude plugin validate .` passes.
- A changed `description` gets a trigger check: a representative prompt fires the skill, and an unrelated prompt does not.
- `skills/fnl-open-source-review/SKILL.md` stays green for this repository.
- `python3 -m unittest discover -s tests` passes, and `python3 scripts/check-references.py .` passes.

## Commits

Follow `skills/fnl-commit-messages/SKILL.md`: atomic commits, imperative subject lines, no secrets, env files or generated output.
