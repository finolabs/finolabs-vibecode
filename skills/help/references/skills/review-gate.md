# review-gate

Typed by the user, or loaded by the agent when the task matches.

**What it does.** Gates work on an independent code review: after each user story or increment, and before every pull request merges, where both a code review and a security review are posted on the pull request. Every finding gets a disposition, and every runtime fix gets a regression test.

**When to use it.** A story is committed, a pull request is about to merge, review findings arrive and need a disposition, or you are deciding whether a fix needs re-review.

**Type:** Claude Code `/finolabs-vibecode:review-gate` or `/review-gate`; Codex `$review-gate`; Antigravity `/review-gate`.

## Tips

- The reviewer is a fresh context, preferably another model family; `review_route.py` picks it from local state.
- A push after a review makes that review stale; the reviewers review the new head and post again.
- `merge_check.py` exits 0 when the merge may go ahead, 1 when something blocks it and 2 when it cannot tell.
- Rework rounds stop at the `Rework limit` under `## Reviews` of `host.md` (2 by default, 2 to 4); then the work goes back to you.
- Reviews can route to Codex, Antigravity or ZCode; outside an away lease a same-family security review counts when you recorded that fallback in `/setup add roles` or when you approve it for that pull request.
- Where a repository adopts it, a low-risk lane gives root-document, version-bump, catalog-pin and post-release record pull requests one review pass.
