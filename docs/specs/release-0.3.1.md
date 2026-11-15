# Release 0.3.1: scope

Status: accepted; prepared, to be tagged v0.3.1 after the owner's yes.

## What shipped

| Pull request | Change |
| --- | --- |
| 293 | The `review-gate` low-risk lane also takes a post-release record (`Status:` line and its index row). |
| 294 | An away lease may add its own worktree under `.claude/worktrees` and run this install's `checks.py`. |
| 295 | An away lease decides unknown requests of an allowlisted shape through the decision ladder, once per exact request; a security review relay under a lease with Merge yes. |
| 297 | Skills, spec and README follow the unknown-request ladder. |
| 298 | This repository's `CLAUDE.md` gains its Agent skills block. |
| 299 | `/setup instructions` points to `afk` and the assignment matrix. |
| 300 | `readme_check.py` caps and checks every read and fails a shipped manifest that a hosts override leaves out. |
| 301 | An away lease merges only with a recent MERGE OK receipt from `merge_check.py --independent`. |
| 302 | Away merge pins and cleanup are bound to the repository the merge check verified; a full log refuses before reserving. |
| 303 | `readme_check.py` LOW findings: outside-root links, private URLs, linear-time scans. |
| 304 | Approved check lists are bound to the full checkout identity. |
| 305 | Docs and tests for repository-scoped merge cleanup. |
| 306 | Native Windows prints one WSL line in setup check and scan; `checks` names the host's `Load limit`; setup wording. |
| 307 | `merge_check.py --ci-context` and this repository's `Merge check` workflow, now a required status on main. |
| 308 | The Codex clause of the compaction nudge rule (`CLAUDE.md`, `PRIVACY.md`, spec). |
| 309 | Per-skill help pages, tips and troubleshooting; `shape` and worktrees in the request-to-merge diagram. |
| 310 | The compaction nudge on Codex (`compact_nudge.py --host codex`). |
| 311 | This release: docs drift fixes, help map rows, re-rendered diagrams, upgrade notes, changelog and manifests. |
| 312 | An away lease commits only on a work branch; `ledger.py` warns on an unverified acceptance; the `verification` aliases are removed. |
| 313 | `## Agent levels` is retired; `matrix_setup.py migrate` still reads it to move levels into the assignment matrix. |
| 314 | The afk mechanism and away decision diagrams show the decided-once path for an unknown request. |
| 315 | Links and the update check's release endpoint point at the renamed repository, `finolabs/vibecode`; lowercase social preview. |
| 316 | Every release ends with `tidy`. |

The changelog's 0.3.1 section holds the user-facing wording; `update` carries the 0.3.1 upgrade notes. The request-to-merge, session-health and afk-mechanism PNGs were re-rendered (2530 pixels wide).

## Owner decisions

- 15/11/2026: release 0.3.1 after the backlog (`.finolabs/backlog-0.3.1.md`).
- 15/11/2026: fold everything left into 0.3.1, including two breaking removals (`## Agent levels` and the `verification` aliases), and still call it 0.3.1. This overrides `versioning`, which asks for a MINOR bump for a breaking change in phase 0; the changelog marks both entries Breaking and the upgrade notes say what to do.
- 15/11/2026: an away lease's `git commit` on the default branch answers `protected`; `ledger.py` warns but still accepts an unverified run or a review without a URL.
- 15/11/2026: the repository moves to `finolabs/vibecode`; the plugin keeps its name. Every release ends with `tidy`.
- 15/11/2026: an away lease decides unknown requests instead of parking them; a merge needs a MERGE OK receipt.
- 15/11/2026: `merge_check` becomes a required status on main (O-b); the Codex compaction nudge lands in 0.3.1 (A9b); the plugin's default load limit stays 12; native Windows gets a clear WSL message, not a port.

## The upgrade

- Codex: trust the plugin's hooks again with `/hooks` after the refresh (`0.3.1/codex-hook-trust`).
- Approved check lists saved before 0.3.1 keep counting until `/setup add checks` writes them again (`0.3.1/checks-identity`).
- Levels still in `## Agent levels` move into the assignment matrix with `/setup add delegation` (`0.3.1/agent-levels-retired`).
- Type `checks` where you typed `verification` (`0.3.1/verification-alias-removed`).
- Installs of 0.3.0 and earlier no longer see update notices after the repository move; update them once by hand (`0.3.1/repository-moved`).

## Known follow-ups

- Live delivery of the Codex nudge in the Codex CLI and app remains unverified.
- The `finolabs/plugins` catalog entry still names the old repository path, which GitHub redirects; it moves with the catalog pin.
- Native Windows support (issue 193) stays out of scope; WSL is the supported path.
