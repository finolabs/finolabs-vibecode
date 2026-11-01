---
name: fnl-ask
description: Describe where you are in your work and get pointed to the right finolabs-vibecode skill, or a companion skill from another pack, and the command to type next. Run only when the user asks for it.
disable-model-invocation: true
---

# Ask: which skill next?

The user describes their situation. Place them on the map below, read the target skill's `SKILL.md` before describing it (so the description is current), then **recommend and stop**: name the skill and what to type, in one or two sentences, and invoke nothing. Leave the how-to to the target skill; it explains itself when it runs.

## The map

| Situation | Skill | Companion skills and native commands |
| --- | --- | --- |
| First time in this repository or on this machine | `/fnl-setup` | `/setup-matt-pocock-skills` if that pack is installed |
| Writing or revising your own instructions for every agent and repository | `/fnl-setup-instructions` | |
| Starting, resuming or redirecting coding work | `fnl-coding-router` | |
| Requirements unclear | `fnl-coding-router` (clarification step) | `/grill-me`, or `/grill-with-docs` to keep a glossary and ADRs |
| A design question only code can answer | `fnl-coding-router` | `prototype` |
| Ready to implement one seam | `fnl-coding-router` (depth, gates) | `tdd` for the red-green loop |
| Bug, failing CI, unexplained behavior | `fnl-coding-router` (debug path and checkpoint) | `diagnosing-bugs` |
| Handing work to another agent (Claude Code, Codex, Antigravity) | `fnl-delegate`, then `fnl-handoff` | `/handoff` for a portable handoff document |
| Checking delegated runs, or how each agent and model performs | `/fnl-status` | |
| Want a second opinion | `fnl-advisor` | |
| Stuck or looping on fixes | `fnl-committee` | |
| Coordinating a spec across desktop app sessions | `fnl-coordinator-sessions` | |
| Remembering a decision or lesson, or finding what was decided before | `fnl-knowledge` | `obsidian-cli` from kepano/obsidian-skills for an Obsidian vault |
| Long session, phase change, compaction | `fnl-session-hygiene` | `/ask-matt` covers its phase-boundary choices |
| A story is done, or before merge | `fnl-review-gate` | `/code-review` (Claude Code), `codex review`, or `code-review` from Matt's pack |
| Change touches auth, permissions, private data, untrusted input | `fnl-security-review-gate` | `/security-review` (Claude Code); `security-audit` from Cloudflare for a full audit |
| "Is it done?" or accepting someone else's work | `fnl-verification` | |
| Writing a commit | `fnl-commit-messages` | `pr` for the pull request body |
| Release, tag, changelog | `fnl-versioning` | |
| Making a repository public | `fnl-open-source-review` | `security-audit` from Cloudflare |
| Packaging skills as a plugin | `fnl-plugin-packaging` | |

## Rules

- A command with a leading `/` is user-invoked: tell the user to type it. Names without `/` load on their own when the task matches, or the user can type them.
- In a Spec Kit repository, Spec Kit owns the process. Companion process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to it; companion phase tools (`grilling`, `tdd`, `diagnosing-bugs`, `prototype`, `code-review`) work inside its phases.
- Companion skills come from [mattpocock/skills](https://github.com/mattpocock/skills), [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) and [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) (all MIT); commands such as `/code-review` and `codex review` are built into their hosts. When one is not installed, say so and point to that repository's install instructions; install nothing yourself. The packs are independent: neither endorses the other.
- When no row fits, say so and name the closest two, with the one question that would decide between them.
