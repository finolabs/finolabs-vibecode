# Explain

Read the shared rules in [map.md](map.md#rules).

The user asks how a skill, agent or script works. Read its `SKILL.md`, `agents/<name>.md` or the script's header comment and argument definitions (read the file; run nothing), then answer in plain words: what it does, when it fires (typed by the user, or loaded by the agent), what it needs and writes, what it costs (quota, time, a confirmation), and what to type. Keep it to about six lines, or one short paragraph and a few bullets, then offer to go deeper on the part they care about (steps, cost, limits); leave the rest in the file. For a companion skill from another pack, say in one line what it is and that it is a separate project.

For a committee, read `advisor`'s `references/committee.md`; for spec coordinator sessions, read `delegate`'s `references/coordinator-sessions.md`; for remembering or recalling, read `session-hygiene`'s `references/knowledge.md`. Saved handovers are in `session-hygiene` "Handover content". Read only the reference the question needs; explaining it runs nothing.

When a question is about the plugin's own behaviour and the file does not say, say that it does not, and name the file you read.

## Bricks and choices

The pack is a box of bricks plus a guideline: choose the pieces that help and how much work other AI helpers do. This idea is inspired by the turnaround of the LEGO Group under Jørgen Vig Knudstorp. This project is independent and is not sponsored by or affiliated with the LEGO Group.

Delegation mode governs handing a task to another model family. Sessions or headless runs of the host's own family follow `delegate`'s project and context rules, retain delegate authority limits, and start with a one-line reason when no offer is needed. Manual does that only when you ask; suggest (the default) offers a helper and waits for yes; auto follows the guideline for independent tasks with clear acceptance tests, records the choice and tells you afterward. Auto relies on the agent's judgment unless a hook or host setting backs it; it never guarantees 100% compliance. Safety checks and authority to publish changes stay the same in every mode.

Routing means starting with the coding guideline. It defaults to on; off removes this pack's start reminder on Claude Code and Codex, while named skills still work and `coding-router` can still load from its description. Codex hooks need your trust. Antigravity's static always-on rule cannot honor this switch; existing instructions can still require the guideline on any host. Use `/setup mode` to see or change both settings and their sources. Environment overrides win, so writing the file has no effect while they are set. `/setup scan` refreshes the inventory of present families and user-confirmed allowed models; routing uses only present families, and with no other family present delegation is off. Both commands preview changes and wait for a clear yes before writing only their host config sections. `/setup check` reports a missing or stale inventory and what remains unverified.

## Roles, verification and run hygiene

For roles and posting, read `review-gate` and its routing/posting script headers: the assigned family is a preference, independence comes first, and a posting setting is verified only after the expected author and marker are observed. For drift, read `agents/fnl-navigator.md` and `delegate`’s navigator procedure. For acceptance, read `checks`: a current-head receipt gates ledger acceptance, with a reason-digested escape hatch; neither a test tick nor a judge answer accepts work.

The judge defaults to a small host model; optional Jev uses the scoped network exception through `judge.py`, with user authorization and budget, screened payloads and reported host fallback. `typesafe-ai` is optional cookbook guidance, outside the call path. For hygiene, explain `brief_check.py`, `delegate_env.py`, `run_env.py` and `log_scan.py show`; protection covers allowlisted headless forms and local logs, while HOME remains reachable. Quota is read on demand before routing; the Claude Code StopFailure marker stores only family and time and starts no reading.

`route_task.py` prints a matrix recommendation, not a selected model. `parallel_slots.py` reports advisory capacity from the user's total and optional family caps; it reserves nothing. For work records, read the coding router's `references/work-record.md` and the `project` setup feature. For context, explain the Claude Code/Antigravity status-line recorder and its parallel-session ambiguity; Codex is not covered. Relay counters remain unimplemented.
