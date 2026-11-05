# Release 0.1.8: spec and plan

Status: scope and plan settled by the owner on 2026-11-05 (the open decisions are recorded under "Decisions settled"). Merged: packages 1 (pull request 58) and 9 (pull request 63). In review: 2 (61), 3 (62), 5 (60) and 10 (64). Not started: 4, 6, 7, 8 and the native sweep follow-up. Release 0.1.7 is tagged; `main` is `0.1.8-dev`.

## Why

0.1.7 shipped the bricks-plus-guideline structure, delegation mode and routing among agents present. Its reviews and the first week of use left three kinds of debt:

1. **Hardening.** The scan and the reference check have known weaknesses (below) that a hostile or merely odd machine can hit.
2. **Rules that nothing enforces.** Compaction, the `auto` mode and "save before the agent edits" are stated as advice. Each needs either a host mechanism or an honest advisory label, and the owner wants real mechanisms where a host offers one.
3. **Newcomer experience.** A first result in about ten minutes, with a way back if the agent goes wrong.

## Scope

In, by package (Plan below gives order and dependencies):

| # | Package | Kind |
| --- | --- | --- |
| 1 | Native question form for every skill that asks the user | merged (pull request 58) |
| 2 | Scan hardening | fix |
| 3 | Reference check and CI fixes | fix |
| 4 | Eval stability | fix |
| 5 | Release checklist: catalog pin step | fix |
| 6 | Compaction: advisory, host thresholds, `PreCompact` reminder | feature |
| 7 | `auto` blocking gate | feature, policy change |
| 8 | Restore point and "try it now" demo | feature |
| 9 | Decisions asked, not listed | merged (pull request 63) |
| 10 | Name every background run by its runner and what it does | feature |

