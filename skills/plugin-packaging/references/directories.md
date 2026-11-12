# Directory submissions

Read when preparing a plugin for Anthropic's plugin directory or OpenAI's Codex plugin directory, or when a directory holds or refuses a submission.

Checked 2026-11-12 against the pages linked below and one listing taken through both portals. Re-read each directory's pages before submitting: their checks change between releases. A line marked **observed** comes from the portal itself and is in no published page; confirm it in the portal.

## Anthropic directory

Sources: [publish to the directory](https://claude.com/docs/directory/publish.md), [submit your plugin](https://claude.com/docs/plugins/submit.md), [pre-submission checklist](https://claude.com/docs/plugins/pre-submission-checklist.md), [plugin structure and surfaces](https://claude.com/docs/plugins/build.md), [Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy).

- **Who submits**: a claude.ai account on Pro, Max, Ultra, Team or Enterprise (an Owner on Team and Enterprise), in the developer portal at `claude.ai/directory/manage`, with GitHub connected in that same Claude organization. The first organization to submit a repository folder holds that listing; a second organization is refused, so submit from the organization that should own it long term.
- **Source fields**: repository, plugin path (the folder holding `.claude-plugin/plugin.json`), and **Branch or tag**, the ref the directory follows for new versions. A tag stays on its commit, so a listing that follows a tag changes only when the tag is moved or the tracked ref is edited; tag protection in `versioning` makes tags immutable, so follow a release branch or edit the tracked tag at each release. The repository and folder cannot change after submitting.
- **Two validators**: `claude plugin validate <folder> --profile directory --strict` checks only well-formedness and a few directory refusals. The portal's **Validate** runs every check and reports each finding as Blocking, Policy hold, Warning or Note; a result covers one commit, so push, then re-validate. A clean local run is no prediction of the portal's holds.
- **Holds to expect** (each lets you submit, then waits for a reviewer, and returns on every new version):
  - **Uses a credential from the user's machine**: a script reads an environment value and could send it to a server. **Observed**: a URL host string in a script that also passes an `env` object to a child process was enough to raise it; keep URLs out of scripts that hand the environment on (whether that alone clears the hold is unconfirmed).
  - **Scripts the validator couldn't follow**: a command hook or server runs a non-shell file, or a shell script that runs another file.
  - **Publisher name may be confused with another** for `author.name`, and the name and brand look-alike holds.
  - **Observed**: notes that command hooks, `allowed-tools` beyond Read, Grep, Glob and LS, and script files will later be accepted only from Verified organizations. No published process to become Verified was found: Verified is decided during review, and the contact is `directory` at `anthropic.com`.
- **Surfaces**: one listing appears in claude.ai chat, Cowork and Claude Code, wherever the plugin's components load (skills load everywhere). A plugin that only works in Claude Code (it runs a local CLI) says so in its README, and in every free-text field the form offers. **Observed**: the portal lists all three surfaces; narrow them by hand.
- **Data handling and compliance**: the form asks whether the plugin reads or stores personal data, sends data to services beyond its declared connectors, how long it keeps data, and whether it is meant for people under 18, then four acknowledgements. **Observed**: one acknowledgement says the plugin executes no code outside its declared MCP servers, which a plugin that runs local scripts cannot truthfully select; name the conflict to the owner and let the owner decide or ask `directory` at `anthropic.com`. The answers and acknowledgements are the owner's.
- **Policy exclusions**: read the policy against what the plugin does (for example, section 4B excludes software that uses AI models to generate images) and ship a directory edition without the excluded parts.

## OpenAI Codex directory

Sources: [plugin submission](https://developers.openai.com/plugins/deploy/submission), [desktop-only plugins](https://developers.openai.com/plugins/deploy/desktop-only), [build plugins](https://developers.openai.com/codex/plugins/build).

- **Who submits**: an organization owner, or a member with Apps Management Write, after individual or business verification in the organization settings.
- **Package**: a ZIP upload. A package with lifecycle hooks or app references cannot be submitted, and Codex loads `hooks/hooks.json` by default when the manifest names no `hooks`, so the submitted edition leaves the `hooks/` folder out, not only the manifest field.
- **Desktop-only**: a plugin that runs a local program or a local MCP server is desktop-only. Choose **Create plugin** → **Skills only**, and set `requires_local_executor: true` (in `extensions.com.openai` of a root `plugin.json`, or at the top level of a legacy `.codex-plugin/plugin.json`). Local MCP submissions are limited to approved partners: if the portal rejects the field, the owner sends the organization ID to an OpenAI representative and waits for allowlisting. Test a clean desktop install of the unpacked ZIP first.
- **Listing fields**: `displayName` and `shortDescription` at most 30 characters each, `longDescription` at most 4000; icons and logos square, at least 48 × 48 px, PNG, JPEG, WebP or SVG up to 5 MiB; every URL HTTPS without embedded credentials.
- **Review**: submitting asks for policy attestations, which are the owner's.
