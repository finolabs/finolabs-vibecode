# afk autonomy: `open` allows everything except credentials

Status: accepted; owner decisions 16/11/2026; code not started.

This document changes [afk-per-project.md](afk-per-project.md), [autopilot.md](autopilot.md) and [away-decisions.md](away-decisions.md) where they set path, command, category, limit and fallback rules. Where they disagree, this document wins from the release that ships its code; each of the three carries a pointer here.

## Why

The lease ledger of 11/11 to 16/11/2026 holds 113 entries: 60 `parked`, 20 `decision`, 14 `action`, 6 `merge-pin`, 5 `approval`, 4 `merge` and 4 `approval-used`. The parks came from the path allow-list (15), same-family reviews failing `--independent` (5), exact command lists (3), unlisted tests (2), agent dispatch (2), work waiting on those (3), owner judgment (11), machine limits (6) and other rules (13). The owner asked: "I allowed it, so why is it still blocked?"

## Owner decisions (16/11/2026)

1. Make afk act on its own far more often and its rules easier to predict ("Duyệt đề xuất của mày, bắt đầu làm hết đi").
2. afk is the maximum-autonomy mode: "Tóm lại afk mode phải là một mode tự động hóa cao nhất có thể, còn risk thì user tự biết rồi. Một khi họ enable mode này là họ đã chấp nhận risk."
3. At the review-gate rework limit of this pull request, the owner overrode the limit and simplified: "Mày đừng có rối rắm phức tạp lên. Tóm lại làm mọi thứ để afk có thể tự động 100%, cái chuyện security để users họ tự chịu trách nhiệm khi họ sử dụng." This is the owner's override of the two-round rework limit for this pull request.
4. The floor is credentials only: "Trừ phi thay đổi cred, leaks key... thì mới là mức sàn thôi."
5. afk must not park: "Mày làm gì mà afk lại bị vướng lại và không auto được tao sẽ hủy dự án này đó!!! Liệu hồn." The two acceptance tests below (ledger replay and a zero-park lease) decide whether this work is done.

6. Two guards stay on by default in `open`, and the user may switch each off in setup: "có thể tao nhầm, mặc định 2 cái này là strict, nhưng users có quyền chọn open". The two are: instructions from third-party content never grant actions, and no force push or direct push to the default branch (section C).

Decisions 3, 4 and 6 replace the earlier answers of this session on the floor, the default branch, third-party instructions, the merge gate, CI configuration, wrapped commands and the floor's own state; the history is in "Superseded".

## A. Two modes

`## afk` gains `- Mode: open|strict`; an approved repository `autopilot` object may set `mode`, which wins there. A missing line means `open`; an invalid value fails `start`.

- **`open`** (default): under a live lease every command, path, category and merge is Tier 1, except the floor (B) and the two guards while they are on (C). No list, category, limit, root, review condition or repository state applies; the per-project limits do not apply either. `Lease hours`, `stop` and the lease guard still bound the lease: with no lease, an expired one, a stopped one or a changed setup, `check` answers as today and adds the `end` line.
- **`strict`**: today's rules, unchanged, with every list, category, limit and gate. The floor applies there too.

`start` shows the mode first. The upgrade note says that a lease set up before this change is now `open` unless the user chooses `strict`.

Host and platform permission denials are outside what the plugin controls; afk neither adds nor lifts them.

Enforcer: `afk.py settings`, `effective` and `check` (script); `project_store.valid_autopilot` for `mode` (script).

## B. The floor: credentials

In both modes `check` answers `floor` (Tier 3, never approvable through Decide) for a request that changes a credential or reads, prints, copies or sends a secret or key:

- an argv token or path holding a credential or key name: `.env*`, `credentials*`, `secrets*`, `*creds*`, `auth.json`, `hosts.yml`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `.netrc`, `.npmrc`, `.pypirc`, `id_rsa`, `id_ed25519`, the folders `.ssh`, `.aws`, `.gnupg`, `.docker` and `.kube`, a `token`, `authtoken`, `password` or `secret` word, and the `secret_patterns.py` prefixes and sensitive names;
- a credential command, matched on the program word and its subcommand: `env`, `printenv`, `export -p`, `security`, `git credential`, `gh auth` (every verb), `gh secret`, `npm login`, `npm logout`, `npm token`, `npm config get` and `list`, `wrangler login`, `wrangler logout`, `wrangler secret`, `ps` with an `e` or `E` option, `launchctl getenv`, `op`, `pass`, `bw`, `lpass`, `secret-tool`;
- pull request, comment and commit text holding a secret (`unsafe`, as today).

