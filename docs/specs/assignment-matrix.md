# Assignment matrix: one section for levels, work types and roles (draft, scoped to release 0.2.3)

Status: draft; the owner described the need and settled the storage choice on 2026-11-09; nothing is built.

## Why

Three questions about the same helpers live in three places: how hard a task each can take (`## Agent levels`), which
reviews and judgments each owns (`## Agent roles`), and, new, which kind of work suits each. The owner reads that as
one matrix, "who does what", and wants to set and see it once. On 2026-11-09 the owner also gave a first example of the
third kind: frontend code, design, video made with remotion, motion or hyperframes and 3D with three.js go to `claude` or
`claudework` on `claude-opus-5-5`; image generation goes to `antigravity` or `codex`, which are also preferred when
content must be transcribed from images, video or audio.

## Owner decisions (2026-11-09)

- One matrix, one stored section, replacing both `## Agent roles` and `## Agent levels` (the owner chose a new stored
  section over keeping three sections behind one setup flow).
- It is set at user scope in `/fnl-setup add delegation`, which absorbs `/fnl-setup add roles` for the assignments; `add
  roles` keeps only review posting (the verified ability to post) until a later release folds it in.
- Until this exists, the owner's host config carries the work-type preference as one paragraph under `## Coordinators and
  reach`, read by agent judgment only.

## Decision analysis (owner request, 2026-11-09: agents must understand, use and follow it, and it must cost few tokens)

Measured on the owner's machine: the data is small (`## Agent roles` plus `## Agent levels` are 218 bytes; the matrix
with types and models is about 600 bytes, roughly 150 tokens). The cost is in the guidance around it: `route.md` is 9.8
KB, with `models.md` 6.2 KB, `entry.md` 2.0 KB and `grade.md` 1.9 KB, about 5k tokens a coordinator reads at each
dispatch decision, and still lets each agent derive a different answer from the same prose. Three ways to make the matrix
usable:

| Option | Understood and used correctly | Compliance | Tokens per decision | Cost to build |
| --- | --- | --- | --- | --- |
| A. One section, agents read it and `route.md` prose | each agent re-derives the order from text; drift between agents | none beyond judgment; no record of deviation | the whole prose plus the section | lowest |
| B. One section plus a table view in session start | sees the table, still derives the answer itself | none beyond judgment | about 150 tokens every session, used or not | low |
| C. One section, one parser, and a query command that returns the answer | one deterministic answer, same for every agent | the dispatch records the type and the ledger shows each deviation from the answer | one call, about 100 tokens | highest |

Recommended and adopted: C, because an advisory rule that is only prose is followed by whoever reads it carefully, and the
failure here (a task sent to an agent outside its range or type preference) is silent. C turns the prose into a computed
answer and makes deviation visible, without turning a preference into a block.

## The section

`## Assignment matrix` in the canonical host config. One header line, one judge line and one line per agent:

```
- Consent: yes (2026-11-09)
- Judge: jev
- <agent>: levels L-H[; works on <type>[, <type>]...][; model <id>][; roles <role>[, <role>]... | roles none]
```

- Agents: `claude`, `codex`, `antigravity` and extra Claude Code commands (the names `levels_setup.py` accepts today).
- Levels: 1 to 5, low to high, `L` not above `H`, as in `agent-levels.md`.
- Types of work (closed list; a new type is a spec change): `frontend`, `design`, `video`, `three-d`, `image-generation`,
  `transcription`. When several agents list the same type, the earlier line is preferred.
- Model: one full model id (letters, digits, dot and dash, at most 64) that applies to the types on that line; `show`
  reports one that is not among the allowed models of `## Agents on this machine` as unverified.
- Roles: `code-review`, `security-review`, `navigator`; each role names at most one agent (as today), and `none` or an
  absent field means no role. `Judge` is `jev` or `host`, as today (`agent-roles.md` part I).
- Everything else (the posting line of `## Review posting`, quota, the shell functions) stays where it is.

## Reading and migration

- One parser: `assignments.py`, a shared module copied into every skill that needs it (the copy group is checked in CI,
  as for `data_root.py`), is the only code that reads the section; `review_config.py` (three copies plus the
  plugin-level one), `judge.py` (five copies), `checkup.py`, `route_pick.py` and `matrix_setup.py` import it, so there is
  one reading of the format. The review and judge readers get roles and judge
  from this section first and from `## Agent roles` only when the matrix has no such line; `checkup.py` reports a
  conflict between the two. Levels and work types have no script reader: `fnl-delegate` `route.md` reads them as advice
  (agent judgment), and the section is the only place they are stored.
