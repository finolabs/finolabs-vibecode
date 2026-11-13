# Feature: delegation (user scope)

Needs: the agent scan (`scan.md`), asked as its own consent; declining it ends this feature. Skip when the `delegate` skill is not installed. Approval questions use neutral Yes and No with none preselected, as `interview.md` says; a default or timeout is not consent.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

Run the scan procedure with the running host passed explicitly, including its model confirmation, preview and clear yes before its section-only write. If it is unavailable, leave the inventory unverified and point to `/setup scan`; never guess which families exist.

Then record what each helper takes with the assignment matrix in [matrix.md](../matrix.md): levels, types of work, model, roles and the judge in one pass. It is the only source of roles and the judge (`## Agent roles` is never read; `migrate` converts it), and with a valid matrix `## Agent levels` is ignored, so [levels.md](../levels.md) serves only a user who declines it.

Ask: "Save how this computer starts and shares work with other AI helpers?"
Yes: Fill the shown local host.md from the delegate template; the saved helper list stays intact. Saving sends nothing; later helper work uses its provider.
No: Leave the file unchanged; ask later.
Undo: Restore the previous sections or edit them through setup.
Choices: "Yes, save the helper settings" / "No, leave the file unchanged".
Create the remaining config from `delegate`'s `references/host-template.md`, preserving the scan section byte for byte, and fill: how this computer invokes the present agents, which agents may coordinate and which delegates each can reach, the heavy-job limits (load, free memory, wait cap and maximum run time), and the durable folder for briefs and logs. Leave unknown commands as questions in the file rather than guesses.
Ask as free text, inside the repository being set up: "How many agent runs may work at the same time in this repository?"
Recommend a small number such as 3 to start; accept an integer from 1 to 32; without an answer the repository keeps the default of 3. Explain that runs of the same family share quota pools, that the limit counts only this repository and that other repositories keep their own.
Then ask as optional free text: "Any per-family caps for claude, codex or antigravity in this repository? Leave blank for the total limit only."
Accept any subset as `claude=<n>, codex=<n>, antigravity=<n>`, each n from 1 to the total. A blank answer means the total only: if caps already exist, show them and clear them with `--clear parallel-caps` after the same yes, so an old cap never outlives a smaller total.
Preview the entries and write each only after a yes, through `python3 -I <this skill folder>/scripts/project_progress.py settings --set parallel=<n>` and `--set parallel-caps=<list>` (clear with `--clear`); never infer a number from silence. They are saved in the repository's own settings file (`.finolabs/vibecode/settings.json` of the main checkout, approved in the data root); the old user-scope `## Limits` lines and the `## Project settings` section of `host.md` are no longer read.
Validate with `python3 -I <delegate skill folder>/scripts/parallel_slots.py check-config` from the repository and show its understood total, caps and source.
Exit 3 means default or unknown: a never configured repository (no approval record, including a file nobody approved) uses the default of 3 with source `default`; a cap above the total, or an approved settings file later edited, deleted, unsafe or unreadable, prints `unknown`. For broken settings every setter refuses: offer the reset in [project-settings.md](../project-settings.md) after its own yes, then ask these questions again. Fix or leave setup unverified; never call a default or unknown the user's choice.
Asking and honoring caps are advisory (agent judgment); `parallel_slots.py` enforces parsing only, not dispatch admission.
When more than one agent coordinates, recommend a host config and ledger path every coordinator's sandbox can read and write.

For each present agent family, ask: "Let <agent family> receive any named runtime settings when it starts?"
Yes: Ask for setting names only, then save confirmed names in Delegate environment in local host.md; sensitive names need separate approval. Later command-line helpers receive those values and may use their provider; saving names sends nothing.
No: Keep the default none for this setup; an existing section stays unchanged unless separately approved. Ask later.
Undo: Remove approved names or set that family to none in the section.
Choices: "Yes, choose setting names" / "No, pass no new settings".

Default none; neutral Yes and No, none preselected. After Yes ask for names only, never values or source files.
Validate each name against `^[A-Z][A-Z0-9_]{0,63}$`; refuse duplicates and loader/interpreter/proxy controls
(`LD_*`, `DYLD_*`, `BASH_ENV`, `ENV`, `NODE_OPTIONS`, `PYTHON*`, `PERL5*`, `RUBY*`, `GIT_*`, `*_PROXY`, `SSL_CERT_*`,
`NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `NODE_TLS_REJECT_UNAUTHORIZED`,
`NODE_PATH`, `PERLLIB`, `SHELLOPTS`, `PS4`, `PROMPT_COMMAND`, `JAVA_TOOL_OPTIONS`).
For each name containing KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, SESSIONID or SESSID anywhere, or
PASS, PASSWD, PASSPHRASE, AUTH, COOKIE, COOKIES, SESSION or PRIVATE as a complete
underscore-delimited part, ask separately:
"Let <agent family> receive the value of <VARIABLE_NAME> when it starts?"
Yes: Save only this name and its approval in Delegate environment in local host.md. Later command-line helpers receive its value, which may authorize provider access; the plugin never copies or stores that value.
No: Approve no new name and pass nothing for this request; ask later.
Undo: Remove this name’s approval from that section before the next handoff.
Choices: "Yes, pass this named setting" / "No, do not pass it".
Offer neutral Yes and No with none preselected; only an explicit Yes
records that name's `; approved: yes`. No, skip or timeout passes nothing. Store names only in canonical
`## Delegate environment`: `- <family>: none` or one `- <family>: <NAME>` per line; sensitive names require
the approval suffix. Never copy a value. `delegate_env.py` strictly checks this section at dispatch.
Explain and report: protection is environment-only; HOME stays and credential files under it, the plugin data
root and keychain-backed helpers remain reachable. Interactive, desktop-app sessions and in-session subagents
are not covered. Private HOME remains an open owner decision; do not offer or create one in this package.

When Antigravity is a delegate, list this repository's test and check commands and ask for each: "Let Antigravity run this exact test command again in this repository without asking?"
Yes: Save a remembered permission in Antigravity’s settings and record it in local host.md. Tests run whatever code they contain and may contact services; task data uses Google’s provider.
No: Add no permission or record; ask later.
Undo: Remove the exact permission in Antigravity’s settings and its host.md record.
Choices: "Yes, allow this test command" / "No, add no permission".
Say that a granted test command runs whatever code the tests contain. Grant only each exact test command, never a wildcard or a general shell; record every granted command in the host config; a grant is for this repository and is not carried to another.
With `agybird`, the first run that needs one reports `needs_permission` and the user picks "allow and remember" (`--grant-scope remember`); without it, the user adds the literal rules to Antigravity's own settings. The host config only records the answer.

Enforcers: asking, previews and the byte-for-byte preservation are agent judgment (advisory); the scan script enforces its own section write.
