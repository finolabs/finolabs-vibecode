# Workflow: obra/superpowers

Read this when the repository works with [obra/superpowers](https://github.com/obra/superpowers) (MIT). The pack supplies process skills; the steps are those of [none.md](none.md), and the router's depth, gates, proof, "Proportion" and checkpoint still apply.

## Detect

The pack's skills are installed for this repository, or the repository's or the user's scoped instructions adopt it. Its skills include `brainstorming`, `writing-plans`, `executing-plans`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`, `using-git-worktrees` and `finishing-a-development-branch`. Check which are actually present.

## Steps

| Step in none.md | Carried by |
| --- | --- |
| 1. Clarify | `brainstorming` when the intent or design is open; `shape` when `brainstorming` is missing. Stop when the criteria are checkable. Run that skill's interview, but put its questions through the host's native question tool (advisory, agent judgment). |
| 2. Plan | `writing-plans`, then `executing-plans`; `subagent-driven-development` only within the router's child budget and `delegate`. |
| 3–4. Red, smallest change | `test-driven-development`; `systematic-debugging` for a bug, failing CI or unexplained behavior. |
| 5. Prove | `checks`; `verification-before-completion` supplies the habit, not the acceptance. |
| 6. Review | `review-gate`, plus `security-review-gate` when its triggers hit; `requesting-code-review` and `receiving-code-review` feed it. |
| Branches | `using-git-worktrees` and `finishing-a-development-branch`, within `commit-messages` "Branches". |

The router's depth decides the ceremony, including where a skill of this pack says it must always run first. At MIN, go straight to step 3 with the criteria already clear: no brainstorming or written plan.

## What yields

In a Spec Kit repository, Spec Kit replaces this pack's process skills ([speckit.md](speckit.md)); debugging and test-first skills still work inside its phases. The gates are ours: this pack's review and verification skills inform `review-gate` and `checks` and do not replace them.

## Gaps

A skill named above that the session does not have: carry that step as none.md describes and say so in the receipt.
