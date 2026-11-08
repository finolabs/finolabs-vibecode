# Delegation host config: <machine name>

Machine-specific facts for the `fnl-delegate` skills. The skills hold what is true on any host; this file holds paths, commands and permission rules for one machine. Keep it as `host.md` under the resolved data root so plugin updates never overwrite it. `ORCHESTRATION_HOST_CONFIG` may supply non-consent settings only; opt-ins and Routing always use the canonical file. When more than one agent coordinates, use `fnl-setup` to locate the data root where every coordinator's sandbox can read and write it and its `ledger.jsonl`. Changing an allow-rule or a shared setting listed here needs the owner's approval.

## Delegation mode

suggest

## Routing

on

## Agents on this machine

Coordinator: unverified

| Agent | Present | Version | Allowed models (confirmed by user) | Checked |
| --- | --- | --- | --- | --- |
| Claude Code | unverified | unverified | unverified | unverified |
| Codex | unverified | unverified | unverified | unverified |
| Antigravity | unverified | unverified | unverified | unverified |

## Delegate environment

<!--
The `Delegate environment` section accepts only blank lines and `- <family>: none` or one
`- <family>: <NAME>` per variable; replace `none` when adding names. Families are `claude`, `codex`,
`antigravity`. Names match `^[A-Z][A-Z0-9_]{0,63}$`, with no duplicates, values or wildcards.
Loader/interpreter controls, `GIT_*`, `*_PROXY`, `SSL_CERT_*` are refused by `delegate_env.py`.
A name containing KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, SESSIONID or SESSID anywhere, or
PASS, PASSWD, PASSPHRASE, AUTH, COOKIE, COOKIES, SESSION or PRIVATE as a complete
underscore-delimited part, needs its own setup Yes and No naming both name and family;
only that Yes records `- <family>: <NAME>; approved: yes`.
The wrapper reads canonical host config, not an environment-selected file. Default: none.
HOME remains: protection is environment-only; credential files remain reachable. Report this residual risk.
Private HOME is an open owner decision and is not offered or created in this package.
-->

- claude: none
- codex: none
- antigravity: none

## Agent roles

- code review: antigravity
- security review: codex
- navigator: claude
- judge: host

## Review posting

- claude: unverified (checked 2026-11-07)
- codex: unverified (checked 2026-11-07)
- antigravity: unverified (checked 2026-11-07)

## Quota probe

- Quota probe: off
- Date: <YYYY-MM-DD>

Advisory (agent judgment): use `/fnl-setup add quota` to opt in after the scan and confirm its path preview. The setup script writes `Agents`, `Executable <agent>`, optional `Interpreter <agent>`, and `Claude config: <label>: <absolute folder>` lines; replace this explanation with that generated section when enabling. The on-demand `quota_probe.py read --family <f>` command enforces the canonical opt-in, a minimum 15-minute age, backoff, one in-flight reading and `FNL_QUOTA_PROBE=off`; hooks start no reading. Before routing, run `read` for each candidate family, then `status`. Claude Code alone can record a family-and-time StopFailure rate-limit marker; a newer successful reading overrides it and its advisory exclusion expires at the eligible reset or after one hour, never over five hours. They store only usage pools and measured times in `state/quota/quota.json`, with no environment redirect. Routing is advisory: below 10% with a future reset is out, older than 8 hours is unverified and excludes nothing, the user's statement wins, and Claude uses `week-all` separately for each install.

## Project labels

## Limits

- The parallel run limit is per project and lives in `## Project settings` (set with `fnl-setup add delegation`); lines here are ignored.

- Machine role: <daily workstation | CI box>. Heavy jobs at one time: <1>.
- Heavy jobs: <container-backed suites, scale measurements, end-to-end suites>.
- Fixture size for local tests and measurements: <e.g. about 1,000 items unless the owner asks for more>.

## Heavy jobs

- Load limit: 12
- Memory minimum GB: 3
- Wait cap minutes: 40

The lock itself needs no setting: `heavy_run.py` keeps it in the fixed anchor folder, so relocating the data root does not move it.

Choose N from 1 to 32; optional family entries may be omitted, each n is 1 to N.
Families are pools: several runs share their quota. Caps are advisory (agent judgment);
`parallel_slots.py check-config` validates these lines; a missing total defaults to 3 and a malformed project entry reports unknown.

## Effort preference

Optional. The plugin's default is `medium` effort on every agent, and one level up per grade above hard (`high` for very hard, `xhigh` for ultra hard) or after a run fell short (`models.md` "Tiers"). Write a different default here, for example "<effort level> for <which agents or kinds of work>", and it overrides that default for this machine.

## Briefs folder

