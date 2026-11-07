# Feature: delegation (user scope)

Needs: the agent scan (`scan.md`), asked as its own consent; declining it ends this feature. Skip when the `fnl-delegate` skill is not installed. Every question below uses neutral Yes and No with none preselected, as `interview.md` says; a default or timeout is not consent.

Run the scan procedure with the running host passed explicitly, including its model confirmation, preview and clear yes before its section-only write. If it is unavailable, leave the inventory unverified and point to `/fnl-setup scan`; never guess which families exist.

Ask: "Fill the host config from the `fnl-delegate` template?" Create the remaining config from `fnl-delegate`'s `references/host-template.md`, preserving the scan section byte for byte, and fill: how this computer invokes the present agents, which agents may coordinate and which delegates each can reach, the parallel limit (5 or fewer), the heavy-job lock path, and the durable folder for briefs and logs. Leave unknown commands as questions in the file rather than guesses.
When more than one agent coordinates, recommend a host config and ledger path every coordinator's sandbox can read and write.

When Antigravity is a delegate, list this repository's test and check commands and ask for each: "Grant Antigravity this exact test command as a remembered allow-rule?" Say that a granted test command runs whatever code the tests contain. Grant only each exact test command, never a wildcard or a general shell; record every granted command in the host config; a grant is for this repository and is not carried to another.
With `agybird`, the first run that needs one reports `needs_permission` and the user picks "allow and remember" (`--grant-scope remember`); without it, the user adds the literal rules to Antigravity's own settings. The host config only records the answer.

Enforcers: asking, previews and the byte-for-byte preservation are agent judgment (advisory); the scan script enforces its own section write.
