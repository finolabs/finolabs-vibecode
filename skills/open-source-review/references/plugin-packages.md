# Plugin and skill packages

Read during step 2 of `open-source-review` when the repository ships a plugin or skills; mark every item below and report it in the Plugin and skill packages group.

- The validators pass: `claude plugin validate .` (and `--profile directory --strict` before a directory submission); the Codex manifest is checked against its current schema. Run them on a fresh clone: in a working checkout they also read untracked files such as `.DS_Store`.
- Before a directory submission, walk that directory's own pre-submission list ([Anthropic](https://claude.com/docs/plugins/pre-submission-checklist.md), [OpenAI](https://developers.openai.com/plugins/deploy/submission)) against the submitted folder or ZIP; `plugin-packaging` lists what each refuses or holds.
  Portal validation uploads the package and is not part of this review: list what only the portal can confirm beside the recheck items, so a ready verdict does not hide it.
- Each skill has a valid `name` and a trigger-rich `description`; a trigger check shows each model-invoked skill fires on a representative prompt and stays quiet on an unrelated one.
- Host-specific facts (paths, commands, allow-rules) live in configuration or references, not in skill bodies.
- Listing assets that the target directory requires (icon, URLs) exist inside the package.
