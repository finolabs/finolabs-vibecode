---
name: fnl-update
description: "Older name for update, kept so the old name still works when typed; follows update with the same arguments."
disable-model-invocation: true
argument-hint: "[status | whats-new | <version> | pin <version> | unpin | skip <version> | never]"
---

# fnl-update

Dependency: `update`. `update` is user-only (`disable-model-invocation: true`), so the Skill tool refuses it: read `update`'s `SKILL.md` in this plugin's skills folder and follow it with the same arguments; never call the Skill tool for it (advisory (agent judgment)).
This alias holds no rules of its own.
