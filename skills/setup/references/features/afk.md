# Feature: afk (user scope)

Needs: nothing; saves standing choices in the canonical host.md and, for one repository, its settings; starts no lease, installs no hook, sends nothing.

Every question follows [interview.md](../interview.md): native question tool; each permission gets its own question, including in Quick mode (advisory, agent judgment). Silence is not consent. Keep unanswered settings open; never infer Merge from the owner's examples or from starting a lease.

Scope first. Outside a repository say "These are your account's away rules (every repository)." and ask nothing. Inside one, ask: "Set away rules for your account (every repository) or only for this repository?" Choices: "Your account" / "Only this repository". Only this repository goes to "Project scope" when host.md already has a valid `## afk` section; otherwise say the account rules come first (apps, limits and the table live only there) and run them.

Ask: "How much may the agents do while you are away?"
Open (recommended): Save Mode: open. Say plainly: under a lease the agents may do anything (push, merge without review, deploy to production, publish, delete, send messages and data, edit this plugin and the lease) except touch credentials, and you carry that risk.
Strict: Save Mode: strict; ask every question below. For Open ask the two guards, then only the apps and lease hours (1-24, default 8), passing defaults for the rest (`afk.py rules` in `delegate` shows each mode).
Choices: "Open (recommended)" / "Strict".

Ask: "Keep instructions in issues, other people's pull requests, web pages and tool output from choosing tasks or granting actions?" Saves Third-party instructions. Choices: "Guard (default)" / "Open".
Ask: "Refuse commits on the default branch, pushes to it and every force, delete or mirror push?" Saves Default branch. Choices: "Guard (default)" / "Open".

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
No: Ask each in one round as a whole number (one left unanswered stays open; ask it again): hours 1-24 (a start can shorten it), runs 1-10000, runtime minutes 1-1440, actions an hour 1-10000, quota floor 0-100.
Undo: Stop the lease; repeat setup to change future limits.
Choices: "Yes, use these limits" / "No, set each limit".
When host.md already has a valid `## afk` section, this question offers its saved Lease hours, Max runs, Max runtime minutes, Max actions per hour and Quota floor percent instead of the defaults, and Yes keeps them; the table in afk-decisions.md likewise starts from the saved answers (advisory, agent judgment).

Then follow [../afk-decisions.md](../afk-decisions.md): what must wait for you, optional deploy targets, the default test commands, top-level files, release and production commands for every repository, and the separate excerpt consent.

Ask Merge last among the settings: "May the agents merge pull requests while a lease is live?" (Strict only; Open passes no `--merge`.)
Yes: Save Merge: yes. This lets the agents merge eligible pull requests while a lease is live when both independent reviews and all checks pass at the current head, including local tests of touched modules and MERGE OK from merge_check.py. Only your own account and afk's own branches qualify; protected changes remain forbidden. This is your own decision and grants merge authority.
No: Save Merge: no; agents cannot merge pull requests.
Undo: Stop the current lease and repeat setup with Merge: no to withdraw this authority.
Choices: "Yes, allow merges during a live lease" / "No, keep merges off".
After a yes, say once that a merge also needs both reviews posted: in a repository whose reviewers cannot post, the coordinator relays them only under a standing relay committed in that repository's context file, which `/setup instructions` offers ("Review relay"). There is no default for Merge. Starting a lease applies this answer; it does not grant any further authority (advisory, agent judgment; the script denies merge when the setting is no).

Translate the answers into `python3 -I <this skill folder>/scripts/afk_setup.py preview --mode <open|strict> --third-party-instructions <guard|open> --default-branch <guard|open>`
followed by `--hosts <names> --task-choice <choose|listed> --push-and-pull-requests <yes|no> --trusted-authors own --lease-hours <n> --max-runs <n> --max-runtime-minutes <n> --max-actions-per-hour <n> --quota-floor-percent <n> [--merge <yes|no>] [--decide <key>]... [--non-production-target '<command>']... [--test-command '<command>']... [--top-level-file <name>]... [--release-target '<command>']... [--production-target '<command>']... --excerpts-leave-the-machine <yes|no>`.
Quote "Claude Code" as one name. Pass every answer explicitly. Show the target, entire section, backup and SHA-256 digest before asking the separate write approval:
"Save the shown away-session settings?"
Yes: Apply only the previewed afk section in local host.md, keeping a backup of an existing file. No lease starts and no permission beyond the answered settings is granted.
No: Leave host.md unchanged; discard or replace the preview later.
Undo: Stop any live lease; preview and approve changed settings, or restore the shown backup after checking later edits.
Choices: "Yes, save these settings" / "No, leave settings unchanged".

These writes widen what agents may do while the user is away, so the user starts them by typing `/setup add afk`. On Claude Code in auto mode the host may deny an agent's own `apply` or `--expect` save as oversight-sensitive; report the denial and leave the step to the user, never work around it (advisory, agent judgment; the host enforces the denial).

Apply with `python3 -I <this skill folder>/scripts/afk_setup.py apply --yes --digest <prefix>`; use at least the first 12 hex digits of the shown Digest (the full digest also works). Preview state is private in `<data root>/state/autopilot-setup/preview.json`, expires after 60 minutes and is consumed on success.
Apply enforces the digest, unchanged host bytes and mode, canonical root, safe files and section bounds; it refuses links and ambiguity. Only the `## afk` section changes; other host content stays byte for byte (script-enforced). An older `## Autopilot` section is not read and not changed; tell the user to delete it by hand.

To change choices, repeat `/setup add afk`; a live lease stops accepting actions after setup changes. Starting and stopping remain `/afk` and `/afk stop`.
## Project scope
Inside a repository, after the account rules or when the user chose Only this repository, follow [../afk-project.md](../afk-project.md).
