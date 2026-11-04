# The map

| Situation | Skill | Companion skills and native commands |
| --- | --- | --- |
| New to the plugin, or not sure what it holds | this skill, "Start" or "Contents" | |
| "Is it set up right?" or what happens automatically on this host | `/fnl-setup` Check mode | |
| First time in this repository or on this machine | `/fnl-setup` | `/setup-matt-pocock-skills` if that pack is installed |
| Writing or revising your own instructions for every agent and repository | `/fnl-setup-instructions` | |
| Starting, resuming or redirecting coding work | `fnl-coding-router` | |
| Requirements unclear | `fnl-coding-router` (clarification step) | `/grill-me`, or `/grill-with-docs` to keep a glossary and ADRs |
| A design question only code can answer | `fnl-coding-router` | `prototype` |
| Ready to implement one seam | `fnl-coding-router` (depth, gates) | `tdd` for the red-green loop |
| Bug, failing CI, unexplained behavior | `fnl-coding-router` (debug path and checkpoint) | `diagnosing-bugs` |
| Handing work to another agent (Claude Code, Codex, Antigravity) | `fnl-delegate`, then `fnl-handoff` | `/handoff` for a portable handoff document |
| Stopping or switching and wanting the work continued later by a new session or another agent | `fnl-handoff` (Resume mode) | writes a handover note and launches nothing |
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
- For Route mode, name the matching skill and command in one or two sentences. When no row fits, say so and name the closest two, with the one question that would decide between them.
