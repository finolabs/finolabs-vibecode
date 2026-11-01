---
name: fnl-committee
description: Convene two contrasting agents (Codex and Claude) for root-cause analysis and a plan. Use when stuck, looping on failed fixes, a bug survives several attempts, or a hard planning or design problem needs fresh eyes.
user-invocable: true
argument-hint: "<problem>"
---

# Committee

Two agents from different model families, fresh context, planning in parallel. Contrast is the point.

**User's additional context:** $ARGUMENTS

## Composition

- **Codex** in a read-only sandbox, at its highest reasoning setting.
- **Claude** with fresh context: a subagent, or a Claude Code session when the analysis needs longer than one turn.

Members the user names win. Antigravity takes no correctness judgements, so it sits on no committee. When one member's agent is out of quota, say so and run a single advisor instead (`fnl-advisor`).

Load the `fnl-delegate` skill and the host config for the invocation commands.

## Rules

- **No edits.** Every prompt to a member ends with:

  ```
  This is analysis only. Do NOT edit, create, or delete any files. Do NOT write code.
  ```

- **Patient budget.** High-reasoning models can think for 15–30 minutes. Give each member a 30–45 minute cap and judge liveness from artifacts at the check deadline; send no hurry-up messages.

## Workflow

1. Write one problem-level prompt: the symptom, the evidence, what was tried and why it failed, relevant files by path. Leave out your favoured hypothesis, so the members reason independently.
2. Dispatch both members in parallel with the same prompt; record each in the ledger with `--kind committee`.
3. Read both answers.
4. Where they disagree, pass each member the other's argument and ask it to rebut or concede. At most two rounds.
5. Converge on one root cause and plan, or name the open disagreement and the evidence that would settle it.

Give the user the consensus, where the members diverged and how it resolved. The plan then goes through `fnl-delegate` like any other work.
