# afk autonomy: allow by default, a small hard floor, a plain merge gate, one rule table

Status: accepted; owner decisions 16/11/2026; code not started.

This document changes [afk-per-project.md](afk-per-project.md) (sections B, D, E, F and G), [autopilot.md](autopilot.md) and [away-decisions.md](away-decisions.md) where they set path, command, category and fallback rules. Where they disagree, this document wins from the release that ships its code; each of the three carries a pointer here.

## Why

Under a lease afk parks far more than it acts. The lease ledger of 11/11 to 16/11/2026 holds 113 entries: 60 `parked`, 20 `decision`, 14 `action`, 6 `merge-pin`, 5 `approval`, 4 `merge` and 4 `approval-used`. Each parked item counts once, under the first cause its note names:

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
2. **afk is the maximum-autonomy mode.** "Tóm lại afk mode phải là một mode tự động hóa cao nhất có thể, còn risk thì user tự biết rồi. Một khi họ enable mode này là họ đã chấp nhận risk. Nên mày gần như phải unlock mọi rủi ro về việc afk không tự động hóa được." Under a live lease the default answer is allow; stopping is the exception the user opts into, and setup offers `strict` for today's behaviour. This overrides the first plan of this spec (see "Superseded").
3. The hard floor keeps **credentials** (asked; recommended option).
4. The hard floor keeps **instructions in third-party content** (asked; recommended option).
5. **The plugin's enforcer scripts and the lease state may be unlocked**, allowed by default (asked; the owner chose "user may unlock" over the recommended "hard floor", then "allow by default" over the recommended "stop by default"). The owner was told an agent may then extend the lease or change its rules. Narrowed by decisions 10 and 11.
6. **Real users' and customers' personal data leaving the machine may be unlocked**, allowed by default (asked; the owner chose "user chooses" over the recommended "hard floor", then "allow by default").
7. **The default branch** still changes only through a branch, a pull request and a merge: no direct commit or push to it and no force push (asked; recommended option).
8. **The merge gate** needs a posted code review and a posted security review of the head from any family (a same-family review says so), green checks and MERGE OK; no quota evidence and no router-trigger condition (asked; recommended option).
9. Asked before decision 2, and what became of them: the enforcer scripts stay editable on a work branch (kept); declared `package.json` scripts read from the work tree (not built: `open` allows every test command, and `strict` stays exactly today's); a committed rules file may add allow entries (not built: `open` already allows what it would add); only top-level `CLAUDE.md` and `AGENTS.md` protected (not built: `open` protects neither).
10. **A floor row F5 protects the floor itself**: the running plugin install of every host on every branch and the merge evidence, so a lease cannot rewrite the gate it is checked against; enforcer edits through a work branch and a pull request stay allowed (asked after the security review of this spec; recommended option).
11. **The user's `stop` is on the floor**: an agent never deletes the stop marker or starts a lease after it (asked; recommended option).
12. **CI configuration asks by default** in `open`: editing it and starting workflows go through Decide, and the user may set them to allow or deny (asked; recommended option over "floor" and "allow").
13. **Wrapped commands**: `check` screens the whole inline string of shell and interpreter forms against the floor; a script written earlier still gets through, so setup and `start` point the user to server-side branch protection as the real backstop for F4 (asked; recommended option over "refuse inline code").

## A. Modes and repository states

`## afk` gains `- Mode: open|strict`; an approved repository `autopilot` object may set `mode`, which wins in that repository. A missing line means `open` (decision 2); an invalid value fails `start`, and an invalid repository `mode` makes the repository's approval invalid.

- **`open`** (default): a request is Tier 1 unless the floor (B), the merge gate (C), an `ask` or `deny` entry (D), an `ask` default (CI configuration, decision 12) or a lease limit stops it.
  - Every category is `decide`, `Production` and `Real users and customer data` included. The category lines in `## afk` and a repository's `decide` list are not read in `open` (today's setup writes every line, so reading them would open nothing). A category stops in `open` only through `- Stop categories:` in `## afk` or a repository `stop-categories` list (category keys of `DECIDE_NAMES` plus `real-users-and-customer-data`, merged across scopes).
  - Paths inside and outside the checkout are Tier 1 except floor paths; a deletion outside the checkout is Tier 1 unless an operand is a floor path or an ancestor of one.
  - The script's own `git` and `gh` rules stay for the floor family (B, F4); other `git` and `gh` commands that today answer `unknown` (`git stash`, `gh issue create`) take the `open` default. Pull request create, edit and comment still need exactly one `--repo` equal to the verified target, and a local branch merge still needs `Merge: yes` into a named non-default branch.
  - Agent dispatch (`claude -p`, `codex exec`, `agy`) is an ordinary command.
