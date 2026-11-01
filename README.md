# finolabs-vibecode

One engineering practice for AI coding agents, packaged as a single plugin with a focused skill set. It tells an agent how to route a change, how deep to go, how to delegate to other agents and accept their work, how to commit, version and release, and which review and verification gates a change must pass.

Version: `0.1.0-dev` (phase 0; see `fnl-versioning`). Targets: Claude Code, Codex and Antigravity, from one `skills/` folder.

## Skills

Every skill carries the `fnl-` prefix.

| Skill | Use it when |
| --- | --- |
| `fnl-coding-router` | Starting or resuming any coding work: Spec Kit first, fallback router, depth (MIN, NORMAL, DEEP), the Spec Kit depth gate, the stop-before-a-third-fix checkpoint. |
| `fnl-session-hygiene` | Context passes about 60%, a phase changes, a title is stale, work moves to another session or writer. |
| `fnl-delegate` | Coordinating Claude Code, Codex and Antigravity from whichever one you run in: grade, route by agent and model through a dated capability map, an optional route judge, quota fallback, at most 5 parallel runs, time budgets, liveness from artifacts, heavy-job lock, verify-before-accept, handover, dispatch ledger. |
| `fnl-handoff` | Writing a self-contained brief and dispatching one task. |
| `fnl-advisor` | One second opinion from a stronger, contrasting model. |
| `fnl-committee` | Stuck or looping: two contrasting agents find the root cause and a plan. |
| `fnl-coordinator-sessions` | Running a spec as a coordinator plus one app session per task, with standby sessions and review gates. |
| `fnl-versioning` | Version bumps, tags, changelog and release notes (SemVer, `0.y.z` until a stable release is declared, immutable `vX.Y.Z` tags, Keep a Changelog). |
| `fnl-commit-messages` | Atomic commits, imperative subjects, no secrets or build output, host attribution trailer, PR descriptions. |
| `fnl-review-gate` | Independent code review after each user story and before merge; a disposition for every finding; a regression test per runtime fix. |
| `fnl-security-review-gate` | Changes to auth, permissions, private data, untrusted input or payments; permission-boundary review with negative tests that prove no existence leak. |
| `fnl-verification` | Choosing targeted tests, reading the evidence, accepting someone else's work, claiming done. |
| `fnl-plugin-packaging` | Packaging skills as a plugin for Claude Code, Codex and Antigravity from one repository: layout, manifests, icon, marketplaces, checks. |
| `/fnl-setup` | First run on a machine or repository: host config, local file placement, the agent-skills block in `CLAUDE.md` or `AGENTS.md`. Typed by the user. |
| `/fnl-setup-instructions` | Interview the user and write their user-scoped instructions for Claude Code, Codex and Antigravity from one shared source. Typed by the user. |
| `/fnl-status` | Open delegated runs and first-pass acceptance per agent and model, from the dispatch ledger. Typed by the user. |
| `/fnl-ask` | Not sure which skill fits: describe the situation and get the next command, including companion skills from other packs. Typed by the user. |
| `fnl-open-source-review` | Before a repository goes public: license, secrets in tree and history, internal leaks, clean payload, community files, identity, data flow, plugin checks. |

### Agents

Read-only subagents in `agents/` that apply the skills above in a fresh context:

| Agent | Use it when |
| --- | --- |
| `fnl-reviewer` | Independent code and security review of a diff or commit range under `fnl-review-gate` and `fnl-security-review-gate`. |
| `fnl-verifier` | Independent check of a completion claim against the diff and targeted test output under `fnl-verification`. |

## Install

