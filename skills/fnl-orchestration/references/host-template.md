# Orchestration host config: <machine name>

Machine-specific facts for the `fnl-orchestration` skills. The skills hold what is true on any host; this file holds paths, commands and permission rules for one machine. Keep it outside the plugin (default `~/.claude/orchestration/host.md`, or the path in `ORCHESTRATION_HOST_CONFIG`) so plugin updates never overwrite it. Changing an allow-rule or a shared setting listed here needs the owner's approval.

## Limits

- Parallel dispatches: at most <N> at one time (5 or fewer).
- Machine role: <daily workstation | CI box>. Heavy jobs at one time: <1>.
- Heavy jobs: <container-backed suites, scale measurements, end-to-end suites>.
- Heavy-job lock: `<absolute path, e.g. ~/.claude/orchestration/heavy.lock>`.
- Fixture size for local tests and measurements: <e.g. about 1,000 items unless the owner asks for more>.

## Briefs folder

Durable, never `/tmp` or a session scratchpad. Default: `.orchestration/` at the main checkout's root, as `fnl-orchestration` "Where files go" says. Per-project exceptions: <project → folder>.

Brief preamble that lets a delegated agent skip its own workflow entry read: "<preamble text>".

## Codex

Invocation with a hard cap and the extra directories the toolchain needs:

```bash
B="<brief file>"; O="<logs folder>"; W="<worktree>"; T="<task label>"
<hard-cap wrapper, e.g. perl -e 'alarm 5400; exec @ARGV'> <codex path> exec \
  -s workspace-write -C "$W" -o "$O/$T-last.txt" "$(cat "$B")" \
  < /dev/null > "$O/$T-codex.log" 2>&1; echo "$T=$?"
```

- Reviews and advice: `-s read-only`.
- Machine quirks: <e.g. broken Node shim on PATH, missing `timeout`>.

## Antigravity (agybird)

- Runner command: <node binary> <agybird runner path> --category code --mode write --cwd "<worktree>" --new-session --model <slug> --timeout 30m
- Allowed models: <list>. Quota is per model and per pool.
- Allow-rules: <file path and the command prefixes allowed>. Everything else ends the run `needs_permission` or `blocked`.

## Claude Code sessions

- How task sessions start on this host: <desktop app session tools | `claude -p` headless>.
- Session title convention: <project, feature, activity>.
