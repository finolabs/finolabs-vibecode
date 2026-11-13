# Setup menu (after core)

The beginner skips companion questions/extras and the instructions offer. Quick opens `companions` directly unless declined. Advanced skips recorded declines on a bare run; otherwise interviews, then offers extras. `add <feature>` works in either.
Show feature/cost lines in Advanced. Load selected features only. For each extra, ask "Explore <the plain-language goal of this feature>?"
Yes: Open only that interview; no feature setting changes or data is sent by this answer. Each later grant keeps its own approval.
No: Save only <feature>: declined in Setup features in local host.md; leave feature settings unchanged. Ask later with add <feature>.
Undo: Run add <feature> to revisit it.
Choices: "Yes, explore this option" / "No, skip this option".
Ask `Needs:` separately, once per run: a need this run already answered (the core scan, say) reuses that answer, yes or no; declining it ends the dependent feature and never records consent as given.
Menu No: `python3 -I <this skill folder>/scripts/setup_features.py decline <feature> --yes`; a bare run does not offer it again (`show` lists them); that record is not a consent; `add <feature>` always asks again. Companions: own procedure. Last offer instructions here: "Draft instructions for how AI helpers should work with you?"
Yes: Open the instructions interview and draft locally; no instruction file changes before its separate approval. The draft uses your current AI provider.
No: Leave instruction files unchanged; ask later with /setup instructions.
Undo: Discard the draft; saved files have their own backup/undo step.
Choices: "Yes, draft instructions" / "No, leave instructions unchanged".

| Feature | Scope | Holds |
| --- | --- | --- |
| `delegation` | user | helper settings, Antigravity test grants |
| `roles` | user | reviewers, evidence checker, posting |
| `quota` | user | AI usage checks |
| `afk` | user | away-session permissions and limits |
| `metrics` | user | private counts, progress, running programs |
| `compaction` | user | conversation limits |
| `companions` | user | optional helpers; prints commands only |
| `project` | project | task counts, display name |
| `checks` | project | the repository's check list; runs nothing |

Install nothing (advisory, agent judgment).
