# Release 0.2.3: scope

Status: draft; scope started by the owner on 2026-11-09; nothing is built.

## Scope (owner decisions, 2026-11-09)

| # | Package | What it covers |
| --- | --- | --- |
| 1 | Pause | The new user-run skill fnl-pause, with the friendly alias fnl-gtg: drain running work, write handovers, and report what recorded work remains before a restart or shutdown (the user decides), with `--in <minutes>` and a `heavy_run.py` refusal while paused. Spec: `pause.md`. |
| 2 | Away skill rename | fnl-afk becomes the main friendly name of the away skill and fnl-brb stays as its alias; the autopilot spec, skills, README and setup text change together. |
| 3 | Assignment matrix | One `## Assignment matrix` section in the host config replacing `## Agent roles` and `## Agent levels`, with levels, types of work, model and roles per agent, a migration, dual readers for roles and judge, one `show` table and one setup pass in `/fnl-setup add delegation`. Spec: `assignment-matrix.md`. |

## Added to the scope (owner, 2026-11-09)

| # | Package | What it covers |
| --- | --- | --- |
| 5 | Away decisions | A decision ladder for the away mandate (recorded rule, Jev, the named advisor, park), the record of who decided, and a lease line at session start. Spec: `away-decisions.md`. |
| 6 | Help skill rename | fnl-help becomes the main name of the plugin help skill and `fnl-ask` stays as its alias. Spec: `away-decisions.md`. |

## Carried from earlier releases

The unresolved notes of the 0.2.2 reviews: the 201-candidate arm of the `heavy_run` test can be masked by a fake `ps` that exits with an error (a note on pull request 201). The owner can add more.

## Left out so far

Everything listed under "Left out of 0.2.2" in `release-0.2.2.md` stays out until the owner pulls it in.

## Release steps

Follow `fnl-versioning`: a release pull request that drops `-dev` and dates the changelog, the tag after CI on that commit, a bump to the next `-dev`, a GitHub release, then the catalog pin and a Codex refresh, each with the owner's go.
