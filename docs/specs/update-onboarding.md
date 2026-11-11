# Update onboarding: what a new version asks of the user (draft, scoped to release 0.2.4)

Status: implemented; for release 0.2.4 (2026-11-11), items 1 to 7 are implemented and tested; the exact-version host command (item 6) is verified on no host yet, so `/fnl-update <version>` leaves the host step to the user. Entries for 0.2.0 to 0.2.3 stay an open decision.

## Why

Each release brings things a user has to know or set up to get the value of it. Release 0.2.3 alone added a setup feature with its own consent (the assignment matrix in `/fnl-setup add delegation`), a migration from two old host config sections, new stop or decide categories and a separate excerpt consent in `/fnl-setup add autopilot`, three renamed or new commands (`/fnl-afk`, `/fnl-pause`, `/fnl-help`) and a new Claude Code hook. `fnl-update` today shows the installed and available versions and runs the host's update command; after that the user is on their own, and most of what a release adds stays unused or half set up.

## Owner decision (2026-11-10)

Each release, `fnl-update` must keep pace with what the release adds and help the user finish it: tell them what is new for them and walk them through the setup it needs.

The update goes to the latest stable release by default, and the user can choose or hold a specific version (owner, 2026-11-10).

## What ships

1. **Upgrade notes, one entry per release.** A machine-readable file in the `fnl-update` skill folder (`references/upgrades.json`) with, per version: what was renamed (old name, new name, until when the old one works), new setup features or questions (the `/fnl-setup add <feature>` to run, and whether it asks a new consent), migrations (the command that previews them, for example `matrix_setup.py migrate`), new hooks per host and what the user must do for them (for example trusting hooks again on Codex), and anything removed. Every item has a short plain sentence for the user and, where one exists, a read-only command that tells whether it is already done for this user (for example `matrix_setup.py show` printing that no matrix is set).
2. **Two ways in (owner, 2026-11-10).** `/fnl-update` runs the whole process: it updates to the target version after the user's yes, then goes straight on to the checklist below and offers to finish each open item. `/fnl-update whats-new` only shows what is new: it reads the notes and prints the checklist, and changes nothing, installs nothing and offers no setup step. A user who only wants to look uses the second; a user who wants to update uses the first and is never sent to a second command.
3. **The checklist.** It covers every version between the last version this user went through and the installed one. Only the notes' read-only "is it done" commands run; each item shows as done, open, not applicable to this user, skipped or unknown. The shipped 0.2.4 entry has no such command on any item, so its items show as unknown (or skipped) and are offered. In `/fnl-update`, for each open item in the order the notes give, it offers to run the matching setup step through `fnl-setup`, which keeps every consent question, preview and neutral yes exactly as today. Skipping an item is recorded so the next run does not ask again; nothing is ever set up without the user's own answer.
4. **State, and who writes it.** Each notes item has a stable id, `<version>/<slug>`. The private state folder holds one small file with three things only: the last version whose checklist the user went through (`last_seen`), the ids the user chose to skip, and nothing else; no text, no answers. Only `update_check.py onboard seen <version>` and `onboard skip <id>` write it, and only `/fnl-update` calls them, after the user went through the checklist or chose to skip an item. `/fnl-update whats-new` never writes. The session-start hook only reads it: while the installed version is newer than `last_seen` and has notes, it adds one line naming `/fnl-update`, independent of the newer-release notice, and the line goes away once `/fnl-update` has marked the version seen. A hook never writes this state.
5. **Host update commands verified.** The Codex procedure used for the 0.2.2 and 0.2.3 refreshes (`codex plugin marketplace upgrade <catalog>`, then remove and add the plugin, then trust its hooks again in `/hooks`) moves from unverified to verified with its date, and `fnl-update` offers it after a yes. Antigravity stays unverified until checked the same way.
6. **Latest by default, or a version the user picks.** `/fnl-update` targets the latest stable release, the one the existing update check already caches. `/fnl-update <version>` targets that exact released version instead, newer or older (an older one is a rollback: the checklist then lists what the user loses, from the notes of the versions in between, and no migration runs backwards). `/fnl-update pin <version>` records that the user holds that version: the newer-release notice stops until `/fnl-update unpin`, and `status` shows the pin. The plugin's update check is not widened: it keeps its one fixed `/releases/latest` request and its stored timestamp and tag. A chosen version is checked by the agent with the user's own `gh release view <version> --repo finolabs/finolabs-vibecode --json tagName,isDraft,isPrerelease,url` (always the plugin's own repository, whichever project the user is in; another host uses its equivalent bound to the same repository), and `update_check.py target --evidence <file>` accepts it only when that output names exactly that tag, published, not a draft, not a prerelease, and its `url` is a release page of `github.com/finolabs/finolabs-vibecode`; without such evidence, or with a `-dev` version, the target is refused, never assumed. Each host's command for an exact version is verified on its installed CLI before it is offered, and a host without a verified way says so and leaves the step to the user. The pin is stored with the update check's existing state as a version string only.
7. **The notes are part of releasing.** `fnl-versioning` requires an upgrade-notes entry before a release is proposed, and a test fails when a manifest carries a released version (no `-dev`) with no entry for it. Writing the entry is part of the documentation review the same skill already requires.

## What enforces what

- Scripts: the notes file's schema, the test tying a released version to an entry, the read-only "is it done" commands, `update_check.py onboard` as the only writer of the seen version and skipped ids, `update_check.py target` validating a chosen version from evidence, the session-start line that only reads.
- `fnl-setup`: every consent, preview and write, unchanged.
- Agent judgment, advisory: walking the checklist with the user, offering each step, and writing a good plain sentence per item.

## Limits

- An item whose state cannot be read without running something stays "unknown" and is offered, never assumed done.
- The checklist covers what the plugin itself set up; a host feature the user changed outside the plugin may show stale.

## Open decisions

| Decision | Owner | What unblocks it |
| --- | --- | --- |
| Whether entries for 0.2.0 to 0.2.3 are written back for users who skip several versions | owner | a preference |

## Evidence

`tests/test_upgrade_notes.py` (schema and refusals, the shipped 0.2.4 entry, the release test) and `OnboardTest` in `tests/test_update_check.py` (range selection, item states, skip, writers, the session-start line, target, rollback, pin) were shown failing before the code and pass after it.

The build covered these behaviors, each with a red test: the notes schema and its refusal of unknown keys, the release test (released version without an entry fails, `-dev` passes), version-range selection, a done item, an open item and an item that does not apply, skip recorded and not asked again, no write without `fnl-setup`'s yes, the session-start line shown once after an update, latest as the default target, an exact version accepted only with evidence naming a published stable tag (an older target, an unknown target, missing evidence, and a matching tag from another repository refused by its URL), a rollback listing what is lost, and a pin that silences newer-release notices until unpinned.
