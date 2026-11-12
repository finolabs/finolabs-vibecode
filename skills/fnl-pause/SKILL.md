---
name: fnl-pause
description: "Older name for pause, kept so the old name still works when typed; follows pause with the same arguments."
disable-model-invocation: true
argument-hint: "[restart|shutdown] [--in <minutes>] | status | resume"
---

# fnl-pause

Dependency: `pause`. `pause` is user-only (`disable-model-invocation: true`), so the Skill tool refuses it: read `pause`'s `SKILL.md` in this plugin's skills folder and follow it with the same arguments; never call the Skill tool for it (advisory (agent judgment)).
This alias holds no rules of its own.
