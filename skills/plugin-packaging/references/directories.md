# Directory submissions

Read when preparing a plugin for Anthropic's plugin directory or OpenAI's Codex plugin directory, building a directory edition, or when a directory holds or refuses a submission.

Checked 2026-11-12 against the pages linked below and one listing taken through both portals. Re-read each directory's pages before submitting: their checks change between releases. A line marked **observed** comes from the portal itself or from other publishers' reports, and is in no published page; confirm it in the current portal.

## Approval before any portal step

Local preparation and local validation need no approval. Every portal step transfers or exposes the package: a ZIP upload, a draft, connecting or granting access to a repository, the portal's **Validate**, a push made so the portal can re-validate, and submitting. Take each one only with the owner's explicit approval for it. Without that approval, stop after the local checks, report the portal checks as pending, and hand the prepared package to the owner.

## Editions

When a directory refuses a component the plugin ships, submit a generated **edition** instead of trimming the plugin itself.

- One build script per directory derives the edition from the same sources: it copies the files the edition keeps, removes regions between marker comments, applies exact text edits that fail the build when the source no longer contains them, and overlays the edition's own files (a README, a setup skill without the refused feature).
- An edition Anthropic's directory follows is committed in its own folder, which becomes the submitted plugin path, and a test fails while it differs from what the build script produces.
  An edition uploaded as a ZIP (Codex) is built from the release tag and never committed.
- Runtime code reads which files the edition ships and turns off the features whose files are missing, so no command offers what the edition left out.
- Leave out what the target directory holds or refuses without need, per its own limits below: hooks, URLs in scripts that hand the environment on, `package.json` and lockfiles, binaries.
  Anthropic holds for a reviewer any file over 256 KiB that is not an image or font; OpenAI accepts listing images up to 5 MiB.

## Anthropic directory

