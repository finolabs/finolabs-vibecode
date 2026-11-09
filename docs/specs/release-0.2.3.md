# Release 0.2.3: scope

Status: draft; scope started by the owner on 2026-11-09; nothing is built.

## Scope (owner decisions, 2026-11-09)

| # | Package | What it covers |
| --- | --- | --- |
| 1 | Pause | The new user-run skill fnl-pause, with the friendly alias fnl-gtg: drain running work, write handovers, and report what recorded work remains before a restart or shutdown (the user decides), with `--in <minutes>` and a `heavy_run.py` refusal while paused. Spec: `pause.md`. |
| 2 | Away skill rename | fnl-afk becomes the main friendly name of the away skill and fnl-brb stays as its alias; the autopilot spec, skills, README and setup text change together. |

## Carried from earlier releases

The unresolved notes of the 0.2.2 reviews: the 201-candidate arm of the `heavy_run` test can be masked by a fake `ps` that exits with an error (a note on pull request 201). The owner can add more.

## Left out so far

Everything listed under "Left out of 0.2.2" in `release-0.2.2.md` stays out until the owner pulls it in.

## Release steps

Follow `fnl-versioning`: a release pull request that drops `-dev` and dates the changelog, the tag after CI on that commit, a bump to the next `-dev`, a GitHub release, then the catalog pin and a Codex refresh, each with the owner's go.
