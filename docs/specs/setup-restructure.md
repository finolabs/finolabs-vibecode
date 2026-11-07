# Setup restructure: a short core, features on demand, instructions inside (release 0.2.0)

Status: implemented; release 0.2.0 core, features, Quick/Advanced companions and guarded instructions writer have local tests; live-host interviews and Codex word passing remain unverified.

## Why

Reading `fnl-setup` and `fnl-setup-instructions` on 2026-11-07, against what the plugin now does, showed seven problems:

1. `fnl-setup/SKILL.md` is 33,793 bytes in 132 lines, five of them over 1,500 characters (quota, metrics, compaction,
   snapshot), and all of it loads on every run though a user usually wants one thing. The repository's convention is to
   disclose reference material into `references/`.
2. Three questions come before any work (scope, set up or check, beginner or mode), then twenty-odd separate consents
   (the inventory below). A new user meets a wall of prompts.
3. The two skills name the same idea differently: `fnl-setup` says machine and project, `fnl-setup-instructions` says
   user and project.
4. New features have no place: agent roles, review posting, the judge and TypeSafe guidance (`agent-roles.md` part J);
   the review-tools section and the steward explanation are stale.
5. Section labels A to G run out of order across the two scopes.
6. The two skills are not connected: setup ends by asking the user to type a second command (on Codex, immediately),
   and the copies of `interview.md` and `work-tracking.md` must be kept identical by CI.
7. `fnl-scan-agents` (4,451 bytes) and `fnl-set-mode` (3,940 bytes) are thin wrappers over scripts that only setup, ask
   and delegate point to.

## Decisions settled (owner, 2026-11-07)

- Instructions become a component of `fnl-setup`; the skill `fnl-setup-instructions` is removed in the same release
  without a deprecation period (the owner exception recorded in `agent-roles.md`).
- `fnl-scan-agents` and `fnl-set-mode` fold into `fnl-setup` as subcommands.
- The words are user scope (everything under the user's account: host config, consent, user-level instruction files) and
  project scope (one repository). "Machine" is retired from the text.
- The shape is a short core plus features loaded on demand, each consent still asked on its own.
- A project-scope default for roles or the judge is not part of this work.
- The release is 0.2.0.
- The question "set up, or check?" on a bare run is dropped; Check is `/fnl-setup check`, and a bare run says in one
  line where it is.
- Declined features are remembered (part C) so a later bare run does not ask again; an explicit `add <feature>` always
  asks again.

## A. Entry and commands

`/fnl-setup` takes an optional first word, documented in the skill's `argument-hint`:

| Command | Does |
| --- | --- |
| `/fnl-setup` | the core path (part B) for the chosen scope, then the menu (part C) |
| `/fnl-setup add <feature>` | one feature on its own |
| `/fnl-setup instructions` | the instructions component (part D) |
| `/fnl-setup check` | Check, per scope and per feature (read-only) |
| `/fnl-setup scan` | the agent inventory refresh (the old `fnl-scan-agents`) |
| `/fnl-setup mode [args]` | Delegation mode and Routing (the old `fnl-set-mode`) |

On Codex the user types `$fnl-setup <word>`. Whether Codex passes the word to a skill is unverified, so the skill also
accepts a plain sentence ("add quota", "set up my instruction files"). A sentence only selects what to present; it never
answers a consent question. A sweeping or ambiguous sentence ("set up everything") gets one clarifying question and
opens the core path, never several features at once.

The skill stays user-invoked. On Claude Code that is `disable-model-invocation: true`, which a test asserts. Codex and
Antigravity have no equivalent flag in this repository today; whether they honour one is unverified and recorded as a
limitation in the README. Because the `description` is widened to name both groups of triggers (host configuration and
instruction files), it stays short and states that the user runs it.

## B. The core path

A fixed, short list of decisions per scope. The final read-back covers **inert facts only** (what will be shown or
written that grants nothing). A step that grants something keeps its own question in every mode, beginner and quick
included, with no default.

- **User scope**: (1) show the effective data root and whether to keep it; moving it is its own question, and the copy
  is a second one; (2) the agent scan (`scan`) with its model confirmation and preview; (3) Delegation mode and Routing
  (`mode`), including the guideline on or off; arming `auto` and the auto gate are each their own question; (4) record
  settled decisions in the user's knowledge base when their instructions name one (through the access those
  instructions approve; failed writes are reported); (5) a read-back and one yes for the inert items; (6) the report and
  the closing "After your first result" list with companion reminders.
