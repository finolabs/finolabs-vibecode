# Release 0.2.3: scope

Status: draft; scope started by the owner on 2026-11-09; nothing is built.

## Scope (owner decisions, 2026-11-09)

| # | Package | What it covers |
| --- | --- | --- |
| 1 | Pause | The new user-run skill fnl-pause, with the friendly alias fnl-gtg: drain running work, write handovers, and report what recorded work remains before a restart or shutdown (the user decides), with `--in <minutes>` and a `heavy_run.py` refusal while paused. Spec: `pause.md`. |
| 2 | Away skill rename | fnl-afk becomes the main friendly name of the away skill and fnl-brb stays as its alias; the autopilot spec, skills, README and setup text change together. |
| 3 | Assignment matrix | One `## Assignment matrix` section in the host config replacing `## Agent roles` and `## Agent levels`, with levels, types of work, model and roles per agent, a migration, dual readers for roles and judge, one `show` table and one setup pass in `/fnl-setup add delegation`. Spec: `assignment-matrix.md`. |
| 4 | Run names | `ledger.py start` prints the run's name on stderr, ready to copy into the host's name field, and the delegate guidance says so, after 8% of 1,555 background runs measured on 2026-11-09 used the documented form. Advisory: nothing renames a call. |

## Added to the scope (owner, 2026-11-09)

| # | Package | What it covers |
| --- | --- | --- |
| 5 | Away decisions | A decision ladder for the away mandate (recorded rule, Jev, the named advisor, park), the record of who decided, and a lease line at session start. Spec: `away-decisions.md`. |
| 6 | Help skill rename and refresh | fnl-help becomes the main name of the plugin help skill and `fnl-ask` stays as its alias. Its map catches up with what shipped (three scripts and three setup features are missing, the script count is stale, and no route answers "which agent takes which work"), and a test fails when a script or setup feature is missing from the map, so it cannot drift again. Spec: `away-decisions.md`. |

## Added from usage data (owner, 2026-11-09)

Measured on the owner's machine over nine days of ledger and usage events (796 dispatches, 5,855 events, six projects) and the last 59 reviewed pull requests. Each row names the number that justifies it.

| # | Package | Evidence | What it covers |
| --- | --- | --- | --- |
| 7 | Log scan false positives | Of 728 finished runs only 13 scanned clean; 316 `not_scanned`, 87 `findings`; 342 of 607 acceptances used `--accept-unverified`. The `named_token` pattern fires on ordinary JSON such as `credential_expires_at` and usage fields in every headless log, and the log folder's mode is refused when not 0700. | Stop the false positives and report a too-open log folder clearly. Acceptance: scanner precision and folder handling only. Fewer `--accept-unverified` also needs a passing verification receipt at the current head (`ledger.py`), which this package leaves unchanged and does not promise to reduce. |
| 8 | Test selection from the diff | 12 of the last 100 CI runs failed; four test modules were missed by hand-picked targeted runs in one day. | A command that maps changed files to the test modules that read them, within the two-module batching rule. |
| 9 | One source for skill counts | The count is written by hand in twelve files and broke CI twice in one day. | Remove the number where it is not needed; check or generate the rest from the folder. |
| 10 | Stale ledger records | 68 open records, 31 older than 24 hours, which keep the pause verdict at `blocked`. | A previewed command that lists records past their budget whose log shows how they ended, and closes them after a yes. |
| 11 | Router coverage | 43 of 133 hand-started sessions with a file edit (32%) recorded a router receipt. | A one-line reminder at the first edit of a session with no receipt; it never blocks. Enforcer: `scripts/metrics_hook.py` on the hosts whose edit events it already reads; off with metrics off, because "no receipt" is unknowable then; unsupported hosts stay advisory. |
| 12 | Usage blind spot | User-typed skills record no event (`fnl-setup`, `fnl-status`, `fnl-ask` show zero despite use); `fnl-verification`, which is model-invoked, also shows zero. | Record user-invoked skills through `scripts/metrics_hook.py` under the existing consent, then check whether `fnl-verification` is loaded at all; a host that exposes no such event stays unmeasured and says so. |
| 13 | Review gate size | `fnl-review-gate` is 18 KB, the largest skill, loaded 38 times in nine days. | Move detail into references, within the 10,000-byte skill limit. |
| 14 | Diagrams and documents | The owner asked on 2026-11-09 for flow and sequence diagrams of how the agents work together, and for the existing diagrams, README and docs to catch up with this release. | A sequence diagram of one delegated task through coordinator, implementer and reviewers, and one of an away decision; the existing architecture diagrams, README and setup docs updated. Done last, from the merged behavior. The same pull request adds the rule to the plugin: `fnl-versioning` requires this review before a release is proposed, and `fnl-open-source-review` checks that diagrams, README, docs and in-product help match what ships (both advisory, agent judgment). |

## Carried from earlier releases

The unresolved notes of the 0.2.2 reviews: the 201-candidate arm of the `heavy_run` test can be masked by a fake `ps` that exits with an error (a note on pull request 201). The owner can add more.

## Left out so far

Everything listed under "Left out of 0.2.2" in `release-0.2.2.md` stays out until the owner pulls it in.

## Release steps

Follow `fnl-versioning`: a release pull request that drops `-dev` and dates the changelog, the tag after CI on that commit, a bump to the next `-dev`, a GitHub release, then the catalog pin and a Codex refresh, each with the owner's go.
