# security-review-gate

Typed by the user, or loaded by the agent when the task matches.

**What it does.** A security review for changes that cross a sensitive boundary, with a permission-boundary review: each actor class, the expected result of every action, negative tests proving denial, and no leak of whether a hidden record exists.

**When to use it.** A change adds or alters authentication, authorization, permissions, sharing or tenancy, private or personal data, secrets, untrusted input, payments, or file and network access, and before merging it.

**Type:** Claude Code `/finolabs-vibecode:security-review-gate` or `/security-review-gate`; Codex `$security-review-gate`; Antigravity `/security-review-gate`.

## Tips

- Every pull request gets a security review; a trigger adds scrutiny of its own and raises the depth to at least NORMAL.
- A denied caller gets the same response as for a resource that does not exist.
- For a wider audit it recommends `security-audit` from cloudflare/security-audit-skill, a separate project.