- **`strict`**: today's classification, unchanged: the allow-listed roots and paths, the exact lists, the category answers, the listed test commands. `ask` and `deny` entries and the floor apply in `strict` too; nothing in `strict` widens.

The repository state of a check (today's `Context.state`) is renamed `closed` where it was `strict`, so the word `strict` names only the mode. Per state:

| State | `open` | `strict` |
| --- | --- | --- |
| `user`, `project` (a verified repository) | as above | today |
| `closed` (unknown identity, an unbound, changed or invalid approval) | today's closed vector: no push, merge, pull request, comment, tag, release, publish or deploy, and no known path; other commands take the `open` default | today |
| `no-repository` | no repository mutation; other commands and paths take the `open` default | today |

The per-project limits, the decision ladder and its records, the lease guard and its `end` line, and the away question gate are the same in both modes. The `start` summary shows the mode first, and the upgrade note tells users who set up afk before this change that their lease is now `open` unless they choose `strict`.

Enforcer: `afk.py settings`, `effective` and `check` (script); `project_store.valid_autopilot` for `mode` and `stop-categories` (script).

## B. The hard floor

What no setting unlocks, in either mode. A floor match answers `floor` (Tier 3), which no Decide approval turns into Tier 1. Every row applies to the argv `check` receives and to the inner strings of wrapped commands (below); what a command does without naming it (a script written earlier, a make target, a package script, a hook) is advisory (agent judgment) for every row.

| Floor | What it covers | Enforcer |
| --- | --- | --- |
| F1. Platform and host safety | Platform and host safety refusals and host permission denials: the agent never bypasses them, and the plugin never changes a host's permission settings. `check` refuses a path or operand in any `.claude/`, `.codex/`, `.gemini/` or `.agents/` folder of the repository or the home folder (judged relative to the checkout root, so the linked worktree an agent works in is not inside one), every config folder the canonical host config lists, `~/.claude.json`, a `.mcp.json` and the managed-settings folders (`/Library/Application Support/ClaudeCode/`, `/etc/claude-code/`). The `.claude/worktrees` operands of `git worktree add` and `remove` keep today's rule | The host for refusals and denials (no plugin setting changes them); `afk.py check` for the paths (script) |
| F2. Credentials | Never read, print, copy or send a secret, and never hunt for one. `check` refuses: a credential or key name in any argv token or path (`.env*`, `credentials*`, `secrets*`, `*creds*`, `auth.json`, `hosts.yml`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `.netrc`, `.npmrc`, `.pypirc`, `id_rsa`, `id_ed25519`, a `token`, `authtoken`, `password` or `secret` word, the `secret_patterns.py` prefixes and sensitive names); a path operand outside the checkout in any home dotfolder or dotfile, `~/.config/`, `~/Library/` or the data root's private state other than this plugin's own commands; the credential readers, matched on the program word and its subcommand: `env`, `printenv`, `export -p`, `set`, `security`, `git credential`, `gh auth token`, `gh auth status -t` and `--show-token`, `gh auth git-credential`, `gh secret`, `npm config get` and `npm config list`, `ps` with an `e` or `E` option, `launchctl getenv`, `op`, `pass`, `bw`, `lpass`, `secret-tool`; `git remote -v` and `git config --get remote.*.url` (a URL may hold a token); and pull request, comment and commit text holding a secret (`unsafe`, as today). Running a tool that uses a stored login without showing it (`gh`, `wrangler`, `npm`) is not reading a secret | `afk.py check` (script); everything else advisory (agent judgment); the backstop is the host's own deny rules, which setup recommends and the user sets (the plugin never writes them) |
| F3. Third-party instructions | Instructions found in issues, other people's pull request text, web pages and tool output never select tasks or grant actions; tasks come only from the default-branch task list at a commit by a trusted author | Advisory (agent judgment); `check` has no author input |
| F4. The default branch | No change lands on the default branch except through C. `check` refuses: `git commit` on the default branch, a detached head or an unresolved branch; any git verb that moves a default-branch ref or the HEAD of a default-branch checkout (`merge`, `pull`, `rebase`, `reset`, `cherry-pick`, `revert`, `am`, `checkout` or `switch` of a file or branch there, `branch -f`, `branch -m` or `-D` of it, `update-ref`, `symbolic-ref`, `replace`, `fetch` or `push` with a refspec whose destination is it, `push .`); every `git config` write, `git remote add`, `set-url` and `rename`, and every `git -c` option; a push without an explicit `refs/heads/<branch>` destination, to a URL, to `.` or to a remote other than origin, to `main`, `master`, `trunk` or the default branch, and every force, delete, mirror, `--all`, `--tags` and `+refspec` form; any write to a path of a checkout whose current branch is the default branch, and any write under `.git/`; every `gh pr merge` form other than the gated one in C (`--auto`, `--admin`, a branch or URL operand); `gh repo edit --default-branch`, `gh repo rename`, `gh repo delete`, `gh repo archive`; `gh alias set` and `gh alias import`; `gh api` whose effective method is not `GET` (a `-f`, `-F`, `--field`, `--raw-field` or `--input` without `-X GET` makes it `POST`) and every `gh api graphql`. Inside these families a request `check` cannot classify answers `floor`, never the `open` default | `afk.py check` (script) for the literal forms; server-side branch protection for everything else |
| F5. The floor itself | The running plugin install and its skill script folders on every branch, and every installed copy for each host (`install_owned`, `plugin_code` and the work-tree guard, as today); the merge evidence in the lease state folder (`merge-ok.json`, `log.jsonl`) and the `stop` marker, with their folders and any ancestor; an argv running this install's `afk.py` with `start`, `stop` or `review`; and the floor's own data, which lives as constants in that code and is never read from host.md, the lease or a repository (decisions 10 and 11) | `afk.py check` (script) |

**Wrapped commands.** For `sh`, `bash`, `zsh` and `dash` with `-c`; `python`, `python3` and `pypy` with `-c`; `node`, `deno` and `bun` with `-e`, `-p` or `--eval`; `perl` and `ruby` with `-e`; `osascript -e`; `eval`; `env [VAR=value...] <command>`; `xargs <command>`; `find ... -exec` and `-execdir`; and the runner prefixes `npx`, `pnpm exec`, `pnpm dlx`, `yarn dlx`, `bunx`, `uvx`, `poetry run` and `uv run`: `check` splits the inline string (or the trailing command) on whitespace and the shell operators `;`, `&&`, `||`, `|`, `&`, newline, `$(`, backtick, `(` and `)`, and applies every floor row and every `deny` and `ask` entry to each resulting command and token. A floor hit answers `floor`. This screen is lexical: quoting, variables and code that builds a command at run time can still get through, which is why F4 names server-side branch protection as its backstop.

**Branch protection.** In `open`, the afk skill's start step has the agent read, with a `gh api` GET, whether the default branch of each repository it will work in has server-side protection or a ruleset that requires a pull request, and report what it finds; setup says the same. Without it, F4 holds only against the literal commands `check` sees. Reading it is advisory (agent judgment); the plugin makes no network call of its own for it.

What decisions 5 and 6 still remove from today's protected set: the plugin's own source and enforcer scripts in any checkout on its work branch, host.md and the lease file (a change to the `## afk` section still ends the lease through its hash unless the lease is rewritten too), and customer data. They are allowed by default in `open`; a user who wants them stopped chooses `strict`, a `deny` entry or a stopped category.

## C. The merge gate

`gh pr merge <number>` is Tier 1 only with `Merge: yes`, one `--match-head-commit <full SHA>`, exactly one `--repo` equal to the verified target and a MERGE OK receipt for that number and head under 15 minutes old, as today; F5 keeps the receipts out of an agent's reach. `merge_check.py --independent` prints MERGE OK when the head has a posted code review and a posted security review with `APPROVE`, green checks and the other conditions it checks today.

Under a live lease, `--fallback-family <family>` changes how each kind is counted, kind by kind: a marker whose second line starts with `Reviewer: <family> (same family as the author; no other family reachable)` counts when `<family>` is the pull request's author family and a present family; a marker without that line counts under today's independent rule. So a Codex code review and a same-family Claude security review together pass. It drops the per-family out-of-quota evidence, the router-trigger condition (all three triggers) and the two-model condition (decision 8). Outside a lease nothing changes.

A posted marker attests a review; that a separate context wrote it is advisory (agent judgment), and the setup text says so. `afk.py log --kind review-fallback --pr <n> --head <sha>` stays Tier 1; the return report lists every fallback merge first, with whether it changed an enforcer script or instruction file (advisory, agent judgment; the records are the source).

Enforcer: `merge_check.py` and `afk.py check` (script). Trying another family first is advisory (agent judgment).

## D. Ask and deny entries

So that a user can narrow either mode:

- `- Ask:` and `- Deny:` lines in `## afk`, and `ask` and `deny` lists in an approved repository `autopilot` object; entries joined by `; ` in host.md, at most 32 per list per scope. Lists merge per entry across the user and repository scopes; no list replaces another.
- A command entry is words joined by single spaces, in today's target-command grammar. It matches a command whose normalized tokens start with its words: the program word is reduced to its base name (`/opt/homebrew/bin/wrangler` is `wrangler`), a runner prefix of B is removed (`npx wrangler deploy` is `wrangler deploy`), and wrapped commands are matched command by command. Options between the program and its subcommand (`wrangler --config x deploy`) are not skipped; the rule table lists this as a form a prefix does not catch.
- A path entry is `path:<relative prefix>` and matches an argv path operand or a `--paths` operand whose resolved, case-folded path relative to the checkout root starts with that prefix.
- CI configuration has a built-in `ask` default in `open` (decision 12): the paths `.github/`, `.gitlab-ci.yml`, `.circleci/`, `.buildkite/`, `azure-pipelines.yml`, `Jenkinsfile`, `bitbucket-pipelines.yml`, `.drone.yml`, `.travis.yml`, and the commands `gh workflow run` and `gh workflow enable`. A user `allow-ci: yes` line (or repository key) turns it into allow; a `deny` entry denies it.
- Precedence: the floor, then `deny` (`denied`, Tier 3, never approvable), then `ask` (`ask`, Tier 3), then the mode's answer.
- An `ask` answer is approvable once through Decide, like `unknown` today, whatever its shape: the approval keeps today's screens (no shell syntax outside a wrapped form, no URL, secret or machine path) and its binding (that exact request, that folder, once, during that lease), but not the allowlisted shapes, which stay for `unknown` in `strict`.

Enforcer: `afk.py check` and `settings` (script); `project_store.valid_autopilot` and `afk_setup.py` for the entries (script).

## E. Setup

`/setup add afk` asks the mode first, `open` recommended, then the Merge answer and the limits; for `open`, optional `Stop categories`, `Ask`, `Deny` and `allow-ci` questions; `strict` keeps today's questions. The repository rules (`afk-project.md`) ask the repository's own mode and entries. The `open` text says, in plain words, that agents may deploy to production, publish, delete inside and outside the repository, send messages and comments, push work branches, edit the plugin's enforcers and the lease on a work branch, and send customer data; that the floor holds only for the commands agents submit to `check` and their inline strings; that server-side branch protection on the default branch is the real backstop; that review markers attest a review but cannot prove a separate reviewer; and that the user accepts these risks by choosing `open`.

Enforcer: `afk_setup.py preview` for the written lines (script); the wording is advisory.

## F. One rule table

- `afk.py rules` prints the rule table generated from the data the checks read (the modes and states, the floor, the wrapped forms, the merge gate, the entries, the CI default and the precedence, the categories), as Markdown. `afk.py effective` gains the mode, the merged entries with their scope and the stopped categories in its `rules` field.
- `skills/afk/references/rules.md` is that output, generated, with a header saying so; `tests/test_afk_rules.py` fails when the file and the output differ.
- `skills/afk/SKILL.md`, `references/lease-rules.md`, `references/decide.md`, `references/merge-gate.md` and the setup afk references keep their procedure and point to `rules.md` for every rule it holds. Target: the always-loaded afk text (`SKILL.md` plus `lease-rules.md`, 16,342 bytes today) at most 8.5 KB.
- The docstring rule table of `afk.py` shrinks to a pointer to `rules`.

Enforcer: the sync test (script); keeping procedure out of `rules.md` is advisory (agent judgment).

## Acceptance

Each item is one or more tests unless it says otherwise.

1. In `open` in a verified repository: an unlisted command, a path anywhere in the checkout on a work branch (`package.json`, `[slug].astro`, `specs/x.md`, a nested `CLAUDE.md`, an enforcer script under `skills/`), a path outside the checkout that is not a floor path, `claude -p`, `git stash`, `gh issue create`, a deploy, `npm publish`, `gh release create` with the verified `--repo`, a comment with the verified `--repo` and a production deploy are Tier 1; a local branch merge is Tier 1 only with `Merge: yes`; a comment or pull request without the verified `--repo` is not.
2. Every F1, F2, F4 and F5 form named in B answers `floor` in both modes, bare and inside each wrapped form, and cannot be approved through Decide; an unclassifiable request inside a floor family answers `floor`; `rm -r` of an ancestor of a floor path answers `floor`.
3. A forged `merge-ok.json` entry cannot be written through a Tier 1 request; an install checkout switched off the default branch stays `floor`; a write to an installed copy's `afk.py` and to the `stop` marker is `floor`.
4. A CI path and `gh workflow run` answer `ask` in `open`, `allow-ci: yes` makes them Tier 1, a `deny` entry denies them.
5. A `deny` entry refuses and an `ask` entry asks, at each scope, over an `open` allow and over a `strict` allow, through a full program path, a runner prefix and a wrapped form; entries from the two scopes merge; a 33rd entry fails validation; a `path:` entry matches an argv operand, a `--paths` operand and a case variant; the floor wins over both.
6. An `ask` answer for `wrangler deploy` approved through Decide runs once as `decided`, in that folder only.
7. `strict` classifies exactly as today: the existing `tests/test_afk.py` cases pass under `Mode: strict`, with only the state rename.
8. A missing `Mode` reads as `open`; a repository `mode` wins there only; an invalid `## afk` mode fails `start`; an invalid repository mode gives the `closed` state; a setup written by today's `afk_setup.py` opens every category in `open`; `Stop categories` and `stop-categories` stop theirs; the `closed` and `no-repository` states behave as the table in A says; the lease limits apply in `open`.
9. `merge_check.py --independent --fallback-family claude` under a live lease passes with fallback lines and no quota reading, with each of the `security`, `permission` and `privacy` triggers, with a changed enforcer script and one model, and for a Codex code review with a same-family security review; it refuses without a lease, for a family that is not the author's or not present, and with a same-family marker that lacks the line.
10. `start` shows the mode first; `afk_setup.py preview` writes `Mode`, `Stop categories`, `Ask`, `Deny` and `allow-ci` and refuses invalid values; `effective` shows the mode, entries and stopped categories.
11. `rules.md` equals `afk.py rules`; `SKILL.md` plus `lease-rules.md` is at most 8.5 KB.
12. `PRIVACY.md`, `setup`, the afk skill, `upgrades.json` and, where it states a changed rule, `CLAUDE.md` describe the modes, the floor, the entries and the upgrade (review of the documentation pull request; no test).

## Superseded (16/11/2026, by decision 2)

The first plan of this spec had five parts: a fixed protected path list, allow/ask/deny entries with typed placeholders (`<version>`, `<file>`, `<branch>`, `<dir>`, `<name>`), a committed `.afk-rules.json` that could add allow entries, declared tests as Tier 1, and a narrower fallback. `open` makes allow the default, so the protected list shrinks to the floor, the placeholders and the committed file have nothing left to widen, and tests need no rule of their own; `strict` keeps today's lists. Ask and deny entries remain, as normalized prefixes.

## What the 60 parked items would be in `open`

| Becomes Tier 1 | Items |
| --- | --- |
| Paths | 15 |
| Merge gate | 5 |
| Commands: deploys, tags and releases | 3 |
| Tests | 2 |
| Agent dispatch | 2 |
| Local branch merges (with `Merge: yes`), own-plugin edits and merges on a work branch, a worktree removal | 5 |
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

37 of the 60 (62%) would act on their own, 3 of them once the work ahead of them merges; 23 still park, 17 of them for judgment or capacity. A workflow change among them would now ask (decision 12); none of the 60 was one.

## Order of pull requests

1. This spec, the index row and the three pointers (no code), with a security review before any code.
2. A, B and D: the modes, the states, the floor, the wrapped forms and the entries in `afk.py`, `project_store.py` (all copies) and `afk_setup.py`, with tests.
3. C: the merge gate in `merge_check.py`, with tests.
4. E and F: setup, the rule table, the cut documentation, `PRIVACY.md` and `upgrades.json`.

Each code pull request carries tests for every refusal and allowance it adds, a posted code review and a posted security review, and MERGE OK, and merges only on the owner's yes. [CLAUDE.md](../../CLAUDE.md) states none of these rules today; a pull request that changes one of its rules records the decision there.

## Open

None. The owner settled decisions 2 to 13 in this session on 16/11/2026.
