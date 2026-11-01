# finos-vibe-code

One engineering practice for AI coding agents, packaged as a single plugin with a focused skill set. It tells an agent how to route a change, how deep to go, how to delegate to other agents and accept their work, how to commit, version and release, and which review and verification gates a change must pass.

Version: `0.1.0-dev` (phase 0; see `fnl-versioning`). Targets: Claude Code and Codex, from one `skills/` folder.

## Skills

Every skill carries the `fnl-` prefix.

| Skill | Use it when |
| --- | --- |
| `fnl-coding-workflow` | Starting or resuming any coding work: Spec Kit first, fallback router, depth (MIN, NORMAL, DEEP), the Spec Kit depth gate, the stop-before-a-third-fix checkpoint. |
| `fnl-session-hygiene` | Context passes about 60%, a phase changes, a title is stale, work moves to another session or writer. |
| `fnl-orchestration` | Delegating to Codex, Antigravity or Claude Code sessions: grade, route, quota fallback, at most 5 parallel runs, time budgets, liveness from artifacts, heavy-job lock, verify-before-accept, handover, dispatch ledger. |
| `fnl-orchestration-handoff` | Writing a self-contained brief and dispatching one task. |
| `fnl-orchestration-advisor` | One second opinion from a stronger, contrasting model. |
| `fnl-orchestration-committee` | Stuck or looping: two contrasting agents find the root cause and a plan. |
| `fnl-coordinator-sessions` | Running a spec as a coordinator plus one app session per task, with standby sessions and review gates. |
| `fnl-versioning` | Version bumps, tags, changelog and release notes (SemVer, `0.y.z` until a stable release is declared, immutable `vX.Y.Z` tags, Keep a Changelog). |
| `fnl-commit-messages` | Atomic commits, imperative subjects, no secrets or build output, host attribution trailer, PR descriptions. |
| `fnl-review-gate` | Independent code review after each user story and before merge; a disposition for every finding; a regression test per runtime fix. |
| `fnl-security-review-gate` | Changes to auth, permissions, private data, untrusted input or payments; permission-boundary review with negative tests that prove no existence leak. |
| `fnl-verification` | Choosing targeted tests, reading the evidence, accepting someone else's work, claiming done. |
| `fnl-open-source-review` | Before a repository goes public: license, secrets in tree and history, internal leaks, clean payload, community files, identity, data flow, plugin checks. |

## Install

The plugin is not published yet. To try it from a local checkout for one session:

```bash
claude --plugin-dir /path/to/finos-vibe-code
```

Once it is listed in the `finolabs-plugins` marketplace:

```text
/plugin marketplace add <owner>/finolabs-plugins
/plugin install finos-vibe-code@finolabs-plugins
```

Codex reads `.codex-plugin/plugin.json`, which points at the same `skills/` folder.

## Host configuration

The orchestration skills keep machine facts (agent commands, paths, allow-rules, lock path, parallel limit) outside the plugin, in a host config file: `ORCHESTRATION_HOST_CONFIG`, else `~/.claude/orchestration/host.md`. Start from `skills/fnl-orchestration/references/host-template.md`. The dispatch ledger defaults to `~/.claude/orchestration/ledger.jsonl` (`ORCHESTRATION_LEDGER` overrides it).

## Layout

```text
.claude-plugin/plugin.json   Claude Code manifest (the version's single source of truth)
.codex-plugin/plugin.json    Codex manifest, version kept equal
skills/fnl-*/SKILL.md        one skill per folder, references/ and scripts/ beside it
LICENSE                      MIT
CHANGELOG.md                 Keep a Changelog
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as [SECURITY.md](SECURITY.md) describes.

## License

MIT. See [LICENSE](LICENSE).

## Validate

```bash
claude plugin validate .
```

The repository root `CLAUDE.md` is context for agents working on this repository; the validator warns that a plugin does not load it, which is intended.
