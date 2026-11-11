# Host update commands

These are observations of each host's CLI and of real refreshes, not proof that a given update completed. A verified procedure still needs the user's yes to its concrete command, and the result is checked with the host's own plugin listing afterwards.

| Host | Status | Allowed update action after yes |
| --- | --- | --- |
| Claude Code | **Verified** (CLI help, 2026-11-04): `claude plugin --help` lists `list` and `update`; `claude plugin update --help` confirms `update <plugin>` and that a restart is required. | `claude plugin update <installed-plugin-identifier>`; use the identifier the host lists, not a guessed catalog or scope. Keep the host's own confirmation if it asks about an install command. Tell the user to restart Claude Code. |
| Codex | **Verified** (2026-11-09, used for the 0.2.2 and 0.2.3 refreshes). | 1. `codex plugin marketplace upgrade <catalog>` to refresh the catalog snapshot. 2. `codex plugin remove <plugin>` and then `codex plugin add <plugin>` with the identifiers the host lists. 3. In a new session, open `/hooks` and trust the plugin's hooks again, because every change of hook content makes Codex ask again. A catalog refresh alone does not update the installed plugin. |
| Antigravity | **Unverified**: `agy plugin --help` and `agy plugin help` list `list`, `install`, `uninstall`, `enable`, `disable`, `import`, `validate`, `link`; no update command. | Updating an existing install with `install` is unverified. Explain the gap and leave the update pending until a native procedure is verified the same way. |

Recheck the relevant host's help if it differs from these observations. Host-native installation may use its own network and provider policies; the automatic check is separate.

## An exact version

`/fnl-update <version>` needs each host's command for an exact version verified on its installed CLI before it is offered. None is verified yet: for a chosen version, report the accepted target and leave the host step to the user, naming the gap. The latest release goes through the table above.

## Privacy of the automatic check

The automatic check is on by default and is the plugin's only automatic network call (the optional judge call to Jev runs only when the coordinator or the user invokes it; see PRIVACY.md): one HTTPS GET to `https://api.github.com/repos/finolabs/finolabs-vibecode/releases/latest` when its cache is missing or at least 24 hours old. It uses the generic User-Agent `finolabs-vibecode-update-check` and sends nothing about the user: no name, machine, repository, session, installed version or metrics. GitHub necessarily sees the connection's source IP. There are no retries, redirects or proxies.

Only a timestamp and validated stable release tag are cached; skipped versions, a never-ask flag and a pinned version are stored separately in the same state folder, and `onboard.json` holds only `last_seen` and the skipped note ids. Files are mode `0600`. The commands `whats-new`, `onboard` and `target` make no network call; a chosen version is checked from the user's own `gh` output.

Set `FNL_UPDATE_CHECK=off` in the host's environment to stop checking and notices (including these helper commands); no files are changed while off. Metrics remain separately opt-in and local. The first release carrying the check notifies nobody: older installs do not carry the hook, and the carrying stable release equals itself. A `-dev` build does precede its own stable release. A missing cache produces no notice, and errors are silent with exit status 0.
