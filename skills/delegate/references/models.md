# Capability map

Checked 2026-11-01. Review by 2026-12-01.

This tier table is seed data. The machine's user-confirmed `Agents on this machine` section in host config wins for presence, coordinator family and allowed models; `unverified` is not permission to probe or dispatch. Refresh it with `/setup scan`.

Model lineups, quotas and flags change every few weeks: before routing on a row, confirm the model still exists with the recheck command, and update this file when it has drifted. Past the review-by date, treat every row as unverified until its recheck command confirms it; whoever updates the file sets both dates again as ISO dates (`YYYY-MM-DD`), the review-by date at most a month after the check. Vendor benchmark numbers are the vendor's own; the ledger summary (`status`) is the evidence that counts on this machine.

## Tiers

Route by tier first, then by agent. A tier names what the work needs; the agent sections below say which model on each agent serves it.

- **frontier**: novel design, subtle bugs, security, long autonomous runs, reviews of medium and harder work.
- **strong**: everyday agentic coding across several files, reviews of easy work.
- **fast**: bounded edits, mechanical changes, extraction, bulk runs.

| Tier | Claude Code | Codex | Antigravity | ZCode |
| --- | --- | --- | --- | --- |
| frontier | Opus 5.5; Fable 5.1 when Opus has already fallen short | `gpt-6-astra` | `claude-opus-5-5-*` (Claude pool) | GLM coding plan models, when configured |
| strong | Sonnet 5.5 | `gpt-6.1-sol` | `gemini-4-argon-*`, `claude-sonnet-5-5-*` | <as configured> |
| fast | Haiku 5.5 | `gpt-6.1-terra`, `gpt-6-luna` | `gemini-3.8-flash-*` | <as configured> |

The model places the work in a tier; effort is a separate choice. **Default to `medium` effort on every agent and tier, hard work included**: a `medium` run still does hard work, and it spends less quota and time. By grade (`SKILL.md` "Grade"): `medium` for easy, medium and hard work, `high` for very hard, `xhigh` for ultra hard, and `max` only when `xhigh` has fallen short. A run that fell short at its level is retried one level up. A host config's "Effort preference" overrides this default.

Each agent's own scale (checked 04/11/2026 with its CLI): Claude Code `low`, `medium`, `high`, `xhigh`, `max`; Codex the same five plus `ultra` (maximum reasoning with automatic task delegation; `gpt-6-luna` has no `ultra`); Antigravity `low`, `medium`, `high`, written as the model name's suffix. Use one five-level scale across agents, `low`, `medium`, `high`, `xhigh`, `max`, and map it to the agent in hand: an agent that lacks a level takes the nearest one below it (Antigravity has nothing above `high`). Routing never picks Codex's `ultra` or Claude Code's `ultracode`: both delegate on their own, and delegation stays with the coordinator.

Capability order when two choices fit equally, for code: **Claude Code, then Codex, then Antigravity**. For plain content writing (documentation, prose and copy with no code change) the order is **Codex, then Claude Code, then Antigravity**.

## Claude Code

Recheck: `claude --help`, `/model` in a session, and the [model overview](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model).

- Models: Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 5.5; 1M context each. Effort `low`, `medium`, `high`, `xhigh`, `max`; `ultracode` is not a level but a session setting (`/effort`, or `--effort ultracode`, which also sets `xhigh`) that makes Claude plan dynamic subagent workflows on its own, so routing never picks it. Pin full model IDs in headless runs: aliases such as `opus` map to different models on different providers.
- Strengths: long-running agentic coding and terminal work (Opus 5.5), the strongest reasoning for hard cases (Fable 5.1, at about 2.5 times Opus's price), speed with good judgement (Sonnet 5.5), cheap high-volume subtasks (Haiku 5.5).
- Quota: plan limits or API billing. A rate limit shows as a `system/api_retry` event with `rate_limit` in `stream-json` output.

## Codex

Recheck: `codex debug models`, `codex exec --help`, and the [models page](https://developers.openai.com/codex/models).

- Models: `gpt-6-astra` (most capable), `gpt-6.1-sol` (near Astra on coding at about a fifth of the cost; the effective default), `gpt-6.1-terra` (fast; UI, vision, computer use), `gpt-6-luna` (cheapest). Effort `low`…`max`, plus `ultra`, which fans out to subagents by itself.
- Weak spot: Luna often fails to disclose a broken tool in OpenAI's own tests. Keep it off work where a silent tool failure would pass unnoticed.
- Quota: per model per 5 hours on Plus and Business, and Astra runs out roughly ten times sooner than Luna. There is no headless quota query: a `turn.failed` or `error` event in `--json` output, or a usage-limit message in the log, means `quota`.

## Antigravity

Recheck: `agy models`, `agy --help`, and `agy -p /usage --output-format json`.

- Models: `gemini-4-argon-{low,medium,high}`, `gemini-3.8-flash-{low,medium,high}`, and Anthropic models served through Antigravity (`claude-opus-5-5-*`, `claude-sonnet-5-5-*`, on paid plans). The suffix and `--effort` set the same level.
- Strengths: 1M context with image, video, audio and PDF input: long logs, screenshots, recordings and large documents go to Argon. Flash is cheap and fast for easy and medium edits.
- Weak spots: terminal-heavy work, where Argon trails Opus 5.5 by third-party reports. Headless runs soft-deny every shell command outside the allow-rules.
- Quota: separate pools for the Gemini models, for Argon, and for the Claude and GPT models; each pool has a 5-hour and a weekly limit. `/usage` in JSON gives `remaining_fraction` and `reset_time` per bucket. One empty pool leaves the others usable.

## ZCode

Recheck: `zcode --help` (or the bundled CLI at `<ZCode.app>/Contents/Resources/glm/zcode.cjs`), `/model` in a session, and `~/.zcode/v2/provider_config.json`.

- Models: chosen in ZCode's own settings (`/model` or provider config), not per-dispatch CLI flags; the model the user confirmed for delegation is recorded in host config `## ZCode`. Commonly GLM models on a coding plan; <list the confirmed model ids here>.
- Effort: no per-dispatch effort flag exists; the session's configured reasoning level applies, so the effort default above cannot be raised for a zcode dispatch.
- Strengths: headless runs with `--cwd`, `--mode build|edit|plan|guarded` and `--json` output; `--disallowed-tools` restricts tools when the user asks.
- Weak spots: no headless quota query and no `--model`/`--effort` flags; the hard-cap wrapper alone bounds a run.
- Quota: coding-plan limits in the user's account; no probe parser exists yet, so treat quota as unverified.

## Strength overrides

Apply these after the tier is set, before the capability order:

- Large logs, screenshots, recordings, PDFs or a whole-repository read → Antigravity Argon.
- UI from a design image, or computer use → Codex Terra or Antigravity Argon.
- Terminal-heavy work (builds, debugging under a shell, migrations run by hand) → Claude Code or Codex.
- Bulk mechanical edits across many files → the fast tier of whichever agent has the most quota left.
