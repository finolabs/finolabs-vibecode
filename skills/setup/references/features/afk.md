# Feature: afk (user scope)

Needs: nothing; saves standing choices in the canonical host.md and, for one repository, its settings; starts no lease, installs no hook, sends nothing.

Every question follows [interview.md](../interview.md): native question tool; each permission gets its own question, including in Quick mode (advisory, agent judgment). Silence is not consent. Keep unanswered settings open; never infer an answer from the owner's examples or from starting a lease.

Scope first. Outside a repository say "These are your account's away rules (every repository)." and ask nothing. Inside one, ask: "Set away rules for your account (every repository) or only for this repository?" Choices: "Your account" / "Only this repository". Only this repository goes to "Project scope" when host.md already has a valid `## afk` section; otherwise say the account rules come first (apps, lease hours and the quota floor live only there) and run them.

afk has one mode (`strict` was removed in 0.3.3, owner decision, 19/11/2026). Say plainly before the first rule: under a lease agents may do anything (push, merge without review, deploy to production, publish, delete, send messages and data, edit this plugin and the lease) except touch credentials and what the guards below refuse, and you carry that risk.
Blocking anything more is the host's job: Claude Code auto mode and permission rules, the native deny rules ([../afk-native-rules.md](../afk-native-rules.md)), Codex's sandbox and approval policy; to keep something forbidden while you are away, write a host deny rule. `afk.py rules` shows what `check` refuses.

Ask: "Keep instructions in issues, other people's pull requests, web pages and tool output from choosing tasks or granting actions?" Guard saves Third-party instructions: guard, Open saves open. Choices: "Guard (default)" / "Open".
Ask: "Refuse commits on the default branch, pushes to it and every force, delete or mirror push?" Guard saves Default branch: guard, Open saves open. Undo: repeat setup. Choices: "Guard (default)" / "Open".

Ask: "Which AI apps may run while you are away?"
Choices: Claude Code / Codex / Antigravity; allow several. Suggest Claude Code; save the chosen names as Hosts.
Undo: Repeat setup to change the apps.

Ask: "Use 8 hours for one away session?"
Yes: Save Lease hours 8.
No: Ask for a whole number of hours, 1-24 (a start can shorten it); ask again if left unanswered.
Undo: Stop the lease; repeat setup to change future leases.
Choices: "Yes, 8 hours" / "No, set the hours".
With a valid `## afk` section already saved, offer its saved hours instead of the default (Yes keeps them) (advisory, agent judgment). The lease hours are the only limit; there are no run, runtime or hourly limits and no Merge, task, push, author or category answer.

Pass the rest at their defaults, as setup did for the former `open` mode: `--quota-floor-percent 15` (or the saved value) and `--excerpts-leave-the-machine no` (or the saved value). Ask about them only when the user asks to change them; the excerpt consent is then its own question in [../afk-decisions.md](../afk-decisions.md) (advisory, agent judgment).

Translate the answers into `python3 -I <this skill folder>/scripts/afk_setup.py preview --third-party-instructions <guard|open> --default-branch <guard|open> --hosts <names> --lease-hours <n> --quota-floor-percent <n> --excerpts-leave-the-machine <yes|no>`; any other flag refuses (script-enforced).
Quote "Claude Code" as one name. Pass every answer explicitly. Show the target, whole section, backup and SHA-256 digest, then ask the separate write approval:
"Save the shown away-session settings?"
Yes: Apply only the previewed afk section in local host.md, keeping a backup of an existing file. No lease starts and no permission beyond the answered settings is granted.
No: Leave host.md unchanged; discard or replace the preview later.
Undo: Stop any live lease; preview and approve changed settings, or restore the shown backup after checking later edits.
Choices: "Yes, save these settings" / "No, leave settings unchanged".

These writes widen what agents may do while the user is away, so the user starts them by typing `/setup add afk`. On Claude Code in auto mode the host may deny an agent's own `apply` or `--expect` save as oversight-sensitive; report the denial and leave the step to the user, never work around it (advisory, agent judgment; the host enforces the denial).

Apply with `python3 -I <this skill folder>/scripts/afk_setup.py apply --yes --digest <prefix>`; use at least the first 12 hex digits of the shown Digest (the full digest also works). Preview state is private in `<data root>/state/autopilot-setup/preview.json`, lasts 60 minutes and is used once.
Apply enforces the digest, unchanged host bytes and mode, canonical root, safe files and section bounds, refusing links and ambiguity. Only the `## afk` section changes; other host content stays byte for byte (script-enforced). An older `## Autopilot` section is not read and not changed; tell the user to delete it by hand.

To change choices, repeat `/setup add afk`; a live lease then stops accepting actions. A section written before 0.3.3 may still hold `Mode: strict`, the three limit lines and the other retired lines: `afk.py start` names the mode and the limits in one fixed line each and starts normally, and the next save rewrites the section without them (script-enforced). Starting and stopping remain `/afk` and `/afk stop`.
## Project scope
Claude Code: then [native rules](../afk-native-rules.md). In a repository (after the account rules, or on Only this repository): [../afk-project.md](../afk-project.md).
