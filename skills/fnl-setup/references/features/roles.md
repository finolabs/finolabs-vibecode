# Feature: roles (user scope)

Needs: the agent scan (`scan.md`), asked as its own consent; declining it ends the roles and posting steps. The judge step needs nothing. If `roles` is never run the judge is `host`. Every question uses neutral Yes and No (or the listed choices) with none preselected, as `interview.md` says. Roles, the judge and posting grant nothing by themselves; the section is never an access or posting right. Asking is advisory (agent judgment); `## Agent roles` and `## Review posting` are read strictly by their readers and an unreadable section falls back to the routing rule.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

## Judge

Ask with three neutral choices: "Which judge should answer semantic questions: Jev, a small model of your host, or none?" Record `judge: jev` or `judge: host` in `## Agent roles`; `none` writes no `judge` line, which reads as `host`, and nothing leaves the host's own provider. Jev needs the user's own TypeSafe authorization and API budget; an installed `typesafe-ai` skill grants neither, and task data goes to that service only on the user's yes.
If the user picks Jev and `typesafe-ai` is missing, print its install command from [companions.md](../companions.md), say the user's own key and budget are needed, and never read, store or search for the key; a read-only `--check` may report whether the variable is set without printing it. Once configured, `fnl-delegate` and `fnl-coding-router` ask the judge first for the grade, route, depth and next activity; if Jev is unavailable at run time the small host model takes over for that call and the report says so.
Receipts hold the answer and an identifier, never the criterion text.

When the judge is not none, ask a second, separate question: "May Check send lines of your instruction files to the judge for the judgment items of the instruction checklist?" Say it sees the text of your private instruction files, apart from lines that look like secrets or machine paths, which are dropped; the provider (TypeSafe) keeps data under its own retention; judge grading is optional and the agent grades those items itself without it. A yes does not follow from the judge choice. Record `Instruction check: on` with the date; no, or no judge, records `off`.

## Roles

Ask: "Assign these review roles?" showing the exact lines to write under `## Agent roles` in the canonical `host.md`, one per role, with defaults from the scan (present families other than the coordinator's):

```
## Agent roles
- code review: <family>
- security review: <family>
- navigator: <family>
- judge: <jev|host>
```

Keys are exactly `code review`, `security review`, `navigator` and `judge`; values are a family named in `## Agents on this machine`, except `judge`; at most 10 lines; any other line, a duplicate or an unknown family makes the section unreadable. The family that codes and the family that reviews should differ (highly recommended, not forced).

## Review posting

Per family, one at a time, show the exact setup step before any write and ask: "Set up review posting for this family?" A review run posts its own comment when it can; otherwise it returns the comment with `cannot-post: <reason>` and the coordinator relays once, a counted fallback, never the steady state. `post_review.py` is the one posting path (the repository comes from the checkout's remote, only `gh pr comment` and `gh pr view` run).
- Codex: a fine-grained GitHub token limited to this one repository with an expiry, supplied through the credential injection the user approves; the plugin never reads, stores or searches for it. State the residual risk: a token with pull-request write can also approve, dismiss, close and edit the body, and a reviewer reads attacker-controlled text, so the wrapper is the only intended path. If the sandbox already reads the user's `gh` login, that is used instead.
- Antigravity: a remembered allow-rule for the exact argv of `post_review.py`, never for `gh` itself, no wildcard, recorded in the host config like the test-command grants.

Record `- <family>: unverified` in `## Review posting`; `yes` is written only after the coordinator sees that family's own marker on a pull request from the expected identity, and enabling a setting does not count. Before `yes`, no family's posting is promised.