- The old sections stay readable through release 0.2.x and are removed in 0.3.0 (the same schedule as the old global
  ledger lines). `matrix_setup.py migrate` previews the matrix built from the old sections (roles, judge and levels) and,
  after a yes, writes it with a backup and removes the old two in the same atomic write; nothing is lost because the
  backup keeps the originals.
- A roles line read from the matrix is held to the same strictness as today (closed vocabulary, one agent per role, a
  value outside the list refused), because review routing and posting trust depend on it. The security review of the code
  pull request covers the dual read and its precedence.

## One view

`matrix_setup.py show` prints the matrix as one table, which is what the owner asked for:

| Agent | Levels | Works on | Model | Roles |
| --- | --- | --- | --- | --- |
| claude | 1-5 | frontend, design, video, three-d | claude-opus-5-5 | none |
| claudework | 3-5 | frontend, design, video, three-d | claude-opus-5-5 | none |
| codex | 1-4 | image-generation, transcription | | security-review |
| antigravity | 1-3 | image-generation, transcription | | code-review, navigator |

and below it the judge, the posting line and anything unknown or unverified. `fnl-delegate` and `fnl-status` may quote
the same table. The session-start line keeps its current summary of roles.

## Writer

`matrix_setup.py` in `skills/fnl-setup/scripts/`, built like `levels_setup.py`: `validate`, `preview`, `apply` (backup,
SHA-256 digest, 60-minute expiry, section-only atomic write, symlink refusal), `show`, `migrate`, `candidates` (the
existing command listing extra Claude Code commands). It runs no command. `/fnl-setup add delegation` asks once per
agent for levels, types, model and roles in one pass, shows the preview and writes only after a neutral yes.

## Routing query

`route_pick.py pick --type <type> --level <1-5> [--author <family>]` in `skills/fnl-delegate/scripts/` prints the ordered
candidates for a task, at most five lines, from the matrix and local state only: an agent whose levels do not contain the
level is dropped, an agent the host config marks unreachable from this coordinator is dropped, one whose cached quota
reading says out of quota is dropped, with `--author` the independent-review rule drops the author's own family, and
each survivor prints as `<agent> <model or default>` in preference order with the reason for every drop on one short line
each. No answer (nothing survives or the matrix is missing) prints `no preference: use the strength table`. It runs no
program, reads no repository, makes no network call and prints no path. `route.md` replaces its prose on levels and
strength overrides with the command, so the coordinator reads the answer instead of the rules (advisory, agent
judgment, to run it before each dispatch; the script computes the answer exactly).

## Compliance and token cost

- `ledger.py start` accepts `--work-type <type>` (the closed list, local ledger only). When the type and level are given it
  runs the same pick and, if the chosen agent or model is not among the survivors, prints one line `off the preferred
  order: <reason>` and records `off_pick` (a short fixed reason) on the start line. It never refuses the dispatch: the
  coordinator or the user may have a reason, and a block would only push agents to omit the type.
- `ledger.py summary` shows the share of dispatches that went off the preferred order, per agent, so a preference that is
  ignored is visible; `fnl-status` may show it. The enforcer of the choice stays agent judgment (advisory); the script
  enforces the computation and the record.
- Session start prints one fixed line, `Assignments: <n> agents set; run route_pick.py before a dispatch`, about 20 tokens,
  instead of the roles summary only; the roles summary stays.
- Expected cost: about 100 tokens per decision instead of about 5k of reading, and 20 tokens per session. These are
  estimates from the sizes above; the code pull request measures them with the real files.

## Routing

Advisory (agent judgment), in `route.md`: for a task of a listed type the coordinator offers the listed agents first and
the listed model for that agent. A preference never overrides an agent's level range, quota, reachability, the review
independence rule or the user's explicit choice, and it never grants anything: a preferred agent out of quota or range
is skipped and the report says why.

## Open decisions

| Decision | Owner | What unblocks it |
| --- | --- | --- |
| Whether the six types are enough for a first release or `backend`, `data` or others are needed | owner | the owner's list |
| Whether a model not allowed on this machine is refused or only reported | owner | a preference |
| Whether `add roles` should keep review posting or fold it into the matrix flow now | owner | a preference |
| Whether `ledger.py start` should stay warn-only on an off-order choice or require a reason with `--reason` | owner | a preference |

## Evidence

None yet. A build needs a red test per behavior: validation (agents, levels, types, model, roles, duplicates and limits),
preview and apply with digest and expiry, strict `show`, migration from the two old sections including their backup,
the dual read and its precedence in `review_config.py` and `judge.py` (every copy), `assignments.py` copies identical, `route_pick.py` drops and ordering, the ledger `--work-type` warning and summary, the `checkup.py` conflict report, and
a routing example in `route.md` that names the section.
