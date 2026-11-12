# Feature: roles (user scope)

Needs: the agent scan (`scan.md`), asked as its own consent; declining it ends the roles and posting steps. The judge step needs nothing. If `roles` is never run the judge is `host`. Every question uses neutral Yes and No (or the listed choices) with none preselected, as `interview.md` says. Roles, the judge and posting grant nothing by themselves; the section is never an access or posting right. Asking is advisory (agent judgment); `## Agent roles` and `## Review posting` are read strictly by their readers and an unreadable section falls back to the routing rule.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

The assignment matrix ([../matrix.md](../matrix.md), part of `add delegation`) is the one path for roles and the judge. When `## Assignment matrix` exists, its readers ignore `## Agent roles`: set roles and the judge there (its judge step asks the TypeSafe question below), and use this page only for the instruction check and review posting. The steps below write `## Agent roles` only for a user without a matrix.

## Judge

Ask with three neutral choices: Jev (TypeSafe’s evidence-checking service), a small model of your current AI app, or none. Question: "Who should help check whether task evidence meets a requirement?"
Description: Save the choice in local host.md. Jev needs separate data/budget approval; the small model uses your AI provider. None omits judge and still reads as host fallback. Undecided keeps the setting; change later here or disable Jev with FNL_JUDGE=off.
Record `judge: jev` or `judge: host` in `## Agent roles`; `none` writes no `judge` line, which reads as `host`, and nothing leaves the host's own provider. Jev needs the user's own TypeSafe authorization and API budget; an installed `typesafe-ai` skill grants neither, and task data goes to that service only on the user's yes.
If the user picks Jev, explain that `judge.py` sends a closed, size-capped English question and its evidence to
`https://api.typesafe.ai/v1/systemone`, only at the four sites allowed by `CLAUDE.md`. The key comes only from
`TYPESAFE_API_KEY` in the process environment; never read, store or search for it. A read-only check may report only
whether it is set. The optional `typesafe-ai` skill supplies cookbooks and is not needed for calls. The script refuses
secrets and machine paths before sending, caps attempts at 24 per run, verifies TLS, ignores proxy/certificate
variables and follows no redirects; `FNL_JUDGE=off` stops calls. No hook starts a judgment. Record `judge: jev` only
after the user's separate yes and API-budget authorization. If unavailable, use the small host model with the same
payload and disclose the fallback. Deterministic rules and explicit choices precede a bounded judge question.
Receipts hold the answer and an identifier, never the criterion text.

Before recording Jev, ask separately: "Let TypeSafe check task evidence using your service account and approved budget?"
Yes: Save judge: jev in local host.md; only the four allowed call sites send capped English evidence to TypeSafe using your approved account and spend budget. No hook calls it.
No: Leave the saved judge unchanged and use the small host fallback; ask later.
Undo: Choose host in setup or use FNL_JUDGE=off; already sent data follows TypeSafe's policy.
Choices: "Yes, allow budgeted TypeSafe checks" / "No, keep the host fallback".

When the judge is not none, ask a second, separate question: "Let your AI provider review your saved instructions during setup checks?"
Yes: Save Instruction check: on and its date in local host.md. Send selected lines from files telling AI how to behave, excluding secret/path matches, to the small host model under that provider’s retention; never TypeSafe for this check.
No: Record off; the agent assesses those items itself. Ask later.
Undo: Set Instruction check to off through setup.
Choices: "Yes, allow instruction-line checks" / "No, keep those checks off".

Say it sees the text of your private instruction files, apart from lines that look like secrets or machine paths, which are dropped; instruction checking uses the small host fallback because it is outside the four outbound sites, under the host provider's retention; judge grading is optional and the agent grades those items itself without it.
A yes does not follow from the judge choice. Record `Instruction check: on` with the date; no, or no judge, records `off`.

## Roles

Show the exact lines first, then ask: "Save which AI helpers review code, check safety and watch project progress?"
Yes: Write the shown Agent roles lines in local host.md. Saving sends nothing; later tasks use the selected helpers’ providers. This grants no access or posting rights.
No: Leave assignments unchanged; ask later.
Undo: Restore or change these role lines through setup.
Choices: "Yes, save these assignments" / "No, keep current assignments".
Write the shown lines under `## Agent roles` in the canonical `host.md`, one per role, with defaults from the scan (present families other than the coordinator's):

```
## Agent roles
- code review: <family>
- security review: <family>
- navigator: <family>
- judge: <jev|host>
```

Keys are exactly `code review`, `security review`, `navigator` and `judge`; values are a family named in `## Agents on this machine`, except `judge`; at most 10 lines; any other line, a duplicate or an unknown family makes the section unreadable. The family that codes and the family that reviews should differ (highly recommended, not forced).

## Review posting

Explain pull requests as proposals to add code changes. Per family, one at a time, show the exact setup step before any write and ask: "Set up this AI helper to post its own review comments on this repository’s pull requests?"
Yes: Apply the exact shown permission or approved credential injection, and record unverified in local host.md. A posting check sends the review to GitHub; permission alone proves no successful post.
No: Leave posting setup unchanged; ask later.
Undo: Revoke the injected permission or remembered rule and update the posting record.
Choices: "Yes, set up review posting" / "No, leave posting unchanged".
A review run posts its own comment when it can; otherwise it returns the comment with `cannot-post: <reason>` and the coordinator relays once, a counted fallback, never the steady state. `post_review.py` is the one posting path (the repository comes from the checkout's remote, only `gh pr comment` and `gh pr view` run).
- Codex: a fine-grained GitHub token limited to this one repository with an expiry, supplied through the credential injection the user approves; the plugin never reads, stores or searches for it. State the residual risk: a token with pull-request write can also approve, dismiss, close and edit the body, and a reviewer reads attacker-controlled text, so the wrapper is the only intended path. If the sandbox already reads the user's `gh` login, that is used instead.
- Antigravity: a remembered allow-rule for the exact argv of `post_review.py`, never for `gh` itself, no wildcard, recorded in the host config like the test-command grants.

Record `- <family>: unverified` in `## Review posting`; `yes` is written only after the coordinator sees that family's own marker on a pull request from the expected identity, and enabling a setting does not count. Before `yes`, no family's posting is promised.
