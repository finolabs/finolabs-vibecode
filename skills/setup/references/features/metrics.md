# Feature: metrics (user scope)

Needs: the plugin's hooks installed (the whole plugin on Claude Code, Codex or Antigravity; a single skill installed alone has none), otherwise skip. Optional. Each later step needs the consent before it: progress, snapshot and the Antigravity hook need metrics consent (declining it ends them without recording any). Every question uses neutral Yes and No with none preselected or recommended; a default, a timeout or an auto-selected option never counts as the yes.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Usage metrics consent

Say, in this order: what is recorded (a time, a session id, a short repository code, a skill or agent name, the router's depth, a review verdict, the number of tasks a coordinator kept with a fixed reason and who settled it, judge receipt site, grader, result and followed status; never prompts, code, command text or file paths); where it lives (the state folder on this computer, readable only by the user); that the dashboard also shows project progress from the repository's task list and the ledger using identifiers and counts only (on by default after consent;
`FNL_PROGRESS=off` disables it); that nothing leaves the computer and the dashboard is a local page; and that it stays off until they say yes and `FNL_METRICS=off` turns it off at any time.

Ask as one question of its own, never bundled: "Let this plugin keep a private record of how its skills and helpers are used on this computer?"
Yes: Save local consent and the chosen 30, 90 or 365 day retention; create the local dashboard and private state records described above. Nothing leaves this computer.
No: Leave recording off; ask later.
Undo: Use FNL_METRICS=off to stop recording; status purge deletes saved records.
Choices: "Yes, record it for 30 days", "Yes, record it for 90 days", "Yes, record it for 365 days" / "No, leave recording off". Claude Code records skill and agent use, first edits, commits, review comments, the router's depth, keep and judge receipts. Codex records the same except skill and agent use, and the user must also trust the plugin's hooks once, with `/hooks`, or they stay off.
Antigravity records the same events as Codex, but its hook is not part of the plugin, because a plugin hook's working folder is unverified. After a yes run `python3 -I <status folder>/scripts/refresh.py consent --retention <days>` to record it with its date, then `refresh.py run` once so the dashboard exists; `status` must be installed beside this skill, otherwise say so and skip. A declined or skipped step leaves everything off.

## Antigravity hook

Show what it adds, then ask: "Let Antigravity record plugin usage for your private dashboard?"
Yes: Add the shown hook, a command Antigravity runs on its events, to your account’s .gemini/config/hooks.json with a backup. Records stay local; nothing is sent.
No: Leave the shared Gemini file unchanged; ask later.
Undo: Run refresh.py antigravity-hook --remove.
Choices: "Yes, add usage recording" / "No, leave the file unchanged".
Only after the yes run `python3 -I <status folder>/scripts/refresh.py antigravity-hook --yes`. It merges one group, `finolabs-vibecode`, into `~/.gemini/config/hooks.json` with an absolute path to the script, leaves every other group alone and keeps a backup; `--remove` takes it out. It refuses unless the skill sits inside the `finolabs-vibecode` plugin. That file is shared Gemini configuration, so never run it unasked.

## Project progress

After metrics consent ask: "Show progress from task lists and work records on your private dashboard?"
Yes: Write on in Project progress in local host.md; read identifiers and counts from local task files and work-run records. Nothing leaves this computer.
No: Record off as requested; leave task files and work-run records unchanged. Ask later.
Undo: Use project_progress.py off --yes or FNL_PROGRESS=off.
Choices: "Yes, show progress counts" / "No, keep progress hidden".
The default is on; record it with `python3 -I <this skill folder>/scripts/project_progress.py on --yes`, or the requested choice with `... off --yes`; `on --dry-run` shows the section first. The script changes only `## Project progress` in canonical `<data root>/host.md`; if the root cannot be resolved it is off. An existing readable host config defaults to on, a missing, unsafe or ambiguous one to off; neither a repository file nor an environment setting grants metrics consent.
`Project progress: off` or `FNL_PROGRESS=off` disables the panel. The reader accepts local regular files only, refuses symlinks and traversal, and shares a one-second budget across reads, parsing and joins.

## Process snapshot

Ask:
"Show how many Claude, Codex and Antigravity programs are running under your account?"
Yes: Save the local host.md opt-in; dashboard refreshes count processes on this computer and replace the local data.js snapshot. Nothing is sent.
No: Leave process counting off; ask later.
Undo: Use agent_processes.py off --yes; purge deletes the saved snapshot.
Choices: "Yes, show running counts" / "No, leave counting off".
Explain that a dashboard refresh runs the system `ps` with fixed arguments, no shell, a two-second limit and a 256 KiB cap; keeps only fixed family names, counts, elapsed seconds and the snapshot time in local `data.js`, overwritten on refresh and deleted by purge, never in usage events; keeps no arguments, paths, environment values or user-chosen names; sends nothing; and cannot identify sub-agents, attribute repositories or list app sessions.
A No or skipped step leaves it off. After a yes run `python3 -I <this skill folder>/scripts/agent_processes.py on --dry-run`, show its host-config section, then record it with `agent_processes.py on --yes`; withdraw with `agent_processes.py off --yes`. Enforcer: the script writes only its section in canonical `<data root>/host.md`, preserving others; unresolved means off. Recorded metrics consent is also required and environment settings cannot opt in.
`FNL_AGENT_SNAPSHOT=off` disables collection; the refresh script alone collects it, at most once per ten seconds.
