# Agent roles: routed reviews, verification without an agent, and a navigator

Status: in progress; release 0.2.0 scripts and local tests are implemented; relay receipt/dashboard counters remain unimplemented; independent navigator/judge validation and live-host routing, posting and SessionStart delivery remain unverified.

## Why

Before this change, the plugin shipped four agents: `fnl-reviewer`, `fnl-security-reviewer`, `fnl-verifier` and `fnl-steward`. Looking at them
on 2026-11-07 showed four problems:

1. Reviews are not routed. The two reviewer agents are the entry; each runs its own host's review tool. On Claude Code
   that is Claude reviewing Claude's work. A review by another family happens only when the coordinator remembers to
   route it separately through `fnl-delegate`, and the reviewer files carry a second "mini router" that repeats the
   decision. The owner wants the family that codes and the family that reviews to differ (highly recommended, not
   forced) and a flow that is direct and cheap in tokens.
2. `fnl-verifier` mostly runs tests again and compares a diff with a brief. The mechanical part is code; the semantic
   part (does this change meet that criterion) is a bounded judgment over supplied evidence.
3. `fnl-steward` wraps `context_steward.py` (a deterministic table) and one optional Jev question. The agent adds no
   judgment that the script or Jev does not already hold.
4. Nothing watches the course. Over time users and agents drift from the outcome set for the project or a spec;
   reviewers see one diff and nobody sees the trajectory.

## Decisions settled (owner, 2026-11-07)

- Keep `fnl-reviewer` and `fnl-security-reviewer`; the user assigns which agent family plays each role. Route first,
  then call that agent directly; no agent routes for another.
- Retire `fnl-verifier`: a script plus Jev replace it. `ledger.py finish --outcome accepted` is refused when no
  verification receipt exists for the current head, with a logged escape hatch (part E).
- Retire `fnl-steward`: the script stays and its steps move into `fnl-session-hygiene`.
- Add fnl-navigator (hoa tieu): detects drift from the original outcome and proposes up to three ways to steer back.
  A small model builds the input, Jev judges, the navigator reports (part G).
- An agent that cannot post its review reports why; the user sets it up (a narrow token for Codex, a remembered
  allow-rule for Antigravity); a coordinator relay is a counted fallback, not a standing arrangement (part D). This
  removes the need for a standing relay of security reviews.
- Jev is a recommendation, not a requirement. Every semantic judgment goes through one judge interface; when the user
  does not choose Jev at setup, or Jev is unavailable, a small model of the host takes its place (part I).
- Second round (same day): `fnl-verifier`, `fnl-steward` and the skill `fnl-setup-instructions` are removed in the same
  release, without a deprecation period (an explicit owner exception to the "deprecate first" rule of
  `fnl-versioning`, 2026-11-07); instructions become a module of `fnl-setup` (the separate setup restructure spec must
  be accepted before the pull request that removes the skill). `merge_check.py` requires a router marker in the pull request body in repositories that adopted
  `fnl-review-gate`; other repositories are not blocked (part K). The verification-receipt gate of the ledger applies
  only to delegated work recorded in the ledger; the coordinator's own work stays under the review gate.
- Payloads to the judge are written in English; criteria written in another language are restated in English by the small
  model and both texts are kept in the report.

## A. The agent set

| Agent | Role | Runs on |
| --- | --- | --- |
| `fnl-reviewer` | code review of a range, posts `kind=code` | the family `review_route.py` picks |
| `fnl-security-reviewer` | security review of a range, posts `kind=security` | the family `review_route.py` picks |
| fnl-navigator | drift check against the anchors | a small model of the family named for it |

All three keep `disallowedTools: [Write, Edit, NotebookEdit]`. The "mini router" paragraphs in the two reviewer files
are removed; each file keeps only its engine, steps and output. `fnl-verifier` and `fnl-steward` are removed with the
removals described in part H.

## B. Roles in the host config

A new section in the canonical `host.md`, one line per role, strict and fail closed like `## Project settings`:

```
## Agent roles
- code review: antigravity
- security review: codex
- navigator: claude
- judge: host
```