Every install path ships the same `skills/` folder. Install the whole plugin on a host, or pick single skills with [skills.sh](https://skills.sh); choose one way per agent, because both together list every skill twice. The repository is its own marketplace for each host.

### Claude Code

```text
/plugin marketplace add fioenix/finolabs-vibecode
/plugin install finolabs-vibecode@finolabs-vibecode
```

Skills are namespaced, for example `/finolabs-vibecode:fnl-handoff`. To try a local checkout for one session: `claude --plugin-dir /path/to/finolabs-vibecode`.

### Codex

```bash
codex plugin marketplace add fioenix/finolabs-vibecode
```

```bash
codex plugin add finolabs-vibecode@finolabs-vibecode
```

### Antigravity

```bash
agy plugin install https://github.com/fioenix/finolabs-vibecode
```

### Single skills, any agent

```bash
npx skills add fioenix/finolabs-vibecode
```

The installer lists the skills to choose from; `--skill <name>` takes one directly and `-a <agent>` picks the agent. It copies editable files into your project (`-g` for every project): update them with `npx skills update`. The plugin path also carries the agents, the session hook and the Antigravity rule, which single-skill installs leave out.

Each skill works alone, with one exception: `fnl-handoff`, `fnl-advisor`, `fnl-committee`, `fnl-coordinator-sessions` and `fnl-status` need `fnl-delegate` beside them. Other skills mention their neighbours by name and work without them. A sensible first pick: `fnl-coding-router`, `fnl-verification`, `fnl-review-gate`, `fnl-commit-messages`, plus `fnl-setup` to configure them.

### First check

Ask your agent: "Route this change through the coding router and tell me the depth you chose." It should load `fnl-coding-router`.

## Works well with

These skills set the gates and the routing; they do not try to replace good phase tools. They pair with [Matt Pocock's skills](https://github.com/mattpocock/skills) (MIT): `tdd` and `diagnosing-bugs` inside the work `fnl-coding-router` routes, `code-review` as the reviewer's instrument in the review gate, `grilling` and `prototype` for clarification, `pr` for pull request bodies, `/handoff` for portable handovers. Install that pack with its own instructions; `/fnl-ask` points to its skills when they fit. The two packs are independent projects.

For reviews, the gates and the `fnl-reviewer` agent use each host's native instruments: `/code-review`, `/security-review` and `claude ultrareview` on Claude Code, `codex review` on Codex. Antigravity has no native AI review, so its reviews route to the other two. For security audits, they recommend [Cloudflare's `security-audit` skill](https://github.com/cloudflare/security-audit-skill) (MIT):

```bash
npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit
```

## Host configuration

The orchestration skills keep machine facts (agent commands, allowed models, which delegates each coordinator can reach, the route judge, allow-rules, lock path, parallel limit) outside the plugin, in a host config file: `ORCHESTRATION_HOST_CONFIG`, else `~/.claude/orchestration/host.md`. Start from `skills/fnl-delegate/references/host-template.md`. The dispatch ledger defaults to `~/.claude/orchestration/ledger.jsonl` (`ORCHESTRATION_LEDGER` overrides it). When Codex or Antigravity also coordinates, put both files where every coordinator's sandbox can read and write them.

The route judge is optional. Routing is complete without one; a judge such as TypeSafe's Jev, called through its own `typesafe-ai` skill, settles only the calls the rules leave open, and the plugin holds no key for it.

## Layout

```text
.claude-plugin/plugin.json        Claude Code manifest (the version's single source of truth)
.claude-plugin/marketplace.json   Claude Code marketplace listing this repository
.codex-plugin/plugin.json         Codex manifest, version kept equal
.antigravity-plugin/plugin.json   Antigravity manifest, version kept equal
.agents/plugins/marketplace.json  Codex marketplace listing this repository
agents/fnl-*.md                   read-only reviewer and verifier subagents
agents/openai.yaml                Codex skill-list display metadata
skills/fnl-*/SKILL.md             one self-contained skill per folder, references/ and scripts/ beside it
hooks/                            Claude Code hooks (session-start reminder)
rules/                            Antigravity always-on rules (session-start reminder)
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
agy plugin validate . --strict
```

```bash
claude plugin eval . --tag trigger --ablation none
```

```bash
claude plugin eval . --tag quality --ablation none --scaffold
```

The eval suite checks that each skill fires on a representative prompt and that unrelated prompts load none. The repository root `CLAUDE.md` is context for agents working on this repository; the validator warns that a plugin does not load it, which is intended.

## Acknowledgements

This pack stands on other people's work. Thank you to:

- **Matt Pocock** and [mattpocock/skills](https://github.com/mattpocock/skills) ([overview](https://www.aihero.dev/skills)), MIT. Its `/setup-matt-pocock-skills` and `/ask-matt` skills inspired `/fnl-setup` and `/fnl-ask`; its user-invoked and model-invoked split, its grilling interview and its `writing-for-agents` guidance shaped how these skills are written. No text is copied, and the two packs are independent projects.
- [Cloudflare's security-audit skill](https://github.com/cloudflare/security-audit-skill), MIT, which the security gates recommend for audits.
- [Spec Kit](https://github.com/github/spec-kit) by GitHub, which `fnl-coding-router` routes through first.
- [Superpowers](https://github.com/obra/superpowers) by Jesse Vincent, whose process skills (brainstorming, systematic debugging, test-driven development, verification before completion, code review requests) fill the fallback router.
- [Paseo](https://github.com/getpaseo/paseo), whose advisor, committee and handoff skills were the reference design for the delegation skills.
- Anthropic's [skills repository](https://github.com/anthropics/skills) and its `skill-creator`, and the [Agent Skills](https://agentskills.io) format that lets one `skills/` folder serve several hosts.
- The packaging documentation of [Claude Code](https://code.claude.com/docs/en/plugins/manifest-reference.md), [Codex](https://developers.openai.com/codex/plugins/build) and [Antigravity](https://antigravity.google/docs/build-plugins).
- [TypeSafe](https://docs.typesafe.ai), whose cookbooks informed the activity-selection reference.
- [Semantic Versioning](https://semver.org/), [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
