# Release 0.2.0: scope and evidence

Status: implemented; release documentation prepared for 2026-11-08 on the release branch; package code is merged, with incomplete mechanisms and live-host limits recorded below. Tagging, publication and installation are separate owner-authorized steps and are not established by this record.

## Why

0.1.10 made running work visible. This release connects that view to the user's outcome: who reviews,
how the coordinator checks a delegate's work, when to reconsider direction and what evidence survives
between sessions. Setup becomes shorter without turning a default, timeout or broad request into consent.
The release also reduces credential exposure in headless runs and makes host guarantees explicit.

The public change is breaking in phase 0: standalone setup commands and two agent wrappers are removed.
The owner selected 0.2.0 instead of the planned 0.1.11. The [changelog](../../CHANGELOG.md#020---2026-11-08)
is the user-facing release note; this record maps its scope to merged packages and evidence.

## Scope by package

The unit here is a merged pull request, found with `git log --merges --oneline v0.1.10..HEAD`.
Local branch-sync merges are excluded. Numbers identify pull requests in
[finolabs/finolabs-vibecode](https://github.com/finolabs/finolabs-vibecode/pulls).
A merged design records intent; it does not establish that every mechanism was implemented.

| # | Package | Delivered by merged pull requests | Status |
| --- | --- | --- | --- |
| 1 | Release baseline | #130 started the 0.1.11 development cycle; #143 selected 0.2.0 for the breaking removals and retargeted the work. | implemented; release preparation only, not evidence of a published tag. |
| 2 | Work tracking | #131 and #132 defined per-repository settings and a one-file work record; #133 added project pipelines; #136 implemented bounded readers, work-record states, drift checks and settings; #137 connected setup and workflow guidance. | implemented; see [work-tracking.md](work-tracking.md) and [project-progress.md](project-progress.md); local reader evidence, live delivery unverified. |
| 3 | Status board | #134 exposed recent session activity and cached quota pools; #139 pinned a fixture clock; #160 added repository names, quota model labels and readable local times; #164 enabled page scrolling and repository-scoped status replies. | implemented; activity is advisory, not proof of process liveness. |
| 4 | Spec status | #135 normalized status vocabulary, removed duplicate index rows and aligned the release record with the parser. | implemented; checked by the spec-status module. |
| 5 | Quota on demand | #138 settled the design; #141 replaced periodic workers with bounded on-demand reads, added the Claude Code rate-limit marker and the narrow Homebrew executable exception. | implemented; see [quota-on-demand.md](quota-on-demand.md); live provider readings and StopFailure delivery unverified. |
| 6 | Roles and review posting | #140 and #142 settled roles, retirement and enforcement decisions; #147 added local role parsing, review routing, reviewer packets and guarded posting; #156 corrected trusted Homebrew gh checks. | implemented; live routing/posting remain unverified and relay accounting is not built as described in [agent-roles.md](agent-roles.md). |
| 7 | Matrix and merge check | #145 added deterministic task routing, local SessionStart state and the base-pinned router-marker check in the merge helper. | implemented; the coordinator still selects allowed models and decides authority. |
| 8 | Navigator | #146 added the read-only navigator agent and bounded anchor/evidence collector with screened payloads and report checks. | implemented; independent behavioral validation remains open. |
| 9 | Verification and judge | #150 recorded the scoped TypeSafe network exception and privacy terms; #149 implemented current-head receipts, ledger acceptance checks, host/Jev judgments and bounded failure handling. | implemented; judge output informs the coordinator and never grants acceptance. |
| 10 | Setup core and modes | #144 specified the restructure; #148 consolidated scan, mode and instructions into setup with guarded writers and declined-feature records; #151 settled hygiene and companion questions; #152 added Quick/Advanced companion selection; #166 rewrote approvals in plain language. | implemented; see [setup-restructure.md](setup-restructure.md); live interviews and Codex word passing unverified. |
| 11 | Run hygiene | #151 established the design; #153 added brief lint, allowlisted children, guarded log scan/show/redaction and fixed ledger scan states. | implemented; environment-only protection, with private HOME deferred; see [run-hygiene.md](run-hygiene.md). |
| 12 | Context snapshots | #159 added the Claude Code recorder, fresh reads, steward input and previewed status-line writer; #161 extended recording and setup to Antigravity. | implemented; see [context-snapshot.md](context-snapshot.md); live host delivery and user-owned composition unverified. |
| 13 | Parallel pools | #162 added shared total/family parsing and advisory capacity checks, connected to setup, SessionStart and the dashboard. | implemented; see [parallel-instances.md](parallel-instances.md); snapshots do not reserve slots or block ledger starts. |
| 14 | Integration and documentation | #154 updated diagram sources; #155 integrated skills, manifests, maps, copies and tests; #158 regenerated README images; #163 corrected documented host contracts; #165 specified family/model run labels; #167 aligned claims with shipped behavior; #168 refreshed diagrams and their wording. | implemented; diagrams and documentation describe mechanisms, not live-host proof. |

This POLISH package re-cuts the combined release notes, updates the README installation entry and version
wording, defines supported security versions and response targets, clarifies contributor checks/reviews,
adds CODEOWNERS and indexes this record. It changes no runtime, manifest, workflow, skill or asset.
`update` and `restore-point` shipped before 0.2.0 and are not new capabilities in this release.

## Decisions settled

Recorded in the accepted area specs on 2026-11-07:

- The owner chose the phase-0 minor release for incompatible removals and explicitly waived a deprecation
  period for the retired verifier/steward agents and standalone instructions skill; setup also absorbs scan
  and mode. Callers use `verification`, `session-hygiene` and `/setup` subcommands instead.
- Review families are user-assigned; independence is preferred and same-family fallback is disclosed.
  Roles grant no posting authority. Relay remains subject to the existing approval rules; its proposed
  counted fallback has not been built.
- Verification receipts gate delegated work recorded in the ledger. The coordinator's own work remains
  under the review gate, and an explicit unverified-acceptance reason is digested and counted.
- The small host model is the default judge. Jev is optional, needs authorization and budget, and may
  send only bounded English payloads through the scoped exception; unavailable calls require disclosed fallback.
- Quota reads occur on demand with a 15-minute minimum, not from a periodic hook worker. The process
  snapshot and metrics remain separate opt-ins, and the user's quota statement wins over advisory readings.
- Setup uses user/project scopes and a short core with on-demand features. Quick and beginner defaults
  apply only to inert choices; each grant retains its separate neutral approval and preview where required.
- Context counts feed the existing steward; they do not add autonomous compaction. Parallel families are
  pools under user-selected totals and optional family caps, with capacity checks remaining advisory.

The POLISH brief sets the release date to 2026-11-08 and moves the unfinished work below to the 0.2.1
backlog. That scheduling decision supersedes the older 0.2.0 targets, not the design or its open questions.

## Upgrade

1. Update through the host's supported path, then open a new session and run `/setup check` (`$` on Codex).
2. On Codex, inspect `/hooks` trust again because bundle file changes can invalidate trust without new declarations.
3. Review `/setup add delegation` for `## Limits`: totals are 1–32, optional family caps cannot exceed the total,
   and missing/invalid totals fall back to 5. Older parenthetical total lines need replacing through setup.
4. Use `/setup add roles` for roles, posting and judge choices, and `/setup add compaction` for optional
   status-line context recording. Existing status lines receive a composition recipe rather than an overwrite.
5. Replace removed entry points using the changelog's Removed group. Data root and consent do not migrate;
   global ledger/task lines remain readable through 0.2.1, with per-repository replacements required before 0.3.0.

## Verification and evidence

Claims were checked against the current skills, scripts and accepted specs, with merge history used for package
attribution. The authority for actual behavior is code; design-only statements are not shipped guarantees.
This documentation package runs only the following whole modules through `scripts/run_env.py`, using each
module's temporary roots and fixtures:

| Module | Tests | Result | What it establishes for this package |
| --- | --- | --- | --- |
| `tests/test_check_references.py` | 12 | PASS | Reference-checker regressions and current document/skill links and inventories. |
| `tests/test_spec_status.py` | 4 | PASS | Status vocabulary, one row per spec and indexed statuses. |
| `tests/test_setup_limits.py` | 21 | PASS | Setup size, entry, consent and feature contract oracles. |
| `tests/test_run_hygiene.py` | 10 | PASS | Static launch allowlists and documented hygiene boundaries. |
| `tests/test_shared_copies.py` | 2 | PASS | Every workflow copy group exists and matches byte for byte. |
| `tests/test_user_language.py` | 2 | PASS | Advisory language rules and shared plain-language text. |
| `tests/test_manifests.py` | 4 | PASS | Matching host metadata, release surface counts and current setup pointers. |

The reference checker also runs directly with `python3 -I scripts/check-references.py .`, followed by
`git diff --check`: both PASS, with `references ok (121 files)` from the checker. The final combined
module run on 2026-11-08 reports `Ran 55 tests in 54.386s`, `OK`, with no skips.
Run the same explicit set from the checkout root:

```bash
python3 -I scripts/run_env.py -- python3 -I -c '
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path.cwd()))
names = ["test_check_references", "test_spec_status", "test_setup_limits",
         "test_run_hygiene", "test_shared_copies", "test_user_language", "test_manifests"]
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName("tests." + n) for n in names)
result = unittest.TextTestRunner().run(suite)
sys.exit(not result.wasSuccessful())'
```

A separate document audit confirms all 38 merged pull requests are covered, nine Highlights and ordered
changelog groups are present, install commands are copied exactly, and releases through 0.1.10 retain their
original bytes except the approved blank-line removal. The inventory is 17 skills (five user-only Claude
frontmatter declarations), three agent definitions, 37 root helpers and 10 skill-only helpers.
These checks do not execute the whole suite, a live hook, setup against real account files, provider readings,
external judgments, review posting or an update. Earlier area-specific local tests are recorded in their specs;
this package does not reclassify them as live acceptance or rerun their entire runtime coverage.

## Known limits

- **Host delivery:** Live SessionStart/compact order, updated hook trust, setup interviews, posting identity and
  status-line delivery are not proven on each host by local fixtures. Antigravity has no SessionStart summary
  or automatic handover re-injection; Claude desktop Code-tab status-line delivery remains unverified.
- **Context:** Codex has no external JSON status-line command for this recorder, and no Codex app-server reader
  is implemented. Latest-snapshot selection can select another parallel session; a known host session id or
  an explicit unavailable reading is needed. Snapshots remain advisory and same-user forgeable.
- **Antigravity stop:** The first-call meaning of invocationNum 0, interactive stop behavior and availability
  of `/compact` remain unverified. The fixed message still names `/compact`; `/new` or `/fork` are the documented
  alternatives. The byte limit is only a proxy for context, not a token count.
- **Judgment:** The agent-roles spec records small, author-derived measurements, not independent validation of
  the navigator/judge. Quoted evidence proves presence, not entailment; the coordinator must assess it.
- **Run hygiene:** Allowlisted headless forms do not hide HOME files or cover interactive/app sessions or
  in-session subagents. Scanning is a best-effort pattern filter; no findings is not proof of no leak,
  and the final same-user log-redaction race remains.
- **Parallelism and quota:** Slot counts are snapshots without reservations or ledger enforcement. Provider
  reads and Claude StopFailure delivery remain unverified; rate-limit markers are advisory per-family signals.
- **Update network:** The automatic check is on by default, independent of metrics consent, and fetches the
  fixed public GitHub latest-release endpoint; `FNL_UPDATE_CHECK=off` stops it. Codex check/notice delivery and
  Codex/Antigravity update procedures remain unverified; no host update was performed here.
- **Judge network:** Jev calls require canonical opt-in, authorized key/budget and explicit invocation. The script
  caps closed payloads and attempts, screens secrets/paths, verifies TLS, rejects redirects/proxies and reports
  fallback. These are code/local-fixture claims, not evidence of live TypeSafe calls in this release package.
- **Relay:** The posting wrapper exists; relay receipts and dashboard counters do not, so the approved temporary
  fallback remains uncounted. Neither configuration nor a tool's completion establishes a successful post.

## Deferred to 0.2.1

These are backlog targets, not guarantees that 0.2.1 will ship every item. Implementation and unresolved
host decisions still require their own evidence and owner approval.

| Work | Remaining boundary |
| --- | --- |
| [Autopilot](autopilot.md), including live dashboard refresh | Accepted design only; no shipped autopilot skill, lease or live loop. |
| [Merge guard](merge-guard.md) | No shipped permission-rule writer; the existing merge-check helper is a separate review gate. |
| Goal skill (fnl-goal) | No shipped skill folder; outcome anchors are available through work tracking. |
| Multi-account agents | Quota supports labelled Claude installs; dispatch/role routing across multiple accounts is not implemented. |
| Relay receipts and counters | Add the missing metadata receipt and dashboard accounting before claiming counted relay. |
| Private HOME | Establish each family's login-store requirements and an isolation design before implementation. |
| Antigravity stop message | Owner decision needed on the fixed `/compact` wording and documented alternatives. |
| Codex PreCompact declaration | Owner decision needed on retaining a declaration whose plain stdout does not reach the model. |

## Release boundary

The manifests already agree on 0.2.0. This package prepares documentation and a local commit only.
No tag, push, merge, GitHub release, catalog change, installation or post-release 0.2.1-dev bump is performed.
The release owner retains those actions and the live checks above.
