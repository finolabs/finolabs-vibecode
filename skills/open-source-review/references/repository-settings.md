# Repository settings

Read during step 2 of `open-source-review`; mark every item below and report it in the Repository settings group.

Read them from the forge; without access to the settings, mark the group BLOCKED. On GitHub, read-only `gh api` calls under `repos/<owner>/<repo>`: the repository itself (merge and listing settings, and `security_and_analysis`, which only admins see), `rules/branches/<branch>` for the rules in effect, `rulesets` and `branches/<branch>/protection`, `vulnerability-alerts` and `automated-security-fixes`, `private-vulnerability-reporting`, `actions/permissions` (including `sha_pinning_required`), `actions/permissions/workflow` and `actions/permissions/fork-pr-contributor-approval`.

Check before publishing what the forge plan offers on a private repository, and check again right after the visibility change. Before publishing, an item the plan offers only on public repositories (on GitHub's free plan: rulesets, classic branch protection, secret scanning and private vulnerability reporting) is N/A with that reason.
Once public, these settings protect the history and its reporters. A FAIL on default branch protection, release tag protection, secret scanning and push protection, dependency alerts and security updates, private vulnerability reporting or Actions blocks a ready verdict; merge settings and listing are recommended and are noted without blocking.

- **Default branch protected** by a ruleset or branch protection: changes arrive through pull requests, the CI checks that gate a merge are required, force pushes and deletion are blocked, and administrators follow the same rules (or the owner records why not).
- **Release tags protected**: `v*` tags, and `<path>/v*` for component tags, cannot be moved or deleted, matching the immutable tags in `versioning`.
- **Secret scanning and push protection** on.
- **Dependency alerts and security updates** on for every ecosystem the repository uses, including its CI actions.
- **Private vulnerability reporting** on, whenever `SECURITY.md` points reporters to it.
- **Merge settings**: the allowed merge methods keep each commit as written (merge commit or rebase), or squash only where each pull request title becomes a verb-led subject line that `commit-messages` accepts (on GitHub, `squash_merge_commit_title` is `PR_TITLE` or `COMMIT_OR_PR_TITLE`); head branches are deleted after merge. These match the branch flow in `commit-messages` "Branches".
- **Actions**: the workflow token is read-only by default and cannot approve pull requests; workflows from first-time contributors' forks wait for approval; third-party actions are pinned to commit SHAs (enforced where the forge can, as GitHub's `sha_pinning_required`).
- **Listing**: description, homepage and topics set; features the project does not use (wiki, projects, discussions) turned off so nothing unmonitored collects reports.
