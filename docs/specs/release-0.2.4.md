# Release 0.2.4: scope

Status: released; tagged v0.2.4 on 2026-11-11 with all six packages. A real `git push` through the installed hook and a run of the generated workflow on GitHub Actions remain unverified.

## Scope (owner decisions, 2026-11-10)

| # | Package | What it covers |
| --- | --- | --- |
| 1 | Rename | `fnl-verification` becomes fnl-checks; the old name stays as a user-only thin alias through 0.2.x. Spec: `checks.md`. |
| 2 | Check list | `/fnl-setup add checks` detects a repository's checks and stores them in `## Checks` of the canonical host config after a previewed yes. Spec: `checks.md`. |
| 3 | Running checks | `checks.py run [--changed]` through `heavy_run.py`, the optional pre-push hook, and the opt-in local receipt that `merge_check.py` labels. Spec: `checks.md`. |
| 4 | Cheaper CI | `references/ci.md`, the previewed workflow writer and `checks.py usage`. Spec: `checks.md`. |
| 5 | Update onboarding | Upgrade notes, `/fnl-update` walking new setup, `whats-new`, latest by default with a chosen or pinned version, and the release test. Spec: `update-onboarding.md`. |
| 6 | Diagrams and documents | Everything that describes the product matches what ships, as `fnl-versioning` requires. |

## Release steps

Follow `fnl-versioning`: a release pull request that drops `-dev`, dates the changelog and writes the upgrade-notes entry; the tag after CI on that commit; a GitHub release; a bump to the next `-dev`; then the catalog pin and the Codex refresh.
