# afk: native deny rules (Claude Code)

Loaded by [features/afk.md](features/afk.md) after the save, on Claude Code. Questions follow [interview.md](interview.md) (advisory, agent judgment).

Offer the host's own blocking of the credential floor (docs/specs/afk-decider.md decision 6). Run `python3 -I <this skill folder>/scripts/afk_native_rules.py preview [--folder <config folder>]...` (default `~/.claude`; name each config folder the user runs Claude Code with, at most four), show its targets, the rules it adds to `permissions.deny`, the backup and the `Digest:` line, then ask with neutral wording and no recommended option:
"Add these deny rules to Claude Code, so it refuses these credential reads and commands in every session, with or without an afk lease?"
Yes: Run `afk_native_rules.py apply --digest <full digest> --yes`; only those rules are added, every other setting stays (script-enforced).
No: Change nothing; `/afk start` then warns that nothing on the host blocks credential reads unless the approval mode asks.
Undo: `afk_native_rules.py preview --remove`, then apply its digest; or restore the shown backup.
Choices: "Yes, add the rules" / "No, leave the settings".
