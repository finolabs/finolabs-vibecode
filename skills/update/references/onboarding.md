# What a new version asks of the user

`references/upgrades.json` holds one entry per released version. Each item has an id `<version>/<slug>`, a kind (`rename`, `setup`, `migration`, `hook`, `removed`, `info`), one plain sentence, and optionally the `/setup add <feature>` step that finishes it, a read-only `check` (a plugin script run without a shell, with a 10-second timeout and the allowlisted environment, in the script's own folder; `"where": "repository"` runs it in the user's current folder instead, for a state that belongs to that repository) and `until` (the version up to which an old name keeps working). `update_check.py` refuses the whole file on any unknown key or bad value. The checks use `setup`'s `scripts/upgrade_state.py`, which reads `host.md` (and, for `repo-checks`, the current repository's approved check list) and writes nothing.

## Commands

All run as `python3 -I <update_check.py> <command>` and print nothing when the update check is off or a read fails; report that as a limitation, never as "nothing new".

| Command | Writes | What it prints |
| --- | --- | --- |
| `whats-new` | nothing | Every version after `last_seen` up to the installed one, each item `[done]`, `[open]`, `[not applicable]`, `[unknown]` or `[skipped]`, with `(setup: ...)` on open and unknown items that have a setup step; or `No new upgrade notes.` |
| `onboard seen <version>` | `onboard.json` `last_seen` | nothing; verify with `whats-new` |
| `onboard first` | `onboard.json` `last_seen` = the installed release, only when neither `host.md` nor `onboard.json` exists (a fresh data root) | nothing |
| `onboard skip <id>` | adds the id to `onboard.json` `skipped` (at most 200; only ids the notes name) | nothing; the item then shows as skipped and is not offered again |
| `target` | nothing | `target <version> latest <direction>` from the cached latest stable tag, or `refused: no cached latest release` |
| `target <version> --evidence <file>` | nothing | `target <version> chosen <direction>`, or `refused: <reason>` |
| `pin <version>` / `unpin` | `update-state.json` `pinned` | nothing; `status` shows `pinned` while set |

The direction is `upgrade`, `installed` (already on it) or `rollback`. A rollback also prints one `lost: <id>: <text>` line for every item of the versions between the target and the installed one; no migration runs backwards, so tell the user what they lose before the yes.

## Item states

A check's exit status decides the state: 0 done, 1 open, 3 not applicable, anything else (or a missing script, a timeout, a standalone skill without the plugin) unknown. An item with no check is unknown, except an `info` item, which shows as `[info]` and is only told. An unknown item is offered like an open one, never assumed done. The checklist covers what the plugin itself set up; a host feature the user changed outside the plugin may show stale.

## A chosen version

Run the user's own `gh release view <version> --repo finolabs/finolabs-vibecode --json tagName,isDraft,isPrerelease,url` (always the plugin's repository, whichever project the user is in; another host uses its equivalent bound to the same repository), save its output to a temporary file and pass it with `--evidence`.

The target is accepted only when the file (at most 64 KB) holds exactly those four fields, names exactly that tag, is neither a draft nor a prerelease, and its `url` is `https://github.com/finolabs/finolabs-vibecode/releases/tag/<tag>`. A `-dev` version, missing evidence or any mismatch is refused; never assume a target.

## The session-start line

While the installed version is newer than `last_seen` and has notes the user has not skipped, the startup hook adds one line naming `/update`, independent of the newer-release notice and of never-ask. The hook only reads `onboard.json`, never writes it, and prints no line on any error. A pin silences only the newer-release notice.

## Who writes what

Only `/update` calls `onboard seen` and `onboard skip`: `seen` after the user went through the checklist, `skip` when the user chose to skip an item. `setup` calls `onboard first` once, before its first write, so a new user is not sent through notes for versions they never had; the script refuses whenever `host.md` or `onboard.json` already exists. `setup` keeps every consent question, preview and write of each setup step; this skill never writes host config itself.
