---
name: clarify
description: Interview the user in short rounds that settle every decision an idea, plan or design depends on, each question with a recommended answer, before anything is built. Use when the user wants to brainstorm, discuss, ideate, shape or stress-test an idea, plan or design, asks to be grilled or interviewed about it, or when requirements are unclear before building; it fires on these requests in any language the user writes.
argument-hint: "<idea, plan or design to clarify>"
---

# Clarify

Turns an open idea, plan or design into decisions the user has made, one round of questions at a time, and acts on none of it until the user confirms the result.

Learned from `grilling` by Matt Pocock ([mattpocock/skills](https://github.com/mattpocock/skills), MIT); no text is copied.

**Topic:** $ARGUMENTS

## Which interview runs

Advisory (agent judgment):

- When `grilling` is installed, it runs instead of this skill: `/grill-me`, or `/grill-with-docs` when the user wants a glossary and decision records kept. Put its questions through the host's native question tool.
- Otherwise run this skill.
- When the user wants many divergent design ideas rather than decisions, and superpowers `brainstorming` is installed, offer it.
- In a Spec Kit repository this skill works inside a phase like the other phase tools and yields to Spec Kit's own clarify step.
- At router depth MIN, skip it unless the user asked for it.

## Procedure

Advisory (agent judgment); no hook or script enforces these steps.

1. **Map the decisions.** List what must be decided and draw the dependencies as a tree: a decision is open to ask only when every decision it depends on is settled.
2. **Split facts from decisions.** A fact the agent can find (a file, a command's output, a read-only subagent's search) is the agent's to find; never ask the user for it. Choices, priorities and trade-offs are the user's.
3. **Ask one round.** Ask every open decision whose prerequisites are settled, and nothing that depends on an answer still missing. Number the questions; give each your recommended answer first, with one line of why, then the alternatives. Use the host's native question tool (`AskUserQuestion` on Claude Code, at most four questions per call, so split a larger round; `request_user_input` on Codex; `ask_question` on Antigravity), and plain text when there is none or it fails. A question that waits on a lookup still running waits; ask the rest now.
4. **Update the tree.** Record each answer, add the decisions it opens, drop the ones it closes, and ask the next round.
5. **Close.** When no open decision remains, summarize what was decided and ask the user to confirm it. Act on nothing (no code, no file, no dispatch) before that confirmation.

When the user only wants many raw ideas, the first round offers two or three distinct directions as options; later rounds go deeper on the one they pick.

## Records

Advisory (agent judgment):

- Write each settled decision with its date where the work keeps its decisions: the work record's goal and acceptance section when `coding-router` created a work record, otherwise the plan, the issue or the pull request body.
- A decision the user cannot make yet stays open in that record, with who owns it and what would unblock it.
- In a delegated or headless run nobody can answer: list the open decisions with your recommended answers in the report, mark them unanswered, and never present a recommendation as the user's decision.

## Language

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged.
