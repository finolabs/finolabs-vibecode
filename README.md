# finolabs-vibecode

One engineering practice for AI coding agents, packaged as a single plugin with a focused skill set. It tells an agent how to route a change, how deep to go, how to delegate to other agents and accept their work, how to commit, version and release, and which review and verification gates a change must pass.

This pack owns the decisions between tools: routing, depth, delegation, gates and conventions. For the work itself it points to trusted skills and native commands from known publishers (Matt Pocock's skills, Cloudflare's security audit, Spec Kit, each host's own review commands) instead of rewriting them, and every such pointer carries a fallback that keeps the skill working when the companion is not installed.

Published by [FINOLABS](https://github.com/finolabs) and listed in its plugin catalog, [finolabs/plugins](https://github.com/finolabs/plugins). Maintained by [Fioenix](https://github.com/fioenix).

It targets Claude Code, Codex and Antigravity from one `skills/` folder. Latest release: [`v0.1.2`](https://github.com/finolabs/finolabs-vibecode/releases/tag/v0.1.2) (phase 0; see `fnl-versioning`). Between releases, `main` carries the next version with `-dev`.

The quickest install: give your coding agent this repository's link and ask it to install the plugin. The next section tells it how.

## For AI agents: install and set up

You were given this repository's link to install it for the user. Follow these steps in order.

1. **Find your host**: Claude Code, Codex, Antigravity, or another agent that reads Agent Skills.
2. **Confirm with the user before installing.** The install changes their agent configuration for every project. Offer the whole plugin by default; it carries the skills, the agents and the session reminder. Offer single skills as the alternative (see [Single skills, any agent](#single-skills-any-agent)). Install only one of the two for an agent, since both together list every skill twice.
3. **Check for an existing install first**: run `claude plugin list` and `claude plugin marketplace list` (or `codex plugin list` and `codex plugin marketplace list`). If `finolabs-vibecode` is already installed from another catalog, such as `finolabs-vibecode@finolabs-vibecode`, or Codex lists the older `Finolabs` catalog, stop and ask the user before switching: two installs list every skill twice, and on Codex the older catalog shares a cache folder with `finolabs`. The [finolabs/plugins README](https://github.com/finolabs/plugins#codex) has the migration.
4. **Install from a shell** with your host's commands:

   | Host | Commands |
   | --- | --- |
   | Claude Code | `claude plugin marketplace add finolabs/plugins`, then `claude plugin install finolabs-vibecode@finolabs` |
   | Codex | `codex plugin marketplace add finolabs/plugins`, then `codex plugin add finolabs-vibecode@finolabs` |
   | Antigravity | `agy plugin install https://github.com/finolabs/finolabs-vibecode` |
   | Other agents | `npx skills add finolabs/finolabs-vibecode -a <agent>` |

5. **Verify** that `claude plugin list`, `codex plugin list` or `agy plugin list` shows `finolabs-vibecode`. Report the command output to the user, and report any failure as it is.
6. **Hand over setup.** Plugins load when a session starts. Tell the user to open a new session and run setup: `/finolabs-vibecode:fnl-setup` on Claude Code, `$fnl-setup` on Codex, `/fnl-setup` on Antigravity. Only the user can start setup, because it interviews them before it writes host config and instructions. `/fnl-setup-instructions` does the same for their user-scoped instructions, and is optional.
7. **Offer the companions, and install them only if the user agrees:** [Matt Pocock's skills](https://github.com/mattpocock/skills) and [Cloudflare's `security-audit`](https://github.com/cloudflare/security-audit-skill) (see [Works well with](#works-well-with)). Every skill works without them.

Done when the plugin is listed by your host and the user knows to run setup in a new session.

## Skills

Every skill carries the `fnl-` prefix. The user types four of them, `fnl-setup`, `fnl-setup-instructions`, `fnl-status` and `fnl-ask` (`/fnl-setup` on Claude Code and Antigravity, `$fnl-setup` on Codex); the agent loads the others when the situation calls for them.

| Skill | Use it when |
| --- | --- |
| `fnl-coding-router` | Starting or resuming any coding work: Spec Kit first, fallback router, depth (MIN, NORMAL, DEEP), the Spec Kit depth gate, the stop-before-a-third-fix checkpoint. |
| `fnl-session-hygiene` | A session's context passes about 60%, a phase changes, a title goes stale, or work moves to another session or writer. |
| `fnl-knowledge` | Remembering and recalling decisions, lessons and project state: native agent memory for working preferences, a shared knowledge base (Orrery, or an Obsidian vault) beside it, the repository for code facts. |
| `fnl-delegate` | Coordinating Claude Code, Codex and Antigravity from whichever one you run in: grading, routing by agent and model through a dated capability map, an optional route judge, quota fallback, at most 5 parallel runs, time budgets, liveness from artifacts, the heavy-job lock, verify-before-accept, handover and the dispatch ledger. |
| `fnl-handoff` | Writing a self-contained brief and dispatching one task. |
| `fnl-advisor` | Getting one second opinion from a stronger model of another family. |
| `fnl-committee` | Work is stuck or looping: two agents from contrasting families find the root cause and a plan. |
| `fnl-coordinator-sessions` | Running a spec as a coordinator plus one app session per task, with standby sessions and review gates. |
| `fnl-versioning` | Bumping a version, tagging a release, or writing the changelog and release notes: SemVer, `0.y.z` until a stable release is declared, immutable `vX.Y.Z` tags, Keep a Changelog. |
| `fnl-commit-messages` | Committing, writing a pull request description, or working with branches: atomic commits, imperative subjects, no secrets or build output, the host attribution trailer, and the branch flow (naming, base, sync, conflicts, merge, cleanup, backports). |
| `fnl-review-gate` | A user story is done or a pull request is about to merge: an independent code review, a disposition for every finding, a regression test per runtime fix. |
| `fnl-security-review-gate` | A change touches auth, permissions, private data, untrusted input or payments: a permission-boundary review, with negative tests proving that not even a record's existence leaks. |
| `fnl-verification` | Choosing targeted tests, reading the evidence, accepting someone else's work, claiming done. |
| `fnl-plugin-packaging` | Packaging skills as a plugin for Claude Code, Codex and Antigravity from one repository: layout, manifests, icon, marketplaces, checks. |
| `fnl-setup` | First run on a machine or repository: host config, local file placement, the agent-skills block in `CLAUDE.md` or `AGENTS.md`. |
| `fnl-setup-instructions` | Writing your user-scoped instructions: it interviews you and writes them for Claude Code, Codex and Antigravity from one shared source. |
| `fnl-status` | Checking open delegated runs and first-pass acceptance per agent and model, from the dispatch ledger. |
| `fnl-ask` | You are not sure which skill fits: describe the situation and get the next command, including companion skills from other packs. |
| `fnl-open-source-review` | Before a repository goes public, and after: license, secrets in tree and history, internal leaks, clean payload, community files, repository settings, identity, data flow, plugin checks. |

### Agents

The read-only subagents in `agents/` apply the skills above in a fresh context. Each answers a different question:

| Agent | Question | Use it when |
| --- | --- | --- |
| `fnl-verifier` | Is the report true? | An agent or session says a task is done: it reruns the targeted tests, checks each acceptance criterion, and confirms the commits are where the report says. It judges facts, not design. |
| `fnl-reviewer` | Is the change good? | A pull request or story is ready: it reads every changed file, then the callers, dependencies, contracts and tests the change affects, under `fnl-review-gate`. |
| `fnl-security-reviewer` | Is the change safe? | The change crosses a sensitive boundary: it reads the changed files, then every trust path that reaches them, under `fnl-security-review-gate`. |

Both reviewers cover two rings, the change and its impact set, rather than the whole repository, and report what they traced. Delegated work is accepted only after the verifier checks it. A pull request merges only after the reviewer and the security reviewer have each posted an approving review comment for its current head commit; a push after a review needs a new review. A story closes only after the verifier and then both reviewers have passed it.

## Install

Every install path ships the same `skills/` folder. Install the whole plugin on a host, or pick single skills with [skills.sh](https://skills.sh). Choose one way per agent, because both together list every skill twice.

Claude Code and Codex install the plugin from the [FINOLABS catalog](https://github.com/finolabs/plugins), marketplace `finolabs`, which groups the FINOLABS plugins together. This repository also remains its own marketplace (`finolabs-vibecode@finolabs-vibecode`) for existing installs. Installs track `main`, which carries the next version with `-dev`; releases are the `vX.Y.Z` tags, with notes in `CHANGELOG.md` and on GitHub.

### Claude Code

```text
/plugin marketplace add finolabs/plugins
/plugin install finolabs-vibecode@finolabs
```

From a shell or an agent, run `claude plugin marketplace add finolabs/plugins`, then `claude plugin install finolabs-vibecode@finolabs`. Skills are namespaced, for example `/finolabs-vibecode:fnl-handoff`. To try a local checkout for one session: `claude --plugin-dir /path/to/finolabs-vibecode`.

### Codex

```bash
codex plugin marketplace add finolabs/plugins
```

```bash
codex plugin add finolabs-vibecode@finolabs
```

### Antigravity

```bash
agy plugin install https://github.com/finolabs/finolabs-vibecode
```

### Single skills, any agent

```bash
npx skills add finolabs/finolabs-vibecode
```

The installer lists the skills to choose from; `--skill <name>` takes one directly and `-a <agent>` picks the agent. It copies editable files into your project (or, with `-g`, for every project); update them with `npx skills update`. The plugin path also carries the agents, the session hook and the Antigravity rule, which single-skill installs leave out.

Each skill works alone, except the delegation family: `fnl-handoff`, `fnl-advisor`, `fnl-committee`, `fnl-coordinator-sessions` and `fnl-status` need `fnl-delegate` beside them. Other skills mention their neighbors by name and work without them. A sensible first pick: `fnl-coding-router`, `fnl-verification`, `fnl-review-gate`, `fnl-commit-messages`, plus `fnl-setup` to configure them.

### First check

Ask your agent: "Route this change through the coding router and tell me the depth you chose." It should load `fnl-coding-router`.

## Works well with

These skills set the gates and the routing; they do not try to replace good phase tools. They pair with [Matt Pocock's skills](https://github.com/mattpocock/skills) (MIT): `tdd` and `diagnosing-bugs` inside the work `fnl-coding-router` routes, `code-review` as the reviewer's instrument in the review gate, `grilling` and `prototype` for clarification, `pr` for pull request bodies, and `handoff` for portable handovers. Install that pack with its own instructions; `/fnl-ask` points to its skills when they fit. The two packs are independent projects.

For reviews, the gates and the `fnl-reviewer` agent use each host's native instruments: `/code-review`, `/security-review` and `claude ultrareview` on Claude Code, `codex review` on Codex. Antigravity has no native review command, so it reviews by reading the diff, and the native second pass runs on Claude Code or Codex. For security audits, the security gates recommend [Cloudflare's `security-audit` skill](https://github.com/cloudflare/security-audit-skill) (MIT):

```bash
npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit
```

## Host configuration

The orchestration skills keep machine facts (agent commands, allowed models, which delegates each coordinator can reach, the route judge, allow-rules, lock path, parallel limit) outside the plugin, in a host config file: the path in `ORCHESTRATION_HOST_CONFIG`, or else `${XDG_CONFIG_HOME:-~/.config}/finolabs-vibecode/host.md`. Start from `skills/fnl-delegate/references/host-template.md`. The dispatch ledger defaults to `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode/ledger.jsonl` (`ORCHESTRATION_LEDGER` overrides it). When Codex or Antigravity also coordinates, put both files where every coordinator's sandbox can read and write them.

The route judge is optional. Routing is complete without one; a judge such as TypeSafe's Jev, called through its own `typesafe-ai` skill, settles only the calls the rules leave open, and the plugin holds no key for it.

## Layout

```text
.claude-plugin/plugin.json        Claude Code manifest (the version's single source of truth)
.claude-plugin/marketplace.json   Claude Code marketplace listing this repository
.codex-plugin/plugin.json         Codex manifest, version kept equal
.antigravity-plugin/plugin.json   Antigravity manifest, version kept equal
.agents/plugins/marketplace.json  Codex marketplace listing this repository
agents/fnl-*.md                   read-only reviewer, security reviewer and verifier subagents
agents/openai.yaml                Codex skill-list display metadata
skills/fnl-*/SKILL.md             one self-contained skill per folder, references/ and scripts/ beside it
rules/AGENTS.md                   session-start reminder: an always-on rule on Antigravity, injected by the hook in .claude-plugin/hooks.json on Claude Code
assets/                           icon (light and dark, SVG and 512 px PNG) and its NOTICE
evals/                            trigger, behavior and parity cases for `claude plugin eval`
scripts/                          repository checks, such as cross-reference validation
tests/                            unit tests for the repository scripts and the ledger
CHANGELOG.md                      Keep a Changelog
LICENSE                           MIT
```

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

The trigger cases check that each skill fires on a representative prompt and that unrelated prompts load none; the quality cases grade what a skill makes the agent decide. The `behavior` cases, a subset of `quality`, are the ones to rerun after changing a skill's rules. The repository root `CLAUDE.md` is context for agents working on this repository; the validator warns that a plugin does not load it, which is intended.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as [SECURITY.md](SECURITY.md) describes.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements

This pack stands on other people's work. Thank you to:

- **Matt Pocock** and [mattpocock/skills](https://github.com/mattpocock/skills) ([overview](https://www.aihero.dev/skills)), MIT. Its `/setup-matt-pocock-skills` and `/ask-matt` skills inspired `/fnl-setup` and `/fnl-ask`; its user-invoked and model-invoked split, its grilling interview and its `writing-for-agents` guidance shaped how these skills are written. No text is copied, and the two packs are independent projects.
- [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) by Steph Ango, MIT, which `fnl-knowledge` recommends for Obsidian vaults.
- Orrery, the FINOLABS knowledge base for agents that `fnl-knowledge` recommends where it is available (not yet published).
- [Cloudflare's security-audit skill](https://github.com/cloudflare/security-audit-skill), MIT, which the security gates recommend for audits.
- [Spec Kit](https://github.com/github/spec-kit) by GitHub, which `fnl-coding-router` routes through first.
- [Superpowers](https://github.com/obra/superpowers) by Jesse Vincent, whose process skills (brainstorming, systematic debugging, test-driven development, verification before completion, code review requests) fill the fallback router.
- [Paseo](https://github.com/getpaseo/paseo), whose advisor, committee and handoff skills were the reference design for the delegation skills.
- Anthropic's [skills repository](https://github.com/anthropics/skills) and its `skill-creator`, and the [Agent Skills](https://agentskills.io) format that lets one `skills/` folder serve several hosts.
- The packaging documentation of [Claude Code](https://code.claude.com/docs/en/plugins/manifest-reference.md), [Codex](https://developers.openai.com/codex/plugins/build) and [Antigravity](https://antigravity.google/docs/build-plugins).
- [TypeSafe](https://docs.typesafe.ai), whose cookbooks informed the activity-selection reference.
- [Semantic Versioning](https://semver.org/), [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
