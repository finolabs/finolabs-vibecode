# Feature: companions (user scope)

Needs: nothing. Questions and recommendations only; nothing installed (advisory, agent judgment).

Load [companions.md](../companions.md) as data: source, license, pin, check date, questions, selection conditions and data notes. Check the skill listing for missing companions; never run an installer to detect one. Keep known missing matches for the core's closing reminders, including when beginner skipped questions.

Every question uses the native question tool per [interview.md](../interview.md), with its stated fallback only. Neutral choices, none preselected or recommended; a default, timeout or auto-selected option never counts. "install everything" never answers a companion question. Headless: leave decisions open. Never execute an install command, script or plugin installer, even after Yes. Install nothing yourself.

## Quick (row 22)

Ask exactly one multi-select question: "What do you do with this plugin?" Choices: writing Vietnamese for readers; delegating work to Antigravity; drawing architecture or flow diagrams; mind maps and outlines; none of these. Several may be selected; never combine "none of these" with another choice (reject mixed answers and leave the selection open). Match only the selection conditions in the data table; `typesafe-ai` is Advanced only. Skip installed matches; `agybird` is eligible only on Claude Code/Codex, never offer its install in Antigravity.

"none of these" alone records `companions: declined` through `python3 -I <this skill folder>/scripts/setup_features.py decline companions --yes`, and ends this feature. A bare run skips recorded declines; `add companions` always asks again. An unanswered or default selection records nothing.

For each selected missing match, show one line of reason and its pinned install command with source, license, check date and data note; then the offer below once per companion, at most four. Quick adds at most five companion questions (one selection plus four offers); no review-instrument offers in Quick.

## Shared offer (row 23)

Ask: "For this companion, show the install command?" Labels: "Show me how to install" / "Not now" (neutral Yes/No). A Yes only prints the pinned install command from the data, with source, license, pin or absence of a tag, check date and data note; it records nothing. A No records nothing. No installation, opt-in, grant, or feature-decline record follows either answer. The selection above alone can record a decline.

## Advanced (rows 23 and 24)

Advanced skips the Quick selection. For each missing companion, use its data question for a short interview: what it does for this user, a concrete example in their stack (look up authorized facts first; ask if unknown), what it costs or sends (telemetry, fonts, accounts), and the fallback the plugin keeps without it; then the same offer. `typesafe-ai` supplies optional cookbooks; `judge.py` makes calls without that skill; never imply the skill enables or consents to Jev.

Advanced review instruments (row 24): look up installed hosts' skill listing and `--help` only: Claude Code `/code-review` and `/security-review`, Codex `codex review`, Cloudflare `security-audit`; Antigravity has none. Review roles run these as engines on their configured family; missing instruments leave manual review, disclosed in every report.
For each missing instrument, explain the benefit/example, costs/data and manual fallback, then ask: "Show this review instrument's install or update command?" Use the same neutral labels and Yes/No behavior above; print only, record nothing. Check the host's official docs for its command. For `security-audit`, show `npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit`; verify release tags and pin one if offered, otherwise disclose none. No review-tool recommendation widens Quick.
