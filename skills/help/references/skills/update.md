# update

Typed by the user only.

**What it does.** Shows the installed and cached available versions, updates through the host's own command after your clear yes, then walks the new version's setup checklist. It can also show what is new without changing anything, target a chosen version, pin or unpin a version, skip a release, or stop update notices.

**When to use it.** A session-start notice says a newer version is available, you want to know what a release changed, or you want to hold, skip or choose a version.

**Type:** Claude Code `/finolabs-vibecode:update` or `/update`; Codex `$update`; Antigravity `/update`. Arguments: `[status | whats-new | <version> | pin <version> | unpin | skip <version> | never]`.

## Tips

- A notice is not permission: nothing is installed before your yes to the exact host command.
- Claude Code needs a restart after updating; on Codex, open `/hooks` in a new session and trust the plugin's hooks again. Each host installs the release its catalog pins; after each release, a catalog pull request moves the pins to the new tag once the owner says go.
- `/update whats-new` only shows the checklist; it installs and changes nothing.
- `FNL_UPDATE_CHECK=off` stops the daily check, the notices and these helper commands.
