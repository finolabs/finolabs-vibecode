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

Every install path ships the same `skills/` folder. The repository is its own marketplace for each host.

### Claude Code

```text
/plugin marketplace add fioenix/finos-vibe-code
/plugin install finos-vibe-code@finos-vibe-code
```

Skills are namespaced, for example `/finos-vibe-code:fnl-orchestration-handoff`. To try a local checkout for one session: `claude --plugin-dir /path/to/finos-vibe-code`.

### Codex

```bash
codex plugin marketplace add fioenix/finos-vibe-code
```

```bash
codex plugin add finos-vibe-code@finos-vibe-code
```

### First check

Ask your agent: "Route this change through the coding workflow and tell me the depth you chose." It should load `fnl-coding-workflow`.

## Host configuration

The orchestration skills keep machine facts (agent commands, paths, allow-rules, lock path, parallel limit) outside the plugin, in a host config file: `ORCHESTRATION_HOST_CONFIG`, else `~/.claude/orchestration/host.md`. Start from `skills/fnl-orchestration/references/host-template.md`. The dispatch ledger defaults to `~/.claude/orchestration/ledger.jsonl` (`ORCHESTRATION_LEDGER` overrides it).

## Layout

```text
.claude-plugin/plugin.json        Claude Code manifest (the version's single source of truth)
.claude-plugin/marketplace.json   Claude Code marketplace listing this repository
.codex-plugin/plugin.json         Codex manifest, version kept equal
.agents/plugins/marketplace.json  Codex marketplace listing this repository
agents/openai.yaml                Codex skill-list display metadata
skills/fnl-*/SKILL.md             one skill per folder, references/ and scripts/ beside it
assets/                           icon (light and dark, SVG and 512 px PNG) and its NOTICE
evals/                            trigger suite for `claude plugin eval`
LICENSE                           MIT
CHANGELOG.md                 Keep a Changelog
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as [SECURITY.md](SECURITY.md) describes.

## License

MIT. See [LICENSE](LICENSE).

## Validate

```bash
claude plugin validate . --profile directory
```

```bash
claude plugin eval . --tag trigger --ablation none
```

The eval suite checks that each skill fires on a representative prompt and that unrelated prompts load none. The repository root `CLAUDE.md` is context for agents working on this repository; the validator warns that a plugin does not load it, which is intended.
