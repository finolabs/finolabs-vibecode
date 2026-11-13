# README standard and release checklist
Status: in progress; standard, checklist, script and release wiring written; pull request open for review

## Goal and acceptance

Every repository that develops with this plugin reviews its README against one standard on each release and fixes what drifted, without depending on someone remembering it (owner request, 2026-11-13).

- [x] AC1 `plugin-packaging` ships `references/readme.md`: required and conditional sections in order with the condition for each, the facts taken from the repository (license, hosts, latest release, install path, counts), and both audiences (people, and agents that install the plugin).
- [x] AC2 The checklist items each name how they are checked (script or agent) and cover section order, badge targets, counts, install commands, the license line, descriptions across README, manifests, catalog and forge, images with light and dark variants and alt text, links, placeholders, and added or removed skills, commands and hosts.
- [x] AC3 `versioning` "Cadence" and `plugin-packaging` "6. Checks before a release" require the checklist before the tag: fix drift or record per item why not.
- [x] AC4 `readme_check.py` checks the mechanical items offline, is advisory and is not wired into CI.
- [x] AC5 Organization style stays out of the skill: a repository-local `.github/readme-standard.json` carries headings, alias folders, badge colour, catalog and the banner follow-up.
- [x] AC6 This repository's README passes the script items.

## Plan

Placement: `plugin-packaging`, which already owns the README's install commands and the release checks for plugin repositories; `versioning` names it from its existing documentation-review bullet. The layout codified is this repository's README on `main` as of 2026-11-13, checked against four other repositories that adopted it the same day, which showed what varies: language of the headings, banner path, catalog-only repositories with no manifest, commands named with a plugin prefix, responsive `<picture>` elements.

## Tasks

### US1
- [x] T1 Write `references/readme.md` (standard, checklist, override, release steps).
- [x] T2 Write `scripts/readme_check.py` and `tests/test_readme_check.py`.
- [x] T3 Wire `versioning`, `plugin-packaging`, the help map, the README layout and the changelog.
- [x] T4 Add `.github/readme-standard.json` for this repository and fix its README (Privacy section) and marketplace description.
- [ ] T5 Owner decision: the README names an unpublished knowledge base in the `tidy` row and in Acknowledgements (checklist P3).

## Evidence

`python3 -I skills/plugin-packaging/scripts/readme_check.py .` prints PASS for all fifteen script items on this branch; the agent items and the review verdicts are recorded in the pull request.
