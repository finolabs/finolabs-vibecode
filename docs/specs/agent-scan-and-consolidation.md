# Agent scan, mode command and skill consolidation

Status: implemented for 0.1.7 (Parts A–E). Verified with local Python tests and plugin validation on macOS from a Codex coordinator; PATH, consent, section preservation and symlink cases use synthetic fixtures. Live slash-command execution on Claude Code, Codex and Antigravity and behavior eval results remain unverified; the coordinator runs the supplied eval cases. `codex --help` exposes no offline model-list command; `agy --help` advertises `models`, whose offline behavior is unverified and is not used by the scan.
Owner decisions: 2026-11-04. All of it ships in 0.1.7 (a large upgrade); the manifest version does not change.

## Why

1. Delegation assumes Claude Code, Codex and Antigravity are all present and that the model lineup in `models.md` is current. Neither holds: users run one, two or three of them, and lineups change every few weeks. Nothing on the machine is detected today and nothing refreshes the host config.
2. A coordinator asked for approval to start a session of its own family (fixed in PR #53). Its own family must come from detection, not from the coordinator's guess.
3. Before consolidation the plugin had 20 skills and 15 model-visible descriptions (5 user-only skills). Package 1 leaves 17 folders and 12 model-visible descriptions. Several skills were small and overlapped. Fewer descriptions means a clearer choice for users and agents.

## Part A: agent scan (fnl-scan-agents)

A user-invoked skill (`disable-model-invocation: true`, `argument-hint: "[--host claude|codex|antigravity]"`). Host support for slash commands: skills are the supported form on Claude Code (the `commands/` folder is the older format); on Codex and Antigravity the same skill is listed with a description that says to run it only on request. No `commands/` folder is added.

**Script** `skills/fnl-scan-agents/scripts/agent_scan.py`: stdlib only, read-only by default, no network, exit 0, output at most about 40 lines.

- For each of the three fixed executables (`claude`, `codex`, `agy`): is it on `PATH` (`shutil.which`), and its version from `<exe> --version` run without a shell, a three-second timeout, output cut to 200 characters and treated as untrusted text. Nothing else is executed.
- The running host is given by the caller (`--host`), never guessed from environment variables. The skill knows which host it runs in. The host's family is the coordinator's **own kind**: the single definition used by `fnl-delegate`.
- Models and effort are not probed: a probe costs quota. The script records the models the user last confirmed in `host.md`, and the skill asks the user to confirm each present agent's allowed models against the tier table. Where a CLI offers an offline model listing, the implementer records that finding in the PR and the script may use it; otherwise the row stays `unverified`.
- Anything not visible from the machine is `unverified`, never a guess.

**Host config section** `## Agents on this machine`, written into `~/.finolabs/vibecode/host.md` (never into the plugin):

| Agent | Present | Version | Allowed models (confirmed by user) | Checked |
| --- | --- | --- | --- | --- |

fnl-scan-agents shows the difference against the current section and writes only after a clear yes. It writes only this section, atomically, refuses a symlinked path component (as `mode.py` does) and keeps every other section byte for byte. `Coordinators and reach` stays user-confirmed, but is prefilled: present agents other than the coordinator's own kind.

**Routing uses it.** `fnl-delegate` routes only among agents recorded present. With no other family present, delegation is off: the coordinator says so in one line and works itself or with sessions of its own kind. When the section is missing, behavior is as before and the coordinator suggests `/fnl-scan-agents`. A section older than 30 days is stale: say so once per session.

**Onboarding.** `fnl-setup` section A names fnl-scan-agents as a dependency and runs its procedure instead of asking which agents exist. `checkup.py` (Check mode) reports a missing or stale section, and any reference in the user's context files to a skill name removed by Part C, as findings.

**Data boundary.** Local only: three fixed `--version` calls and a read of `host.md`. No network, no telemetry, nothing stored outside `host.md`. `PRIVACY.md` gets one sentence. A new `SCHEMA` field is not needed.

## Part B: mode command (fnl-set-mode)

User-invoked skill, `argument-hint: "[manual|suggest|auto] [routing on|off]"`. No arguments shows the effective Delegation mode and Routing, each with its source (environment variable, host config, default). When an environment variable overrides the file, it says writing the file will not take effect. A change shows the old and new value and writes only after a clear yes, through `mode.py` extended with a `set` action (atomic, symlink refusal, only the two headings touched). `mode.py` has one more byte-identical copy in the new skill; the CI copy check lists it.

## Part C: consolidation

Package 1 reduces 20 skills to 17 folders (model-visible 15 → 12, five user-only skills unchanged). Package 2 adds two user-only skills, for 19 folders (12 model-visible, seven user-only).

| Change | Result |
| --- | --- |
| Committee procedure into `fnl-advisor` | One skill, two procedures: one second opinion, or a committee of two contrasting families. The committee procedure moves to `references/committee.md`, loaded only for it. The description carries both triggers. |
| Coordinator-session procedure into `fnl-delegate` | Becomes `references/coordinator-sessions.md`. The delegate description gains the case "run a spec as a coordinator with one session per task". |
| Knowledge procedure into `fnl-session-hygiene` | Where decisions, lessons and project state go becomes `references/knowledge.md`, loaded when the user says to remember or recall something. The hygiene description gains those triggers. Handover content stays in session-hygiene as the one home; `fnl-handoff`'s save-a-handover mode points to it. `fnl-delegate`'s "Handover after an interrupted run" is about checkout state and stays. |

No alias skills are kept: an alias is another description. The changelog lists old name to new home. Updated everywhere they appear: README, `fnl-ask` map and contents, `contract-template.md`, `fnl-setup`, `check-references.py` and its test, status fixtures, trigger evals (renamed to expect the surviving skill).

Out of scope: moving `fnl-review-gate` "Pull requests" into a reference. It is the gate in use and other documents cite it by section name; a text move is not worth the risk in this release.

## Part D: the six follow-ups from the PR 53 reviews

1. `fnl-delegate` "Delegation mode": say "a session or headless run of your own kind", not "or subagent" (subagents never own implementation, `agents.md`).
2. Under `manual`: an own-kind session starts without an offer only when the project requires it or your context needs sparing, and you say so in one line.
3. Own kind means "the family recorded as the coordinator's in `Agents on this machine`, else the family of the host that runs you". Other families still require recorded presence to route to them.
4. An own-kind session stays a delegate for the Never delegated list: it gains none of the coordinator's authority.
5. The project's rules still decide whether own-kind sessions are allowed.
6. The `verdict` grader of `quality-fnl-delegate-keep-own-kind` must fail when the reply offers Codex as the hand-off target, instead of only matching "worktree".

## Part E: one consistent story across every guide

Every surface that tells a person or an agent what the plugin contains or how to start must say the same thing after each package, not only after the last one. For package 1, a surface matches the 17 surviving folders and the existing Delegation mode and Routing settings. Package 2 adds the two new commands and the agent-scan setting below; only then do the guides describe those as available.

| Surface | What changes |
| --- | --- |
| `README.md` | skill count and lists, the "What you hand over" block, the bricks section (three settings: Delegation mode, Routing, agents), commands table with `/fnl-scan-agents` and `/fnl-set-mode`, the file tree, install and first-run steps |
| `fnl-ask` (`SKILL.md`, `references/map.md`, `explain.md`, `contents.md`) | map, per-skill explanations, "which skill fits" answers, the list of typed commands |
| `fnl-setup` (`SKILL.md`, `references/check.md`, `companions.md`) | section A runs the scan; Check mode reports the new findings; the first-run order |
| `fnl-setup-instructions` (`SKILL.md`, `references/hosts.md`, `contract-template.md`) | skill pointers written into user contracts use only surviving names |
| `fnl-delegate` (`SKILL.md`, `references/host-template.md`, `models.md`, `agents.md`) | the new section, present-agents routing, tier table as seed data only, own kind defined once |
| `fnl-status`, `fnl-update` | any skill list or command mention |
| `rules/AGENTS.md` and `scripts/session_start.py` | the session-start text names only surviving skills and the new commands where it names any |
| Manifests (all three) | `longDescription` and `defaultPrompt` entries that name removed skills |
| `CONTRIBUTING.md`, `PRIVACY.md`, `CHANGELOG.md`, `docs/specs/` | removed names, the scan's data boundary, the mapping from old to new names |
| `evals/` and `tests/fixtures/` | renamed or removed cases and fixtures |

**Mechanical check, not memory.** `scripts/check-references.py` gains one rule with a unit test: every skill folder is listed in the `README.md` skill list and in `fnl-ask` `references/map.md`, and each of those lists names no skill that has no folder. A removed name found in any tracked file outside dated changelog releases and the Unreleased migration mapping fails the check. The two packages each leave this check green; package 2 does not inherit a red check from package 1.

## Acceptance

Package 1 covers consolidation; package 2 adds scan, mode settings, inventory-aware routing and onboarding. Automated script checks use fake CLIs and host files; routing behavior cases are supplied for the coordinator to run.

- fnl-scan-agents on a machine with only two of the three CLIs records exactly those two, marks the rest absent, writes nothing without a yes, and a second run with no change reports no difference.
- With one family present, `fnl-delegate` offers no hand-off and says why; with two, an offer names only the other family.
- fnl-set-mode changes only the two headings, reports an environment override, and never writes without a yes.
- No removed skill name remains in the repository except in the changelog mapping; `check-references.py`, the unit tests, `claude plugin validate .` and the evals (trigger cases renamed, new cases below) pass.
- New eval cases: a Claude Code coordinator with only Claude Code and Codex present never offers Antigravity; no other family present states delegation is off and continues itself; an environment override wins over mode file changes. The existing own-kind case remains.

## Delivery

Two packages, one writer each, in order (they touch the same files): package 1 is Parts C and D plus the applicable Part E surfaces; package 2 is Parts A and B and the remaining Part E updates on top of it. Each takes both reviews before merge.