- **Project scope**: (1) the repository facts (look first); (2) the `.finolabs/` exclude line; (3) the `## Agent skills`
  block; (4) workflow detection; (5) a read-back and one yes; (6) the report.

A bare invocation asks one scope question (user, project, both), recommendation first, then runs the core. The beginner
path and Quick or Advanced modes apply to the core only: beginner and Quick take defaults for inert items and write after
one confirmation; Advanced asks each inert item. The Preferences "effort" and routing handling lives in `mode`.

## C. Features

Each feature is a file under `references/features/` loaded only when the user picks it, from the menu that ends the core
(each item with one line on what it does and costs, a neutral Yes and No per item, none preselected) or by
`add <feature>`:

| Feature | Scope | Holds |
| --- | --- | --- |
| `delegation` | user | host template fill, test-command grants for Antigravity |
| `roles` | user | agent roles, the judge choice and TypeSafe guidance, review posting (`agent-roles.md` parts B, D, I, J) |
| `quota` | user | the on-demand quota reading and its preview |
| `metrics` | user | usage metrics consent and retention, project progress, the process snapshot, the Antigravity hook |
| `compaction` | user | native threshold plan and the Antigravity stop |
| `companions` (was `review-tools`, section F) | user | review instruments and companion skills (questions and recommendations only, nothing installed) |
| `project` | project | work tracking settings, project label |

A feature starts by naming what it needs from another feature and asks that prerequisite as its own consent; declining
it ends the dependent feature and never records consent as given. The judge defaults to `host` when `roles` is never
run. A declined feature is recorded as `declined` in the canonical host config, distinct from any consent, and a bare
run does not offer it again until the user asks.

### Consent inventory

Every consent below keeps its own neutral Yes and No (none preselected), is asked once, and has exactly one home.

| # | Consent | Today (`fnl-setup` section) | New home | Prerequisite |
| --- | --- | --- | --- | --- |
| 1 | Move the data root; copy to the target | Data location | core, user | none |
| 2 | Write Delegation mode and Routing values | Preferences | core `mode` | none |
| 3 | Arm `auto`; the auto gate | `fnl-set-mode` | core `mode`, own questions | 2 |
| 4 | Write the agent scan section; confirm models | A | core `scan` | none |
| 5 | Fill host config; each Antigravity test-command grant | A | `delegation` | 4 |
| 6 | Quota probe opt-in; exact-path preview | Quota probe | `quota` | 4 |
| 7 | Judge choice (Jev, host, none) | route judge | `roles` | none |
| 8 | Instruction check may send lines to the judge | route judge, second question | `roles` | 7 not none |
| 9 | Roles; review posting per family (token or allow-rule) | `agent-roles.md` J | `roles` | 4 |
| 10 | Usage metrics and retention | F | `metrics` | hooks installed |
| 11 | Antigravity metrics hook write | F | `metrics` | 10 |
| 12 | Project progress on or off | project progress preference | `metrics` | 10 |
| 13 | Process snapshot | Agent snapshot | `metrics` | 10 |
| 14 | Native threshold help; the value; the plan approval (three) | Compaction suggestion, plan approval | `compaction` | none |
| 15 | Antigravity compaction stop; its preview approval (two) | Compaction stop | `compaction` | Antigravity present |
| 16 | `.finolabs/` exclude line | B | core, project | none |
| 17 | `## Agent skills` block write | C | core, project | none |
| 18 | Workflow detection confirmation | Workflow detection | core, project | none |
| 19 | Ledger name; task file (two) | Work tracking settings | `project` | 10, 12 |
| 20 | Project label | Project label | `project` | 10 |
| 21 | Instruction-file writes (one per file) | `fnl-setup-instructions` | instructions component | none |

