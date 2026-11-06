# Workflow: mattpocock/skills

Read this when the repository works with [mattpocock/skills](https://github.com/mattpocock/skills) (MIT). The pack supplies phase tools; the steps are those of [none.md](none.md), and the router's depth, gates, proof, "Proportion" and checkpoint still apply.

## Detect

The pack's skills are installed for this repository (for example under `.claude/skills/` or as a project plugin), or the repository's or the user's scoped instructions adopt it. Its skills include `grilling` (typed as `/grill-me` or `/grill-with-docs`), `prototype`, `tdd`, `diagnosing-bugs`, `code-review`, `to-spec`, `to-tickets`, `implement`, `implement-spec`, `pr` and `handoff`. Check which are actually present.

## Steps

| Step in none.md | Carried by |
| --- | --- |
| 1. Clarify | `grilling` when the intent is open; `/grill-with-docs` also keeps a glossary and ADRs. Stop when the criteria are checkable. Run that skill's interview, but put its questions through the host's native question tool (advisory, agent judgment). |
| 2. Plan | `prototype` for a design question only code can answer; `to-spec` and `to-tickets` for work larger than one pass, then `implement` or `implement-spec` over what they produced. |
| 3–4. Red, smallest change | `tdd` for the red-green loop; `diagnosing-bugs` for a bug, failing CI or unexplained behavior. |
| 5. Prove | `fnl-verification`; the red and green that `tdd` and `diagnosing-bugs` leave are its evidence. |
| 6. Review | `fnl-review-gate`, with `code-review` as the reviewer's instrument, plus `fnl-security-review-gate` when its triggers hit. |
| Pull request, handover | `pr` for the description, `handoff` for a portable handover. |

At MIN, go straight to step 3 with the criteria already clear: no grilling, spec or tickets.

## What yields

In a Spec Kit repository, Spec Kit owns the process: this pack's process skills (`to-spec`, `to-tickets`, `implement`, `implement-spec`) yield to it, and its phase tools work inside Spec Kit phases ([speckit.md](speckit.md)). The gates are ours: `code-review` informs `fnl-review-gate` and does not replace it.

## Gaps

A skill named above that the session does not have: carry that step as none.md describes and say so in the receipt.
