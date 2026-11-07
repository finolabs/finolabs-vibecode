# Interview rules

The goal is a shared understanding with the user in as few rounds as the decisions allow. Enforcer: agent judgment (advisory).

## Map, look up, ask

List the decisions the interview must settle and which depend on others; a decision is **ready** when everything it depends on is settled. Facts are your job: look up anything the environment can tell you (files, installed tools, existing settings) before asking, delegating slow lookups to a subagent when the host has one. Ask the user only for decisions, and for facts you tried and failed to observe, saying what you tried.

Each round asks every ready decision at once, one numbered question each, with your recommended answer and one line of reason, worded so that "yes" accepts it. Ask about the decision, not the wording; write the wording yourself. After the answers, update the map and ask the next round.

## Native question form

When the session has a native question tool (`AskUserQuestion` on Claude Code, `request_user_input` on Codex, `ask_question` on Antigravity), put the round into it: the decision as the question, the options as choices with the recommended one first, free text through the tool's own "Other" where it has one. Send as many questions per call as the tool takes (four on Claude Code, each with two to four options), blocking questions first, the rest in the next call; use a numbered text list only as the last resort. The read-back and every consent go through it as neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes.

Ask in text when the session has no such tool, the tool is refused or fails, nobody can answer (a delegated or headless run records the open decision and never assumes or invents an answer), or the decision is free text such as a list of model IDs.

## Vague answers and finish

An answer such as "be careful" settles nothing: ask the follow-up that turns it into a rule an agent can follow and someone can check, or offer two concrete readings. The interview is done when no decision is left open or silently assumed: read the settled decisions back as one short list and get the user's yes before writing. A grilling skill the user has installed may run the interview instead; these rules still define what to settle.
