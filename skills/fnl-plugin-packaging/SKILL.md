---
name: fnl-plugin-packaging
description: Package agent skills as a plugin that installs on Claude Code, Codex and Antigravity from one repository. Use when creating or restructuring a plugin or skill repository, writing or fixing a plugin manifest or marketplace catalog, designing a plugin icon, preparing listing metadata, adding a new host, or checking that a package validates before a release or directory submission.
---

# Plugin packaging

One repository, one `skills/` folder, one manifest per host. This skill holds the decisions that stay stable across hosts. Field-level schemas change often, so read them from each host's own tools and docs at the time you package (the **authority** column below) instead of copying them into the repository.

| Host | Manifest | Catalog | Authority for fields and checks |
| --- | --- | --- | --- |
| Claude Code | `.claude-plugin/plugin.json` | `.claude-plugin/marketplace.json` | [plugin manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference.md), [marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference.md), `claude plugin validate . --profile directory`; the `plugin-dev` and `skill-creator` skills for authoring |
| Codex | `.codex-plugin/plugin.json` | `.agents/plugins/marketplace.json` | [build plugins](https://developers.openai.com/codex/plugins/build), [submission fields](https://developers.openai.com/plugins/deploy/submission); no local validator, the portal validates the upload |
| Antigravity | `.antigravity-plugin/plugin.json` | none; install from the repository URL | [build plugins](https://antigravity.google/docs/build-plugins), `agy plugin validate . --strict`; the built-in `plugin` and `agy-customizations` skills |

## 1. Layout

- Skills live in `skills/<name>/SKILL.md`; the folder name equals the `name` field. A shared name prefix keeps a pack's skills together and avoids collisions with other packs.
- Each host's manifest sits in its own folder. A root `plugin.json` is read by both Codex (its preferred location) and Antigravity (its native manifest, with a closed schema), so one file cannot satisfy both.
- Disclose reference material into `references/` and executables into `scripts/` beside the skill that uses them. Keep machine-specific facts in user configuration, never in the package.
- Ship only what the host loads: no build output, caches, OS files, local notes or eval results.

Done when every host's validator finds the expected number of skills.

## 2. Manifests

- Fill the identity fields consistently on every host: `name` (kebab-case, no host or vendor name as a prefix), display name, description, version, author, homepage, repository, license (SPDX).
- **Version**: one manifest is the source of truth and the others copy it; CI fails when they differ. Bumps, tags and the changelog follow `fnl-versioning`.
- **Description**: what the plugin does and for whom, in the length each host recommends (Antigravity suggests 120–160 characters; Codex limits its short description to 30).
- **Listing metadata**: icon, documentation, support, privacy and terms URLs where the host reads them (Claude's directory fields, Codex's `interface` block). URLs point at files that exist in the public repository.

## 3. Skill frontmatter across hosts

- `name` and `description` are the portable core. The description carries the triggers: what the skill does, then each distinct case that should fire it.
- Claude Code also reads keys such as `disable-model-invocation`, `user-invocable` and `argument-hint`; other hosts ignore them, but a claude.ai skill upload rejects them. Keep that in mind before offering a skill as a standalone upload.
- A skill the human should start by hand (a setup or a router) sets `disable-model-invocation: true`, which removes its description from the agent's context. Another skill then tells the human to type it rather than calling it.

## 4. Icon

- Square, transparent canvas, one simple glyph that reads at 32 px, in the project's brand family (stroke width, corner style, light and dark colors from the project's brand tokens).
- Light and dark variants with identical geometry. Keep the SVG sources and export 512 × 512 transparent PNGs; some directories accept only PNG.
- An `assets/NOTICE.md` records the concept, the owner's approval, that no third-party artwork or image-model output is included, and the SHA-256 of each file.
- The owner approves the design. Show variants side by side on light and dark backgrounds at full size and at 32 px.

## 5. Distribution

- Make the repository its own marketplace on hosts that use catalogs, so `owner/repo` installs work before any directory listing.
- An aggregate marketplace in another repository pins each plugin by commit SHA (`source` of type `github` with `sha`), not by branch.
- Write the install commands for every host in the README, verified against each host's `--help`.

## 6. Checks before a release

Run and read each one:

- every host validator above, strict where available;
- the trigger suite: one `claude plugin eval` case per model-invoked skill that must fire it, plus negative cases that must fire nothing (`--ablation none` keeps `Skill` graders scored);
- after installing, `/skill-doctor` for each skill's listing cost and whether it is ever used;
- `fnl-open-source-review` for license, payload, leaks and community files.

A validator pass shows the package loads; only the trigger suite and real use show the skills help.

## Authority

Creating a marketplace repository, submitting to a directory, tagging and publishing need the owner's explicit approval. Preparing manifests, icons and checks for review needs none.
