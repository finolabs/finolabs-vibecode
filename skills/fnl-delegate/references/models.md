# Capability map

Checked 01/11/2026. Review by 01/12/2026.

Model lineups, quotas and flags change every few weeks: before routing on a row, confirm the model still exists with the recheck command, and update this file when it has drifted. Past the review-by date, treat every row as unverified until its recheck command confirms it; whoever updates the file sets both dates again, the review-by date at most a month after the check. Vendor benchmark numbers are the vendor's own; the ledger summary (`fnl-status`) is the evidence that counts on this machine.

## Tiers

Route by tier first, then by agent. A tier names what the work needs; the agent sections below say which model on each agent serves it.

- **frontier**: novel design, subtle bugs, security, long autonomous runs, final review of hard work.
- **strong**: everyday agentic coding across several files, reviews of medium work.
- **fast**: bounded edits, mechanical changes, extraction, bulk runs.

| Tier | Claude Code | Codex | Antigravity |
| --- | --- | --- | --- |
| frontier | Opus 5.5 at `high`/`xhigh`; Fable 5.1 when Opus has already fallen short | `gpt-6-astra` at `high` or above | `claude-opus-5-5-high` (Claude pool) |
| strong | Opus 5.5 at `medium`, Sonnet 5.5 at `high` | `gpt-6.1-sol` | `gemini-4-argon-high`, `claude-sonnet-5-5-high` |
| fast | Sonnet 5.5 at `medium`, Haiku 5.5 | `gpt-6.1-terra`, `gpt-6-luna` | `gemini-3.8-flash-medium`/`-high` |

Capability order when two choices fit equally: **Claude Code, then Codex, then Antigravity**.

## Claude Code

Recheck: `claude --help`, `/model` in a session, and the [model overview](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model).

- Models: Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 5.5; 1M context each. Effort `low`…`max` (Claude Code adds `ultracode`). Pin full model IDs in headless runs: aliases such as `opus` map to different models on different providers.
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

## Strength overrides

Apply these after the tier is set, before the capability order:

- Large logs, screenshots, recordings, PDFs or a whole-repository read → Antigravity Argon.
- UI from a design image, or computer use → Codex Terra or Antigravity Argon.
- Terminal-heavy work (builds, debugging under a shell, migrations run by hand) → Claude Code or Codex.
- Bulk mechanical edits across many files → the fast tier of whichever agent has the most quota left.
