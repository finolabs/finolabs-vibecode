# Relay and posting setup

Detail behind `SKILL.md` "Cannot post and relay". The wrapper interface is in [routing-and-posting.md](routing-and-posting.md) "Post".

## Posting path

Each reviewer posts its whole report as one comment through `post_review.py`. This is the only intended posting path for every family. The wrapper allows only `gh pr comment` and `gh pr view`, binding the repository to the checkout's GitHub remote.

## Cannot post

`post_review.py` emits those fixed reasons for posting failures; the reviewer uses them for missing host capabilities too (advisory, agent judgment). Explain the missing capability and direct the user to `fnl-setup`; do not make relay the steady state.

## Relay

A general right to post does not authorize a relay. An approval counts only when its scope and date are committed in the agent context file on the default branch; host settings, memory and uncommitted text do not count. Where approval is missing, return the comment to the owner and leave the merge pending. Preserve the report, verdict and marker; the relay attribution on the second line names the reviewer, coordinator and approval record. Relay through the same wrapper and report the relay once to the owner (advisory, agent judgment). Relay-specific receipts and dashboard counters are not implemented; `record.py` has no relay command. The coordinator enforces the once-per-run limit; the wrapper grants no relay authority and counts nothing.

## Posting setup

Only `fnl-setup` writes `## Review posting`, after the user's neutral Yes or No and the shown setup step. Codex uses the existing sandbox `gh` login or approved credential injection of a repository-scoped, expiring fine-grained token; the plugin never reads, stores or searches for a token. Such a token may also approve, dismiss, close or edit a pull request; explain this residual risk and that public-repository comments are public. Antigravity gets a remembered allow-rule for the exact wrapper argv, never `gh` or a wildcard. Setup and these consent rules are advisory (agent judgment); host permission rules enforce the grant.

Before recording `yes`, the coordinator calls `post_review.posting_verified(comments, expected_identity, expected_marker)` with the family's exact marker and the identity the user expected, after observing the comment on the intended PR. The pure function requires both; a marker posted by a coordinator does not verify the reviewer's identity. A configured permission or enabled setting is not proof. Reading the PR, associating the marker with the family and calling the function before setup writes are advisory (agent judgment); the function enforces the supplied evidence check.

## Adoption

Where the repository has not adopted it, ask the user once whether to add that line (`fnl-setup` writes it) before posting. It grants no authority to merge, which stays with the owner.
