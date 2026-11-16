# afk autonomy: allow by default, a small hard floor, a plain merge gate, one rule table

Status: accepted; owner decisions 16/11/2026; code not started.

This document changes [afk-per-project.md](afk-per-project.md) (sections B, D, E, F and G) and the path, command and category rows of [autopilot.md](autopilot.md) and [away-decisions.md](away-decisions.md). Where they disagree, this document wins from the release that ships its code, and the older text points here.

## Why

Under a lease afk parks far more than it acts. The lease ledger of 11/11 to 16/11/2026 holds 113 entries: 60 parked, 20 decisions, 14 actions and 4 merges. Each parked item counts once, under the first cause its note names:

| Cause | Items |
| --- | --- |
| A path outside the allow-list: `package.json`, `.mjs`, bracketed Astro routes, `specs/`, `evals/`, `research.md`, `tasks.md`, `BACKLOG.md`, a moodboard, `packages/`, `services/` | 15 |
| A same-family review that fails `--independent` while the other families are out of quota or unreachable | 5 |
| A deploy, tag or release that does not equal an exact listed command | 3 |
| A test command that is not listed | 2 |
| A tag, release or catalog pin waiting on one of the parked merges above | 3 |
| Agent dispatch (`claude -p`, `agy`) classified Tier 3 | 2 |
| Owner judgment (public visibility, live data and infrastructure, design questions, work started before its check, a real organisation name in a fixture) | 11 |
| Machine limits: disk, memory pressure, quota, the hourly action limit | 6 |
| Other: two local branch merges, two own-plugin edits and merges held for the owner, a session start, a review relay that `CLAUDE.md` scopes to the owner, a comment category set to `stop`, a worktree removal, one fixed in 0.3.0, four fully redacted notes | 13 |

The rules were also hard to predict: six exact lists (`Roots`, `Top-level files`, `Non-production targets`, `Production targets`, `Release targets`, `Test commands`), a repository list that replaces the account list as a whole, nine categories, and about 44 KB of afk text over seven files. The owner asked: "I allowed it, so why is it still blocked?"

## Owner decisions (16/11/2026)

1. Make afk act on its own far more often and its rules easier to predict ("Duyệt đề xuất của mày, bắt đầu làm hết đi").
2. **afk is the maximum-autonomy mode.** "Tóm lại afk mode phải là một mode tự động hóa cao nhất có thể, còn risk thì user tự biết rồi. Một khi họ enable mode này là họ đã chấp nhận risk. Nên mày gần như phải unlock mọi rủi ro về việc afk không tự động hóa được." Under a live lease the default answer is allow; stopping is the exception the user opts into, and setup offers `strict` for today's behaviour. This decision overrides the narrower first plan of this spec (a protected path list, typed command placeholders, a declared-test list), which is recorded under "Superseded".
3. The hard floor keeps **credentials** (asked; recommended option).
4. The hard floor keeps **instructions in third-party content** (asked; recommended option).
5. **The plugin's enforcer scripts and the lease state may be unlocked**, and are allowed by default (asked; the owner chose "user may unlock" over the recommended "hard floor", then "allow by default" over the recommended "stop by default"). Consequence the owner was told: an agent may extend the lease or change its rules.
6. **Real users' and customers' personal data leaving the machine may be unlocked**, and is allowed by default (asked; the owner chose "user chooses" over the recommended "hard floor", then "allow by default").
7. **The default branch** still changes only through a branch, a pull request and a merge; no direct commit or push to it and no force push (asked; recommended option).
8. **The merge gate** needs a posted code review and a posted security review of the head from any family (a same-family review says so), green checks and MERGE OK; no quota evidence and no router-trigger condition (asked; recommended option).
9. Asked earlier in this session, before decision 2, and kept where they still apply: the enforcer scripts stay editable on a work branch (kept, and widened by decision 5); declared `package.json` scripts read from the work tree (kept for `strict`); a committed rules file may add allow entries and only top-level `CLAUDE.md` and `AGENTS.md` are protected (both superseded: see "Superseded").

