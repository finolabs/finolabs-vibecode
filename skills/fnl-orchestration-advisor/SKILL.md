---
name: fnl-orchestration-advisor
description: Get a second opinion from another model (Codex, or a fresh Claude context) without handing over the work. Use when the user asks for an advisor, a second opinion or what another model thinks, or before committing to a risky design or fix.
user-invocable: true
argument-hint: "[--agent codex|claude] <question>"
---

# Orchestration advisor

One agent reads the situation and gives a judgement. You stay the decider; the advisor does not drive the work.

**User's request:** $ARGUMENTS

## Picking the advisor

1. An agent the user names wins.
2. Otherwise prefer contrast: a different model family from your own, at the strong end. From a Claude coordinator that is Codex in a read-only sandbox; when Codex is out of quota, a Claude subagent with fresh context.
3. Antigravity takes no reviews or correctness judgements, so it is not an advisor.

Load the `fnl-orchestration` skill and the host config for the invocation commands.

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

Dispatch with a budget (15–30 minutes) and record it in the ledger with `--kind advise`. Read the answer, check its claims against the code where they matter, then give the user the advisor's verdict and your own recommendation, saying where you agree and where you differ.

For ongoing input, keep the advisor's context and send follow-ups to it; start fresh when the topic shifts.
