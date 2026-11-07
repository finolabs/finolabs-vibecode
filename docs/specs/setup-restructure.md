# Setup restructure: a short core, features on demand, instructions inside (release 0.2.0)

Status: accepted; owner decisions recorded on 2026-11-07; ships in 0.2.0 with the agent roles work; implementation not started.

## Why

Reading `fnl-setup` and `fnl-setup-instructions` on 2026-11-07, against what the plugin now does, showed seven problems:

1. `fnl-setup/SKILL.md` is 33.8 KB in 132 lines, many over 1500 characters (quota, metrics, compaction, snapshot), and all
   of it loads on every run, though a user usually wants one thing. The repository's own convention is to disclose
   reference material into `references/`.
2. Three questions come before any work (scope, set up or check, beginner or mode), then at least nine separate consents
   (quota, metrics, snapshot, compaction twice, compaction stop, judge twice, label). A new user meets a wall of prompts.
3. The two skills name the same idea differently: `fnl-setup` says machine and project, `fnl-setup-instructions` says
   user and project.
4. New features have no place: agent roles, review posting, the judge, TypeSafe install guidance
   (`agent-roles.md` part J), and old text is stale (the review-tools section and the steward explanation).
5. Section labels A to G run out of order across the two scopes.
6. The two skills are not connected. Setup ends by asking the user to type a second command (on Codex, immediately),
   and the two copies of `interview.md` and `work-tracking.md` must be kept identical by CI.
7. `fnl-scan-agents` (20 lines) and `fnl-set-mode` (19 lines) are thin wrappers over scripts that only setup, ask and
   delegate point to.

## Decisions settled (owner, 2026-11-07)

- Instructions become a component of `fnl-setup`; the skill `fnl-setup-instructions` is removed in the same release
  without a deprecation period (the owner exception recorded in `agent-roles.md`).
