# Explain

Read the shared rules in [map.md](map.md#rules).

The user asks how a skill, agent or script works. Read its `SKILL.md`, `agents/<name>.md` or the script's header comment and argument definitions (read the file; run nothing), then answer in plain words: what it does, when it fires (typed by the user, or loaded by the agent), what it needs and writes, what it costs (quota, time, a confirmation), and what to type. Keep it to about six lines, or one short paragraph and a few bullets, then offer to go deeper on the part they care about (steps, cost, limits); leave the rest in the file. For a companion skill from another pack, say in one line what it is and that it is a separate project.

For a committee, read `fnl-advisor`'s `references/committee.md`; for spec coordinator sessions, read `fnl-delegate`'s `references/coordinator-sessions.md`; for remembering or recalling, read `fnl-session-hygiene`'s `references/knowledge.md`. Saved handovers are in `fnl-session-hygiene` "Handover content". Read only the reference the question needs; explaining it runs nothing.

When a question is about the plugin's own behaviour and the file does not say, say that it does not, and name the file you read.

## Bricks and choices

The pack is a box of bricks plus a guideline: choose the pieces that help and how much work other AI helpers do. This idea is inspired by the turnaround of the LEGO Group under Jørgen Vig Knudstorp. This project is independent and is not sponsored by or affiliated with the LEGO Group.

Delegation mode governs handing a task to another model family. Sessions or headless runs of the host's own family follow `fnl-delegate`'s project and context rules, retain delegate authority limits, and start with a one-line reason when no offer is needed. Manual does that only when you ask; suggest (the default) offers a helper and waits for yes; auto follows the guideline for independent tasks with clear acceptance tests, records the choice and tells you afterward. Auto relies on the agent's judgment unless a hook or host setting backs it; it never guarantees 100% compliance. Safety checks and authority to publish changes stay the same in every mode.

Routing means starting with the coding guideline. It defaults to on; off removes this pack's start reminder on Claude Code and Codex, while named skills still work and `fnl-coding-router` can still load from its description. Codex hooks need your trust. Antigravity's static always-on rule cannot honor this switch; existing instructions can still require the guideline on any host. Ask `/fnl-setup` to choose or Check to see effective settings and what remains unverified.
