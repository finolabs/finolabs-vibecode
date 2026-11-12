# Companion skills

Optional data for the `companions` feature; questions are advisory (agent judgment). Install nothing. Commands below are for the user to run, never setup. Skills CLI installs a skill, not a plugin; choose the current host when prompted (project-local by default). The CLI is pinned and telemetry disabled; downloads still contact npm and GitHub. Show the check date next to each command.

## Sources and install commands

| Skill | Official source / license | Release/tag | Install command (print only) | Checked |
| --- | --- | --- | --- | --- |
| `agybird` | [finolabs/agybird](https://github.com/finolabs/agybird/tree/v0.4.0), MIT | v0.4.0 | `DISABLE_TELEMETRY=1 npx skills@1.5.20 add https://github.com/finolabs/agybird/tree/v0.4.0 --skill agybird` | 2026-11-07 |
| `vietnamizer` | [finolabs/vietnamizer](https://github.com/finolabs/vietnamizer/tree/v0.13.3), MIT | v0.13.3 | `DISABLE_TELEMETRY=1 npx skills@1.5.20 add https://github.com/finolabs/vietnamizer/tree/v0.13.3 --skill vietnamizer` | 2026-11-07 |
| `typesafe-ai` | [typesafe-ai/skills](https://github.com/typesafe-ai/skills/tree/v0.6.2), MIT | v0.6.2 | `DISABLE_TELEMETRY=1 npx skills@1.5.20 add https://github.com/typesafe-ai/skills/tree/v0.6.2 --skill typesafe-ai` | 2026-11-07 |
| `diagram-design` | [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design), MIT | none (no release/tag) | `DISABLE_TELEMETRY=1 npx skills@1.5.20 add https://github.com/cathrynlavery/diagram-design --skill diagram-design` | 2026-11-07 |
| `markmap` | [finolabs/markmap-skills](https://github.com/finolabs/markmap-skills/tree/v0.2.0), MIT | v0.2.0 | `DISABLE_TELEMETRY=1 npx skills@1.5.20 add https://github.com/finolabs/markmap-skills/tree/v0.2.0 --skill markmap` | 2026-11-07 |
| `security-audit` | [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill), MIT | none (no release/tag) | `DISABLE_TELEMETRY=1 npx skills@1.5.20 add https://github.com/cloudflare/security-audit-skill --skill security-audit` | 2026-11-07 |

These are preferences for choosing offers: no file changes, consent or installation follows an answer; setup sends nothing. Skip or revise later. Installation commands have their own approval.

## Questions and selection data

| Skill | Question text | Quick selection condition | Data note and fallback |
| --- | --- | --- | --- |
| `agybird` | What tasks would you ask Antigravity to do from Claude Code or Codex? | delegating work to Antigravity | Task/context goes to Google's CLI with the user's account/subscription; quota applies, no agybird telemetry. Never install in Antigravity. Fallback: plugin delegation or a manual handoff; separate test-command grants stay in `delegation`. |
| `vietnamizer` | What Vietnamese documents or posts do your readers need? | writing Vietnamese for readers | Edits reader-facing Vietnamese in the host's model/context; host data policy and token costs apply, not agent text/logs/code. Fallback: host edits manually and checks meaning/voice. |
| `typesafe-ai` | Which small decisions would you like TypeSafe’s examples to help you check? | Advanced only; never selected by Quick | Optional cookbooks, not required for calls: plugin `judge.py` makes the call. Jev separately needs authorized key/budget and sends the bounded payload to TypeSafe; the skill grants neither. Fallback: plugin's host judge; no skill needed. |
| `diagram-design` | Which software parts or steps would you like to see in a diagram? | drawing architecture or flow diagrams | Produces HTML/SVG/PNG in the host; Google Fonts requests and optional browser/export dependencies may access the network; no author telemetry declared. Fallback: host draws Mermaid or plain diagrams. |
| `markmap` | What notes or outline would you turn into a mind map? | mind maps and outlines | Host processes source text and uses tokens; Node.js/npx rendering may download npm packages; offline HTML embeds libraries, alternative template loads jsDelivr. No bundled server/maintainer daemon. Fallback: host writes a Markdown outline. |

## Review-instrument data (Advanced only)

| Instrument | Data note and fallback |
| --- | --- |
| `security-audit` | Multi-phase repository security review with independent verification; audit context uses the host's model/provider, token budget and subagents. Node.js runs its validators; audit artifacts are written to the chosen output folder. No source tag exists: installation follows the default branch. Fallback: manual security review with coverage limits disclosed. |

Sources checked against official README/LICENSE and tags on the dates above. Markmap's [README at v0.2.0](https://github.com/finolabs/markmap-skills/blob/v0.2.0/README.md) documents Skills CLI installation and npm/CDN behavior. [Skills CLI source at v1.5.20](https://github.com/vercel-labs/skills/blob/v1.5.20/src/source-parser.ts) supports GitHub `/tree/<tag>` sources. A missing tag is disclosed, never invented.
