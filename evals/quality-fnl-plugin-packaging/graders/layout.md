---
type: llm
weight: 1
---

Pass if the answer recommends a separate manifest per host (.claude-plugin/plugin.json, .codex-plugin/plugin.json, .antigravity-plugin/plugin.json) sharing one skills/ folder, AND explains that a single root plugin.json does not work for all three because Codex and Antigravity both read a root plugin.json with conflicting schemas. Fail if it endorses one root plugin.json for all hosts.
