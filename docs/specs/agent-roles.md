# Agent roles: routed reviews, verification without an agent, and a navigator

Status: draft; owner decisions recorded on 2026-11-07 (see "Decisions settled"); target release open (part H); implementation not started.

## Why

The plugin ships four agents: `fnl-reviewer`, `fnl-security-reviewer`, `fnl-verifier` and `fnl-steward`. Looking at them
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

1. Inputs it reads locally: the author family of the head (commit trailers, else the ledger), `## Agent roles`,
   `## Agents on this machine`, `## Review posting` (part D) and the canonical quota cache (`quota_probe.py read`
   first when a candidate cache is older than 15 minutes, per `quota-on-demand.md`).
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
`merge_check.py` for the markers, unchanged.

## D. Posting

- A review run posts its own comment when it can. When it cannot it returns the finished comment, marker included, and
  one line `cannot-post: <reason>` from a fixed list (`no-cli`, `no-network`, `no-auth`, `no-permission`, `other`).
- The coordinator relays that comment once (the existing relay rules of `CLAUDE.md` and `fnl-review-gate` still decide
  whether it may), and tells the user the exact missing capability and the setup below. It never accepts relay as the
  steady state.
- Setup, after the user's yes, one family at a time, by `fnl-setup`: Codex gets a GitHub token limited to pull
  requests (write) on the repository, supplied through the credential injection the user approves; the plugin never
  reads, stores or searches for it. If the sandbox already reads the user's `gh` login, that is used instead.
  Antigravity gets remembered allow-rules for exactly `gh pr comment` and `gh pr view`, recorded in the host config
  like the test-command grants; no wildcard.
- `## Review posting` in `host.md` holds one line per family: `- codex: unverified`, `yes` or `no`, with the check
  date. `yes` is recorded only after the coordinator sees the family's own marker on a pull request; enabling a
  setting does not count. `review_route.py` prefers a `yes` family only between two otherwise valid candidates;
  independence of family comes first.
- Each relay is counted by a receipt (`record.py`) and the dashboard shows relayed reviews per family.

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

- Removing two agents changes the public surface: CHANGELOG entries under Removed and Changed, a note that callers by
  name (`fnl-verifier`, `fnl-steward`) now follow the skill text, and the agent counts in README, `fnl-ask` and the
  manifests updated. The release number is the owner's call (open decision 1).
- `fnl-delegate` Accept step, `fnl-verification`, `fnl-review-gate` ("Instruments", "Who reviews"), `fnl-setup` (roles
  and posting steps), `fnl-session-hygiene`, `host-template.md` and the two reviewer agent files change in the same
  work. Skills stay self-contained: scripts used by two skills are copied and compared in CI.
- `CLAUDE.md` is not edited by this work. If the owner later wants the "Standing relay" paragraph reworded as
  temporary, that is a separate pull request.

## I. The judge: Jev when chosen, a small host model otherwise

All semantic judgments of this spec (parts E, F and G) use one interface: a narrow question and its evidence in, one of
`yes`, `no`, `insufficient` out. Two implementations:

- **Jev** through the user's `typesafe-ai` skill, with its probability kept. Chosen at setup by a separate neutral Yes
  and No in `fnl-setup` (it needs the user's own authorization and API budget; the skill being installed grants
  neither) and recorded as `judge: jev`. Only a validated reply counts as Jev use.
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

## J. Setup and instruction changes this spec needs

- `fnl-setup`, user scope: after the scan, one question for the judge with three neutral choices (Jev, a small host
  model, none), recorded as `judge`; the route-judge reference is replaced by it. Choosing Jev when `typesafe-ai` is
  missing prints the install command (checked against the skill's official source at the time of writing, never
  guessed), says that the user's own API key and budget are needed, and never reads, stores or searches for the key;
  a read-only `--check` may report whether the variable is set without printing it. `companions.md` lists TypeSafe with
  the condition "wants an external judge" and the data-processor note. README says the judge is optional and how to pick.
- `fnl-setup`, user scope: asks for the three roles with defaults from the scan, and per family whether review posting is
  set up (part D) with the exact setup step shown before any write. Section E and the steward explanation are
  rewritten for the new agent set.
- `fnl-setup`, `references/check.md`: reports roles, judge and posting state, each as configured, unverified or
  missing.
- `fnl-setup-instructions`, project scope: the `## Work tracking` block gains the `Outcome` line (goal and three to five
  success criteria, dated), written only after the user's yes. User scope text stays free of machine settings.
- Both skills use the same scope names in their text: user scope (everything under the user's account: host config,
  consent, user-level instruction files) and project scope (one repository). The wider restructure of the setup skill
  (a short core path with optional features loaded on demand) is a separate spec.

## Not in scope

A forced rule that author and reviewer families differ; changing the review markers or `merge_check.py`; a hook for the
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
- The judge: the quote check turns an unquoted or misquoted `yes` into `insufficient`; the harness runs both judges on
  the same cases; `judge` absent means `host`.
- `fnl-steward` and `fnl-verifier` files gone, no manifest or text still names them as callable, `fnl-ask` map and
  counts updated, `check-references.py` and the manifests test green.
- Navigator: `nav_state.py` output limited to the allowed fields, payload check, English restatement kept with the
  original, the validation over merged pull requests recorded, and a test that a finding without evidence is rejected.
- `PRIVACY.md` lists any new stored value (the posting state, the relay count, the receipts) as metadata only.
- Each implementation pull request gets its own code and security review; the posting setup is shown to the user
  and confirmed before any write.

## Open decisions

1. Release number: removing two agents may justify 0.2.0; the owner decides before the first implementation pull
   request.
2. Where the project `Outcome` line lives if a repository has no agent context file.
3. Whether a repository may name its own default roles that override the user's (not in this spec; the user's host
   config is the only source).
