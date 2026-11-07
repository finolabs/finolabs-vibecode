# Feature: delegation (user scope)

Needs: the agent scan (`scan.md`), asked as its own consent; declining it ends this feature. Skip when the `fnl-delegate` skill is not installed. Every question below uses neutral Yes and No with none preselected, as `interview.md` says; a default or timeout is not consent.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

Run the scan procedure with the running host passed explicitly, including its model confirmation, preview and clear yes before its section-only write. If it is unavailable, leave the inventory unverified and point to `/fnl-setup scan`; never guess which families exist.

Ask: "Fill the host config from the `fnl-delegate` template?" Create the remaining config from `fnl-delegate`'s `references/host-template.md`, preserving the scan section byte for byte, and fill: how this computer invokes the present agents, which agents may coordinate and which delegates each can reach, the parallel limit (5 or fewer), the heavy-job lock path, and the durable folder for briefs and logs. Leave unknown commands as questions in the file rather than guesses.
When more than one agent coordinates, recommend a host config and ledger path every coordinator's sandbox can read and write.

For each present agent family, ask: "Does <agent family> need any environment variable passed through?"
Default none; neutral Yes and No, none preselected. After Yes ask for names only, never values or source files.
Validate each name against `^[A-Z][A-Z0-9_]{0,63}$`; refuse duplicates and loader/interpreter/proxy controls
(`LD_*`, `DYLD_*`, `BASH_ENV`, `ENV`, `NODE_OPTIONS`, `PYTHON*`, `PERL5*`, `RUBY*`, `GIT_*`, `*_PROXY`, `SSL_CERT_*`,
`NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `NODE_TLS_REJECT_UNAUTHORIZED`,
`NODE_PATH`, `PERLLIB`, `SHELLOPTS`, `PS4`, `PROMPT_COMMAND`, `JAVA_TOOL_OPTIONS`).
For each name containing KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, SESSIONID or SESSID anywhere, or
PASS, PASSWD, PASSPHRASE, AUTH, COOKIE, COOKIES, SESSION or PRIVATE as a complete
underscore-delimited part, ask separately:
"Pass <VARIABLE_NAME> to <agent family>?" Offer neutral Yes and No with none preselected; only an explicit Yes
records that name's `; approved: yes`. No, skip or timeout passes nothing. Store names only in canonical
`## Delegate environment`: `- <family>: none` or one `- <family>: <NAME>` per line; sensitive names require
the approval suffix. Never copy a value. `delegate_env.py` strictly checks this section at dispatch.
Explain and report: protection is environment-only; HOME stays and credential files under it, the plugin data
root and keychain-backed helpers remain reachable. Interactive, desktop-app sessions and in-session subagents
are not covered. Private HOME remains an open owner decision; do not offer or create one in this package.

When Antigravity is a delegate, list this repository's test and check commands and ask for each: "Grant Antigravity this exact test command as a remembered allow-rule?" Say that a granted test command runs whatever code the tests contain. Grant only each exact test command, never a wildcard or a general shell; record every granted command in the host config; a grant is for this repository and is not carried to another.
With `agybird`, the first run that needs one reports `needs_permission` and the user picks "allow and remember" (`--grant-scope remember`); without it, the user adds the literal rules to Antigravity's own settings. The host config only records the answer.

Enforcers: asking, previews and the byte-for-byte preservation are agent judgment (advisory); the scan script enforces its own section write.
