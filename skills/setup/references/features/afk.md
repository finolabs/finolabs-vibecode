# Feature: afk (user scope)

Needs: nothing; this saves standing choices in the canonical host.md only. It starts no lease, installs no hook and sends nothing.

Every question follows [interview.md](../interview.md): native question tool; each setting gets its own question, including in Quick mode (advisory, agent judgment). Yes/No choices are neutral, with none preselected or recommended. Silence is not consent. Keep unanswered settings open; never infer Merge from the owner's examples or from starting a lease.

Ask: "Which AI apps may run while you are away?"
Choices: Claude Code / Codex / Antigravity; allow several. Suggest Claude Code; save the chosen names as Hosts.
Undo: Run this interview again to change the allowed apps.

Ask: "May the agents choose new tasks from your task list?"
Yes: Save Task choice: choose; agents may choose eligible tasks while a lease is live.
No: Save Task choice: listed; work only on tasks you list at start.
Undo: Run this interview again to change task selection.
Choices: "Yes, allow task selection" / "No, use only my listed tasks".

Ask: "May the agents push their branches and open pull requests?"
Yes: Save Push and pull requests: yes; allow their branches and pull requests, never a push to the default branch.
No: Save Push and pull requests: no; keep that permission off.
Undo: Run this interview again to change this permission.
Choices: "Yes, allow branches and pull requests" / "No, keep that permission off".

Ask: "Whose pull requests may the agents check out and test?"
Choices: Your own account, including agents using that login, and autopilot's own branches (Trusted authors: own). This slice offers no other authors; declining leaves setup pending.
Undo: Stop autopilot if you no longer want those pull requests handled.

Ask: "How many hours may one away session last?"
Choices: A whole number from 1 to 24; suggest 8 (Lease hours). A start can shorten this limit.
Undo: Stop the current lease; repeat setup to change future leases.

Ask: "How many helper runs may one away session start?"
Choices: A whole number from 1 to 10000; suggest 20 (Max runs).
Undo: Stop the lease; repeat setup to change future limits.

Ask: "How many runtime minutes may one away session use?"
Choices: A whole number from 1 to 1440; suggest 480 (Max runtime minutes).
Undo: Stop the lease; repeat setup to change future limits.

Ask: "How many actions may the agents take in one hour?"
Choices: A whole number from 1 to 10000; suggest 30 (Max actions per hour).
Undo: Stop the lease; repeat setup to change future limits.

Ask: "At what remaining AI usage percentage should work stop?"
Choices: A whole number from 0 to 100; suggest 15 (Quota floor percent). Missing or stale readings also stop routing; the coordinator checks readings in this slice (advisory, agent judgment).
Undo: Stop the lease; repeat setup to change the floor.

Then follow [../autopilot-decisions.md](../autopilot-decisions.md): what must wait for you, optional deploy targets and the separate excerpt consent.

Ask Merge last among the settings: "May the agents merge pull requests while a lease is live?"
Yes: Save Merge: yes. This lets the agents merge eligible pull requests while a lease is live when both independent reviews and all checks pass at the current head, including local tests of touched modules and MERGE OK from merge_check.py. Only your own account and autopilot's own branches qualify; protected changes remain forbidden. This is your own decision and grants merge authority.
No: Save Merge: no; agents cannot merge pull requests.
Undo: Stop the current lease and repeat setup with Merge: no to withdraw this authority.
Choices: "Yes, allow merges during a live lease" / "No, keep merges off".
There is no default for Merge. Starting a lease applies this answer; it does not grant any further authority (advisory, agent judgment; the script denies merge when the setting is no).

Translate the answers into `python3 -I <this skill folder>/scripts/autopilot_setup.py preview --hosts <names> --task-choice <choose|listed> --push-and-pull-requests <yes|no> --trusted-authors own --lease-hours <n> --max-runs <n> --max-runtime-minutes <n> --max-actions-per-hour <n> --quota-floor-percent <n> --merge <yes|no> [--decide <key>]... [--non-production-target '<command>']... --excerpts-leave-the-machine <yes|no>`.
Quote "Claude Code" as one name. Pass every answer explicitly. Show the target, entire section, backup and SHA-256 digest before asking the separate write approval:
"Save the shown away-session settings?"
Yes: Apply only the previewed Autopilot section in local host.md, keeping a backup of an existing file. No lease starts and no permission beyond the answered settings is granted.
No: Leave host.md unchanged; discard or replace the preview later.
Undo: Stop any live lease; preview and approve changed settings, or restore the shown backup after checking later edits.
Choices: "Yes, save these settings" / "No, leave settings unchanged".

Apply with `python3 -I <this skill folder>/scripts/autopilot_setup.py apply --yes --digest <prefix>`; use at least the first 12 hex digits of the shown Digest (the full digest also works). Preview state is private in `<data root>/state/autopilot-setup/preview.json`, expires after 60 minutes and is consumed on success.
Apply enforces the digest, unchanged host bytes and mode, canonical root, safe files and section bounds; it refuses links and ambiguity. Only the Autopilot section changes; other host content stays byte for byte (script-enforced). Backups and preview state are local writer records, not lease changes.

To change choices, repeat `/setup add afk`; a live lease stops accepting actions after setup changes. Starting and stopping remain `/autopilot` and `/autopilot stop`. Push notifications, the live dashboard, scheduler and host backstop are deferred; offer no settings for them in this slice.
## Project scope
Offer this only inside a repository, after the user-scope questions; host.md stays unchanged. A project value wins over the user value here, for five keys only; Hosts, Lease hours, the limits, the quota floor and the categories stay user scope only (one lease covers the machine). Each default answer is "Use my user setting", which leaves the key out.
Ask: "In this repository, may the agents choose new tasks from your task list?" Use my user setting / Yes / No (`task-choice`: choose or listed).
Ask: "In this repository, may the agents push their branches and open pull requests?" Use my user setting / Yes / No (`push-and-pull-requests`).
Ask: "In this repository, whose pull requests may the agents check out and test?" Use my user setting / Your own account and autopilot's branches (`trusted-authors`: own).
Ask: "Which other top-level folders hold this repository's code?" Use my user setting (none) or names such as packages (`roots`, at most 16, no leading dot); same path rules as src, protected paths stay protected.
Ask: "In this repository, may the agents merge pull requests and local branches while a lease is live?" Use my user setting / Yes / No (`merge`); ask it last; yes is your own decision.
If every answer is Use my user setting, write nothing. Else preview: `python3 -I <this skill folder>/scripts/project_progress.py settings --set 'autopilot=<JSON of the answered keys>' --dry-run`; show the object, then ask:
"Save these away settings for this repository?"
Yes: Run the same command without --dry-run; it writes the `autopilot` object to the repository's settings file and approves its digest.
No: Leave the repository's settings unchanged.
Undo: Run `project_progress.py settings --clear autopilot` here to return to your user settings.
Choices: "Yes, save them for this repository" / "No, keep my user settings here".