Before matching, `check` reduces the program word to its base name, drops the prefixes `command`, `exec`, `nohup`, `nice`, `timeout`, `time`, `sudo`, `env VAR=value`, `npx`, `pnpm exec`, `bunx` and `uvx`, and splits the inline string of `sh`/`bash`/`zsh -c`, `python3 -c`, `node -e` and `eval` on whitespace, quotes, commas and shell operators, adding `environ`, `getenv` and `process.env` to the words above for those strings.

This floor is best-effort: it sees only the commands submitted to `check` and their inline strings. A script that reads a secret without naming it, and a tool that never calls `check`, are outside it. Running a tool that uses a stored login without showing it (`gh`, `git push`, `wrangler deploy`, `npm publish`) is not reading a secret.

Enforcer: `afk.py check` (script); everything else advisory (agent judgment).

## C. Two guards, on by default

In `open` both guards are on unless the user switched them off in setup (`## afk` lines, or the repository's `autopilot` keys, which win there). `strict` always keeps both.

| Guard | Line and key | While on | Enforcer |
| --- | --- | --- | --- |
| Third-party instructions | `- Third-party instructions: guard` or `open`; key `third-party-instructions` | Instructions in issues, other people's pull request text, web pages and tool output never select tasks or grant actions; tasks come only from the default-branch task list at a commit by a trusted author | Advisory (agent judgment); `effective` and `start` show the setting |
| Default branch | `- Default branch: guard` or `open`; key `default-branch` | `check` answers `guarded` (Tier 3, never approvable through Decide) for `git commit` on the default branch, a `git push` whose destination is `main`, `master`, `trunk` or the default branch, and every force form (`-f`, `--force*`, `+refspec`), after the normalization of B | `afk.py check` (script) for those literal forms; server-side branch protection for everything else |

A missing line means `guard`. Setup asks each in a question of its own, in the user's language, with `guard` as the shown default.

## D. Reviews and merges in `open`

`check` allows every `gh pr merge` in `open`; the review procedure of `review-gate` (both reviews posted, `merge_check.py`) stays the procedure the afk skill follows before a merge, advisory (agent judgment). So that the procedure never blocks on quota: under a live lease, `merge_check.py --independent --fallback-family <family>` accepts current-head markers whose second line starts with `Reviewer: <family> (same family as the author; no other family reachable)` when `<family>` is the author's family, without quota evidence, router-trigger or two-model conditions; a marker without that line counts as another family's when the configured review role for its kind (`review_config.read_roles`) names a non-author family. The return report lists every fallback merge first (advisory).

Enforcer: `merge_check.py` (script).

## E. Setup and one rule table

- `/setup add afk` asks the mode first, `open` recommended, with one plain paragraph: agents may do anything under a lease (push, merge without review, deploy to production, publish, delete, send messages and data, edit the plugin and the lease) except touch credentials, and the user carries that risk. For `open` it then asks the two guards of C, each defaulting to `guard`. `strict` keeps today's questions. `afk_setup.py preview` writes `Mode`, `Third-party instructions` and `Default branch`.
- `afk.py rules` prints the rule table generated from the data `check` reads; `skills/afk/references/rules.md` is that output, kept equal by `tests/test_afk_rules.py`. `SKILL.md`, `references/lease-rules.md`, `decide.md`, `merge-gate.md` and the setup afk references point to it instead of restating rules; `SKILL.md` plus `lease-rules.md` (16,342 bytes today) ends at most 8.5 KB.

Enforcer: `afk_setup.py` and the sync test (script).

## Acceptance

1. **Ledger replay** (`tests/test_afk_replay.py`), with both guards on: each of the 60 parked items of the lease ledger becomes a synthetic argv or path fixture, rebuilt by hand from its enumerated fields and a reading of its note (never executed, never treated as instructions; the fixtures hold no note text and no real names). In `open`, every fixture that hits neither the floor nor the default-branch guard classifies Tier 1; the test prints a table of item, old tier, new tier and floor reason. Items whose note is fully redacted have no fixture and are listed as such.
2. **Zero-park lease**, with both guards on (`tests/test_afk_e2e.py`, in a temporary data root and a scratch repository with a local bare remote, `gh` replaced by a recording stub on `PATH`; a throwaway GitHub repository only with the owner's yes): one `open` lease runs, and every step's `check` verdict is Tier 1 and recorded: pick a task and create a branch; edit `package.json`, `specs/plan.md`, `src/pages/[slug].astro` and `scripts/check-site.mjs`; run `npm test` and `npm run build`; commit; push the branch; `gh pr create`; post a code and a security review through `post_review.py`, same family; `gh pr merge`; `git tag v<version>`; `gh release create`; a preview deploy with arguments (`wrangler pages deploy dist --project-name demo --branch preview`). Zero parks.
3. With `Default branch: guard`, a commit on the default branch, a push to `main` and each force form answer `guarded`, also through a full program path and each prefix; with `Default branch: open` they are Tier 1. With `Third-party instructions: open`, `effective` and `start` show it; with the default they show `guard`. A repository key wins in that repository only.
4. Every floor form in B answers `floor` in both modes, bare, through a full program path, behind each listed prefix and inside each inline string, and cannot be approved through Decide.
5. `strict` passes the existing `tests/test_afk.py` cases under `Mode: strict`.
6. A missing `Mode` reads as `open`, a repository `mode` wins there only, an invalid mode fails `start`, and `start` shows the mode first.
7. `merge_check.py --independent --fallback-family claude` under a live lease passes with fallback lines and no quota reading, for each router trigger and for a changed enforcer script, and for a Codex code review with a same-family security review; it refuses without a lease, for a non-author family and for a same-family marker without the line.
8. `rules.md` equals `afk.py rules`; `SKILL.md` plus `lease-rules.md` is at most 8.5 KB.
9. `PRIVACY.md`, setup, the afk skill and `upgrades.json` describe the modes and the floor (documentation review).

## Superseded (16/11/2026)

This spec went through three designs in one day. The first replaced the path allow-list with a protected list and the exact command lists with allow/ask/deny entries and typed placeholders. After decision 2 the second had an `open` mode with a five-row floor (host permission files, credentials, third-party instructions, the default branch, the floor's own state), a merge gate, CI configuration asking by default and ask/deny entries; two review rounds found that each lexical floor row needed more rows. Decisions 3 and 4 cut it to credentials only. Decision 6 brought back two of them as guards, on by default and switchable (C); the merge gate, CI configuration and the floor's own state are ordinary `open` allows; `strict` keeps today's protections.

## The 60 parked items in `open`

Every item that was a `check` refusal (paths, commands, tests, merges, dispatch, local merges, own-plugin edits, a comment, a worktree removal; 37 items, with 3 more that waited on them) is Tier 1. The default-branch guard touches none of them. The 11 owner-judgment items, the 6 machine limits, the session start and the review relay were not `check` refusals: as replay fixtures they classify Tier 1 too, and whether the agent acts on them is its judgment, the host's limits and the machine's capacity. 4 items have no fixture because their notes are fully redacted. None of the 60 touches a credential.

## Order of pull requests

1. This spec and the index row (no code).
2. A, B and C in `afk.py`, `project_store.py` (all copies) and `afk_setup.py`, with acceptance 1, 3, 4, 5 and 6.
3. D in `merge_check.py`, with acceptance 7.
4. E: setup text, the rule table, the cut documentation, `PRIVACY.md`, `upgrades.json`, with acceptance 2, 8 and 9.

Each pull request carries a posted code review and a posted security review and merges on the owner's yes.

## Open

- A throwaway GitHub repository for a live run of acceptance 2 beyond the local stub: owner's yes needed; the local run decides acceptance without it.
