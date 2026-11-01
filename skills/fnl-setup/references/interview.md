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

## Push on vague answers

An answer such as "be careful" or "use best practices" settles nothing. Ask the follow-up that turns it into a rule an agent can follow and someone can check, or offer two concrete readings and ask which one is meant.

## Finish

The interview is done when no decision is left open or silently assumed. Read the settled decisions back as one short list and get the user's yes before writing anything.

When the user has a grilling skill installed (for example `grilling` from mattpocock/skills), it may run the interview instead; these rules still define which decisions each section must settle.