- `fnl-scan-agents` and `fnl-set-mode` fold into `fnl-setup` as subcommands (proposal accepted by the owner).
- The words are user scope (everything under the user's account: host config, consent, user-level instruction files) and
  project scope (one repository). "Machine" is retired from the text.
- The shape is a short core plus features loaded on demand, with each consent still asked on its own.
- A project-scope default for roles or the judge is not part of this work.
- The release is 0.2.0.

## A. Entry and commands

`/fnl-setup` takes an optional first word; the skill documents the grammar in its `argument-hint`:

| Command | Does |
| --- | --- |
| `/fnl-setup` | the core path (part B) for the chosen scope, then the menu (part C) |
| `/fnl-setup add <feature>` | one feature on its own (part C) |
| `/fnl-setup instructions` | the instructions component (part D) |
| `/fnl-setup check` | Check, per scope and per feature |
| `/fnl-setup scan` | the agent inventory refresh (the old `fnl-scan-agents`) |
| `/fnl-setup mode [args]` | Delegation mode and Routing (the old `fnl-set-mode`) |

On Codex the user types `$fnl-setup <word>`; whether Codex passes the word to a skill is unverified on the installed
version, so the skill also accepts the choice as a plain sentence ("add quota", "set up my instruction files"). The
skill stays user-invoked only (`disable-model-invocation: true`).

## B. The core path

Short, with a fixed number of decisions. For each scope:

- **User scope**: (1) the effective data root and whether to keep it (data location stays its own approved step if the
  user wants to move it); (2) the agent scan (`scan`) and the host config it needs; (3) Delegation mode and Routing
  (`mode`); (4) a read-back of every file the core will write, with one yes.
- **Project scope**: (1) the repository facts (look first); (2) the `.finolabs/` exclude line; (3) the `## Agent skills`
  block; (4) the workflow detection; (5) a read-back and one yes.

A bare invocation asks one scope question (user, project, both) with the recommendation first, then runs the core.
Check is `/fnl-setup check`, not a second question on every bare run; a bare run says in one line where Check is.
The beginner path and quick or detailed modes keep their meaning for the core only: beginner and quick take defaults and
write after one confirmation; detailed asks each decision. No mode bundles a consent that belongs to a feature.

## C. Features

Each feature is a file under `references/features/` that the skill loads only when the user picks it, from the menu
that ends the core ("Add anything now?", each item with one line saying what it does and what it costs, neutral Yes and
No per item, none preselected) or by `add <feature>`:

| Feature | Scope | Holds |
| --- | --- | --- |
| `delegation` | user | host template fill, test-command grants for Antigravity (today's section A) |
| `roles` | user | agent roles, the judge choice and TypeSafe guidance, review posting (`agent-roles.md` parts B, D, I, J) |
| `quota` | user | the on-demand quota reading and its preview (today's quota text) |
| `metrics` | user | usage metrics consent and retention, project progress, the process snapshot, the Antigravity hook |
| `compaction` | user | native threshold plan and the Antigravity stop |
| `review-tools` | user | the review instruments and companion skills (today's sections E and G), rewritten for the new agent set |
| `project` | project | work tracking settings, project label |

Every feature keeps its consent exactly as today: a separate neutral Yes and No, a preview with a digest where a script
writes, nothing bundled, nothing opted in by a scope choice. Moving text must not weaken it; a feature's file starts by
saying what it needs from another feature (for example `project` needs metrics consent) and asks that step first.

Size limits, enforced by a test: `SKILL.md` at most 70 lines and 10 KB; each feature file at most 80 lines; a bare run
loads `SKILL.md` and at most the references the core names (interview rules, work-tracking look-first).

## D. The instructions component

`/fnl-setup instructions` runs what `fnl-setup-instructions` does today, from `references/instructions/`
(`contract-template.md`, `hosts.md`, the work-tracking block text), with the same behaviour: ask the scope, explore the
existing files, draft, show a diff for every file, back up as `<file>.bak-YYYYMMDD`, write only after a yes per file,
`AGENTS.md` as the project source with an include in `CLAUDE.md`, no machine settings in instruction files. The
project-scope `## Work tracking` block gains the `Outcome` line (`agent-roles.md` part J). The core ends by offering this
component in the same session (a neutral Yes and No) instead of dispatching the user to another command. There is one
`interview.md` and one `work-tracking.md` after the merge, so the CI copy pairs for them go away.

The skill's `description` leads with what the whole skill does and lists both groups of triggers, host configuration
and instruction files. A trigger check pins it: representative prompts for each group fire it, and an unrelated coding
prompt does not.

## E. Removals and compatibility

Removed in 0.2.0: the skills `fnl-setup-instructions`, `fnl-scan-agents` and `fnl-set-mode`. CHANGELOG entries under
Removed give the consumer action for each (`/fnl-setup instructions`, `/fnl-setup scan`, `/fnl-setup mode`). References
to the old names are updated in `fnl-delegate` (its text and references), `fnl-ask` (map, contents, start and explain
references and the skill count), the README, CONTRIBUTING, `docs/diagrams`, the manifests, `build-parity-plugins.sh`,
`check-references.py` and its tests, the CI copy groups, `checkup.py` messages and the evals that name them. `fnl-delegate`
used standalone has no scan command; it says to fill the inventory by hand in that case.

The removal of `fnl-setup-instructions` ships after this restructure is built, so the component exists before the
skill goes (`agent-roles.md` part H). The removal of the other two ships in the same change that adds `scan` and `mode`.

## Not in scope

A project-scope default for roles or the judge; changing what any script writes or its previews and digests; new
consents; the dashboard; changing the scope chosen for existing data (host config stays where it is).

## Acceptance

- `SKILL.md` and every feature file stay within the limits of part C, checked by a test; a bare run's loaded size is at
  most 40% of today's 33.8 KB `SKILL.md` plus the references it loads now.
- Every consent of today exists in exactly one feature or core step, asked separately; a test checks that each consent
  sentence still appears once and that none is bundled with another.
- `scan`, `mode`, `check`, `instructions` and `add <feature>` work for the three hosts' entry forms; Codex plain-sentence
  choices work where a word is not passed.
- The instructions component keeps its backup, diff, per-file yes and `AGENTS.md` source behaviour (an eval covers it,
  as the existing interview eval does); there is one copy of `interview.md` and `work-tracking.md`.
- The trigger check of part D passes; the old three skills are gone with the references updated and the counts correct
  in `fnl-ask` and the README; `check-references.py`, the manifests test and the copy checks are green.
- The vocabulary is user scope and project scope in the skill, the references, `check.md`, the report headings and the
  README.
- `check.md` reports each feature as configured, unconfigured or unverified, including roles, judge and posting.

## Open decisions

1. Whether `scan` and `mode` keep thin alias skills for one release (the owner approved the fold; the default here is no
   alias, as for `fnl-setup-instructions`).
2. Whether Codex passes a word after `$fnl-setup`; until verified, the plain-sentence path is the contract.
3. Whether the menu at the end of the core remembers what the user declined, so a later bare run does not ask again.
