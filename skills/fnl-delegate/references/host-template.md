# Delegation host config: <machine name>

Machine-specific facts for the `fnl-delegate` skills. The skills hold what is true on any host; this file holds paths, commands and permission rules for one machine. Keep it outside the plugin (default `${XDG_CONFIG_HOME:-~/.config}/finolabs-vibecode/host.md`, or the path in `ORCHESTRATION_HOST_CONFIG`) so plugin updates never overwrite it. When more than one agent coordinates, keep this file and the ledger (`ORCHESTRATION_LEDGER`) where every coordinator's sandbox can read and write them. Changing an allow-rule or a shared setting listed here needs the owner's approval.

## Limits

- Parallel dispatches: at most <N> at one time (5 or fewer).
- Machine role: <daily workstation | CI box>. Heavy jobs at one time: <1>.
- Heavy jobs: <container-backed suites, scale measurements, end-to-end suites>.
- Heavy-job lock: `<absolute path, e.g. ~/.local/state/finolabs-vibecode/heavy.lock>`.
- Fixture size for local tests and measurements: <e.g. about 1,000 items unless the owner asks for more>.

## Briefs folder

Durable, never `/tmp` or a session scratchpad. Default: `.orchestration/` at the main checkout's root, as `fnl-delegate` "Where files go" says. Per-project exceptions: <project → folder>.

Brief preamble that lets a delegated agent skip its own workflow entry read: "<preamble text>".

## Coordinators and reach

Which agent can coordinate on this machine, and which delegates each one can reach (`agents.md` "When an agent coordinates"). A delegate marked unreachable is skipped by routing.

| Coordinator | Claude Code | Codex | Antigravity |
| --- | --- | --- | --- |
| Claude Code | — | <yes / no: reason> | <yes / no: reason> |
| Codex | <yes / no> | — | <yes / no> |
| Antigravity | <yes / no> | <yes / no> | — |

## Route judgment

- Judge: <none | the skill name, for example `typesafe-ai`>. The user approved sending task summaries to this service on <DD/MM/YYYY>.
- Spend limit: <the judge skill's own guard, or a per-day cap>.

## Claude Code

- Headless command: <hard-cap wrapper> <claude path> -p "$(cat "$B")" --model <full model id> --effort <level> --output-format json --max-turns <n> --max-budget-usd <cap> --allowedTools "<tools the brief needs>" < /dev/null
- Allowed models: <full model ids>.
- How task sessions start on this host: <desktop app session tools | `claude -p` headless>.
- Session title convention: <`<project> <scope>: <activity>` as `fnl-session-hygiene` says, or this machine's own>.

## Codex

Invocation with a hard cap and the extra directories the toolchain needs:

```bash
B="<brief file>"; O="<logs folder>"; W="<worktree>"; T="<ledger id>-<slug>"  # slug: a-z, 0-9, -, at most 40 characters
<hard-cap wrapper, e.g. perl -e 'alarm 5400; exec @ARGV'> <codex path> exec \
  -m <model> -c model_reasoning_effort=<level> -s workspace-write -C "$W" -o "$O/$T-last.txt" "$(cat "$B")" \
  < /dev/null > "$O/$T-codex.log" 2>&1; echo "$T=$?"
```

- Allowed models: <list>.
- Reviews and advice: `-s read-only`, or `codex review`.
- Machine quirks: <e.g. broken Node shim on PATH, missing `timeout`>.

## Antigravity

- Command: <agy path> -p "$(cat "$B")" --model <model id> --mode accept-edits --output-format json --print-timeout 30m, or the `agybird` runner when installed: <runner command>.
- Allowed models and their pools: <list>.
- Per-run settings file with allow-rules: <path>. Global allow-rules: <file path and the command prefixes allowed>. Everything else is soft-denied.
- Rules the user granted per repository (test and check commands): <repository: literal commands, date approved>.
