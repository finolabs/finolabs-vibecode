---
name: fnl-open-source-review
description: Review a repository's readiness to be published as open source and report findings with evidence. Use before making a repository public, before a first public release, when publishing a plugin or skill package to a marketplace, or when asked whether a repository is safe or ready to open source.
---

# Open source review

A read-only review: it finds and reports, it does not publish. Fixes, history rewrites, visibility changes and releases each need the owner's explicit authority.

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
- Scan the working tree and the full history for secrets (`gitleaks detect`, `trufflehog git file://.`, or `git log -p` with targeted patterns when no scanner is installed). Report the file and commit, never the secret's value.
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
- `CHANGELOG.md` (`fnl-versioning`), and issue and pull request templates where the forge supports them.

### Identity and versions

- One name across repository, package, manifests, display names and install commands. URLs resolve and point at the same owner.
- Versions agree across every manifest; the changelog's latest release matches them, or between releases its `Unreleased` section targets the `-dev` version; the single source of truth is named (`fnl-versioning`).

### Data flow and privacy

- State what data the software reads, where it sends it, what it stores and who can delete it, including optional services. A `PRIVACY.md` is needed when data leaves the user's machine.
- Behavior that runs, fetches or sends anything is documented, and dependencies are pinned.

### Plugin and skill packages

Only when the repository ships a plugin or skills:

- The validators pass: `claude plugin validate .` (and `--profile directory` before a directory submission); the Codex manifest is checked against its current schema.
- Each skill has a valid `name` and a trigger-rich `description`; a trigger check shows each model-invoked skill fires on a representative prompt and stays quiet on an unrelated one.
- Host-specific facts (paths, commands, allow-rules) live in configuration or references, not in skill bodies.
- Listing assets that the target directory requires (icon, URLs) exist inside the package.

## 3. Report

A table per group with status and evidence, then the FAIL and BLOCKED items ordered by severity: secrets and private data first, then internal leaks, license, payload, everything else. For each, the smallest fix and whether it needs the owner's authority (history rewrite, visibility change, publishing). End with a one-line verdict: **ready**, **ready after fixes**, or **not ready**.

Done when every item above has a status and every FAIL has a fix.
