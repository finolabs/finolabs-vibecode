---
name: open-source-review
description: Review a repository's readiness to be published as open source and report findings with evidence. Use before making a repository public, before a first public release, when publishing a plugin or skill package to a marketplace, when asked whether a repository is safe or ready to open source, or when checking a public repository's settings (branch and tag protection, secret scanning, vulnerability reporting).
---

# Open source review

A read-only review: it finds and reports, it does not publish. Fixes, history rewrites, visibility changes and releases each need the owner's explicit authority. After a repository is public, run it again before each MINOR release and whenever `SECURITY.md`, CI or the repository settings change; a patch release does not need one.

## 1. Fix the scope

Name the repository, the exact commit, and what will become public: the working tree, the full git history, release archives, or a packaged plugin. History counts unless the owner will publish a fresh history; say which.

Done when the scope line is written in the report.

## 2. Run every check

Mark each item **PASS**, **FAIL**, **N/A** (with why) or **BLOCKED** (with what is missing), and attach evidence: the command and its output, or the file and line. A tool that is not installed is BLOCKED, not PASS, unless the check names a fallback; a fallback result names the method it used.

### License

- A `LICENSE` file at the root, and the same SPDX id in every manifest (`package.json`, plugin manifests, `pyproject.toml`).
- Notices for vendored or copied third-party code, with their original licenses kept.
- Dependency licenses are compatible with the project license.

### Secrets and private data

- Recommend a `security-audit` run from [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) before the first public release of code that runs (services, CLIs, plugins with scripts or hooks); report whether one ran and its verdicts.
- Scan the full history and the working tree for secrets: `gitleaks git .` and `gitleaks dir .` (`detect` is deprecated), `trufflehog git file://.`, or `git log -p` with targeted patterns when no scanner is installed. Report the file and commit, never the secret's value. Install nothing yourself, but strongly recommend that the user installs a scanner when none is present: name `gitleaks` or `trufflehog` with its install command, and say that the `git log -p` fallback covers less.
- No real `.env` files, credentials, keys, cookies, transcripts, customer data or personal data, in the tree or the history.
- A leaked secret is a stop: tell the owner so it can be rotated. Removing it from the tree does not remove it from history.

### Internal leaks

- No employer, customer or partner names, internal hostnames, private URLs, ticket links or internal tool names.
- No absolute paths from a personal machine (`/Users/<name>/`, `/home/<name>/`, `C:\Users\`), usernames or email addresses beyond the published maintainer contact.
- Agent context files (`AGENTS.md`, `CLAUDE.md`) hold only what contributors need; personal context lives in an untracked local file.
- Examples and fixtures use synthetic names and data.

### Clean payload

- `git ls-files -ci --exclude-standard` is empty: no ignored file is still tracked.
- No build or cache output, virtualenvs, `node_modules`, OS files (`.DS_Store`, `Thumbs.db`), editor folders, scratch output or logs.
- No symlinks out of the repository, no submodules or LFS pointers the package depends on, no file names that collide by case or are invalid on Windows or macOS.
- Large files are justified; binaries are justified and their source is published.

### Community files

- `README.md`: what it does, who it is for, install, a first use, configuration, limits. At least a few paragraphs of prose, not only code.
- `CONTRIBUTING.md`: how to set up, test, and propose a change; the commit and review conventions.
- `CODE_OF_CONDUCT.md` (for example Contributor Covenant) with a working contact.
- `SECURITY.md`: how to report a vulnerability privately, and the supported versions.
- `CHANGELOG.md` (`versioning`), and issue and pull request templates where the forge supports them.
- Diagrams, the README, docs and in-product help (with its feature map) match what ships: what they name exists, and nothing shipped is missing. Report each drift (advisory, agent judgment).

### Repository settings

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

### Identity and versions

- One name across repository, package, manifests, display names and install commands. URLs resolve and point at the same owner.
- Versions agree across every manifest; the changelog's latest release matches them, or between releases its `Unreleased` section targets the `-dev` version; the single source of truth is named (`versioning`).

### Data flow and privacy

- State what data the software reads, where it sends it, what it stores and who can delete it, including optional services. A `PRIVACY.md` is needed when data leaves the user's machine.
- Behavior that runs, fetches or sends anything is documented, and dependencies are pinned.

### Plugin and skill packages

Only when the repository ships a plugin or skills:

- The validators pass: `claude plugin validate .` (and `--profile directory --strict` before a directory submission); the Codex manifest is checked against its current schema. Run them on a fresh clone: in a working checkout they also read untracked files such as `.DS_Store`.
- Before a directory submission, walk that directory's own pre-submission list ([Anthropic](https://claude.com/docs/plugins/pre-submission-checklist.md), [OpenAI](https://developers.openai.com/plugins/deploy/submission)) against the submitted folder or ZIP; `plugin-packaging` lists what each refuses or holds.
  Portal validation uploads the package and is not part of this review: list what only the portal can confirm beside the recheck items, so a ready verdict does not hide it.
- Each skill has a valid `name` and a trigger-rich `description`; a trigger check shows each model-invoked skill fires on a representative prompt and stays quiet on an unrelated one.
- Host-specific facts (paths, commands, allow-rules) live in configuration or references, not in skill bodies.
- Listing assets that the target directory requires (icon, URLs) exist inside the package.

## 3. Report

A table per group with status and evidence, then the FAIL and BLOCKED items ordered by severity: secrets and private data first, then internal leaks, license, payload, everything else. For each, the smallest fix and whether it needs the owner's authority (history rewrite, visibility change, repository settings, publishing). List every item marked N/A until publishing as a **recheck after the visibility change**, so a ready verdict does not hide it.
End with a one-line verdict: **ready**, **ready after fixes**, or **not ready**. A BLOCKED item in secrets and private data, internal leaks or license caps the verdict at **not ready**, naming the group that could not be checked, because what was not scanned cannot be called clean.

Done when every item above has a status and every FAIL has a fix.