Out of 0.1.8, recorded so it is not lost: **multiple accounts** per host (needs each host's real support and a second account to verify; the open points are what each host supports, how quota fallback picks an account since quota is per account, where account facts live (host config, never skill bodies), and that any metrics field stays metadata with no identity and goes through `SCHEMA` and `PRIVACY.md`). A research spike may start it later; it is not scheduled.

Every rule a package adds names its enforcer (host setting, hook, review gate or agent judgment). A rule that needs monitoring and has no host mechanism is marked advisory.

## Package 1: native question form

Merged (pull request 58). Skills ask through the host's native question tool when the session has one (`AskUserQuestion` on Claude Code, `request_user_input` on Codex, `ask_question` on Antigravity); text is the fallback. Approvals use neutral Yes and No choices and never count a default or timeout.

Open LOW findings from the last security review, carried into package 2's pass: the "neutral Yes and No, no default counts" clause appears only in the setup `interview.md`; add it to `fnl-scan-agents` step 3, `fnl-set-mode` step 2 and the `fnl-delegate` suggest offer, with a grep test, and drop "recommended answer first" from approval questions in both `plain-language.md` copies.

Still asking in text after the merge: the `fnl-setup` beginner-path and mode questions, `references/check.md`, `fnl-update` and `fnl-status`. The owner chose to sweep them: a follow-up to package 2 moves them to the native form and updates the CHANGELOG line that lists the covered skills. No eval can exercise the native path (the parity evals allow no question tool), so verification stays manual per host.

## Package 2: scan hardening

`skills/fnl-scan-agents/scripts/agent_scan.py` and its skill.

- Allowlist the version format before it is stored: `^[0-9A-Za-z.+_ ()-]{1,80}$` after the existing control-character strip; anything else becomes `unverified`. Planted binary text must not persist in `host.md`.
- `--yes` requires a digest of the previewed section (`--digest <sha256 prefix>` printed by the preview); a mismatch writes nothing.
- Ignore empty and relative `PATH` entries; cap captured output at 200 characters and 4 KiB read; catch non-POSIX errors (`OSError` families) and report `unverified`.
- `replace_section`: ignore headings inside code fences; require a blank line before a section it appends.
- Rows carry the check date, so "no difference" would hold only on the same day: compare without the date column and keep the stored date only while it is at most seven days old. An older date is refreshed as a date-only difference the user confirms, so the 30-day staleness clock of `fnl-delegate` and `checkup.py` keeps running.
- `PRIVACY.md`: say the script itself uses no network, and that the three fixed executables are run by the script, not by the shell.

Acceptance: one unit test per bullet with synthetic executables and fixtures; the existing scan tests stay green; a second run within a week with nothing else changed reports no difference and writes nothing, and a run after a week shows a date-only difference. Enforcer: the script (tests).

## Package 3: reference check and CI

`scripts/check-references.py`, `tests/`, `.github/workflows/validate.yml`.

- Retired skill names are allowed inside released `CHANGELOG.md` sections (the rule rewrote 0.1.4 to 0.1.6 history); they stay forbidden in `Unreleased` outside the mapping and everywhere else.
- List files with `git ls-files`, not the filesystem, so a git-ignored local file cannot fail the check.
- Remove the stray `$ARGUMENTS` line in `skills/fnl-advisor/references/committee.md`.
- Catalog standard in CI: the plugin description is 120 to 160 characters and identical in the three manifests. `tests/test_manifests.py` already pins it; confirm CI runs it (it runs `unittest discover`) and add a named step only if the test is not reached.

Acceptance: tests for each rule; the check passes in a checkout that has an untracked local context file naming a retired skill. Enforcer: CI.

## Package 4: eval stability

`evals/trigger-fnl-handoff` passes about 60 percent on both the old and the new tree; `quality-fnl-ask-looping` wobbles on `main` too.

- Read the failing answers first; fix the case (prompt, grader) when the answers read correct, fix the skill description only when they do not.
- Judges that count a quoted wrong offer as an offer cause false failures: apply the reason-judge wording already used in `quality-fnl-delegate-keep-own-kind` to the other delegate cases.
- Done when each case holds at least 5 of 6 on `main` over two runs of six. Report the numbers; a case that stays flaky is marked so in its README line, not silently kept.

Enforcer: the eval suite, run by the coordinator (it costs quota and is not in CI).

## Package 5: release checklist, catalog pin

`skills/fnl-versioning` gains a release step: after the tag and the GitHub release, open a pull request in the catalog repository that moves `ref` to the new tag and syncs name, description and keywords with the default-branch manifests (the catalog's own check compares them against the raw default-branch files, which lag a few minutes). The step is advisory (agent judgment); the catalog's CI is the enforcer for the content. This repository names the catalog generically; its URL lives in the release procedure, not in the skill body.

Acceptance: the step appears in `fnl-versioning` and in the release procedure used for 0.1.8, and the 0.1.8 catalog pull request is opened from it.

## Package 6: compaction

Problem: `fnl-session-hygiene` says to compact at about 60 percent of the context, but an agent cannot see its own percentage and nothing monitors it.

- **Who enforces what**, stated in the skill: the host compacts at its own threshold (a host setting); the skill adds only what the host cannot know: write back decisions before a compaction.
- **Setup suggests the host's native threshold** after a yes, as a shared-setting change: Claude Code `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` and `CLAUDE_CODE_AUTO_COMPACT_WINDOW`; Codex `model_auto_compact_token_limit` and `model_post_turn_compact_threshold_percent`; Antigravity none found. These names come from the hosts' binaries and are unverified in behavior: verify each on the installed version before the skill states a value.
- **`PreCompact` hook** (Claude Code and Codex declare it; Antigravity does not): a non-blocking reminder to write back decisions and the next action. It prints text only, exits 0 and fails closed. Delivery of that text to the model is unverified on every host: prove it with a real compaction before the skill relies on it.
- `checkup.py` reports whether the hook is declared (it already marks `PreCompact` optional) and says "delivery unverified".

Acceptance: skill text names each enforcer; the hook has a unit test (exit 0 on any input, no network, no paths in output); `setup` writes a threshold only after a yes. Data: no new field, no metrics.

## Package 7: `auto` blocking gate

Today `auto` is advice: agent judgment, "never 100 percent". The owner wants a mechanism where a host has one.

Evidence from one small test per host (04/11, temp folders): Claude Code `Stop` can force continuation and `PreToolUse` can block `Write` until a decision file exists; Antigravity `Stop` forced continuation with `decision: block` though its docs name only `continue`, and `PreToolUse` deny blocked the write; Codex hooks did not fire in the test (trust unsettled), so unverified.

**Policy change.** `CLAUDE.md` says a hook never blocks a session. This package needs a scoped exception, owner-approved in the committed `CLAUDE.md` through the review gate: a hook may block only when all hold: Delegation mode is `auto`, the user opted into the gate in setup, and the block is a single, named tool call (a write or a hand-off dispatch) that lacks a recorded decision. Every other path, and every error, exits 0 and allows (fail open). The gate never blocks a session start, a stop or a read.

Design to settle before code (a short design note in this spec, reviewed first):

- What decision the gate checks (settled): a ledger `start` line for the task (always written), or a keep decision. A keep receipt writes nothing when usage metrics are off (`keep-receipt.md`), so with the gate opted in the keep step also writes a small local decision file under the state folder, independent of metrics; the gate reads that file, never the metrics store.
- The decision file's location under `~/.finolabs/vibecode/state/` and its lifetime (per session).
- How the user turns it off at once (`FNL_AUTO_GATE=off`) and how a blocked agent is told why in one line.

Hosts: Claude Code and Antigravity first; Codex stays unverified until a trusted hook fires in a real session.

Acceptance: a unit test per branch (mode not `auto`, no opt-in, decision present, decision missing, malformed state, hook error), each exiting 0 except the one named block; a real-session check per host that the block fires and that turning the gate off removes it. Security review is mandatory (permission boundary). The gate is not counted in usage metrics (settled): no new event field.

## Package 8: restore point and "try it now" demo

**Restore point** ("save before the AI edits").

- A new user-invoked restore-point skill (name settled when it is built), in git repositories only: it records the working tree as a commit object on a private ref (`refs/finolabs/restore/<timestamp>`) without touching the index, the branch or the working tree, never pushes, and lists restore points. Restoring shows the difference first and writes only after a clear yes.
- User-invoked only (settled): an automatic snapshot before the first edit would write into the user's repository without a request, so there is no hook.
- Outside git: say that it cannot help and name `git init` as the user's step. Nothing is installed or created.
- Enforcer: the script (symlink refusal, preview before write, no network); the user's yes for a restore.

**"Try it now" demo.** `fnl-ask` Start mode offers, once, a guided first result in a new empty folder the user names (never inside an existing repository): the agent builds one tiny thing from the user's own idea with the pack's gates in plain words, then shows how to continue. Done when a newcomer reaches a working result in about ten minutes with no internal word.

Acceptance: tests for the restore script on a synthetic repository (create, list, restore with and without a clean tree, symlinked path refused); the demo is evaluated with the persona study rerun on the final README and `fnl-ask`, reporting clarity, first-step and non-technical-fit scores against the 0.1.7 baseline. Persona runs are model role-play, not real users, and say so.

## Package 9: decisions asked, not listed

When a spec or a plan has decisions the user can settle, the agent asks them through the host's native question tool (text when there is none) instead of writing them as an "Open decisions" list for the user to answer later. Answers go into the document as settled decisions with the date; only a decision the user cannot make yet (it needs evidence, another person or a later step) stays listed, with its owner and what unblocks it.

Where it lives: `fnl-coding-router`, as one line in "Work, then gate" ("These hold on every path"), because the router is loaded at every coding entry and every workflow path (Spec Kit, a workflow pack, none) writes specs and plans. Not `fnl-setup-instructions`: that skill writes the user's contract once and is not loaded while a spec is written. The rule is advisory (agent judgment); a run with nobody to answer (delegated or headless) records the decisions as open and never invents an answer. Each Spec Kit, pack and none adapter keeps its own clarify step; this rule only says that the unsettled ones are asked, not listed.

Acceptance: the router line exists and names its enforcer; a unit test checks the line is in `skills/fnl-coding-router/SKILL.md`; this spec is the first case (its decisions were asked, not listed).

## Package 10: run names

Problem: when an agent starts a background task (a headless Codex or Antigravity run) or a reviewer or other subagent, the user cannot tell which agent is running or what it is doing.

Rule, in `fnl-session-hygiene` "Titles" with a per-host paragraph in `references/titles.md`: every background run or agent gets, at the moment it starts, the label `<runner>: <project> <scope> <activity>`, where the runner is the agent family with a short model name (`codex sol`, `agy flash`, `claude sonnet`) or, for a reviewer or subagent, its role (`code review`, `sec review`). The same label goes in the host's name or description field, the ledger task, the log file names and the dispatch line. `fnl-delegate`, `fnl-review-gate` and `fnl-handoff` point to it. Advisory (agent judgment); no hook renames a tool call. Not in the user contract: the rule needs per-host fields and the contract is loaded every turn.

Acceptance: a unit test pins the rule and its enforcer in `fnl-session-hygiene` and the pointers in the three skills.

## Plan

Writers: one writer and one worktree per package; coordinator merges. Effort `medium` except package 7's design and package 8's restore design (`high`). Every pull request gets a posted code review and security review (`fnl-review-gate`); packages 3 and 5 touch only documents and the checker and may take the low-risk lane only where `merge_check.py --lane` says so (the checker script is not a lane path, so package 3 goes to both reviewers).

| Step | Packages | Depends on | Files at risk of overlap |
| --- | --- | --- | --- |
| 0 | 1 and 9 merged (done) | none | none |
| 1 | 2, 3, 5 in parallel (2 merged) | 0 | `CHANGELOG.md` `Unreleased` only; resolve at merge |
| 2 | 4 | 1 (evals read the merged skills) | `evals/` |
| 3 | 10 (run names), then the native sweep follow-up to 2 | 0, 1 | `skills/fnl-session-hygiene` (titles), `fnl-delegate`, `fnl-review-gate`, `fnl-handoff`; the skills named in the sweep |
| 4 | 6 | 3 (both edit `fnl-session-hygiene`) | `skills/fnl-session-hygiene`, `skills/fnl-setup`, `.claude-plugin`/`.codex-plugin` hooks |
| 5 | 7 design note, then code | 4 (both touch the hooks) | hooks, `CLAUDE.md`, `fnl-delegate` |
| 6 | 8 restore point, then demo | 0 | new skill folder, `fnl-ask`, README, file tree |
| 7 | Release 0.1.8 | all merged, full suite and evals run once | manifests, CHANGELOG |

Release 0.1.8 follows `fnl-versioning`: a release pull request (manifest versions and CHANGELOG), an annotated tag after CI, a GitHub release, the catalog pin pull request (package 5), then the bump to `0.1.9-dev`. Pushes, merges, the catalog pull request and the release each need the owner's go.

Budget guide (`fnl-delegate`): packages 2, 3, 5: medium, 30 to 45 minutes each; 9 and 10: easy, written by the coordinator; 4: medium, 45 minutes plus the owner's quota for eval reruns; 6: hard, 60 minutes; 7: very hard, a session; 8: hard for the restore script, medium for the demo.

## Risks

- Package 7 moves a published rule. Without the exception reviewed and merged first, no code lands.
- Packages 6 and 7 depend on hook delivery that is unverified on Codex and Antigravity; they ship as advisory there and say so.
- Eval judges are noisy; a number near 0.5 to 0.75 is not a verdict until the answers are read.
- `CHANGELOG.md` `Unreleased` is touched by every package: merge in order and resolve once.

## Decisions settled

Asked of the owner through the native question form on 2026-11-05; each took the recommended answer.

1. **Release number:** `0.1.8` (pre-1.0, same practice as 0.1.7; `1.0.0` stays the owner's call).
2. **Restore point trigger:** user-invoked only; no automatic snapshot.
3. **`auto` gate:** a recorded decision is a ledger `start` line or a keep receipt; blocks are not counted in usage metrics.
4. **Native form sweep:** the remaining text questions move to the native form (follow-up to package 2).
5. **Package 10 (run names):** added at the owner's go on 2026-11-05, after a proposal that the rule live in `fnl-session-hygiene` "Titles" and not in the user contract.

## Verification and limits

Not verified anywhere yet: the native form on Codex and Antigravity; the `PreCompact` reminder reaching a model; the `auto` gate on Codex; Safari, Firefox and Windows for the dashboard (unchanged from 0.1.7). Each package states what it verified on which host; a claim about a host that was not exercised says so.
