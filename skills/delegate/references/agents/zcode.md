# ZCode

How ZCode is dispatched as a delegate, what ends its run, and how its result maps to a ledger outcome. Read [agents.md](../agents.md) first: its common procedure (brief lint, private log folder, `delegate_env.py`, hard-cap wrapper, residual risk) holds for every family.

ZCode is Z.ai's coding agent ([zai-org/ZCode](https://github.com/zai-org/ZCode), Apache-2.0). The facts below come from its own CLI documentation, [zai-org/ZCode](https://github.com/zai-org/ZCode) `apps/zcode-cli/docs/usage/` (`02-cli-reference.md`, `05-permissions.md`, `13-automation.md`), read on 12/11/2026; they were not run on the machine that wrote them, so the first dispatch on a machine starts with the check at the end of this file. Delegation to ZCode covers code tasks, advice and reviews (in `plan` mode, routed by `review_route.py` since 17/11/2026); the away advisor form refuses it.

- **Headless**: `python3 -I <this skill folder>/scripts/delegate_env.py --family zcode -- <zcode executable> --prompt "$(cat "$B")" --cwd <worktree, absolute> --mode <plan|edit> --disallowed-tools "AskUserQuestion EnterPlanMode ExitPlanMode" --output-format json --no-color`, run in the worktree under the hard-cap wrapper. Always pass `--mode`: a `--prompt` run defaults to `yolo`. ZCode has no `--model`, `--effort`, `--max-turns` or `--allowed-tools` flag: the model comes from ZCode's own configuration and the runtime limit from the wrapper, which kills the whole process group.
- **Modes**: `edit` for code tasks: workspace file edits need no approval and everything else follows `build`, where an action that needs approval fails in a run with no client, so the delegate cannot run shell commands and the coordinator runs the brief's tests itself. `plan` for advice: it restricts ordinary writes and command execution, but it is not an operating-system sandbox and still allows some non-destructive MCP and session tools. Never `yolo` (ordinary tools skip permission prompts; ZCode's docs keep it for isolated unattended runs), `guarded` (dangerous commands still ask, so it is not for unattended runs) or `build` (its approvals fail headless). A `deny` or `allow` rule in ZCode's configuration does not replace isolation.
- **Denials**: a denied action goes back to the model as a tool error and the run can continue and exit 0, so the exit code alone never proves the tools ran; read the result, stderr and the diff.
- **Result**: with `--output-format json`, stdout holds one object whose `response` is the final answer, beside `sessionId`, `traceId` and `projection.status`; ZCode says the fields can change between builds, so a result without a string `response` is an `error`. stderr holds diagnostics; an error path may print only stderr.
- **Provenance and data**: the brief and the repository code ZCode reads go to the model provider set in ZCode's configuration (Z.ai's coding plan by default, or another provider the user configured), under that provider's terms. ZCode keeps diagnostic model-io logs on the machine; check its retention setting before dispatching private code. It runs as `node … zcode.cjs` or a single executable, so the process snapshot does not count it.

JSON result → ledger outcome:

| Result | Outcome | Next |
| --- | --- | --- |
| exit 0 with a string `response` | verify, then `accepted` / rework / `rejected` | an answer that asks for approval or says an action was denied is unfinished work: `needs-permission` |
| an answer or stderr showing a denied action | `needs-permission` | never grant on the user's behalf; rewrite the brief edit-only or route the work elsewhere |
| the wrapper's time limit or a signal | `timeout` | run the handover |
| a provider error in stderr naming quota, rate limit or 429 | `quota` | the quota fallback in [dispatch.md](../dispatch.md), keeping its tier rules |
| exit 1, a missing `response`, or anything else | `error` | read stderr, then reroute |

First dispatch on a machine (advisory, agent judgment): run ZCode's own permission check from `05-permissions.md` in a throwaway folder, with the chosen executable, before any real brief: in `plan` a file write is refused, in `edit` a file write succeeds and a shell command is refused. Record the date and the ZCode version in host config `## ZCode`; when either result differs, do not dispatch ZCode and say so.
