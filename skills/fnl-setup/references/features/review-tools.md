# Feature: review-tools (user scope)

Needs: nothing. This feature asks no consent: it recommends and installs nothing (advisory, agent judgment). Companion skills are covered by the same rule through [companions.md](../companions.md).

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

Look up from the skill listing and `--help` only which review instruments each installed host has: Claude Code `/code-review` and `/security-review`, Codex `codex review`, and the `security-audit` skill from Cloudflare. Antigravity has none.

The `fnl-reviewer` and `fnl-security-reviewer` agents run these instruments as their engine, on the family each review role names (`roles`), so a review meets the standard only where the instrument is installed. For each one the findings show missing, strongly recommend installing it and give the command: for `security-audit`, `npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit`; for a host's native review, the host's own update or install path, checked against its docs. Install nothing yourself.
Until a tool is installed the reviewers work by hand and say so in each report.

Record each missing companion whose condition the findings match, for the closing "After your first result" list of the core path. Include these reminders even when the beginner path skipped this feature.
