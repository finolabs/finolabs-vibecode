---
name: plugin-packaging
description: Package agent skills as a plugin that installs on Claude Code, Codex and Antigravity from one repository. Use when creating or restructuring a plugin or skill repository, writing or fixing a plugin manifest or marketplace catalog, designing a plugin icon, preparing listing metadata, adding a new host, or checking that a package validates before a release or directory submission.
---

# Plugin packaging

One repository, one `skills/` folder, one manifest per host. This skill holds the decisions that stay stable across hosts. Field-level schemas change often, so read them from each host's own tools and docs at the time you package (the **authority** column below) instead of copying them into the repository.

| Host | Manifest | Catalog | Authority for fields and checks |
| --- | --- | --- | --- |
| Claude Code | `.claude-plugin/plugin.json` | `.claude-plugin/marketplace.json` | [plugin manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference.md), [marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference.md), `claude plugin validate . --profile directory --strict` (well-formedness only: the directory portal's **Validate** runs more checks); the `plugin-dev` and `skill-creator` skills for authoring |
| Codex | `.codex-plugin/plugin.json` | `.agents/plugins/marketplace.json` | [build plugins](https://developers.openai.com/codex/plugins/build), [submission fields](https://developers.openai.com/plugins/deploy/submission); no local validator, the portal validates the upload |
| Antigravity | `.antigravity-plugin/plugin.json` | none; install from the repository URL | [build plugins](https://antigravity.google/docs/build-plugins), `agy plugin validate . --strict`; the built-in `plugin` and `agy-customizations` skills |

## 1. Layout

- Skills live in `skills/<name>/SKILL.md`; the folder name equals the `name` field. A shared name prefix keeps a pack's skills together and avoids collisions with other packs.
- Each host's manifest sits in its own folder. A root `plugin.json` is read by both Codex (its preferred location) and Antigravity (its native manifest, with a closed schema), so one file cannot satisfy both.
- Hooks shared by Claude Code and Codex stay in shell form. Claude Code's exec form (`"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/…"]`, no shell) has no Codex counterpart: Codex hook handlers take one `command` string and no `args`, and expose `PLUGIN_ROOT` and `CLAUDE_PLUGIN_ROOT` as environment variables. To use exec form on Claude Code, give Codex its own hooks file through the `hooks` field of its manifest, which replaces Codex's default `hooks/hooks.json` ([Claude Code hooks](https://code.claude.com/docs/en/hooks.md), [Codex hooks](https://learn.chatgpt.com/docs/hooks)).
- Keep every skill folder self-contained: single-skill installers (skills.sh) copy one folder and nothing around it. Disclose reference material into `references/` and executables into `scripts/` beside the skill that uses them; a file two skills need gets a copy in each, with a CI check that the copies match. A skill that cannot work without another names it as a dependency and says how to install it. Keep machine-specific facts in user configuration, never in the package.
- Ship only what the host loads: no build output, caches, OS files, local notes or eval results.

Done when every host's validator finds the expected number of skills.

## 2. Manifests

- Fill the identity fields consistently on every host: `name` (kebab-case, no host or vendor name as a prefix), display name, description, version, author, homepage, repository, license (SPDX).
- **Version**: one manifest is the source of truth and the others copy it; CI fails when they differ. Bumps, tags and the changelog follow `versioning`.
- **Description**: what the plugin does and for whom, in the length each host recommends (Antigravity suggests 120–160 characters; Codex limits its short description to 30).
- **Listing metadata**: icon, documentation, support, privacy and terms URLs where the host reads them (Claude's directory fields, Codex's `interface` block). URLs point at files that exist in the public repository.

## 3. Skill frontmatter across hosts

- `name` and `description` are the portable core. The description carries the triggers: what the skill does, then each distinct case that should fire it.
- Claude Code also reads keys such as `disable-model-invocation`, `user-invocable` and `argument-hint`; other hosts ignore them, but a claude.ai skill upload rejects them. Keep that in mind before offering a skill as a standalone upload.
- A skill the human should start by hand (a setup or a router) sets `disable-model-invocation: true`, which removes its description from the agent's context. Hosts that ignore the key still list it, so its description also says to run it only when the user asks for it. Another skill then tells the human to type it rather than calling it.

## 4. Icon

Apply this section only when preparing a submission to a directory that asks for an icon; a plugin installed straight from its repository needs none of it.

- Square, transparent canvas, one simple glyph that reads at 32 px, in the project's brand family (stroke width, corner style, light and dark colors from the project's brand tokens).
- Light and dark variants with identical geometry. Keep the SVG sources and export 512 × 512 transparent PNGs; some directories accept only PNG.
- An `assets/NOTICE.md` records the concept, the owner's approval, that no third-party artwork or image-model output is included, and the SHA-256 of each file.
- The owner approves the design. Show variants side by side on light and dark backgrounds at full size and at 32 px.

## 5. Distribution

- Make the repository its own marketplace on hosts that use catalogs when the plugin is outside any family catalog, so `owner/repo` installs work before any directory listing; inside a family, install from the shared catalog (Codex shows each marketplace as its own group).
- A family of plugins shares one catalog repository serving every host that uses catalogs; it either pins each plugin by commit SHA or tracks protected default branches, and says which; details in [references/catalogs.md](references/catalogs.md).
- Antigravity installs from the repository URL (see [references/catalogs.md](references/catalogs.md)).
- Offer single-skill installs beside the plugin: skills.sh (`npx skills add owner/repo --skill <name>`) finds `skills/<name>/SKILL.md` on its own. Tell users to pick one path per agent, since both list every skill twice.
- Write the install commands for every host in the README, verified against each host's `--help`.

### Directory editions

Read [references/directories.md](references/directories.md) before preparing a submission to Anthropic's or OpenAI's plugin directory: who submits, the fields, the holds each portal raises that no local validator shows, and what the owner must answer.

- When a directory refuses a component the plugin ships (Anthropic's policy excludes AI image generation; OpenAI refuses lifecycle hooks), submit a generated **edition** instead of trimming the plugin itself. One build script per directory derives the edition from the same sources: it copies the files the edition keeps, removes regions between marker comments, applies exact text edits that fail the build when the source no longer contains them, and overlays the edition's own files (a README, a setup skill without the refused feature).
- An edition Anthropic's directory follows is committed in its own folder, which becomes the submitted plugin path, and a test fails while it differs from what the build script produces. An edition uploaded as a ZIP (Codex) is built from the release tag and never committed.
- Runtime code reads which files the edition ships and turns off the features whose files are missing, so no command offers what the edition left out.
- Leave out of an edition everything a directory holds or refuses without need: hooks, URLs in scripts that hand the environment on, `package.json` and lockfiles, binaries, files over 256 KiB. For an organization that is not Verified, Anthropic's directory refuses scripts and other local code outright, so an edition there holds Markdown, JSON and images only, or the plugin stays on its own marketplace.

## 6. Checks before a release

Run and read each one:

- every host validator above, strict where available;
- the trigger suite: one `claude plugin eval` case per model-invoked skill that must fire it, plus negative cases that must fire nothing (`--ablation none` keeps `Skill` graders scored). Run only the cases of skills whose `description` changed since the last release (`--case`), and the whole suite before a MINOR release; a patch release with no `description` change needs none;
- after installing on Claude Code, `/skill-doctor` for each skill's listing cost, and from the second release on, whether it is ever used (an interactive check: where it cannot run, say so);
- `open-source-review` for license, payload, leaks and community files;
- before a directory submission, rebuild each edition, run the local validator on it, then the directory portal's own validation, and read every finding marked blocking or held;
- when the plugin is listed in a shared catalog, run the catalog check and, if the catalog pins SHAs, update it after the tag.

A validator pass shows the package loads; only the trigger suite and real use show the skills help.

## Authority

Creating a marketplace repository, submitting to a directory, tagging and publishing need the owner's explicit approval. Preparing manifests, icons, editions and checks for review needs none. A directory form's data-handling answers, policy attestations and compliance acknowledgements are the owner's to give; when one conflicts with what the plugin does, show the owner the conflict instead of choosing.
