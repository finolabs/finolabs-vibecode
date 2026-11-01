---
name: fnl-advisor
description: Get a second opinion from another model family (Claude or Codex) without handing over the work. Use when the user asks for an advisor, a second opinion or what another model thinks, or before committing to a risky design or fix.
user-invocable: true
argument-hint: "[--agent claude|codex] <question>"
---

# Advisor

One agent reads the situation and gives a judgement. You stay the decider; the advisor does not drive the work.

**User's request:** $ARGUMENTS

## Picking the advisor

1. An agent the user names wins.
2. Otherwise prefer contrast: a model family other than the one you run on, at strong tier or above (`fnl-delegate` `references/models.md`). Running on Claude, ask Codex; running on Codex, ask Claude Code; running on Antigravity, ask Claude Code, then Codex. Both read-only.
3. When the contrasting agent is out of quota or unreachable, use a subagent of your own host with fresh context, and say that the opinion comes from the same family.
4. Antigravity advises only on a Claude model it serves, and only when Claude Code and Codex are both unavailable.

Load the `fnl-delegate` skill and the host config for the invocation commands and read-only flags. Requires the `fnl-delegate` skill installed beside this one. When it is missing, tell the user to add it (`npx skills add fioenix/finolabs-vibecode --skill fnl-delegate`, or install the whole plugin) and stop.

## The briefing

The advisor has zero context:

- the question, sharply;
- what you have considered and ruled out;
- relevant files by path, for the advisor to read itself;
- the ask: "Give me a recommendation, with reasoning and the evidence you used."

If the arguments reference another skill (`/name` or `$name`), tell the advisor: "Invoke the `<name>` skill against this task before anything else," and pass the remaining arguments as that skill's input.

End every briefing with:

```
This is analysis only. Do NOT edit, create, or delete any files. Do NOT write code.
```

## Run and synthesize

Dispatch with a budget and hard cap from `fnl-delegate` "Budget and liveness" and record it in the ledger with `--kind advise`. Read the answer, check its claims against the code where they matter, then give the user the advisor's verdict and your own recommendation, saying where you agree and where you differ.

For ongoing input, keep the advisor's context and send follow-ups to it; start fresh when the topic shifts.
