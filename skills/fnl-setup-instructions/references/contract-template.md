# Working contract: sections and questions

Sections marked *optional* are skipped when the user has no need. Each section lists the decisions to settle; turn each answer into one or two imperative lines.

Each rule line says who enforces it: a host setting, a hook, the review gate, or agent judgment. A rule enforced only by agent judgment is advisory.

## 1. Identity and voice (required)

- Default language for replies, and when to switch (the user writes in another language, a document is for another audience).
- How to address the user and how the agent refers to itself, if the language has forms of address.
- Domains the user works in and expertise to assume, so the agent skips basics.
- Tone: concise or detailed, candor (challenge assumptions, say when something is wrong), and how to scale explanation to the stakes.
- Public writing (posts, docs for others): language, concrete numbers and detail, house style or editing skill to use.

## 2. Authority and approvals (required)

- Actions that always need the user's explicit yes: push, merge, deploy, publish, send messages, delete or overwrite data, change shared settings or other people's work.
- Whether repository or organization ownership grants access by itself (recommended: no).
- How to handle conflicting instructions (recommended: expose the conflict; a newer instruction does not win by being newer).
- Other sessions and agents: may the agent message, rename or stop sessions it did not start? (recommended: only with authority).

## 3. Secrets and private data (required)

- Credentials are injected by the approved mechanism and never read, printed or embedded (name it: environment variables, keychain, secret manager).
- Files the agent never reads (`.env`, credential stores).
- What happens on a leak: stop, tell the user, keep traces for rotation.
- Personal or customer data: which law or policy applies, and which services may receive it.

## 4. How work is done (required)

- Surgical changes in the existing style; no unsolicited refactors or features.
- Coding entry: "Before substantive coding, load `fnl-coding-router`." It covers routing, depth, review, verification and delegation.
- Status words for reports: drafted, verified, integrated, delivered, parked.
- Test scope (recommended: targeted tests for changed code and its consumers; full suites only on request, as `fnl-verification` says).
- Commits and versions: point to `fnl-commit-messages` and `fnl-versioning`; add only the user's own deviations.
- Learning from corrections: when the user corrects the same behavior twice in a session, propose one line for this contract at the end of the task, at most one proposal per session, and write it only after the user says yes.

## 5. Delegation (optional)

- Which other agents the user has (Codex, Antigravity, Claude Code sessions) and that `fnl-delegate` governs routing, budgets and acceptance.
- How much work should the agent hand to other agents? Recommended: propose delegation for independent tasks and ask before dispatch; when the plugin supports a delegation setting, record it here; until then record the preference in one line. This is a preference, not an available plugin setting.
- Machine facts live in the delegation host config written by `/fnl-setup`, not here.

## 6. Knowledge base (optional)

- Where durable notes live (a knowledge base such as Orrery, an Obsidian vault, a docs repository) and the only approved way to access them.
- Which single knowledge base agents use (Orrery where available, or an Obsidian vault), and that any other store is retired from agent use.
- What gets written back, and where decisions and lessons go. `fnl-knowledge` covers the practice; the contract holds only the user's stores and access rules.

## 7. Evaluators and external services (optional)

- Services approved to receive task data (for example a judgment or evaluation API), what fields may be sent, and spend limits.
- Services explicitly not approved.

## 8. Formats (optional)

- Time zone, date and number formats, currency, brand colors and fonts for documents.

## 9. Host section (one per host)

- Session titles: when and how to name or rename the session.
- Context pressure: when to compact or start fresh (`fnl-session-hygiene` "Context pressure"); for Claude Code, ask the user's threshold (recommended: about 60% at a safe idle boundary) and record it in one line. Enforcement belongs to host settings or hooks written by `fnl-setup`; a contract line alone is advisory, and no enforcement is claimed until verified.
- Host quirks: model selection, review commands, tools that need care.
