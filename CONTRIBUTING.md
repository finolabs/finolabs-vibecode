# Contributing

Thank you for helping improve `finolabs-vibecode`. The plugin is a set of skills written for AI coding agents, so a contribution is usually a change to a skill's wording, triggers or references.

## Before you start

Open an issue describing the problem or the rule you want to change, with an example of the agent behavior you observed and the behavior you expect. Use synthetic names and data in examples; never paste private transcripts, credentials or customer information.

## Making a change

1. Fork the repository and create a branch from `main`.
2. Edit the skill under `skills/fnl-<name>/`. Keep each skill focused; put long reference material in `references/` and executable helpers in `scripts/`. The conventions are in [CLAUDE.md](CLAUDE.md).
3. Record the change under `Unreleased` in [CHANGELOG.md](CHANGELOG.md) when it alters what a skill tells an agent to do.
4. Run the checks below.
5. Open a pull request that explains the change, the evidence for it, and the checks you ran.

## Checks

CI runs the full script suite and the reference/copy checks on every pull request (`.github/workflows/validate.yml`). Locally, run whole targeted modules covering the change and traced consumers; running the full suite is optional for contributors because CI runs it. Agents follow `fnl-verification` and run the full suite only when the owner requests it. For example, for a documentation/reference change:

```bash
claude plugin validate .
python3 -I scripts/run_env.py -- python3 -I tests/test_spec_status.py
python3 -I scripts/run_env.py -- python3 -I tests/test_shared_copies.py
python3 -I scripts/check-references.py .
```

- The tests include the usage-metrics hook and the dashboard page. `tests/page_runner.js` runs the page's script in node against a fake DOM; those tests skip when node is not installed. Shared helpers have byte-identical copies in consuming skills; the canonical copy groups are in the workflow and `tests/test_shared_copies.py` checks them. For example, `scripts/fnl_metrics.py` is copied into `fnl-coding-router`, `fnl-status` and `fnl-update`. Update every listed copy with a shared change.
- Script tests use temporary account homes/data roots via `tests/data_root_fixture.py` and module-local helpers. Never print, dump, log or assert on the process environment or read credentials; use synthetic mappings and compare only names. Build secret- or path-shaped test literals by concatenation. `HOME` does not redirect canonical state, and `FNL_STATE_DIR` redirects only events/dashboard, so neither isolates consent, quota, receipts or other canonical data. A live `claude --plugin-dir .` session can still touch real state and contact providers; it is a separate, explicitly authorized check.
- `check-references.py` keeps the skills consistent with each other: every `fnl-` name exists, every `fnl-<name>` "Section" and `<file>.md` "Section" reference names a real heading, relative links resolve, ledger flags cited in the skills exist in `ledger.py`, and every flag in the host config template is described in the agent contracts. It also checks that the README skill list and `fnl-ask` map match every skill folder, and rejects retired skill names in tracked files except dated changelog releases and the Unreleased migration mapping. When consolidating skills, update both lists, the guides, manifests, trigger evals and fixtures in the same change. When you rename a heading or a flag, fix what it reports.
- When you change a skill's `description`, run a trigger check: start an agent with the plugin loaded (`claude --plugin-dir .`), give it a representative prompt for the skill, and confirm the skill loads; then give it an unrelated prompt and confirm it does not. The suite in `evals/` runs with `claude plugin eval`; after changing a skill's rules, run its behavior cases (`claude plugin eval . --tag behavior --scaffold`).

## Review and merge

Code and security reviews are posted as pull request comments with the gate's current-head markers; the low-risk lane lets one reviewer post both comments when `merge_check.py --lane` confirms eligibility. The repository ruleset requires the `validate` check and zero GitHub approving reviews; `skills/fnl-review-gate/scripts/merge_check.py` enforces the separate comment-based review gate, passing checks and any required router marker before merge. A contributor without write access also needs an owner's approving review on the current head; changed bytes need fresh review.

## Adding a host

A host is an agent that installs the plugin or takes delegated work (today Claude Code, Codex and Antigravity). Adding one touches every place that holds per-host facts; `git grep -il antigravity` lists them. In order:

1. **Manifest**: `.<host>-plugin/plugin.json` with the same version as `.claude-plugin/plugin.json`, and the host added to the "Manifest versions match" step in the workflow. `fnl-plugin-packaging` covers layout and schemas; the host's own validator is the authority.
2. **Install and setup**: the README sections for people and for AI agents, with the install, verify and setup commands, each checked on a real install.
3. **Session start**: the host's way of loading the coding-router reminder (a hook, an always-on rule such as `rules/AGENTS.md`).
4. **Delegation**: a section in `fnl-delegate`'s `references/agents.md` (headless command, read-only mode, end of run, quota, outcome mapping), a column in `references/models.md` with its recheck command, a section in `references/host-template.md`, and the host's name in the `AGENTS` and `COORDINATORS` lists of `skills/fnl-delegate/scripts/ledger.py` (with a test).
5. **Per-host references**: instruction files in `fnl-setup/references/instructions/hosts.md`, titles in `fnl-session-hygiene/references/titles.md`, review instruments in `fnl-review-gate` and `fnl-security-review-gate`.
6. **Evidence**: a trigger run on the new host for a few skills, recorded in the pull request, and the facts dated where the file keeps a "checked" date.

## Releasing

Maintainers only; tags and releases need the owner's go (`fnl-versioning` "Authority").

1. Every change since the last tag is under `Unreleased` in `CHANGELOG.md`.
2. An adversarial review of the whole release by a model family other than the one that wrote most of it (for example Codex or Antigravity reviewing work written with Claude Code): contradictions between skills, rules that no longer match the scripts, claims about hosts that nobody checked. Record its findings and their dispositions in the release pull request.
3. `references/models.md` in `fnl-delegate` has a review-by date in the future; recheck the rows when it has passed.
4. The release pull request moves `Unreleased` under the version heading, drops `-dev` from the three manifests, and passes the review gate and CI.
5. After merge, tag the merge commit `vX.Y.Z` once CI passes on it, publish the GitHub release from the changelog section, then set `main` to the next `-dev` version.

## Commits

Atomic commits with imperative subject lines, as described in [skills/fnl-commit-messages/SKILL.md](skills/fnl-commit-messages/SKILL.md).

## License

By contributing, you agree that your contribution is licensed under the [MIT License](LICENSE).
