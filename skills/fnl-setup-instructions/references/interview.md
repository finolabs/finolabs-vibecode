# Interview rules

Shared by the setup skills. Each skill keeps an identical copy so it works when installed alone; edit them together (CI checks they match). The goal is a shared understanding with the user, reached in as few rounds as the decisions allow.

## Map the decisions

Before asking anything, list the decisions this interview must settle and which ones depend on others. A decision is **ready** when every decision it depends on is already settled.

## Facts versus decisions

Facts are your job: look up anything the environment can tell you (files, installed tools, existing settings) before asking, and delegate slow lookups to a subagent when the host has one. A lookup still running holds back only the decisions that depend on it. Ask the user only for decisions, and for facts you have tried and failed to observe, saying what you tried.

## Ask in rounds

Each round asks every ready decision at once, so the user can answer them together:

```
**Q1. <short title>**: <the decision, with the options when there are several>
Recommended: <your answer, with one line of reason>

**Q2. <short title>**: …
```

- Word each question so that "yes" accepts the recommendation.
- Ask about the decision, not the wording; write the wording yourself from the answers.
- A question that depends on another one still open in this round waits for a later round.
- After the user answers, update the map: settled decisions make new ones ready. Ask the next round.

## Use the host's native question form

When the session has a native question tool (`AskUserQuestion` on Claude Code, `request_user_input` on Codex, `ask_question` on Antigravity), put the round's questions into it instead of the text format above: the decision as the question, the options as choices with the recommended one first and marked "(Recommended)", and a free-text answer through the tool's own "Other". Send as many questions per call as the tool takes (Claude Code takes up to four, each with two to four options) and the rest in the next call. The read-back and the final yes go through it too.

Ask in text, in the format above, when the session has no such tool, the tool is refused or fails, nobody can answer (a delegated or headless run never waits on a question), or the decision is free text such as a list of model IDs. Codex may expose its tool only in some modes, and Antigravity's is not exercised here; the names come from each host's CLI. The enforcer is agent judgment, so this is advisory.

## Push on vague answers

An answer such as "be careful" or "use best practices" settles nothing. Ask the follow-up that turns it into a rule an agent can follow and someone can check, or offer two concrete readings and ask which one is meant.

## Finish

The interview is done when no decision is left open or silently assumed. Read the settled decisions back as one short list and get the user's yes before writing anything.

When the user has a grilling skill installed (for example `grilling` from mattpocock/skills), it may run the interview instead; these rules still define which decisions each section must settle.