Keys are exactly `code review`, `security review`, `navigator` and `judge`; values are a family named in `## Agents on this
machine` (`claude`, `codex`, `antigravity`), except `judge`, whose value is `jev` or `host`; absent means `host`. Any other line, a duplicate key or an unknown family makes the section
unreadable and every role falls back to the rule in part C. At most 10 lines. Written only by `fnl-setup`, after a
neutral Yes and No and a shown line, with defaults taken from the scan (the present families other than the
coordinator's). The section never grants access or posting rights.

## C. Routing before reviewing

`review_route.py` (script, no model tokens; one copy per skill that needs it, kept identical by CI) decides before any
review starts:

1. Inputs it reads locally, with no model and no network: the author family of the head (commit trailers, else the
   ledger), `## Agent roles`, `## Agents on this machine`, `## Review posting` (part D) and the quota cache with its
   rate-limit markers, through `quota_probe.py status` only. A reading is started by the coordinator before routing
   (`quota_probe.py read --family <f>` when a candidate's cache is older than 15 minutes, as the quota rule in
   `CLAUDE.md` allows), never by this script.
2. For each review kind it picks the assigned family if it differs from the author family, is present and not out of
   quota. Otherwise the next present family that differs from the author family, in the capability order of
   `fnl-delegate`. With none left it picks the author's family in a fresh context and prints `same-family` so the
   report says so. For a change that hits a `fnl-security-review-gate` trigger and has no other family, the coordinator
   stops and asks the user, as today.
3. When both kinds pick the same family, one run covers both with one packet and posts two comments. In the low-risk
   lane (`merge_check.py --lane`) one reviewer posts both markers.
4. It prints one line per kind: family, form and reason; nothing else.

The coordinator then calls that agent directly: Claude through the `fnl-reviewer` or `fnl-security-reviewer` agent
(engine `/code-review` or `/security-review`), Codex through a headless `codex review` run, Antigravity through a
headless `agy` run that reads the diff. Delegated runs follow `fnl-delegate` (ledger, brief, hard cap). The reviewer
packet is built by script from git (base and head, `git diff --stat`, known consumers as a starting list) plus the
acceptance criteria and decisions the coordinator supplies. A re-review resumes the same run. A reviewer from the
security gate runs `security-audit` when `fnl-security-review-gate` says so; the brief says it explicitly.

Enforcers: the script for the choice; `fnl-review-gate` text and agent judgment (advisory) for calling it first;
`merge_check.py` for the review markers, which keep their meaning (part K3 adds one check beside them).

## D. Posting

- A review run posts its own comment when it can. When it cannot it returns the finished comment, marker included, and
  one line `cannot-post: <reason>` from a fixed list (`no-cli`, `no-network`, `no-auth`, `no-permission`, `other`).
- The coordinator relays that comment once (the existing relay rules of `CLAUDE.md` and `fnl-review-gate` still decide
  whether it may), and tells the user the exact missing capability and the setup below. It never accepts relay as the
  steady state.
- One posting path for every family: `post_review.py` (script, one copy where needed). It takes the pull request
  number, takes the repository from the checkout's remote (never from an argument), reads the comment from a file
  inside the run folder, requires the first line to match the review marker pattern exactly, caps the size, refuses
  every other option, and runs only `gh pr comment` and `gh pr view`. Tests: `--repo`, a body file outside the run
  folder, `--web`, `--edit-last`, a missing or malformed marker and an oversized body are refused.
- The wrapper searches for `gh` only in `/opt/homebrew/bin`, `/usr/local/bin` and `/usr/bin`, never relative or
  workspace PATH entries or temporary folders. Its executable check mirrors the quota-probe **Execution** exception
  in `CLAUDE.md`: under `/opt/homebrew`, only the git work tree rooted at exactly that prefix is allowed; nested
  repositories (including taps and clones) are refused. The resolved target and every component from the prefix to
  the file must stay inside that prefix, with no symlink leaving it, be owned by root or the current user, and not be
  world-writable; group write is allowed only for numeric gid 80 (`admin`, without a name lookup). Outside that
  prefix, `/usr/local` and `/usr/bin` retain the strict check: root or current-user ownership, no group or world write,
  and no `.git` in any ancestor. Tests cover the prefix-root repository, nested repositories, ownership, write bits,
  escaping symlinks and the installed Homebrew `gh` when present.
- Setup, after the user's yes, one family at a time, by `fnl-setup`. Codex: a fine-grained GitHub token limited to this
  one repository with an expiry, supplied through the credential injection the user approves; the plugin never reads,
  stores or searches for it; network limited to the GitHub API host where the host allows it; the brief allows only
  comment and view. A token with pull-request write can also approve, dismiss, close and edit the pull request body,
  and a reviewer reads attacker-controlled text, so the wrapper is the only intended path and the residual risk is
  stated to the user at setup. If the sandbox already reads the user's `gh` login, that is used instead.
  Antigravity: a remembered allow-rule for the exact argv of `post_review.py`, never for `gh` itself; recorded in the
  host config like the test-command grants; no wildcard.
- Before `yes` is recorded for a family, the coordinator checks that the comment's author is the expected identity
  as well as that the family's marker appears.
- `## Review posting` in `host.md` holds one line per family: `- codex: unverified`, `yes` or `no`, with the check
  date. `yes` is recorded only after the coordinator sees the family's own marker on a pull request; enabling a
  setting does not count. `review_route.py` prefers a `yes` family only between two otherwise valid candidates;
  independence of family comes first.
- Relay receipts and dashboard counters per family are not built in 0.2.0. They remain in the [0.2.1 backlog](release-0.2.0.md#deferred-to-021); relay is not yet counted.

## E. Verification without an agent

`fnl-verification` "Accepting someone else's work" gains a command, `verify_claim.py`:

1. Mechanical part, no model: runs exactly the tests the brief lists (never the full suite), compares the changed
   files with the brief's scope, checks that the head is the one reported, and prints `PASS` or `FAIL` with the
   evidence lines.
2. Semantic part: for each acceptance criterion, a question to the judge (part I) over the diff summary and test
   results; answers `yes`, `no`, `insufficient`. `no` and `insufficient` are read by the coordinator. The judge informs
   judgment and grants no acceptance; a `yes` never replaces the mechanical part. A criterion that compares two
   documents is split into one question per document and the answers are compared in code.
3. It writes a receipt (head, test result, criteria answers) through `record.py`.

`ledger.py finish --outcome accepted` refuses unless a receipt for the current head of the task's checkout exists. The
escape hatch is `--accept-unverified --reason <text>`, for work with nothing to check (for example a text-only
change); it is accepted, recorded and counted. The dashboard shows accepted-without-verification per agent. The ledger
check cannot stop an agent that never uses `ledger.py`; the spec says so and does not promise more.

## F. The steward folds into session hygiene

`context_steward.py` is unchanged. `fnl-session-hygiene` "Context pressure" gets the procedure in prose: run
`context_steward.py check` with the counts and the threshold, ask the judge (part I) the one boundary question only
when the script says `compact` and the boundary is not obvious, and run the script again. The agent file, its entry in the manifests
and `agents/openai.yaml` lines are removed. `compaction-steward.md` gets a note that the agent is retired.

## G. The navigator

Anchors, never invented. A project's anchor is an `Outcome` line in the project's `## Work tracking` block (the goal
and three to five success criteria, written only after the user's yes and dated); a spec's anchor is the Spec Kit
`spec.md` success criteria or the work record's `## Goal and acceptance`. A changed anchor is a dated decision, not an
edit; an anchor changed without one is itself a finding.

Drift kinds: work that traces to no criterion; a criterion dropped, narrowed or reworded without a decision; effort in
non-core areas while a core criterion has no evidence; a spec in progress with no commits or pull requests; status
that disagrees with the repository.

Flow:

1. `nav_state.py` (script) collects the facts since the last course check, each with a reference: pull requests and
   commits by identifier, spec statuses, ledger outcomes, criteria with their evidence. No model, no free text from
   files beyond the criterion wording.
2. A small model (the family and tier named for `navigator`; fast tier) turns each criterion and its evidence into a
   narrow question in English. A criterion in another language is restated in English; the report keeps the original
   and the sent text. A script checks that the payload holds only the allowed fields.
3. The judge (part I) answers `yes`, `no` or `insufficient`. With Jev, only the needed fields are sent and spend
   guards stay on.
4. The navigator reports to the host, per anchor: status (on course, drifting, abandoned), items matching no anchor,
   Jev's answers verbatim with the evidence, and at most three options to steer back, each with its cost. "No drift"
   is a valid result; a finding without evidence is not allowed. It decides nothing and edits nothing.

Run at boundaries (a user story closes, before a release is cut, a spec status changes) or when the user asks; this
is advisory (agent judgment), with no hook. The dashboard may show the date of the last course check. Before the
navigator is trusted, a validation runs the same questions over a handful of merged pull requests with known answers
and records the agreement; that result is part of acceptance.

## H. Retirement, compatibility, scope

- Removing two agents and one skill changes the public surface: CHANGELOG entries under Removed and Changed with the
  consumer action for each (`fnl-verifier` and `fnl-steward` callers follow the skill text; `fnl-setup-instructions`
  callers use `fnl-setup`), and the agent and skill counts in README, `fnl-ask` and the manifests updated. In Phase 0
  `fnl-versioning` makes a breaking change a MINOR bump, so a release that removes them is at least 0.2.0 (the
  owner chose 0.2.0 on 2026-11-07 and moved all work planned for 0.1.11 into it). The owner waived "deprecate first"
  for this removal.
- `fnl-delegate` Accept step and Route text, `fnl-verification`, `fnl-review-gate` ("Instruments", "Who reviews", the
  rules about relay and the low-risk lane), `fnl-coding-router` (the router marker), `fnl-setup` (roles, judge and
  posting steps), `fnl-session-hygiene`, `host-template.md`, the two reviewer agent files, `merge_check.py` with its
  tests and the `SessionStart` script change in the same work. Skills stay self-contained: scripts used by two skills are copied and compared in CI.
- `CLAUDE.md` is not edited by this work. If the owner later wants the "Standing relay" paragraph reworded as
  temporary, that is a separate pull request.

## I. The judge: Jev when chosen, a small host model otherwise

All semantic judgments of this spec (parts E, F and G) use one interface: a narrow question and its evidence in, one of
`yes`, `no`, `insufficient` out. Two implementations:

- **Jev**, with its probability kept, called by the plugin's `judge.py` (owner decision 07/11/2026: the fourth scoped
  exception in `CLAUDE.md` governs the call; the user's `typesafe-ai` skill remains the place to read the cookbooks and
  is not on the call path). One HTTPS POST per judgment to the fixed endpoint, the key only from `TYPESAFE_API_KEY`,
  a closed per-site payload schema with size caps and a refusal on a secret or path hit, no redirect or proxy, TLS
  verified, a loopback base URL only through a user-typed flag for tests, at most 24 outbound attempts in one process, including failed attempts (`MAX_CALLS` in `judge.py`), and `FNL_JUDGE=off`.
  Chosen at setup by a separate neutral Yes and No in `fnl-setup` (it needs the user's own authorization and API
  budget; the skill being installed grants neither) and recorded as `judge: jev`. Only a validated reply counts as
  Jev use; a timeout, 401, 429, missing key, DNS or TLS failure falls back to the host model and the report says so.
- **A small model of the host** (the fast tier of `fnl-delegate` `models.md`: a Haiku-class model on Claude, a mini
  model on Codex, a flash model on Antigravity), the default when `judge` is absent or `host`. The question and the
  evidence are in English, the answer is constrained to the three values, and for a `yes` the model must quote the
  evidence line that supports it. A script checks that the quote occurs in the supplied evidence; if it does not, the
  answer becomes `insufficient`. It gives no probability, so no threshold applies: only a checked `yes` counts as
  support, and every `no` and `insufficient` goes to the coordinator. Nothing leaves the host's own provider.

If Jev is chosen but unavailable at run time (no interface, an error, a missing budget), the host model takes over for
that call and the report says so. Both judges inform and grant nothing; neither replaces the mechanical checks. The same
rule holds for any other judgment in the plugin that today says "Jev, when available" (the steward boundary question,
the route judge): the fallback is the small host model, not silence.

Validation: one harness runs the same questions with either judge over cases whose answers are known from merged pull
requests, and records agreement. A judge with no recorded agreement is labelled unvalidated in the reports that use it.
First measurement (Jev, 2026-11-07, 12 cases from pull requests 138, 139 and 141, thresholds 0.7 and 0.3): 9 agree,
2 unsure, 1 wrong (a contradiction between two documents, accepted at 0.88); all six corrected-version cases passed.
The result drives the rules above: a judge is a filter, and cross-document consistency is decided in code.
Second measurement (small host model, a Haiku-class subagent, same 12 cases, `yes` only with a quoted line checked by
script): 10 agree, 2 insufficient, 0 wrong, including the cross-document case Jev accepted. This supports `host` as the
default, with caveats: a small sample, one repository, answers known to the author, the same model family as most of
the changes judged, and an unrecorded read scope for the subagent. A claim of absence ("no hook starts a worker") has
no line to quote, so it is phrased as the removal that proves it ("the worker start was removed from each hook") or it
ends as `insufficient`. The measurement stays labelled unvalidated until cases from other authors are run: these
cases come from the findings of this project's own reviews.

The quote check proves that a line is present, not that it supports the answer, and attacker-controlled diff text can
contain any line. The evidence is therefore passed as data, never as instructions, and quotes are preferred from added
lines and test output. For both judges the payload holds only the fields the question needs, and it is the same on the
Jev-to-host fallback. Receipts hold the answer and an identifier, not the criterion text, as `PRIVACY.md` requires.

## J. Setup and instruction changes this spec needs

- `fnl-setup`, user scope: after the scan, one question for the judge with three neutral choices (Jev, a small host
  model, none), recorded as `judge`; the route-judge reference is replaced by it. The optional `typesafe-ai` skill is for cookbooks only and is not required for calls. Choosing Jev says
  that the user's own API key and budget are needed, and that `judge.py` sends the bounded payload to TypeSafe with that key (the PRIVACY.md text), never reads, stores or searches for the key;
  a read-only `--check` may report whether the variable is set without printing it. `companions.md` lists TypeSafe with
  the condition "wants an external judge" and the data-processor note. README says the judge is optional and how to pick.
- `fnl-setup`, user scope: asks for the three roles with defaults from the scan, and per family whether review posting is
  set up (part D) with the exact setup step shown before any write. Section E and the steward explanation are
  rewritten for the new agent set.
- `fnl-setup`, `references/check.md`: reports roles, judge and posting state, each as configured, unverified or
  missing.
- The instructions module of `fnl-setup` (the successor of `fnl-setup-instructions`, which the same release removes):
  its project-scope `## Work tracking` block gains the `Outcome` line (goal and three to five success criteria,
  dated), written only after the user's yes. User scope text stays free of machine settings.
- The setup restructure is a separate spec (a short core path, optional features and the instructions module loaded on
  demand, one set of scope names: user scope for everything under the user's account, project scope for one
  repository). That spec is accepted before the pull request that removes `fnl-setup-instructions`.

## K. Enforcement at the end of the work

Starting a task cannot be enforced; evidence at the end can. Three pieces:

1. **Cheaper start.** The `SessionStart` hook already runs a script. It prints, from local files only, the state an agent
   would otherwise call `fnl-delegate` to learn: delegation mode, the roles, the cached quota summary and the count of
   open ledger entries, as fixed enumerated words and capped integers, never text read from a file (it runs in
   untrusted repositories). It never blocks and fails closed. Missing or invalid role sections, a missing host config
   or an invalid canonical data root print `unassigned` for code review, security review and navigator, and `host` for
   judge, as the reader's fallback in part B specifies. Valid assignments print the recorded family (`claude`, `codex`
   or `antigravity`); judge prints `host` or `jev`. Metrics consent is not required to read these local settings.
   Posting defaults to `unverified`. `unknown` means the role reader is unavailable, raises an error or returns a value
   outside its closed vocabulary; it does not mean an absent assignment.
2. **`route_task.py`** (script): applies the decision matrix of `fnl-delegate` to a kind and a grade and prints the
   tier, effort, budget, run form and family order. The implemented helper prints `model=coordinator`:
   presence, allowed models, quota and the final model selection remain coordinator responsibilities. Grading difficulty is the one semantic judgment; it goes to the judge (part I) with the
   coordinator free to override. The agent runs one command.
3. **Router marker.** A pull request body carries one line matching exactly
   `^<!-- fnl-router depth=(MIN|NORMAL|DEEP) trigger=(none|contract|security|privacy|permission|migration|dependency|uncertainty|consumers|irreversible|calculation|prediction|input) -->$`
   (the values `record.py router` accepts). `merge_check.py` gains the field `body` and checks the marker at merge time;
   the body can be edited after a review, so only the state at merge counts. Adoption is read from the pull request's
   base commit with `git show <base oid>:<path>`, never from the head or a local branch, so a change cannot exempt
   itself: a repository has adopted the gate when `CLAUDE.md` or `AGENTS.md` at the base commit has a `## Agent skills`
   section whose text contains the token `fnl-review-gate`. A file that does not exist means not adopted; a file or a
   body that cannot be read, or a `git show` that fails, makes `merge_check.py` exit 2 (an error, not a pass). When
   adopted, a missing or malformed marker is blocking, for the low-risk lane and for bot pull requests as well. The
   marker never changes which review markers or lane apply: `depth=MIN` on a diff that hits a security trigger still
   needs the security marker, and a test pins that. The reviewer compares the stated depth with the diff. A false marker
   is a visible claim a reviewer can contradict, not a silent omission.

## Not in scope

A forced rule that author and reviewer families differ; changing what the review markers mean or which of them a
change needs; a hook for the
navigator; reading quota or accounts of the review families beyond the existing on-demand reading; Jev outside the
judgments listed.

## Acceptance

- `## Agent roles` and `## Review posting`: tests for each rejected shape, fail-closed fallback, writes only through
  `fnl-setup`.
- `review_route.py`: tests for the assigned family, the same-family case with the disclosure, an out-of-quota family,
  a missing family, both kinds on one family (one run, two comments), the low-risk lane, and that it runs no model and
  no network.
- Posting: the `cannot-post` reasons, one relay per run, the receipt count, and `yes` recorded only after a seen marker.
- `verify_claim.py` and the ledger check: refusal without a receipt, acceptance with one, the escape hatch recorded and
  counted, and the fallback from Jev to the host judge reported in the receipt.
- The judge: `tests.test_judge` covers every closed per-site schema, field and total byte caps, secret and machine-path
  refusals (field name only), the 24-call per-run cap, canonical opt-in and invalid root pointers, `FNL_JUDGE=off`,
  user-typed literal loopback HTTP overrides (never environment URLs), verified TLS ignoring proxy/certificate
  overrides, no redirects, header-only keys and explicit host fallback on timeout, 401, 429, missing key, DNS/TLS
  errors and invalid replies. Quotes need at least 8 alphanumeric characters and 8 trimmed characters;
  shorter, whitespace-only, punctuation-only, unquoted or misquoted `yes` becomes `insufficient`; the harness runs both judges on
  the same cases; `judge` absent means `host`.
- `fnl-steward` and `fnl-verifier` files gone, no manifest or text still names them as callable, `fnl-ask` map and
  counts updated, `check-references.py` and the manifests test green.
- Navigator: `nav_state.py` output limited to the allowed fields, payload check, English restatement kept with the
  original, the validation over merged pull requests recorded, and a test that a finding without evidence is rejected.
- `PRIVACY.md` lists any new stored value (the posting state, the relay count, the receipts) as metadata only.
- `post_review.py` refuses the cases listed in part D; the identity check precedes `yes`.
- `fnl-setup-instructions` is gone from the plugin, the manifests and the maps, with its CHANGELOG consumer action, and the
  setup restructure spec is accepted before that pull request.
- `merge_check.py`: the marker cannot relax review requirements; adoption comes from the base commit; an unreadable
  file or body exits 2; a missing file means not adopted.
- `route_task.py` returns the matrix row for each kind and grade; the `SessionStart` output is read-only and cannot
  block; `merge_check.py` blocks a missing marker only when the base branch adopted the gate, and ignores a head that
  adds or removes the adoption line.
- Each implementation pull request gets its own code and security review; the posting setup is shown to the user
  and confirmed before any write.

## Open decisions

1. Where the project `Outcome` line lives if a repository has no agent context file.
2. Whether a repository may name its own default roles that override the user's (not in this spec; the user's host
   config is the only source).
