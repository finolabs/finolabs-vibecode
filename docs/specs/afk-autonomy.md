# afk autonomy: a protected list for paths, allow/ask/deny for commands, declared tests, a plain review fallback, one rule table

Status: accepted; owner decision 16/11/2026; code not started.

This document changes [afk-per-project.md](afk-per-project.md) (sections B, D, E, F and G) and the path and command rows of [autopilot.md](autopilot.md) and [away-decisions.md](away-decisions.md). Where they disagree, this document wins from the release that ships its code, and the older text points here.

## Why

Under a lease afk parks far more than it acts. The lease ledger of 11/11 to 16/11/2026 holds 113 entries: 60 parked, 20 decisions, 14 actions and 4 merges. The parks, by cause (each line counts the items whose note names that cause; a note may name two):

| Cause | Items |
| --- | --- |
| A path outside the allow-list: `package.json`, `.mjs`, bracketed Astro routes, `specs/`, `evals/`, `research.md`, `tasks.md`, `BACKLOG.md`, a moodboard, `packages/`, `services/` | 15 |
| A same-family review that fails `--independent` while the other families are out of quota or unreachable | 5 |
| A deploy, tag or release that does not equal an exact listed command (a deploy with project arguments, a tag with no `Release targets`) | 3 |
| A test command that is not listed | 2 |
| A tag, release or catalog pin waiting on one of the parked merges above | 3 |
| Owner judgment, correct by design (public visibility, live data and infrastructure, design questions, work started before its check, a real organisation name in a fixture) | 11 |
| Machine limits: disk, memory pressure, quota, the hourly action limit | 6 |
| Agent dispatch (`claude -p`, `agy`) classified Tier 3 | 2 |
| Other: two local branch merges, two own-plugin edits and merges held for the owner, a session start, a review relay that `CLAUDE.md` scopes to the owner, a comment category set to `stop`, a worktree removal, one fixed in 0.3.0, four fully redacted notes | 13 |

Each item counts once, under the first cause its note names; two path items also name agent dispatch and one test item also names memory pressure.

Five separate exact lists (`Roots`, `Top-level files`, `Non-production targets`, `Production targets`, `Release targets`, plus `Test commands`), a repository list that replaces the account list as a whole, and about 44 KB of afk text over seven files made the rules hard to predict. The owner asked: "I allowed it, so why is it still blocked?"

## Owner decisions (16/11/2026)

1. The five changes below, in this order ("Duyệt đề xuất của mày, bắt đầu làm hết đi").
2. A committed rules file in a repository may add `allow` entries, not only `ask` and `deny` (asked in this session; the owner chose it over the recommended "approved settings only"). Section B bounds it.
3. The security enforcer scripts stay editable as today: only as the plugin's own source (`skills/**`, `scripts/**`) of a checkout on its own non-default work branch (asked; the owner chose it over the recommended "always protected under a lease"). With change 4 this lets an unattended agent edit an enforcer and merge it after one same-family review; the owner accepted that, and the return report lists every such merge first.
4. `npm run <script>` and its equivalents read the declared scripts from the `package.json` in the work tree (asked; recommended option).
5. Only the top-level `CLAUDE.md` and `AGENTS.md` join the protected list; one in a subfolder is a known path (asked; the owner chose it over the recommended "every depth").

## A. Paths: a protected list instead of an allow-list (pull request 2)

On the agent's own non-default work branch of a verified repository (a found identity in the `user` or `project` state, the current branch resolved and not the default branch, `main`, `master` or `trunk`), every relative path inside the checkout is a known path except the protected list. Anywhere else (the default branch, a detached or unreadable head, the strict and no-repository states, no identity) no path is known.

The protected list, fixed in the script and the same in every repository:

