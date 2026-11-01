# Contributing

Thank you for helping improve `finos-vibe-code`. The plugin is a set of skills written for AI coding agents, so a contribution is usually a change to a skill's wording, triggers or references.

## Before you start

Open an issue describing the problem or the rule you want to change, with an example of the agent behavior you observed and the behavior you expect. Use synthetic names and data in examples; never paste private transcripts, credentials or customer information.

## Making a change

1. Fork the repository and create a branch from `main`.
2. Edit the skill under `skills/fnl-<name>/`. Keep each skill focused; put long reference material in `references/` and executable helpers in `scripts/`. The conventions are in [CLAUDE.md](CLAUDE.md).
3. Record the change under `Unreleased` in [CHANGELOG.md](CHANGELOG.md) when it alters what a skill tells an agent to do.
4. Run the checks below.
5. Open a pull request that explains the change, the evidence for it, and the checks you ran.

## Checks

```bash
claude plugin validate .
```

When you change a skill's `description`, run a trigger check: start an agent with the plugin loaded (`claude --plugin-dir .`), give it a representative prompt for the skill, and confirm the skill loads; then give it an unrelated prompt and confirm it does not.

## Commits

Atomic commits with imperative subject lines, as described in [skills/fnl-commit-messages/SKILL.md](skills/fnl-commit-messages/SKILL.md).

## License

By contributing, you agree that your contribution is licensed under the [MIT License](LICENSE).
