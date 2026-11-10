# Update onboarding: what a new version asks of the user (draft, scoped to release 0.2.4)

Status: draft; the owner asked for it on 2026-11-10; nothing is built.

## Why

Each release brings things a user has to know or set up to get the value of it. Release 0.2.3 alone added a setup feature with its own consent (the assignment matrix in `/fnl-setup add delegation`), a migration from two old host config sections, new stop or decide categories and a separate excerpt consent in `/fnl-setup add autopilot`, three renamed or new commands (`/fnl-afk`, `/fnl-pause`, `/fnl-help`) and a new Claude Code hook. `fnl-update` today shows the installed and available versions and runs the host's update command; after that the user is on their own, and most of what a release adds stays unused or half set up.

## Owner decision (2026-11-10)

Each release, `fnl-update` must keep pace with what the release adds and help the user finish it: tell them what is new for them and walk them through the setup it needs.

The update goes to the latest stable release by default, and the user can choose or hold a specific version (owner, 2026-11-10).

## What ships

1. **Upgrade notes, one entry per release.** A machine-readable file in the `fnl-update` skill folder (`references/upgrades.json`) with, per version: what was renamed (old name, new name, until when the old one works), new setup features or questions (the `/fnl-setup add <feature>` to run, and whether it asks a new consent), migrations (the command that previews them, for example `matrix_setup.py migrate`), new hooks per host and what the user must do for them (for example trusting hooks again on Codex), and anything removed. Every item has a short plain sentence for the user and, where one exists, a read-only command that tells whether it is already done for this user (for example `matrix_setup.py show` printing that no matrix is set).
2. **Two ways in (owner, 2026-11-10).** `/fnl-update` runs the whole process: it updates to the target version after the user's yes, then goes straight on to the checklist below and offers to finish each open item. `/fnl-update whats-new` only shows what is new: it reads the notes and prints the checklist, and changes nothing, installs nothing and offers no setup step. A user who only wants to look uses the second; a user who wants to update uses the first and is never sent to a second command.
3. **The checklist.** It covers every version between the last version this user went through and the installed one. Only the notes' read-only "is it done" commands run; each item shows as done, open or not applicable to this user. In `/fnl-update`, for each open item in the order the notes give, it offers to run the matching setup step through `fnl-setup`, which keeps every consent question, preview and neutral yes exactly as today. Skipping an item is recorded so the next run does not ask again; nothing is ever set up without the user's own answer.
4. **Remember what was seen.** The last version the user went through is stored in the plugin's private state folder (a version string only). After an update the session-start line already shown for a newer version says once that the installed version has upgrade notes and names `/fnl-update whats-new`; it never runs anything itself.
5. **Host update commands verified.** The Codex procedure used for the 0.2.2 and 0.2.3 refreshes (`codex plugin marketplace upgrade <catalog>`, then remove and add the plugin, then trust its hooks again in `/hooks`) moves from unverified to verified with its date, and `fnl-update` offers it after a yes. Antigravity stays unverified until checked the same way.
6. **Latest by default, or a version the user picks.** `/fnl-update` targets the latest stable release. `/fnl-update <version>` targets that exact released version instead, newer or older (an older one is a rollback: the checklist then lists what the user loses, from the notes of the versions in between, and no migration runs backwards). `/fnl-update pin <version>` records that the user holds that version: the session-start notice stops offering newer releases until `/fnl-update unpin`, and `status` shows the pin. Only a version that exists as a published stable tag is accepted, validated against the cached release list; a `-dev` build is never a target. Each host's command for an exact version is verified on its installed CLI before it is offered (on Claude Code and Codex this likely goes through a marketplace pinned to the tag), and a host without a verified way says so and leaves the step to the user. The pin and the version are stored with the update check's existing state, as a version string only.
7. **The notes are part of releasing.** `fnl-versioning` requires an upgrade-notes entry before a release is proposed, and a test fails when a manifest carries a released version (no `-dev`) with no entry for it. Writing the entry is part of the documentation review the same skill already requires.

## What enforces what

- Scripts: the notes file's schema, the test tying a released version to an entry, the read-only "is it done" commands, the stored last-seen version.
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

None yet. A build needs a red test per behavior: the notes schema and its refusal of unknown keys, the release test (released version without an entry fails, `-dev` passes), version-range selection, a done item, an open item and an item that does not apply, skip recorded and not asked again, no write without `fnl-setup`'s yes, the session-start line shown once after an update, latest as the default target, an exact version accepted only when it is a published stable tag, a rollback listing what is lost, and a pin that silences newer-release notices until unpinned.