Durable, never `/tmp` or a session scratchpad. Default: `.finolabs/` at the main checkout's root, as `fnl-delegate` "Where files go" says. Per-project exceptions: <project → folder>.

Brief preamble that lets a delegated agent skip its own workflow entry read: "<preamble text>".

## Coordinators and reach

Which agent can coordinate on this machine, and which delegates each one can reach (`agents.md` "When an agent coordinates"). A delegate marked unreachable is skipped by routing. `/fnl-setup scan` prefills suggested reach with present agents other than the recorded coordinator; the user still confirms reachability and permission. Presence in `Agents on this machine` restricts this table: a reach entry never makes an absent family eligible.

| Coordinator | Claude Code | Codex | Antigravity |
| --- | --- | --- | --- |
| Claude Code | — | <yes / no: reason> | <yes / no: reason> |
| Codex | <yes / no> | — | <yes / no> |
| Antigravity | <yes / no> | <yes / no> | — |

## Route judgment

Judge selection now lives only in canonical `## Agent roles`; this legacy heading retains instruction-check consent. `judge.py` caps calls at 24 per run, and no skill install is required for calls.

- Instruction check: <on | off>. Default off. `on` means the user approved, on <DD/MM/YYYY>, sending lines of their private instruction files to the configured judge for the Check judgment items. Instruction checks use the small host fallback because they are outside the four outbound sites; retention is the host provider's. It is separate from the routing approval and is global to this machine; turning it off takes effect on the next run.

## Dispatch marker

Each headless command below starts with `FNL_DISPATCH_ID=<ledger id>`, the id `ledger.py start` printed. The usage metrics read it to tell a delegated session from one the user started. It is a short label and carries no task data.

## Claude Code

- First lint the brief with `brief_check.py` from `fnl-handoff`; set `umask 077` and create the private log folder as the common procedure in `agents.md` requires; the wrapper checks its mode. Headless command: FNL_DISPATCH_ID=<ledger id> python3 -I <delegate skill folder>/scripts/delegate_env.py --family claude -- <hard-cap wrapper> <claude path> -p "$(cat "$B")" --model <full model id> --effort <level> --output-format json --max-turns <n> --max-budget-usd <cap> --allowedTools "<tools the brief needs>" < /dev/null
- Allowed models: <full model ids>.
- How task sessions start on this host: <desktop app session tools | `claude -p` headless>.
- Session title convention: <`<project> <scope>: <activity>` as `fnl-session-hygiene` says, or this machine's own>.

## Codex

Invocation with a hard cap and the extra directories the toolchain needs:

```bash
B="<brief file>"; O="<logs folder>"; W="<worktree>"; T="<ledger id>-<slug>"  # slug: a-z, 0-9, -, at most 40 characters
umask 077
# Prepare the private log folder first, as the common procedure in agents.md requires.
python3 -I <handoff skill folder>/scripts/brief_check.py "$B" || exit 1
FNL_DISPATCH_ID="<ledger id>" python3 -I <delegate skill folder>/scripts/delegate_env.py --family codex -- <hard-cap wrapper, e.g. perl -e 'alarm 5400; exec @ARGV'> <codex path> exec \
  -m <model> -c model_reasoning_effort=<level> -s workspace-write -C "$W" -o "$O/$T-last.txt" "$(cat "$B")" \
  < /dev/null > "$O/$T-codex.log" 2>&1; echo "$T=$?"
```

- Allowed models: <list>.
- Reviews and advice: `-s read-only`, or `delegate_env.py --family codex -- codex review`.
- Machine quirks: <e.g. broken Node shim on PATH, missing `timeout`>.

## Antigravity

- First lint with `brief_check.py` from `fnl-handoff`; set `umask 077` and create the private log folder as the common procedure in `agents.md` requires; the wrapper checks its mode. Command: FNL_DISPATCH_ID=<ledger id> python3 -I <delegate skill folder>/scripts/delegate_env.py --family antigravity -- <hard-cap wrapper> <agy path> -p "$(cat "$B")" --model <model id> --mode accept-edits --output-format json --print-timeout 30m, or the `agybird` runner through the same `delegate_env.py --family antigravity --` wrapper when installed: <how to look up the runner's install path at each dispatch, for example a command that reads it from the host's plugin list; not a path>. Resolve it at each dispatch, never from a pinned version folder or the highest folder in the plugin cache, which keeps old versions after an upgrade.
- Allowed models and their pools: <list>.
- Per-run settings file with allow-rules: <path>. Global allow-rules: <file path and the command prefixes allowed>. Everything else is soft-denied.
- Rules the user granted per repository (test and check commands), as a record only: the grant itself lives in Antigravity's settings or the user's answer. <repository: literal commands, date approved>.
