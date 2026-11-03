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

CI runs these on every pull request (`.github/workflows/validate.yml`); run them locally first:

```bash
claude plugin validate .
python3 -m unittest discover -s tests -v
python3 -I scripts/check-references.py
```

- The tests include the usage-metrics hook and the dashboard page. `tests/page_runner.js` runs the page's script in node against a fake DOM; those tests skip when node is not installed. `scripts/fnl_metrics.py` is copied byte for byte into `skills/fnl-coding-router/scripts/` and `skills/fnl-status/scripts/`; edit the one in `scripts/` and copy it over, because a test fails when the copies differ.
- To try a change on a real session without installing it, load the plugin with `claude --plugin-dir .` and point `FNL_STATE_DIR` at a throwaway folder so the test events stay out of your own record.
- `check-references.py` keeps the skills consistent with each other: every `fnl-` name exists, every `fnl-<name>` "Section" and `<file>.md` "Section" reference names a real heading, relative links resolve, ledger flags cited in the skills exist in `ledger.py`, and every flag in the host config template is described in the agent contracts. When you rename a heading or a flag, fix what it reports.
- When you change a skill's `description`, run a trigger check: start an agent with the plugin loaded (`claude --plugin-dir .`), give it a representative prompt for the skill, and confirm the skill loads; then give it an unrelated prompt and confirm it does not. The suite in `evals/` runs with `claude plugin eval`; after changing a skill's rules, run its behavior cases (`claude plugin eval . --tag behavior --scaffold`).

## Adding a host

A host is an agent that installs the plugin or takes delegated work (today Claude Code, Codex and Antigravity). Adding one touches every place that holds per-host facts; `git grep -il antigravity` lists them. In order:

1. **Manifest**: `.<host>-plugin/plugin.json` with the same version as `.claude-plugin/plugin.json`, and the host added to the "Manifest versions match" step in the workflow. `fnl-plugin-packaging` covers layout and schemas; the host's own validator is the authority.
2. **Install and setup**: the README sections for people and for AI agents, with the install, verify and setup commands, each checked on a real install.
3. **Session start**: the host's way of loading the coding-router reminder (a hook, an always-on rule such as `rules/AGENTS.md`).
4. **Delegation**: a section in `fnl-delegate`'s `references/agents.md` (headless command, read-only mode, end of run, quota, outcome mapping), a column in `references/models.md` with its recheck command, a section in `references/host-template.md`, and the host's name in the `AGENTS` and `COORDINATORS` lists of `scripts/ledger.py` (with a test).
5. **Per-host references**: instruction files in `fnl-setup-instructions/references/hosts.md`, titles in `fnl-session-hygiene/references/titles.md`, review instruments in `fnl-review-gate` and `fnl-security-review-gate`.
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
