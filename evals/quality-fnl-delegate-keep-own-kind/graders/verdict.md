---
type: regex
target: last_message
match: contains
flags: i
---

^(?![\s\S]*(?:this could go to\s+Codex|(?:hand[ -]?off|hand(?:ing)?\s+(?:it|these|the(?:se)?\s+tasks?)\s+off|delegat(?:e|ing))\s+to\s+Codex|(?:offer|propos)(?:s|es|e|ing|al)?[^.!?\n]{0,80}\bCodex\b[^.!?\n]{0,80}(?:say yes|approv|hand[ -]?off)))[\s\S]*\bworktree\b