1. Git and host internals: any component `.git`, `.github`, `.claude`, `.codex`, `.agents`, `.ssh`, `.aws`, `.gnupg`, and the git hook names (`pre-commit`, `pre-push`, `commit-msg`, `post-commit`, `prepare-commit-msg`, `post-checkout`, `post-merge`).
2. Instruction files: the top-level `CLAUDE.md` and `AGENTS.md` (decision 5), and at every depth `CLAUDE.local.md`, `AGENTS.override.md`, `GEMINI.md`, `AGENTS.afk.md` (the afk overlay of [afk-overlay.md](afk-overlay.md), once it is merged) and `.specify/memory/constitution.md`.
3. The committed rules file of section B, `.afk-rules.json`, at every depth.
4. Credential and key names, as today: `.env*`, `credentials*`, `secrets*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `.netrc`, `.npmrc`, `.pypirc`, `id_rsa`, `id_ed25519`, any component holding `credential`, or `token`, `password` or `secret` as a word, and the secret prefix and sensitive-name patterns of `secret_patterns.py`.
5. afk's own state names: `host.md`, `lease.json`, `log.jsonl`, `root.json`, `stop`.
6. Links: a symbolic link on any component from the checkout root down to the path.
7. Anything outside the checkout: an absolute path, `..`, `~`, a path that resolves outside the checkout root.
8. This install's own checkout on every branch, and this install's skill script folders (as today, `install_owned` and `plugin_code`).
9. The security enforcer scripts (the `ENFORCERS` names of `afk.py`), except as a source path (`skills/**`, `scripts/**`) of the check's own checkout on its work branch (decision 3, unchanged from today).

What else holds:

- A directory operand stays `unknown`: staging a folder would stage everything below it, protected names included.
- The path grammar widens to `[A-Za-z0-9_.@+()\[\]/-]`, so bracketed routes (`[slug].astro`, `[...path].ts`), route groups (`(marketing)`), slots (`@modal`) and SvelteKit names (`+page.svelte`) are plain paths. A component of `.` or `..`, an empty component, a space, `=`, `:`, `\` and every control character stay refused.
- No extension list: a known path may have any extension or none (`Makefile`, `package.json`, `check-site.mjs`, a design file).
- The soft names of today (`settings`, `config`, `hooks`, `setup.*`, `SKILL.md`) are no longer protected on a work branch: the protected list names what an unattended agent must never touch, and those names are ordinary project files in most repositories. A host's own settings stay protected through `.claude`, `.codex` and `.agents`.
- Default-branch writes stay forbidden: on the default branch every path is `protected`, and `git commit` there stays `protected`, as today. Merging still needs the merge gate.
- `check --paths`, `git add`, `git rm` and the path operands of read-only Git queries use this one rule.

Retired keys, kept readable: `roots` and `top-level-files` (project), `Top-level files` (`## afk`) and `skill-repository` (project). The validators keep accepting them, so an approved settings file and a `## afk` section that carry them stay valid and the lease hash is unchanged for a section that has them; `check` ignores them; `setup` stops writing them; `effective` stops showing them. The upgrade note says they no longer do anything.

Enforcer: `afk.py check` (script). Tests: every protected entry refuses on a work branch; the same path is known on a work branch and protected on the default branch; a bracketed route, an `.mjs` file, `package.json`, `specs/x.md`, `evals/x.json`, `BACKLOG.md`, a nested `CLAUDE.md` and a nested `SKILL.md` are known on a work branch; a link, a directory, `..` and an absolute path refuse; an enforcer name outside `skills/**` and `scripts/**` refuses; settings with the retired keys stay valid.

## B. Commands: allow, ask and deny entries (pull request 3)

### Entries and scopes

An entry is one command line: words joined by single spaces (the `production-targets` grammar of today, at most 32 words and 240 characters), where a whole word may be a typed placeholder. Three lists, `allow`, `ask` and `deny`, at three scopes:

| Scope | Where | Who writes it | What it may hold |
| --- | --- | --- | --- |
| User | `## afk` in host.md: `- Allow:`, `- Ask:`, `- Deny:`, entries joined by `; ` | `/setup add afk`, previewed | allow, ask, deny; no production entry |
| Repository, approved | `allow`, `ask`, `deny` in the approved `autopilot` object | `/setup add afk` inside the repository, previewed and bound to the digest as today | allow, ask, deny; production entries only here |
| Repository, committed | `.afk-rules.json` at the checkout root: `{"allow": [...], "ask": [...], "deny": [...]}` | anyone who can merge into the default branch (decision 2) | allow, ask, deny; no production entry |

- Lists merge per entry across the scopes that apply: the effective allow list is the union of the user, approved and committed allow lists, and the same for ask and deny. No scope replaces another.
- Precedence: deny, then ask, then allow. A deny entry that matches wins at every scope, over every other entry and over the script's built-in Tier 1 forms (a user may deny `git push`). An ask entry that matches turns a built-in Tier 1 form or an allow match into `ask`.
- The strict and no-repository states use the user lists only for deny and ask; no allow entry applies there, and no deploy, tag, release or publish runs.
- The committed file is read only from the main checkout, and only when that checkout's `HEAD` is the default branch and its commit equals `refs/remotes/origin/<default>` (metadata reads, no Git process). The file must be a regular file of at most 16 KiB, no link on its path, parsed as a closed JSON object with the three keys. A work branch's copy never applies, and the file is on the protected list, so an agent under a lease cannot write the rules it is checked against. Anything unreadable or invalid in it is ignored as a whole and `effective` says so.
- Residual risk the owner accepted (decision 2): anyone who can merge into the default branch, or edit the main checkout's file locally, can add allow entries. Production entries are refused from this file, deny entries from the other scopes still win, and the protected list, the text screens and the categories still apply.

### Placeholders

| Placeholder | Matches |
| --- | --- |
| `<version>` | `v`, then the SemVer version of the repository's manifest at the default branch head, for a tag that does not exist yet. The manifest is the first of `.claude-plugin/plugin.json` and `package.json` in the main checkout, read under the same `HEAD` condition as the committed file; its `version` must be SemVer without a `-dev` suffix. A tag exists when `refs/tags/<tag>` is a loose ref or a `packed-refs` line. |
| `<file>` | A file that passes today's `--body-file` rules: a regular file of at most 64 KiB inside the check's own checkout, outside the data root, no link, whose text passes the control, marker, secret and path screens. |
| `<branch>` | A non-default branch name of `BRANCH` grammar that is not `main`, `master`, `trunk` or the default branch, with no `..`. |
| `<dir>` | A relative directory inside the checkout that exists, passes the path rules of section A (not protected, no link) and is not the checkout root. |
| `<name>` | `[a-z0-9-]{1,64}`. |

A placeholder is a whole word; a word that holds text and a placeholder (`--name=<name>`) is a literal. Matching is on token lists, so a token holding a space never equals two words.

### What an entry may name

- Never these words, in any entry at any scope (setup refuses, `check` ignores the entry): `-d`, `-D`, `-f`, `--force` and every word starting with `--force`, `--delete`, `delete`, `destroy`, `--mirror`, `--all`, `--tags`, `--prune`.
- An entry starting with `git` or `gh` may only be a tag or release form (`git tag`, `gh release`); other Git and `gh` commands keep the script's own rules. An entry starting with `rm` is refused.
- A production entry (a deploy entry with a word matching `prod` or `live`) is accepted only in the approved repository scope and applies only with `production` in that repository's `decide`, as today.
- Categories stay: a tag, release or publish runs only when its category is `decide` and an allow entry matches; a deploy runs only when an allow entry matches; `Real users and customer data` and credentials stay fixed `stop`. The closed grammar after the match (tag names, `gh release create` with exactly one `--repo` equal to the verified target, publish options) still applies, so an entry never widens a form `check` refuses.
- The protected-token check, the text screens and shell-syntax refusal run first, before any entry is matched.

### Results

- deny match: `denied`, Tier 3, never approvable through Decide.
- ask match: `ask`, Tier 3, approvable once through Decide like `unknown` today (the decided approval keeps its own shape rules).
- allow match: Tier 1, for the forms above and for any other command whose first word is not `git`, `gh`, `rm` or `python3 -I` of this install's scripts (the test-command rule of today).
- no match: today's classification.

### Migration

The old lists stay readable and become allow entries: `Non-production targets`, `Release targets` and `Test commands` (user) and `non-production-targets`, `release-targets` and `test-commands` (repository, approved) read as allow entries of the same scope; `production-targets` (repository) reads as production allow entries; a user-scope `Production targets` line is read and ignored, and `start` says so. The upgrade note says the lists now merge rather than replace, so a repository list that narrowed the account list no longer narrows it; narrow with `deny` instead.

Enforcer: `afk.py check`, `settings()` and `project_store.valid_autopilot` (script); `afk_setup.py` for the account lines (script). Tests: each placeholder accepts its form and refuses the near misses (an existing tag, a `-dev` version, the default branch, a protected or missing directory, an upper-case name, a body file outside the checkout); deny beats ask beats allow across all three scopes; a deny beats a built-in Tier 1 form; a refused word, a `git push` entry and an `rm` entry are ignored; a production entry from the user scope or the committed file is ignored; the committed file applies only from the main checkout at the origin head and never from a work branch; the old lists read as allow entries.

## C. Tests: the repository's declared scripts are Tier 1 (pull request 4)

In a found repository in the `user` or `project` state, on any branch, these forms are Tier 1 without being listed, bare or as the command of `heavy_run.py run [options] -- <command>`:

| Form | Condition |
| --- | --- |
| `npm test`, `pnpm test`, `yarn test` | the `package.json` of the check's folder declares a `test` script |
| `npm run <script>`, `pnpm run <script>`, `yarn run <script>` | `<script>` matches `[A-Za-z0-9:_-]{1,64}`, is declared in the `scripts` object of the `package.json` in the check's folder (work tree, decision 4), and holds none of `deploy`, `publish`, `release`, `prod`, `live` |
| `python3 -m unittest`, `python3 -m unittest <module>...`, `python3 -m unittest discover -s <dir> [-p <pattern>]` | modules match `[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*`; `<dir>` passes section A; the pattern matches `[A-Za-z0-9_*.-]{1,64}` |
| `pytest [-q] [-x] [<path>...]`, `python3 -m pytest [-q] [-x] [<path>...]` | each path passes section A's rules (a known path, or a known directory) |
| `go test <pkg>...` | `./...` or `./<relative path>[/...]` inside the checkout; flags from today's `GO_FLAG` list |
| `cargo test` | bare, or `-p <name>` with `[a-z0-9_-]{1,64}` |

- The `package.json` read follows the committed file's rules (a regular file, at most 256 KiB, no link, inside the checkout, closed JSON object), in memory only, and only the `scripts` keys are used; nothing is stored or logged.
- A repository's tests run whatever code its work tree holds, including code and `package.json` scripts the agent edited under the lease. That is the grant the owner made in 0.3.0 for listed test commands and in decision 4 here.
- The order of section B holds: the protected-token check, deny and ask entries run first, so a user can still ask or deny any of these forms.
- Commands that start with `git`, `gh` or `rm` keep their own rules. The heavy-job gate still governs a bare heavy command on hosts where it is on, and `heavy_run.py`'s own rules are unchanged.

Enforcer: `afk.py check` (script). Tests: each form with and without a declared script; a script named with a refused word; a module with a path separator; a `pytest` path that is protected or outside the checkout; `go test` with an absolute package; the strict and no-repository states refuse; a deny entry beats a declared test.

## D. Same-family review fallback without evidence for every family (pull request 5)

`merge_check.py --independent --fallback-family <family>` keeps these conditions of [afk-per-project.md](afk-per-project.md) D: a live, valid away lease (1); `<family>` is the pull request author's family and a present family (2); a `fnl-router` trigger that is present and not `security`, `permission` or `privacy` (4); and on each kind (code and security) a current-head marker whose second line is exactly the fallback reviewer line, `Reviewer: <family> (same family as the author; no other family reachable)`, optionally followed by a space and free text (5).

It drops:

- Condition 3, positive out-of-quota evidence for every other present family. Whether every other family is out of quota or unreachable is the caller's judgment (advisory, agent judgment); the marker's second line states it, and the lease records it.
- Condition 6, two models per kind when an enforcer script or instruction file changed (decision 11 of 15/11/2026 is lifted). One same-family approval per kind at the head is enough.

It prints `ok    same-family review: fallback accepted (<family>)`. `afk.py log --kind review-fallback --pr <n> --head <full sha>` stays Tier 1 and the merge procedure requires it before the merge (advisory, agent judgment). On return, the report lists every fallback merge first, each with its pull request, head and whether it changed an enforcer script or instruction file (advisory, agent judgment; the `review-fallback` records are the source).

Enforcer: `merge_check.py` (script) for conditions 1, 2, 4 and 5. Tests: the fallback passes with no quota reading at all and with every family reachable by its readings; it passes for a change to an enforcer script with one model per kind; it refuses without a lease, for another family, with a `security`, `permission` or `privacy` trigger, with a missing trigger and with a marker that lacks the line.

## E. One rule table (pull request 6)

- `afk.py rules` prints the rule table, generated from the same data the checks read (the protected list, the placeholders, the test forms, the precedence and the categories), as Markdown. `afk.py rules --effective` prints the merged allow, ask and deny entries and the decided categories that apply in the current folder, with each entry's scope.
- `skills/afk/references/rules.md` is that output, generated, with a header saying so; a test (`tests/test_afk_rules.py`) fails when the file and the output differ.
- `skills/afk/SKILL.md`, `references/lease-rules.md`, `references/decide.md`, `references/merge-gate.md` and the setup afk references (`skills/setup/references/features/afk.md`, `afk-project.md`, `afk-decisions.md`) keep their procedure and point to `rules.md` for every rule it holds, instead of restating it. Target: the always-loaded afk text (`SKILL.md` plus `lease-rules.md`) about half of today's 16.3 KB.
- The docstring rule table of `afk.py` shrinks to a pointer to `rules`.

Enforcer: the sync test (script); keeping procedure out of `rules.md` is advisory (agent judgment).

## Not changed

Default-branch writes, the merge gate and its MERGE OK receipt, the per-project limits, the categories and their fixed `stop` rows, the text screens, the decision ladder, the unknown-request approval and its shapes, push rules, the worktree rules, agent dispatch rules (`claude -p`, `codex exec`, `agy` stay Tier 3 outside the ladder's own forms), local branch merges, and the away question gate.

## What the 60 parked items would be

After all five changes, by the same causes:

| Becomes Tier 1 | Items |
| --- | --- |
| Section A (paths) | 15; in two of them the agent dispatch still parks |
| Section D (fallback) | 5 |
| Section B (commands) | 3: a preview deploy with project arguments (`wrangler pages deploy <dir> --project-name <name>`), a deploy once it has an allow entry, and a release once `git tag <version>` and `gh release create <version> ...` are allowed |
| Section C (tests) | 2: `python3 -m unittest tests.test_afk` and a declared `ci` script (which also hit memory pressure) |
| Follows the merges above | 3 tags, releases and catalog pins, once their allow entries exist |

| Still parks | Items | Why |
| --- | --- | --- |
| Owner judgment | 11 | Correct by design |
| Machine limits | 6 | afk cannot create capacity |
| Agent dispatch | 2 | Outside these changes; a candidate for a later change |
| Other | 13 | Local branch merges and a session start are outside these changes; the relay rule and the comment category are the owner's settings; the rest are fixed, redacted or unclear |

25 of the 60 (42%) would act on their own, and 3 more once the work ahead of them merges; 32 still park, 11 of them by design.

## Order of pull requests

1. This spec and the index row (no code), with a security review before any code.
2. A: paths.
3. B: allow, ask and deny entries.
4. C: declared tests.
5. D: the review fallback.
6. E: the rule table and the cut documentation.

Each code pull request carries tests for every refusal and allowance it adds, a posted code review and a posted security review (another model family when one is reachable), and MERGE OK, and merges only on the owner's yes. [CLAUDE.md](../../CLAUDE.md) states none of these rules; a pull request that changes one of its rules records this decision there.

## Open

None. The owner settled decisions 2 to 5 in this session on 16/11/2026.
