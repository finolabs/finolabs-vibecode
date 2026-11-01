---
name: fnl-ask
description: Describe where you are in your work and get pointed to the right finos-vibe-code skill, or a companion skill from another pack, and the command to type next.
disable-model-invocation: true
---

# Ask: which skill next?

The user describes their situation. Place them on the map below, read the target skill's `SKILL.md` before describing it (so the description is current), then **recommend and stop**: name the skill and what to type, in one or two sentences, and invoke nothing. Leave the how-to to the target skill; it explains itself when it runs.

## The map

| Situation | Skill | Companion skills (Matt Pocock's pack) |
| --- | --- | --- |
| First time in this repository or on this machine | `/fnl-setup` | `/setup-matt-pocock-skills` if that pack is installed |
| Writing or revising your own instructions for every agent and repository | `/fnl-setup-instructions` | |
| Starting, resuming or redirecting coding work | `fnl-coding-workflow` | |
| Requirements unclear | `fnl-coding-workflow` (clarification step) | `/grill-me`, or `/grill-with-docs` to keep a glossary and ADRs |
| A design question only code can answer | `fnl-coding-workflow` | `prototype` |
| Ready to implement one seam | `fnl-coding-workflow` (depth, gates) | `tdd` for the red-green loop |
| Bug, failing CI, unexplained behavior | `fnl-coding-workflow` (debug path and checkpoint) | `diagnosing-bugs` |
| Handing work to Codex, Antigravity or another session | `fnl-orchestration`, then `/fnl-orchestration-handoff` | `/handoff` for a portable handoff document |
| Want a second opinion | `/fnl-orchestration-advisor` | |
| Stuck or looping on fixes | `/fnl-orchestration-committee` | |
| Coordinating a spec across desktop app sessions | `fnl-coordinator-sessions` | |
| Long session, phase change, compaction | `fnl-session-hygiene` | `/ask-matt` covers its phase-boundary choices |
| A story is done, or before merge | `fnl-review-gate` | `code-review` as the reviewer's instrument |
| Change touches auth, permissions, private data, untrusted input | `fnl-security-review-gate` | |
| "Is it done?" or accepting someone else's work | `fnl-verification` | |
| Writing a commit | `fnl-commit-messages` | `pr` for the pull request body |
| Release, tag, changelog | `fnl-versioning` | |
| Making a repository public | `fnl-open-source-review` | |
| Packaging skills as a plugin | `fnl-plugin-packaging` | |
| After a session, improving the setup | | `/retro` |

## Rules

- A command with a leading `/` is user-invoked: tell the user to type it. Names without `/` load on their own when the task matches, or the user can type them.
- In a Spec Kit repository, Spec Kit owns the process. Companion process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to it; companion phase tools (`grilling`, `tdd`, `diagnosing-bugs`, `prototype`, `code-review`) work inside its phases.
- Companion skills come from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT). When one is not installed, say so and point to that repository's install instructions; install nothing yourself. The packs are independent: neither endorses the other.
- When no row fits, say so and name the closest two, with the one question that would decide between them.
