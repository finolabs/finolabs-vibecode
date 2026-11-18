# Feature: afk (user scope)

Needs: nothing; saves standing choices in the canonical host.md and, for one repository, its settings; starts no lease, installs no hook, sends nothing.

Every question follows [interview.md](../interview.md): native question tool; each permission gets its own question, including in Quick mode (advisory, agent judgment). Silence is not consent. Keep unanswered settings open; never infer Merge from the owner's examples or from starting a lease.

Scope first. Outside a repository say "These are your account's away rules (every repository)." and ask nothing. Inside one, ask: "Set away rules for your account (every repository) or only for this repository?" Choices: "Your account" / "Only this repository". Only this repository goes to "Project scope" when host.md already has a valid `## afk` section; otherwise say the account rules come first (apps, limits and the table live only there) and run them.

Ask: "How much may the agents do while you are away?"
Open (recommended): Save Mode: open. Say plainly: under a lease agents may do anything (push, merge without review, deploy to production, publish, delete, send messages and data, edit this plugin and the lease) except touch credentials, and you carry that risk.
Strict: Save Mode: strict; skip the guards (strict keeps both on) and ask every question from the apps on.
Undo: Repeat setup to change it.
Choices: "Open (recommended)" / "Strict".
Open only: ask the two guards, then only the apps and lease hours (1-24, default 8); pass defaults for the rest (`afk.py rules` shows each mode).

Ask: "Keep instructions in issues, other people's pull requests, web pages and tool output from choosing tasks or granting actions?" (Open only.) Guard saves Third-party instructions: guard, Open saves open. Choices: "Guard (default)" / "Open".
Ask: "Refuse commits on the default branch, pushes to it and every force, delete or mirror push?" (Open only.) Guard saves Default branch: guard, Open saves open. Undo: repeat setup. Choices: "Guard (default)" / "Open".

Ask: "Which AI apps may run while you are away?"
Choices: Claude Code / Codex / Antigravity; allow several. Suggest Claude Code; save the chosen names as Hosts.
Undo: Repeat setup to change the apps.

Ask: "May the agents choose new tasks from your task list?"
Yes: Save Task choice: choose; agents may choose eligible tasks while a lease is live.
No: Save Task choice: listed; work only on tasks you list at start.
Undo: Repeat setup to change it.
Choices: "Yes, allow task selection" / "No, use only my listed tasks".

Ask: "May the agents push their branches and open pull requests?"
Yes: Save Push and pull requests: yes; allow their branches and pull requests, never a push to the default branch.
No: Save Push and pull requests: no; keep that permission off.
Undo: Repeat setup to change it.
Choices: "Yes, allow branches and pull requests" / "No, keep that permission off".

Ask: "Whose pull requests may the agents check out and test?"
Choices: Your own account, including agents using that login, and afk's own branches (Trusted authors: own). This slice offers no other authors; declining leaves setup pending.
Undo: Stop afk to stop handling them.

Ask: "Use these limits for one away session: 8 hours, and in each repository 20 helper runs, 480 runtime minutes, 30 actions an hour, and stop when 15% of AI usage is left?"
Yes: Save Lease hours 8, Max runs 20, Max runtime minutes 480, Max actions per hour 30, Quota floor percent 15.
No: Ask each in one round as a whole number (ask again any left unanswered): hours 1-24 (a start can shorten it), runs 1-10000, runtime minutes 1-1440, actions an hour 1-10000, quota floor 0-100.
Undo: Stop the lease; repeat setup to change future limits.
Choices: "Yes, use these limits" / "No, set each limit".
With a valid `## afk` section already saved, offer its saved limits instead of the defaults (Yes keeps them) and start the table in afk-decisions.md from the saved answers (advisory, agent judgment).

Then follow [../afk-decisions.md](../afk-decisions.md): what must wait for you, optional deploy targets, the default test commands, top-level files, release and production commands for every repository, and the separate excerpt consent.

Ask Merge last among the settings: "May the agents merge pull requests while a lease is live?" (Strict only; Open passes no `--merge`.)
Yes: Save Merge: yes. Agents may merge eligible pull requests during a lease once both independent reviews, all checks, local tests of touched modules and MERGE OK from merge_check.py pass at the head. Only your own account and afk's own branches qualify; protected changes remain forbidden. This is your own decision and grants merge authority.
No: Save Merge: no; agents cannot merge pull requests.
Undo: Stop the current lease and repeat setup with Merge: no to withdraw this authority.
Choices: "Yes, allow merges during a live lease" / "No, keep merges off".
After a yes, say once that a merge also needs both reviews posted: in a repository whose reviewers cannot post, the coordinator relays them only under a standing relay committed in that repository's context file, which `/setup instructions` offers ("Review relay"). There is no default for Merge. Starting a lease applies this answer; it does not grant any further authority (advisory, agent judgment; the script denies merge when the setting is no).

Translate the answers into `python3 -I <this skill folder>/scripts/afk_setup.py preview --mode <open|strict> --third-party-instructions <guard|open> --default-branch <guard|open>`
followed by `--hosts <names> --task-choice <choose|listed> --push-and-pull-requests <yes|no> --trusted-authors own --lease-hours <n> --max-runs <n> --max-runtime-minutes <n> --max-actions-per-hour <n> --quota-floor-percent <n> [--merge <yes|no>] [--decide <key>]... [--non-production-target '<command>']... [--test-command '<command>']... [--top-level-file <name>]... [--release-target '<command>']... [--production-target '<command>']... --excerpts-leave-the-machine <yes|no>`.
Quote "Claude Code" as one name. Pass every answer explicitly. Show the target, whole section, backup and SHA-256 digest, then ask the separate write approval:
"Save the shown away-session settings?"
Yes: Apply only the previewed afk section in local host.md, keeping a backup of an existing file. No lease starts and no permission beyond the answered settings is granted.
No: Leave host.md unchanged; discard or replace the preview later.
Undo: Stop any live lease; preview and approve changed settings, or restore the shown backup after checking later edits.
Choices: "Yes, save these settings" / "No, leave settings unchanged".

These writes widen what agents may do while the user is away, so the user starts them by typing `/setup add afk`. On Claude Code in auto mode the host may deny an agent's own `apply` or `--expect` save as oversight-sensitive; report the denial and leave the step to the user, never work around it (advisory, agent judgment; the host enforces the denial).

Apply with `python3 -I <this skill folder>/scripts/afk_setup.py apply --yes --digest <prefix>`; use at least the first 12 hex digits of the shown Digest (the full digest also works). Preview state is private in `<data root>/state/autopilot-setup/preview.json`, lasts 60 minutes and is used once.
Apply enforces the digest, unchanged host bytes and mode, canonical root, safe files and section bounds, refusing links and ambiguity. Only the `## afk` section changes; other host content stays byte for byte (script-enforced). An older `## Autopilot` section is not read and not changed; tell the user to delete it by hand.

To change choices, repeat `/setup add afk`; a live lease then stops accepting actions. Starting and stopping remain `/afk` and `/afk stop`.
## Project scope
Claude Code: then [native rules](../afk-native-rules.md). In a repository (after the account rules, or on Only this repository): [../afk-project.md](../afk-project.md).
