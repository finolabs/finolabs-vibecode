---
name: fnl-advisor
description: Get a second opinion from another model family (Claude, Codex or Antigravity) without handing over the work. Use when the user asks for an advisor, a second opinion or what another model thinks, or before committing to a risky design or fix.
user-invocable: true
argument-hint: "[--agent claude|codex|antigravity] <question>"
---

# Advisor

One agent reads the situation and gives a judgement. You stay the decider; the advisor does not drive the work.

**User's request:** $ARGUMENTS

## When to run

Propose an advisor and wait for the user's yes, because each run spends quota. Propose it when the decision cannot be undone or changes a contract, or when your own analysis leaves you unsure. A user who asks for one needs no proposal. When the user is away, run one without the yes when a decision would otherwise wait for them, as `fnl-delegate` says for an absent user, and record who settled it.

## Picking the advisor

1. An agent the user names wins.
2. Otherwise prefer contrast: a model family other than the one you run on (`fnl-delegate` `references/models.md`). Three families are on offer: Claude (Claude Code), GPT (Codex) and Gemini (Antigravity Argon). Running on Claude, ask Codex or Argon; running on Codex, ask Claude Code or Argon; running on Antigravity, ask Claude Code or Codex. All read-only. The tier follows the question's difficulty: strong for an easy or medium question (a mid-priced model is enough), frontier for a hard or very hard one.
3. When one family is out of quota or unreachable, try the other family, and each of its models. Use a subagent of your own host with fresh context only when every model of both other families is out of quota or unreachable, and say that the opinion comes from the same family.

Load the `fnl-delegate` skill and the host config for the invocation commands and read-only flags. Requires the `fnl-delegate` skill installed beside this one. When it is missing, tell the user to add it (`npx skills add finolabs/finolabs-vibecode --skill fnl-delegate`, or install the whole plugin) and stop.

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

Dispatch with a budget and hard cap from `fnl-delegate` "Budget and liveness" and record it in the ledger with `--kind advise` and the question's difficulty as `--grade`. Read the answer, check its claims against the code where they matter, then give the user the advisor's verdict and your own recommendation, saying where you agree and where you differ. Where you differ on a point that changes direction, give the user both arguments and let them decide. When the user is away, take the option that can be undone, record who settled it, and hold the part of the work that depends on a point you cannot undo until the user answers; never settle it by weighing the two opinions.

For ongoing input, send follow-ups to the same advisor: a session or a resumable run keeps its context; a one-shot headless run gets a new prompt that carries the earlier question and answer. Start fresh when the topic shifts.
