---
name: fnl-ask
description: Get oriented in finolabs-vibecode: first steps for someone new, what the plugin contains, how a given skill, agent or script works, or which skill fits your situation and the command to type next. Run only when the user asks for it.
disable-model-invocation: true
---

# Ask: where do I start, what is here, which skill next?

The user is new, curious or stuck. Pick the mode that fits what they said, read the target file before describing it (so the answer is current), then **answer and stop**: invoke nothing, and leave the how-to to the target skill, which explains itself when it runs. On Codex the user types `$fnl-ask` and `$fnl-setup`; elsewhere `/fnl-ask` and `/fnl-setup`.

## Modes

**Start.** The user is new to the plugin, or says they do not know how to begin. Give the first steps below in order, skipping any they say they have done, and end on the single next command. Offer the map for a specific situation.

1. Install the plugin for the host and open a new session; plugins load when a session starts.
2. Run `/fnl-setup` once. It asks a few questions (quick mode accepts the recommended defaults), writes only what the user confirms and installs nothing.
3. Work as usual. The agent starts coding work by loading `fnl-coding-router`, which names the workflow and depth (MIN, NORMAL, DEEP) before it edits.
4. Expect a stated depth, commits shaped by `fnl-commit-messages`, and pull requests held for a posted code review (plus a security review at sensitive boundaries).
5. After a few sessions, `/fnl-status` opens the usage dashboard, if the user consented to usage metrics in setup.

The plugin's README, section "Getting started", holds the full version; name it for detail.

**Contents.** The user asks what is in the plugin, or what exists for a purpose. List it grouped by purpose from the map below and "Agents and scripts", in three groups: typed by the user only (`fnl-setup`, `fnl-setup-instructions`, `fnl-status`, `fnl-ask`); typed by the user or proposed by the agent (`fnl-advisor`, `fnl-committee`, `fnl-handoff`); and loaded by the agent when the task matches (the rest). When the installed folder differs from the map, trust the folder: list the `fnl-` skills beside this one and the plugin root's `agents/fnl-*.md` with each file's one-line description, and fall back to the map when neither can be listed. State a count only after counting it in the folder; when the folder cannot be listed, say the list comes from the map and give no totals.

**Explain.** The user asks how a skill, agent or script works. Read its `SKILL.md`, `agents/<name>.md` or the script's header comment and argument definitions (read the file; run nothing), then answer in plain words: what it does, when it fires (typed by the user, or loaded by the agent), what it needs and writes, what it costs (quota, time, a confirmation), and what to type. Keep it to about six lines, or one short paragraph and a few bullets, then offer to go deeper on the part they care about (steps, cost, limits); leave the rest in the file. For a companion skill from another pack, say in one line what it is and that it is a separate project.

**Route.** The user describes a situation. Place them on the map, then name the skill and the command in one or two sentences.

## The map

| Situation | Skill | Companion skills and native commands |
| --- | --- | --- |
| New to the plugin, or not sure what it holds | this skill, "Start" or "Contents" | |
| First time in this repository or on this machine | `/fnl-setup` | `/setup-matt-pocock-skills` if that pack is installed |
| Writing or revising your own instructions for every agent and repository | `/fnl-setup-instructions` | |
| Starting, resuming or redirecting coding work | `fnl-coding-router` | |
| Requirements unclear | `fnl-coding-router` (clarification step) | `/grill-me`, or `/grill-with-docs` to keep a glossary and ADRs |
| A design question only code can answer | `fnl-coding-router` | `prototype` |
| Ready to implement one seam | `fnl-coding-router` (depth, gates) | `tdd` for the red-green loop |
| Bug, failing CI, unexplained behavior | `fnl-coding-router` (debug path and checkpoint) | `diagnosing-bugs` |
| Handing work to another agent (Claude Code, Codex, Antigravity) | `fnl-delegate`, then `fnl-handoff` | `/handoff` for a portable handoff document |
| How the practice is working for you: router coverage, skill use, load cost, delegated runs, review outcomes | `/fnl-status` (opens the usage dashboard) | |
| Deleting the recorded usage data, or stopping the recording | `/fnl-status purge` (asks before deleting) | |
| Want a second opinion | `fnl-advisor` (proposed first and waits for your yes; spends quota) | |
| Stuck or looping on fixes | `fnl-committee` (proposed first and waits for your yes; spends two families' quota) | |
| A query on live data, an infrastructure change, a dashboard or a forecast | `fnl-coding-router`, which reads `references/non-code-work.md` | |
| Coordinating a spec across desktop app sessions | `fnl-coordinator-sessions` | |
| Remembering a decision or lesson, or finding what was decided before | `fnl-knowledge` | `obsidian-cli` from kepano/obsidian-skills for an Obsidian vault |
| Long session, phase change, compaction | `fnl-session-hygiene` | `/ask-matt` covers its phase-boundary choices |
| A story is done, or before merge | `fnl-review-gate` | `/code-review` (Claude Code), `codex review`, or `code-review` from Matt's pack |
| Change touches auth, permissions, private data, untrusted input | `fnl-security-review-gate` | `/security-review` (Claude Code); `security-audit` from Cloudflare for a full audit |
| "Is it done?" or accepting someone else's work | `fnl-verification` | |
| Writing a commit | `fnl-commit-messages` | `pr` for the pull request body |
| Creating, syncing or merging a branch, or a backport | `fnl-commit-messages` "Branches" | |
| Release, tag, changelog | `fnl-versioning` | |
| Making a repository public, or checking a public repository's settings | `fnl-open-source-review` | `security-audit` from Cloudflare |
| Packaging skills as a plugin | `fnl-plugin-packaging` | |

## Agents and scripts

| Piece | What it answers or does | Where it comes from |
| --- | --- | --- |
| `fnl-verifier` agent | Is the report true? Reruns targeted tests and checks each acceptance criterion. | `fnl-delegate` (accepting delegated work) |
| `fnl-reviewer` agent | Is the change good? Reads the diff, then its callers, contracts and tests. | `fnl-review-gate` |
| `fnl-security-reviewer` agent | Is the change safe? Reads the diff, then every trust path that reaches it. | `fnl-security-review-gate` |
| `scripts/ledger.py` | Records delegated runs and lists the open ones. | `fnl-delegate` |
| `scripts/merge_check.py` | Checks a pull request's posted reviews before merge, and the low-risk lane. | `fnl-review-gate` |
| `scripts/refresh.py` | Rebuilds the dashboard data; also consent and purge for usage metrics. | `fnl-status` |
| `scripts/record.py` | Prints the router's depth receipt. | `fnl-coding-router` |
| `scripts/record.py` | Prints a coordinator's keep receipt. | `fnl-delegate` |

## Rules

- A command with a leading `/` is user-invoked: tell the user to type it. Names without `/` load on their own when the task matches, or the user can type them.
- In a Spec Kit repository, Spec Kit owns the process. Companion process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to it; companion phase tools (`grilling`, `tdd`, `diagnosing-bugs`, `prototype`, `code-review`) work inside its phases.
- Companion skills come from [mattpocock/skills](https://github.com/mattpocock/skills), [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) and [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) (all MIT); commands such as `/code-review` and `codex review` are built into their hosts. When one is not installed, say so and point to that repository's install instructions; install nothing yourself. The packs are independent: neither endorses the other.
- When no row fits, say so and name the closest two, with the one question that would decide between them.
- When a question is about the plugin's own behaviour and the file does not say, say that it does not, and name the file you read.
