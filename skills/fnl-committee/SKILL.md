---
name: fnl-committee
description: Convene two agents from contrasting model families (Claude, Codex or Antigravity's Gemini) for root-cause analysis and a plan. Use when stuck, looping on failed fixes, a bug survives several attempts, or a hard planning or design problem needs fresh eyes.
user-invocable: true
argument-hint: "<problem>"
---

# Committee

Two agents from different model families, fresh context, planning in parallel. Contrast is the point.

**User's additional context:** $ARGUMENTS

## Composition

Two members from different model families, each on its frontier or strong model at a high reasoning setting, read-only: Claude (Claude Code), GPT (Codex) or Gemini (Antigravity Argon). The default pair is Claude and Codex.

Whichever agent coordinates, the member from its own family runs as its own subagent, or as a session when the analysis needs longer than one turn; the other runs headless as `fnl-delegate` `references/agents.md` says. Members the user names win. When one member's agent is out of quota or unreachable, the third family takes its seat; with only one family left, say so and run a single advisor instead (`fnl-advisor`).

Load the `fnl-delegate` skill and the host config for the invocation commands. Requires the `fnl-delegate` skill installed beside this one. When it is missing, tell the user to add it (`npx skills add fioenix/finolabs-vibecode --skill fnl-delegate`, or install the whole plugin) and stop.

## Rules

- **No edits.** Every prompt to a member ends with:

  ```
  This is analysis only. Do NOT edit, create, or delete any files. Do NOT write code.
  ```

- **Patient budget.** High-reasoning models can think for 15–30 minutes. Give each member the committee budget and its hard cap from `fnl-delegate` "Budget and liveness", and judge liveness from artifacts at the check deadline; send no hurry-up messages.

## Workflow

1. Write one problem-level prompt: the symptom, the evidence, what was tried and why it failed, relevant files by path. Leave out your favoured hypothesis, so the members reason independently.
2. Dispatch both members in parallel with the same prompt; record each in the ledger with `--kind committee` and the problem's difficulty as `--grade`.
3. Read both answers.
4. Where they disagree, pass each member the other's argument and ask it to rebut or concede: a follow-up to a session or resumable run, or a new prompt carrying its earlier answer for a one-shot run. At most two rounds.
5. Converge on one root cause and plan, or name the open disagreement and the evidence that would settle it.

Give the user the consensus, where the members diverged and how it resolved. The plan then goes through `fnl-delegate` like any other work.
