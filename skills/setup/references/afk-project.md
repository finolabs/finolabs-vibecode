# afk: one repository's own away rules

Loaded by [features/afk.md](features/afk.md) inside a repository. Questions follow [interview.md](interview.md) (advisory, agent judgment).

Offered only inside a repository; host.md stays unchanged. First read the repository's stored object: run `settings --clear autopilot --dry-run` (below), report a refusal, and name the values in its `current` field.

After the account rules ask: "Should this repository use different away rules than your account?" No: with no object, save nothing; with one, preview its removal and ask the save question.

On Yes, or straight away when the user chose Only this repository, ask: "Which rules should differ in this repository?" as one multi-select of four: task choice, push, code folders, merge. Limits get their own question after these. Ask only the ticked ones; an unticked key keeps its value in `current`, else its default answer "Use my user setting".
Trusted authors stays own (`trusted-authors`; no other choice yet). A project value wins over the user value for these keys only, wider or narrower; Hosts, Lease hours, the quota floor and the categories stay user scope only.
Ask: "In this repository, may the agents choose new tasks from your task list?" Use my user setting / Yes / No (`task-choice`: choose or listed).
Ask: "In this repository, may the agents push their branches and open pull requests?" Use my user setting / Yes / No (`push-and-pull-requests`).
Ask: "Which other top-level folders hold this repository's code?" Use my user setting (none) or names such as packages (`roots`, at most 16, no leading dot; src's path rules apply).
Ask: "How many helper runs, runtime minutes and actions an hour may the agents use in this repository during one away session?" Asked every time; its default answer is Use my user setting, else whole numbers: runs 1-10000, runtime minutes 1-1440, actions an hour 1-10000 (`max-runs`, `max-runtime-minutes`, `max-actions-per-hour`); limits count per repository.
Ask: "In this repository, may the agents merge pull requests and local branches while a lease is live?" Use my user setting / Yes / No (`merge`); ask it last; yes is your own decision.
Answers, with the current values of unticked keys, become one object; "Use my user setting" leaves a key out. Preview: `python3 -I <this skill folder>/scripts/project_progress.py settings --set 'autopilot=<JSON>' --dry-run` (replaces the whole object), or `settings --clear autopilot --dry-run` when every answer inherits (keeps other settings). Report a refusal; on action `none`, stop. Else show the repository, `target`, action, object, effective values and the `changed` keys (each with its old value), then ask:
"Save these away settings for this repository?"
Yes: Rerun it with `--expect <token>` instead of `--dry-run`; a changed repository, settings or origin refuses (script), so preview again. PR commands then need `--repo github.com/OWNER/NAME` (create also `--head <branch>`); a changed origin turns these permissions off.
No: Keep the current settings.
Undo: Repeat this, answer No to the differ question and save the removal.
Choices: "Yes, save them for this repository" / "No, keep the current settings".