Review tools and companions (today's E and G) install nothing, but section F gives companions a question process, so rows 22 to 24 below cover it.

| # | Consent | Today (`fnl-setup` section) | New home | Prerequisite |
| --- | --- | --- | --- | --- |
| 22 | Companion selection (Quick: one multi-select question; Advanced: skipped, each companion is interviewed) | `fnl-setup` | `companions` | none |
| 23 | Per-companion "Show me how to install" and "Not now" (Quick: at most one per selected companion, at most four; Advanced: after its interview) | `fnl-setup` | `companions` | none; a Yes only prints the pinned install command and records nothing, a No records nothing (answering No to row 22 alone records `companions: declined` with `setup_features.py`) |
| 24 | Advanced review-tool recommendation (same Yes and No shape as row 23) | `fnl-setup` | `companions` | none |

### Size limits (enforced by a test)

`SKILL.md` at most 70 lines and 10,000 bytes; each feature file at most 80 lines and 8,000 bytes; no line in any of
them over 600 characters. The budget for a bare run is a static sum: `SKILL.md` plus every reference the core path names
(interview rules, work-tracking look-first, the core feature text) at most 15,000 bytes, against 37,549 bytes today
(`SKILL.md` plus `interview.md`).

## D. The instructions component

`/fnl-setup instructions` runs what `fnl-setup-instructions` does today, from `references/instructions/`
(`contract-template.md`, `hosts.md`, the work-tracking block text): ask the scope, explore the existing files, draft,
show a diff for every file, write only after a yes per file, `AGENTS.md` as the project source with an include in
`CLAUDE.md`, no machine settings in instruction files. The project-scope `## Work tracking` block gains the `Outcome`
line (`agent-roles.md` part J). The core ends by offering the component in the same session (neutral Yes and No) instead
of sending the user to another command. There is one `interview.md` and one `work-tracking.md` afterwards.

The writes become script-enforced. `instructions_write.py` (new, `preview` and `apply --digest`, like the other setup
scripts) takes the drafted content, shows the diff and a full digest, and on apply: refuses a symlink and any target
outside the allowed set (the user-level files `hosts.md` lists, and files in the repository root), refuses when the
content digest differs from the one shown, writes atomically, and makes a backup that never overwrites an earlier one
(`<file>.bak-YYYYMMDD`, then `-2`, `-3`). Drafted content is the template plus the user's answers, never text copied from
repository files.

The skill's `description` names both groups of triggers; a test checks that it does, since no prompt fires a
user-invoked skill implicitly.

## E. Removals, moves and compatibility

Removed in 0.2.0: the skills `fnl-setup-instructions`, `fnl-scan-agents` and `fnl-set-mode`. CHANGELOG entries under
Removed give the consumer action for each (`/fnl-setup instructions`, `/fnl-setup scan`, `/fnl-setup mode`).

Script moves: `agent_scan.py` moves to `skills/fnl-setup/scripts/`; the `data_root.py`, `quota_probe.py` and `mode.py`
copies in the removed skills are deleted and the CI copy groups in `validate.yml` updated. The folded scripts keep their
preview-and-digest behaviour.

Consumers to update (none is optional): `fnl-delegate` (its `SKILL.md` and `references/{agents,models,modes,host-template}.md`;
used standalone it says to fill the inventory by hand), `fnl-ask` (map, contents, start and explain references and the skill
count), `fnl-setup/references/{check,companions}.md`, the README, CONTRIBUTING, `docs/diagrams`, the manifests,
`build-parity-plugins.sh`, `check-references.py` and its tests, `checkup.py` messages, other specs that name the old skills,
the evals `parity-interview-ours`, `parity-interview-with-grilling`, `quality-fnl-set-mode-env-override`,
`quality-fnl-setup-instructions-interview`, `quality-fnl-ask-contents` and `quality-fnl-ask-start`, and the tests
`test_agent_scan`, `test_data_root`, `test_delegation_mode`, `test_instruction_standard`, `test_quota_probe`,
`test_work_tracking_skills` and `test_check_references`.

The removal of `fnl-setup-instructions` ships after the component and `instructions_write.py` are built
(`agent-roles.md` part H); the other two are removed in the same change that adds `scan` and `mode`.

## F. Quick and Advanced modes, and companion questions (owner, 2026-11-07)

Owner direction: a recommendation without a question process leaves the user nothing to decide with. The detailed mode
is renamed **Advanced**; **Quick** keeps only what the plugin needs to work well; everything that widens it moves to
Advanced. Companion skills get a real question process in both.

Decisions settled (owner, 2026-11-07):

- **Quick** asks the inert items once with their recommended defaults, plus **one multi-select companion question**:
  "What do you do with this plugin?" with choices (writing Vietnamese for readers, delegating work to Antigravity,
  drawing architecture or flow diagrams, mind maps and outlines, none of these); several may be chosen. Each choice
  selects the companions whose condition it matches. Quick then presents each selected companion with one line of reason
  and its install command, and the user answers a neutral Yes and No per companion (none preselected), worded "Show me
  how to install" and "Not now", so a Yes never means "install it for me". **A Yes only prints the pinned install
  command and records nothing; a No records nothing. Answering "none of these" to the multi-select records
  `companions: declined` through `setup_features.py`, so a bare run does not ask again; `add companions` always asks.**
  Installing stays the user's act; no choice installs anything. The Quick inert items and the question count are rows 22
  and 23 of the consent inventory (Quick adds at most five companion questions: one selection plus one per selected
  companion).
- **Advanced** asks, per companion, a short interview: what the companion does for this user, a concrete example in
  their stack, what it costs or sends (telemetry, fonts, accounts), the fallback the plugin keeps without it, and
  then the same neutral Yes and No. It also holds the other widening features: roles and judge, quota, metrics,
  compaction, project settings, and the review-instrument recommendations (row 24).
- **Renaming**: the word "detailed" becomes "Advanced" in `fnl-setup` (including section B above), `plain-language.md`,
  `fnl-ask`, README, the evals and the tests that pin it (`tests/test_native_sweep.py` splits on "Otherwise
  **detailed**" and moves with the text); the beginner path stays as it is and takes the Quick defaults without the
  companion question. The feature `review-tools` is renamed `companions`; its file `references/features/companions.md`
  holds the procedure and `references/companions.md` stays the data file.
- **Companion list** (`references/companions.md`): `agybird`, `vietnamizer`, `diagram-design` stay; **`markmap`**
  (mind maps and outlines) is added after the source, license and install command are checked against its official
  repository at writing time and recorded in the file with the check date, shown to the user next to the install
  command; install commands are pinned to a released version or tag where the source offers one and say so when it
  does not. The question text, the condition that selects the companion in Quick and the data note live in a second
  table of the same file (one row per companion, each line under 600 characters), so rows stay data.
- **Consent**: the Quick question and every Yes and No follow the consent rules in `references/interview.md` and
  `SKILL.md` (neutral choices, none preselected, a default or timeout never counts as a yes). A sentence such as
  "install everything" never answers a companion question.
- **Enforcer**: the selection table lives in data; a test asserts each companion row has its question, condition,
  install command, check date and data note, that Quick asks exactly one multi-select question for companions, and that
  no script or command installs a companion. The questioning itself is agent judgment (advisory).

Acceptance additions: the size limits of section C hold after the rename and the added rows; `test_native_sweep`
and `test_agent_scan` stay green; the consent inventory lists rows 22 to 24 and Quick's question count; the README table
of modes says Quick and Advanced; `setup_features.py` accepts `companions` and refuses an unknown name.

## Not in scope

A project-scope default for roles or the judge; changing what any other script writes, its previews or digests; new
consents; the dashboard; moving existing data (host config stays where it is).

## Acceptance

- The size limits of part C hold, checked by a test, including the static budget for a bare run.
- The consent inventory is the oracle: a test lists each row's consent sentence and checks it appears exactly once, in
  its home, never in the core read-back; quick and beginner modes still ask rows 1, 3, 5, 9, 11 and 21 on their own.
- Prerequisites: declining one ends the dependent feature without recording consent; a declined feature is recorded
  distinctly and an explicit `add <feature>` asks again.
- `scan` and `mode` still refuse to write without the preview digest (behaviour tests on the folded scripts).
- `instructions_write.py` refuses a symlink, an out-of-scope target and a digest mismatch, never overwrites a backup, and
  its content comes from the template and the answers (tests, plus the existing interview eval for the flow).
- One eval per entry form: slash command, `$` with a word, `$` without a word (plain sentence), including that a
  sweeping sentence gets one clarifying question and a sentence never answers a consent.
- The Claude flag `disable-model-invocation: true` is asserted by a test; the Codex and Antigravity limitation is in
  the README.
- The three old skills are gone with every consumer in part E updated and the counts correct; `check-references.py`,
  the manifests test and the copy checks are green.
- The vocabulary is user scope and project scope throughout; `check.md` reports each feature as `configured`, `missing`
  or `unverified` (the words of `agent-roles.md` J), including roles, judge and posting.

## Open decisions

1. Whether `scan` and `mode` keep thin alias skills for one release (the default here is no alias).
2. Whether Codex passes a word after `$fnl-setup`; until verified, the plain-sentence path is the contract.