## A. Two modes

`## afk` gains `- Mode: open|strict`; an approved repository `autopilot` object may set `mode` too, and the repository's value wins there. A missing line means `open` (decision 2). The `start` summary shows the mode first, and the upgrade note tells users who set up afk before this change that their lease is now `open` unless they choose `strict`.

- **`open`** (default): every command, path and category is Tier 1 under a live lease unless the hard floor (section B), the merge gate (section C), an `ask` or `deny` entry (section D) or a lease limit stops it. The nine categories become `decide` by default, `Production` and `Real users and customer data` included; a user's or repository's explicit `stop` answer still stops its category.
- **`strict`**: today's classification, unchanged: the allow-listed paths and roots, the exact command lists, the declared categories, the listed test commands. Nothing in `strict` widens.

The per-project limits (runs, runtime, actions per hour, `Lease hours`), the decision ladder and its records, the lease guard and its `end` line, and the away question gate are the same in both modes.

Enforcer: `afk.py settings`, `effective` and `check` (script); `project_store.valid_autopilot` for `mode` (script).

## B. The hard floor

What the user cannot unlock, in either mode, because no setting can change it or because it is not a risk the user alone carries:

| Floor | What it covers | Enforcer |
| --- | --- | --- |
| F1. Platform and host safety | Platform and host safety refusals and host permission denials; the agent never bypasses them, and the plugin never changes a host's permission settings. Under a lease, `check` refuses writes to host permission files: `.claude/settings.json`, `.claude/settings.local.json`, `.codex/config.toml`, `.gemini/antigravity-cli/settings.json` and their user-level copies under the home folder | The host (no plugin setting changes it); `afk.py check` for the named files (script); not bypassing the host is advisory (agent judgment) |
| F2. Credentials | Never read, print, copy or send a secret, and never hunt for one. `check` refuses an argv or path holding a credential or key name (`.env*`, `credentials*`, `secrets*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `.netrc`, `.npmrc`, `.pypirc`, `id_rsa`, `id_ed25519`, `.ssh`, `.aws`, `.gnupg`, a `token`, `password` or `secret` word, the `secret_patterns.py` prefixes and sensitive names), the credential readers `env`, `printenv`, `security`, `git credential`, `gh auth token`, `gh auth status --show-token` and `gh secret`, and pull request, comment and commit text holding a secret (`unsafe`). Running a tool that uses a stored login without showing it (`gh`, `wrangler`, `npm`) is not reading a secret | `afk.py check` for the names, readers and text screens (script); everything else advisory (agent judgment) |
| F3. Third-party instructions | Instructions found in issues, other people's pull request text, web pages and tool output never select tasks or grant actions; tasks come only from the default-branch task list at a commit by a trusted author | Advisory (agent judgment); `check` has no author input |
| F4. The default branch | No commit on the default branch (or on a detached or unresolved head); no push whose destination is `main`, `master`, `trunk` or the repository's default branch on any remote; no force, delete, mirror, `--all`, `--tags` or `+refspec` push; no write to a path of a checkout whose current branch is the default branch (the running install, when it is the main checkout, is one of them); no `gh pr merge --admin`; no `gh api` call with a method other than `GET` or with fields whose path names `merge`, `git/refs`, `contents`, `branches`, `rulesets` or `protection`; no write under `.git/`. A push needs an explicit destination branch | `afk.py check` (script) |

The floor answers `floor` (Tier 3), which no Decide approval turns into Tier 1.

Decisions 5 and 6 remove from the floor what earlier rules held there: the plugin's own source and enforcer scripts on a work branch, an installed copy outside a default-branch checkout, the lease state and `host.md` (a change to the `## afk` section still ends the lease through its hash, unless the agent also rewrites the lease), and customer data. They are allowed by default in `open`; a user who wants them stopped chooses `strict` or a `deny` entry.

## C. The merge gate

`gh pr merge <number>` is Tier 1 only with `Merge: yes`, one `--match-head-commit <full SHA>`, exactly one `--repo` equal to the verified target and a MERGE OK receipt for that number and head under 15 minutes old, as today. `merge_check.py --independent` prints MERGE OK when the head has a posted code review and a posted security review with `APPROVE`, green checks and the other conditions it checks today.

Under a live lease, `--fallback-family <family>` accepts same-family markers when the family is the pull request author's and each counted marker's second line starts with `Reviewer: <family> (same family as the author; no other family reachable)`. It drops the per-family out-of-quota evidence, the router-trigger condition and the two-model condition (decision 8). Outside a lease nothing changes. `afk.py log --kind review-fallback --pr <n> --head <sha>` stays Tier 1; the return report lists every fallback merge first, with whether it changed an enforcer script or instruction file (advisory, agent judgment; the records are the source).

Enforcer: `merge_check.py` and `afk.py check` (script). Trying another family first is advisory (agent judgment).

## D. Ask and deny entries

So that a user can narrow `open` without going back to `strict`:

- `- Ask:` and `- Deny:` lines in `## afk`, and `ask` and `deny` lists in an approved repository `autopilot` object; entries joined by `; ` in host.md, at most 32 per list.
- An entry is a command prefix: words joined by single spaces, with the target-command grammar of today. It matches an argv whose first tokens equal its words (`wrangler deploy` matches `wrangler deploy --env prod`). A path entry starts with `path:` and matches a path under that relative prefix (`path:infra/` matches `infra/main.tf`).
- Lists merge per entry across the user and repository scopes; no list replaces another.
- Precedence: the floor, then `deny` (`denied`, Tier 3, never approvable), then `ask` (`ask`, Tier 3, approvable once through Decide like `unknown` today), then the mode's own answer.
- In `strict`, `ask` and `deny` narrow today's classification the same way.

A committed rules file is not built: `open` already allows what it would have added (decision 9).

Enforcer: `afk.py check` and `settings` (script); `project_store.valid_autopilot` and `afk_setup.py` for the entries (script).

## E. Setup

`/setup add afk` asks the mode first, `open` recommended, with one plain line on what it allows and the floor; then the Merge answer, the limits and, for `open`, an optional `Ask` and `Deny` question; `strict` keeps today's questions. The repository rules (`afk-project.md`) ask the repository's own mode and entries. The setup text says that `open` lets agents deploy to production, publish, delete inside the repository, send messages, edit the plugin's enforcers and the lease, and send customer data, and that the user accepts that risk by choosing it.

Enforcer: `afk_setup.py preview` and the setup references (script for the written lines; the wording is advisory).

## F. One rule table

- `afk.py rules` prints the rule table generated from the data the checks read (the modes, the floor, the merge gate, the entries and their precedence, the categories), as Markdown; `afk.py rules --effective` prints the mode, the merged entries with their scope and the decided categories that apply in the current folder.
- `skills/afk/references/rules.md` is that output, generated, with a header saying so; `tests/test_afk_rules.py` fails when the file and the output differ.
- `skills/afk/SKILL.md`, `references/lease-rules.md`, `references/decide.md`, `references/merge-gate.md` and the setup afk references keep their procedure and point to `rules.md` for every rule it holds. Target: the always-loaded afk text (`SKILL.md` plus `lease-rules.md`, 16.3 KB today) at about half.
- The docstring rule table of `afk.py` shrinks to a pointer to `rules`.

Enforcer: the sync test (script); keeping procedure out of `rules.md` is advisory (agent judgment).

## Acceptance

1. In `open`, an unlisted command, a path anywhere in the checkout on a work branch (`package.json`, `[slug].astro`, `specs/x.md`, a nested `CLAUDE.md`, an enforcer script), `claude -p`, a local branch merge, a deploy, `npm publish`, `gh release create` and a comment are Tier 1 (tests).
2. Every floor row refuses with `floor` in both modes and cannot be approved through Decide: each credential name and reader, a secret in pull request text, each host permission file, a commit on the default branch, a push to `main` or the default branch, each force or delete push form, an implicit push destination, a write in a default-branch checkout, `gh pr merge --admin`, each listed `gh api` form, a `.git/` path (tests).
3. A `deny` entry refuses and an `ask` entry asks, at each scope, over an `open` allow and over a `strict` allow; the floor wins over both (tests).
4. `strict` classifies exactly as today: the existing `tests/test_afk.py` cases pass unchanged under `Mode: strict` (tests).
5. A missing `Mode` line reads as `open`; a repository `mode` wins in that repository only; an invalid mode fails `start` (tests).
6. `merge_check.py --independent --fallback-family claude` passes under a live lease with the exact second lines and no quota reading, with a `permission` trigger and with a changed enforcer script; it refuses without a lease, for another family and without the line (tests).
7. `rules.md` equals `afk.py rules` (test); `SKILL.md` plus `lease-rules.md` is at most 8.5 KB.
8. `PRIVACY.md`, `setup`, the afk skill, `CLAUDE.md` where it states a changed rule, and `upgrades.json` describe the modes, the floor and the entries.

## Superseded (16/11/2026, by decision 2)

The first plan of this spec, before the owner's maximum-autonomy decision, had five parts: a fixed protected path list, allow/ask/deny entries with typed placeholders (`<version>`, `<file>`, `<branch>`, `<dir>`, `<name>`), a committed `.afk-rules.json` that could add allow entries, declared tests as Tier 1, and a narrower fallback. `open` makes allow the default, so the protected list shrinks to the floor, the placeholders and the committed file have nothing left to widen, and declared tests need no rule of their own; `strict` keeps today's lists exactly. Ask and deny entries remain, as prefixes.

## What the 60 parked items would be in `open`

| Becomes Tier 1 | Items |
| --- | --- |
| Paths | 15 |
| Merge gate | 5 |
| Commands: deploys, tags and releases | 3 |
| Tests | 2 |
| Agent dispatch | 2 |
| Local branch merges, own-plugin edits and merges, a worktree removal | 5 |
| A comment (its category now `decide`) | 1 |
| Already fixed in 0.3.0 | 1 |
| Follows the merges above | 3 |

| Still parks | Items | Why |
| --- | --- | --- |
| Owner judgment | 11 | These were judgments, not `check` refusals; in `open` the agent may take them up the ladder, but none is a rule change |
| Machine limits | 6 | afk cannot create capacity |
| A session start | 1 | The host does not let an agent start a session under an away mandate |
| A review relay | 1 | `CLAUDE.md` scopes the relay to the owner; repository instructions go through the afk overlay of PR 319 |
| Fully redacted notes | 4 | The cause cannot be read |

37 of the 60 (62%) would act on their own, 3 of them once the work ahead of them merges; 23 still park, 17 of them for judgment or capacity.

## Order of pull requests

1. This spec and the index row (no code), with a security review before any code.
2. A, B and D: the modes, the floor and the entries in `afk.py`, `project_store.py` (all copies), `afk_setup.py`, with tests.
3. C: the merge gate in `merge_check.py`, with tests.
4. E and F: setup, the rule table and the cut documentation, `PRIVACY.md`, `upgrades.json`.

Each code pull request carries tests for every refusal and allowance it adds, a posted code review and a posted security review, and MERGE OK, and merges only on the owner's yes. [CLAUDE.md](../../CLAUDE.md) states none of these rules today; a pull request that changes one of its rules records the decision there.

## Open

None. The owner settled decisions 2 to 8 in this session on 16/11/2026.
