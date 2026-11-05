---
name: fnl-set-mode
description: Show or change Delegation mode and Routing with their effective sources and environment overrides. Run only when the user asks.
disable-model-invocation: true
argument-hint: "[manual|suggest|auto] [routing on|off]"
---

# Set delegation and routing preferences

The agent enforces the user's clear yes by judgment; the script enforces preview by default, atomic writes and symlink refusal. No network or model call is needed. `fnl-delegate` explains the delegation rules; this skill works alone to show or save preferences.

1. With no arguments run `python3 -I <this skill folder>/scripts/mode.py show` and report effective Delegation mode and Routing, each with its source: `FNL_DELEGATION_MODE` / `FNL_ROUTING`, host config, or default (`suggest` / `on`). Environment values take precedence; invalid values use defaults. When an environment variable is set, say explicitly that it overrides the file and writing the file has no effect while it remains set. Change no environment or shared settings.
2. For a request such as `manual routing off`, run `python3 -I <this skill folder>/scripts/mode.py set --delegation-mode manual --routing off` without `--yes`. Include only the requested setting flags. Show the old and proposed values and any environment override; ask for a clear yes to the shown change, through the host's native question tool when the session has one. Manual means other-family handoffs only when asked; suggest offers and waits; auto follows the guideline. Own-kind sessions and authority limits follow `fnl-delegate`. Routing off removes this pack's session-start reminder on supported hosts, while named skills and stronger existing instructions still apply. Auto is never 100%. Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes.
3. Only after that yes, repeat the same `set` command with `--yes`. It uses the delegation host config path (`ORCHESTRATION_HOST_CONFIG`, else the canonical `~/.finolabs/vibecode/host.md`, or the existing legacy file while the canonical file is absent). A new file uses the canonical location. It replaces only the requested `## Delegation mode` / `## Routing` sections; other bytes stay intact. Every symlinked path component is refused. Read the result: exit 0 alone does not prove a write.
4. Report the result and the effective values from `show`, including any override that still wins. A refusal leaves the change pending; do not bypass it.
