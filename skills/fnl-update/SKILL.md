---
name: fnl-update
description: Update finolabs-vibecode with the user's permission, show installed and cached available versions, skip a release, or stop update notices. Use when the user requests a plugin update, asks whether a newer release is available, chooses skip this version, or says never ask again.
argument-hint: "[status | skip <version> | never]"
disable-model-invocation: true
---

# Update the plugin

Run only at the user's request. A session-start notice tells the agent to let the user know a newer version is available and that they can type `/fnl-update` (on Codex `$fnl-update`). Only the user can invoke this skill; the notice is not permission to update. An earlier yes to checking or opening this skill is not a yes to installing an update.

The helper and its shared core are in this skill's own `scripts/` folder. Resolve `<update_check.py>` there. It uses `fnl_metrics.state_dir()` for all state, independently of metrics consent. It reads the plugin's own manifest when installed with the plugin; a standalone skill has no manifest, so its installed version is unknown. Use the host's installed-plugin listing to establish that version rather than guessing it.

**Arguments:** $ARGUMENTS

## Show the facts, then ask

Ask in text when the session has no such tool, the tool is refused or fails, nobody can answer (a delegated or headless run records the open decision and never assumes or invents an answer), or the decision is free text. The enforcer is agent judgment, so this is advisory.

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged. Script output stays English; report it to the user in their language (advisory, agent judgment).

1. Run `python3 -I <update_check.py> status`. This reads local state only. Show `installed`, `available` (the cached latest stable release), whether it is `newer`, whether the cache is `stale`, and any skipped versions or never-ask choice. A null value is unknown, not evidence that the plugin is current. Empty output means the check is off or a read failed: report that limitation. Do not fetch a release manually or claim a stale cache is current. The automatic startup hook schedules a background refresh after 24 hours; the result is read on a later startup. A standalone skill has no automatic hook.
2. If the user only asked for status, finish with those facts. If the user requests an update, identify the host and installed plugin identifier from its plugin listing. Report the proposed native command, the verified or unverified status below, and any required restart or trust step. Ask for a clear **yes to running that command now**, through the host's native question tool when the session has one. Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes. Wait for the answer. A skip, silence or ambiguous answer grants no permission to update.
3. After that yes, run only a verified native update command for the matching host and installed identifier. Report the actual result. An error is an error, not a successful update. On Claude Code, tell the user to restart Claude Code before using the new plugin. On Codex, the plugin's hooks need trust again after an update: open `/hooks` in a new session and review them. Verify the resulting installed version with the host's listing; a still-running session's manifest can describe the old loaded copy.

## Host commands: checked 2026-11-04

These are CLI help observations, not proof that an update completed. No update was executed during implementation.

| Host | Native support observed | Allowed update action after yes |
| --- | --- | --- |
| Claude Code | `claude plugin --help` lists `list` and `update`; `claude plugin update --help` confirms `update <plugin>` and restart required | `claude plugin update <installed-plugin-identifier>`; use the identifier the host lists, not a guessed catalog or scope. Keep the host's own confirmation if it asks about an install command. |
| Codex | `codex plugin --help` lists `add`, `list`, `marketplace`, `remove`; `codex plugin marketplace --help` describes `upgrade` as refreshing marketplace snapshots | Plugin update procedure **unverified**. A marketplace refresh alone does not prove an installed plugin was updated. Explain the gap and leave the update pending until the host's current native procedure is verified. Do not invent `codex plugin update` or remove/reinstall as a substitute. |
| Antigravity | `agy plugin --help` and `agy plugin help` list `list`, `install`, `uninstall`, `enable`, `disable`, `import`, `validate`, `link`; no update command | Updating an existing install with `install` is **unverified**. Explain the gap and leave the update pending until a native update procedure is verified. |

Recheck the relevant host's help if it differs from these observations. A newly verified procedure still needs the user's yes to its concrete command. Host-native installation may use its own network and provider policies; the automatic check below is separate.

## Skip a version or stop asking

When the user explicitly chooses **skip this version**, use the validated available version from status and run `python3 -I <update_check.py> skip <version>`. When the user explicitly chooses **never ask**, run `python3 -I <update_check.py> never`. Both commands are local and silent; read `status` again to verify the choice before reporting success. Never put response text into a shell command: versions must match `v?X.Y.Z` with decimal digits and dots only. Skip affects that release only; never-ask suppresses all notices, but the background check remains on.

## Privacy and off switch

The automatic check is on by default and is the plugin's only network call: one HTTPS GET to `https://api.github.com/repos/finolabs/finolabs-vibecode/releases/latest` when its cache is missing or at least 24 hours old. It uses the generic User-Agent `finolabs-vibecode-update-check` and sends nothing about the user: no name, machine, repository, session, installed version or metrics. GitHub necessarily sees the connection's source IP. There are no retries, redirects or proxies. Only a timestamp and validated stable release tag are cached; skipped versions and a never-ask flag are stored separately in the same state folder. Files are mode `0600`.

Set `FNL_UPDATE_CHECK=off` in the host's environment to stop checking and notices (including these helper commands); no files are changed while off. Metrics remain separately opt-in and local. The first release carrying the check notifies nobody: older installs do not carry the hook, and the carrying stable release equals itself. A `-dev` build does precede its own stable release. A missing cache produces no notice, and errors are silent with exit status 0.
