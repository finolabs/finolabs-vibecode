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

Read [directory-anthropic.md](directory-anthropic.md): who submits, the tracked branch or tag, the two validators, the holds and the Verified-only refusals to expect, surfaces, the data-handling form and policy exclusions.

## OpenAI Codex directory

Sources: [plugin submission](https://developers.openai.com/plugins/deploy/submission), [desktop-only plugins](https://developers.openai.com/plugins/deploy/desktop-only), [build plugins](https://developers.openai.com/codex/plugins/build).

- **Who submits**: an organization owner, or a member with Apps Management Write, after individual or business verification in the organization settings.
- **Package**: a ZIP upload, which creates a draft and runs the automated checks before **Submit for review**; both need the owner's approval (see the first section).
  A package with lifecycle hooks or app references cannot be submitted, and Codex loads `hooks/hooks.json` by default when the manifest names no `hooks`, so the edition leaves the `hooks/` folder out, not only the manifest field.
- **Desktop-only**: a plugin that runs a local program or a local MCP server is desktop-only. Choose **Create plugin** → **Skills only**, and set `requires_local_executor: true` (in `extensions.com.openai` of a root `plugin.json`, or at the top level of a legacy `.codex-plugin/plugin.json`).
  Local MCP submissions are limited to approved partners: if the portal rejects the field, the owner sends the organization ID to an OpenAI representative and waits for allowlisting. Test a clean desktop install of the unpacked ZIP first.
- **Listing fields**: `displayName` and `shortDescription` at most 30 characters each, `longDescription` at most 4000; icons and logos square, at least 48 × 48 px, PNG, JPEG, WebP or SVG up to 5 MiB; every URL HTTPS without embedded credentials.
- **Review**: submitting asks for policy attestations, which are the owner's.