Sources: [publish to the directory](https://claude.com/docs/directory/publish.md), [submit your plugin](https://claude.com/docs/plugins/submit.md), [pre-submission checklist](https://claude.com/docs/plugins/pre-submission-checklist.md), [plugin structure and surfaces](https://claude.com/docs/plugins/build.md), [Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy), and publishers' reports in [anthropics/claude-plugins-official issue 7024](https://github.com/anthropics/claude-plugins-official/issues/7024) (read 2026-11-12).

- **Who submits**: a claude.ai account on Pro, Max, Ultra, Team or Enterprise, in the developer portal at `claude.ai/directory/manage`, with GitHub connected in that same Claude organization.
  On Team and Enterprise an Owner submits; on Enterprise also a member whose custom role grants the **Directory** permission. The first organization to submit a repository folder holds that listing and a second is refused, so submit from the organization that should own it long term.
- **Source fields**: repository, plugin path (the folder holding `.claude-plugin/plugin.json`), and **Branch or tag**, the ref the directory follows for new versions. The repository and folder cannot change after submitting.
  A tag stays on its commit, so a listing that follows a tag changes only when the tracked ref is edited; tags are immutable under `versioning`, so follow a release branch or edit the tracked tag at each release.
- **Two validators**: `claude plugin validate <folder> --profile directory --strict` checks well-formedness and a few directory refusals. The portal's **Validate** runs every check and rates each finding Blocking, Policy hold, Warning or Note, for one commit; a clean local run does not predict the portal's holds.
- **Holds to expect** (each lets you submit, then waits for a reviewer, and returns on every new version):
  - **Uses a credential from the user's machine**: a script reads an environment value and could send it to a server.
    **Observed**: it fired when a script passed the whole environment object to a child process and some script held a remote URL host or a template string read as a command built at run time (`` `job-${id}` ``). Removing the URLs cleared the per-file finding; the cross-file one stayed a warning.
  - **Scripts the validator couldn't follow**: a command hook or server runs a non-shell file, or a shell script that runs another file.
  - **Publisher name may be confused with another** for `author.name`, and the name and brand look-alike holds.
- **Verified-only refusals** (**observed**, this whole item: reported in issue 7024 and seen in the portal; no published page states it):
  - Since about 2026-11-05 the policy check after submitting refuses a version, updates to listed plugins included, from an organization that is not Verified when it ships command hooks, local MCP servers, mods, a `bin/` folder, lockfile installs, `allowed-tools` beyond Read, Grep, Glob and LS, or files outside the allowed types.
  - The allowed types were Markdown, text, JSON, YAML and PNG, JPEG, GIF, WebP and ICO images; scripts (`.mjs`, `.py`, `.sh`, anything starting with `#!`) and package-manager configuration were refused. An allowed `allowed-tools` entry held no `${...}`, `//`, `\\` or URL.
  - The local validator and the portal's **Validate** show these only as notes ("not refused yet"); the refusal comes after submitting.
  - No published way to become Verified exists. The portal says Verified means Anthropic knows the organization is a real company; verifying a domain in Claude did not change it.
  - Before submitting, check every file and every `allowed-tools` entry against these lists. A plugin that needs local code expects refusal until its organization is Verified: keep its own marketplace as the install path, offer a text-only edition if one still helps, and leave writing to `directory` at `anthropic.com` to the owner.
- **After submitting**: the plugin's page has Overview, Review, Versions and Settings tabs, **Check for new commits** and **Withdraw submission**. Without the GitHub push webhook the directory scans on a schedule (**observed**: about every 6 hours).
- **Surfaces**: one listing appears in claude.ai chat, Cowork and Claude Code, wherever the plugin's components load (skills load everywhere). A plugin that works only in Claude Code (it runs a local CLI) says so in its README and in every free-text field the form offers.
  **Observed**: the portal lists all three surfaces; narrow them by hand in the form and again on the Settings tab.
- **Data handling and compliance**: the form asks whether the plugin reads or stores personal data, sends data beyond its declared connectors, how long it keeps data, and whether it is meant for people under 18, then four acknowledgements. The answers and acknowledgements are the owner's.
  **Observed**: one acknowledgement says the plugin executes no code outside its declared MCP servers, which a plugin that runs local scripts cannot truthfully select; show the owner the conflict. Mail to `directory` at `anthropic.com` is the owner's, sent from the contact address the portal lists for the submission.
- **Policy exclusions**: read the policy against the plugin's actual workflow before deciding what an edition leaves out. Section 4B restricts software that uses AI models to generate images, video or audio, but permits design-focused software that creates only visual aids (slides, diagrams, charts, UI mockups, logos, other design assets) when it offers no standalone image generation; a design-only plugin keeps that feature.

## OpenAI Codex directory

Sources: [plugin submission](https://developers.openai.com/plugins/deploy/submission), [desktop-only plugins](https://developers.openai.com/plugins/deploy/desktop-only), [build plugins](https://developers.openai.com/codex/plugins/build).

- **Who submits**: an organization owner, or a member with Apps Management Write, after individual or business verification in the organization settings.
- **Package**: a ZIP upload, which creates a draft and runs the automated checks before **Submit for review**; both need the owner's approval (see the first section).
  A package with lifecycle hooks or app references cannot be submitted, and Codex loads `hooks/hooks.json` by default when the manifest names no `hooks`, so the edition leaves the `hooks/` folder out, not only the manifest field.
- **Desktop-only**: a plugin that runs a local program or a local MCP server is desktop-only. Choose **Create plugin** → **Skills only**, and set `requires_local_executor: true` (in `extensions.com.openai` of a root `plugin.json`, or at the top level of a legacy `.codex-plugin/plugin.json`).
  Local MCP submissions are limited to approved partners: if the portal rejects the field, the owner sends the organization ID to an OpenAI representative and waits for allowlisting. Test a clean desktop install of the unpacked ZIP first.
- **Listing fields**: `displayName` and `shortDescription` at most 30 characters each, `longDescription` at most 4000; icons and logos square, at least 48 × 48 px, PNG, JPEG, WebP or SVG up to 5 MiB; every URL HTTPS without embedded credentials.
- **Review**: submitting asks for policy attestations, which are the owner's.
