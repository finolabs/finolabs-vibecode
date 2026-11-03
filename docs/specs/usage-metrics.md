# Usage metrics and the status dashboard

Status: draft for review. Target release: `0.1.7`. Depth: DEEP (hooks run on every matching tool call and record behavior data).

## Goal

Show each user whether `finolabs-vibecode` earns its cost on their own machine: did their agents follow the practice, what did loading it cost, and what did delegation and review produce. Today the only evidence is the delegate ledger; everything else has to be reconstructed from host transcripts.

## Non-goals

- Analyzing a user's codebase or whether a project is on course for its original outcome. That is a separate feature, started after this one, and it first checks what `speckit-analyze` already covers.
- Any network send of metrics. The dashboard is a local page; nothing is published or uploaded.
- Recording prompts, code, command text, file paths or review text.
- Metrics for hosts that cannot ship plugin hooks (see "Hooks").

## Decisions already made (owner, 03/11/2026)

| # | Decision |
| --- | --- |
| 1 | Six metrics, each tied to an action the user can take (below). |
| 2 | Metadata only, stored locally, off until the user consents in `fnl-setup`, with an environment switch to turn it off. |
| 3 | Hooks are the primary source; the delegate ledger keeps delegate semantics; the router adds one receipt line. No third collection mechanism. |
| 4 | Claude Code first. Codex after its event names and trust step are confirmed. Antigravity has ledger data only until it ships plugin hooks. |
| 5 | `fnl-status` is upgraded into the dashboard. No new skill. |
| 6 | Sessions started by a delegate dispatch are marked with `FNL_DISPATCH_ID`; sessions started by the desktop app are shown as "unclassified". |
| 7 | Retention is chosen in `fnl-setup` (30, 90 or 365 days), default 90, plus a `purge` command. |
| 8 | The dashboard is one static local page, `dashboard.html`, that loads its numbers from a `data.js` beside it. The agent creates and publishes nothing; there is no Artifact and no terminal report. A refresh script keeps `data.js` current. (Replaces the earlier Artifact decision.) |
| 9 | Codebase and direction analysis is a later, separate spec. |

## Metrics

Each is computed by the refresh script from the event store and the ledger; the hooks compute nothing.

| Metric | Definition | Action it supports |
| --- | --- | --- |
| Router coverage | Sessions with a file edit whose first `router` or `skill` event for `fnl-coding-router` precedes the first `first_edit` event, over sessions with a file edit. Dispatch sessions are excluded; app-started sessions are shown as unclassified. | Router not firing: check `CLAUDE.md`, `fnl-setup` and the session reminder. |
| Skill and agent use | Count of `skill` and `agent` events per `fnl-` name, per week. | Remove or fix what is never used. |
| Load cost | Per session, the sum of bytes of `SKILL.md` for each `skill` event, divided by four, labeled as an estimate. | Trim a skill that is loaded often and rarely acted on. |
| Depth vs outcome | Per router receipt, the depth, and whether the next pull request in that repository got a `REWORK` verdict before merge. Indicative only: the join is by repository and time, not by session. | Thresholds too loose when `MIN` work is reworked often. |
| Delegation | `ledger.py summary` per agent, model and grade: first-pass acceptance, quota and error rates, rework rounds. Groups under five runs show counts without comment. | Reroute or change budgets. |
| Review gate | Per pull request: review verdicts in order. Share of pull requests that took at least one `REWORK`. | Briefs or acceptance criteria too thin. |

## Event store

Directory: `${FNL_STATE_DIR:-${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode}`, created with mode `0700`; files `0600`. One file per month, `events-YYYY-MM.jsonl`, one JSON object per line, written with a single append.

Common fields: `ts` (UTC, ISO 8601), `sid` (the host's session id), `repo` (first 8 hex characters of SHA-256 of the repository root path), `event`. No other free-form field exists.

| `event` | Extra fields | Recorded by |
| --- | --- | --- |
| `session_start` | `host`, `dispatch` (value of `FNL_DISPATCH_ID` or null), `source` (`startup`, `resume`, `clear`, `compact`) | hook on `SessionStart` |
| `skill` | `name` (only when it starts with `fnl-`) | hook after the `Skill` tool |
| `agent` | `name` (only when it starts with `fnl-`) | hook after the `Agent` tool |
| `first_edit` | none; written once per session | hook after `Edit` or `Write`, guarded by a marker file per session |
| `commit` | none | hook after `Bash`, only when the command contains `git commit` |
| `review` | `kind` (`code` or `security`), `verdict` (`APPROVE` or `REWORK`), `pr` (number) | hook after `Bash`, only when the command posts a comment (`gh pr comment`) whose body file starts with a `fnl-review` marker |
| `router` | `depth` (`MIN`, `NORMAL`, `DEEP`), `trigger` (one value from a fixed list in the router skill) | `fnl-coding-router`, one `metrics.py record` call at the end of step 3 |

Rules the writer enforces, so a hook bug cannot widen what is stored:

- Fields are checked against the table; an unknown field or a value outside its enum drops the whole event.
- For `review`, only the first line of the body file is read, capped at 4 KB, regular files only (no symlink follow). Nothing from the comment body is stored except `kind` and `verdict` parsed from the marker.
- For `commit` and `review`, the command string is tested for the trigger and discarded; it is never written or logged.
- The writer exits 0 on every path and finishes within 2 seconds. A failure increments `errors.count` in the state directory and writes nothing else; the dashboard shows that count.
- `FNL_METRICS=off` makes the writer exit before touching the store. Without recorded consent (`consent.json`, written by `fnl-setup`) it also exits before touching the store.

## Hooks

Plugin-level, not inside a skill: they only exist when the whole plugin is installed, and the dashboard says so when it finds no events.

- Claude Code: extend `.claude-plugin/hooks.json` with `PostToolUse` entries (matchers `Skill`, `Agent`, `Edit|Write`, `Bash`) and a `SessionStart` entry beside the existing reminder. The `Bash` entry uses the host's `if` condition, so a Bash call that is not `git commit` or `gh pr comment` does not start the script. The script lives at `scripts/metrics_hook.py` and is called as `python3 -I`.
- On `SessionStart`, after recording `session_start`, the hook runs the refresh (below) when `data.js` is older than ten minutes.
- Codex: same events and the same script, shipped in the Codex plugin's hooks file, once the verification items below are confirmed. The user must trust the hook hash; `fnl-setup` says so.
- Antigravity: none in this release.

## Dispatch marker

`fnl-delegate`'s host template exports `FNL_DISPATCH_ID=<ledger id>` in each headless dispatch command. The writer copies it into `session_start`. The ledger id is already a short label with no task data.

## Setup, consent and retention

`fnl-setup` gains a section that, in this order, states what is recorded and where, states that the dashboard is a local page and that nothing leaves the machine, asks for consent, asks the retention (30, 90, 365 days), and writes `consent.json` with the date and the retention. Consent is asked on its own and never bundled, like the route judge. Declining leaves everything off and the dashboard still shows the ledger.

Retention: on each `session_start` the writer deletes event files older than the retention, and marker files older than seven days. `fnl-status purge` deletes the whole store, `data.js` and `dashboard.html` after one confirmation.

## Dashboard

Two files in the state directory:

- `dashboard.html`: the page, shipped as `skills/fnl-status/assets/dashboard.html` and copied into the state directory by every refresh, so it follows the installed plugin version. It is static; the agent never writes, edits or republishes it.
- `data.js`: `window.FNL_DATA = {...};`, written by `skills/fnl-status/scripts/refresh.py` from the event store and the ledger. A browser will not read a local JSON file from a page, but it loads a sibling script, so this is how the page gets its numbers with no server and no agent.

The refresh runs when `fnl-status` is called and on `SessionStart` when `data.js` is more than ten minutes old. The page shows its `generated` time, so a stale page says so. `fnl-status` (`disable-model-invocation: true` stays) is one step: run `python3 -I refresh.py --open`, which refreshes and opens `dashboard.html` with the system opener, then report the script's one-line summary: the period, the number of sessions, unclassified sessions, the writer's error count and any missing source (no hooks installed, consent not given, ledger empty). A missing source is stated, never shown as zero.

Repository labels are short codes (`repo-3f2a`); folder names appear only when the user asked for them in setup.

`ledger.py` gains `summary --json` so the refresh reads the same numbers the text report would.

### Page contract

The layout is fixed, so every user's dashboard has the same sections in the same order: the prompt line, four KPI tiles, two bands of panes, delegation, the data tables, then sources and a status line. The page renders every value with `textContent` or an attribute, never as markup, and reads `window.FNL_DATA` only; with no `data.js` it shows an empty state that says how to fill it. It is a complete HTML document with a doctype, `<meta charset="utf-8">` and a viewport meta, because nothing wraps it (without the charset a browser reads it as Windows-1252 and garbles its punctuation). It has a `<title>` of two to four words, colors as tokens on `:root` with a dark and a light set and an explicit `body` background, a layout that works at phone width, an inline script and style, and no external script, stylesheet, font or image.

`data.js` is generated with `json.dumps` (its default `ensure_ascii` keeps the file ASCII, so it loads the same under any charset) and then has `<`, U+2028 and U+2029 escaped, so stored text can never close or break the script. The refresh writes it atomically (write a temporary file, then rename) with mode `0600`.

A test fails on any `http`, `//` or `data:` resource reference in the page, except the SVG namespace string `http://www.w3.org/2000/svg`, which names a format and loads nothing. The page never sets `innerHTML`, `outerHTML`, `insertAdjacentHTML` or `document.write`; a test greps for them.

#### Visual style

The page simulates a terminal window in plain HTML and CSS, with a GitHub-like dashboard structure: a title bar, a prompt line (`$ fnl-status --since <n>d` with a blinking cursor that stops under `prefers-reduced-motion`), a KPI strip, then bordered panes. It uses no terminal framework: TermUI renders to a real terminal through Node or Bun and has no browser target, so it would add a build step and a dependency for what CSS does here.

- **Charts first, words second**: every metric is a chart and explanations live in tooltips. KPI tiles carry a 12-week column chart and a signed delta against the previous week. Activity is a compact month calendar: Monday first, 28 px cells with a small date, a shade by count (the count is in the tooltip and the aria label), previous and next month buttons and a ring on the latest day, with a side column that shows the month's events, active days, busiest day and events by weekday. Router coverage is one stacked bar of all sessions with a bracket marking the eligible ones. Skill and agent use, load cost and depth are horizontal bars (depth splits each bar into clean and reworked). The review gate leads with the share of pull requests that took at least one rework, then a timeline of verdict marks per pull request (circle for approve, diamond for rework). Delegation is a lollipop chart per agent and model with a solid 60% line and quota and error counts. A collapsed "show the data as tables" section holds the same numbers as tables, for screen readers and exact reading.
- **Theme switch**: a `dark | light` control on the right of the title bar. It follows the viewer's theme until clicked, then sets `data-theme` on the root and remembers the choice in `localStorage` (every access in `try`/`catch`, so a blocked store only loses the memory).
- **Palette**: the FINOLABS plugin palette, taken from the plugin icon, the Codex manifest brand colors and the social-preview template. Dark uses mint `#7FE2CE` as the primary color on a near-black violet field (`#07040D`, with a faint `#14081F` glow at the top, so colors stand out). Light uses violet `#7A3FA6` as the primary color on paper `#F7F2FC` with ink `#22123A`, and a darker mint `#1B7A66` for small text. The primary color carries the prompt, cursor, bars, column charts, focus rings and the calendar ramp. The other brand color is secondary and appears only where a second category must differ: the "dispatch, excluded" segment of the router bar. Status colors (good, warning, critical) are reserved for state and never used to tell series apart; "good" shares the mint hue, so a mark that means "good" always has a label or a shape.
- **Type**: the system monospace stack with JetBrains Mono first when installed. The page downloads no font, so it stays offline. Labels are lowercase and short.
- **Marks** follow the dataviz rules: bars grow from a baseline, are at most 24 px thick, round only the data end, carry their value at the tip and have no track; stacked segments are separated by a 2 px gap; single-series charts use one color; the delegation lollipop has a stem to the baseline, a 0 to 100% axis and an open ring when a group has fewer than five runs; part-to-whole is a stacked bar, not a donut; large figures use proportional digits and tabular digits are kept for columns of numbers.
- **Layout**: two bands of panes in two columns. In the first band the activity pane sits beside router coverage over depth vs outcome; in the second, skill and agent use sits beside load cost over the review gate. The tall pane spans two rows, so the two sides end at about the same height. Delegation spans the full width. The bands become one column below 900 px. On a phone (below 560 px) the calendar fills the width with shorter cells, its three numbers sit in one row, bars put the name above the bar, and tables and the delegation chart scroll or reflow inside their own container; nothing makes the page scroll sideways.
- **Contrast**: body and muted text at least 4.5:1 on their surface in both themes, checked for the shipped tokens, including the text color on each calendar shade.

A reviewable preview with synthetic data is `tests/fixtures/status-sample.json` written as `data.js` beside the page.

## User stories and acceptance criteria

**US1. Hooks record events.**
- With consent and `FNL_METRICS` unset, each trigger in the event table appends one valid line.
- Without consent, or with `FNL_METRICS=off`, no file is created or changed.
- An event with an unknown field or out-of-enum value is dropped and counted in `errors.count`.
- The writer never exits non-zero, and a `Bash` call that is not a trigger does not start it on Claude Code.
- Median hook latency is under 50 ms on the developer's machine (one measurement, reported with the command), and a `SessionStart` that also refreshes stays under two seconds.

**US2. Router and dispatch marker.**
- `fnl-coding-router` records `router` with a depth and a trigger from the fixed list.
- A dispatch command from the host template sets `FNL_DISPATCH_ID`, and the matching `session_start` carries it.

**US3. Dashboard.**
- After `fnl-status`, opening `dashboard.html` shows the dashboard with the ledger's and the store's numbers, with no agent step in between; a `SessionStart` refresh updates `data.js` when it is more than ten minutes old.
- Each metric matches a hand computation over a fixture store.
- With no events, the page says which source is missing and shows no zeros; with no `data.js`, it shows its empty state.
- No value from the store reaches the page as markup, and `data.js` cannot be broken out of by stored text (a test feeds `</script>` and U+2028 through the writer).
- The copied `dashboard.html` is byte-identical to the shipped one.

**US4. Setup, privacy and retention.**
- `fnl-setup` asks consent and retention in their own question and writes `consent.json`.
- Files older than the retention are removed at the next `session_start`; `purge` removes the store and both dashboard files after one confirmation.
- `PRIVACY.md` replaces the "no analytics and no telemetry" sentence with an accurate statement: local usage metrics when consented, shown on a local page, nothing sent by the plugin.

## Security review triggers

This change hits `fnl-security-review-gate` for: new input to a process that runs automatically (hook payloads and command text), writes of user behavior data, a file read named by a command, and a script file generated from stored data and loaded by a page. The reviewer checks at least: event validation and enum bounds, path handling for the marker file, file modes and atomic writes, no command text reaching disk or logs, escaping in `data.js` and in the page, behavior when the state directory is unwritable or full, and that off means off.

## Out of scope for tests

Tests cover the writer, the refresh computations and the escaping. No load or scale tests: the store holds a few thousand lines at most (about 8 MB for 90 days at the heaviest observed rate, an estimate of 200 bytes per event that was not measured).

## Files

New: `scripts/metrics_hook.py`, `skills/fnl-status/scripts/refresh.py`, `skills/fnl-status/assets/dashboard.html`, `skills/fnl-status/references/events.md`, tests for both scripts and a parity test for event names between the writer and `events.md`.
Changed: `.claude-plugin/hooks.json`, `skills/fnl-status/SKILL.md`, `skills/fnl-coding-router/SKILL.md` (receipt call), `skills/fnl-delegate/scripts/ledger.py` (`summary --json`), `skills/fnl-delegate/references/host-template.md`, `skills/fnl-setup/SKILL.md`, `PRIVACY.md`, `README.md`, `CHANGELOG.md`.

## Verify before building

1. Claude Code: the `if` field on a `Bash` hook, the matcher names `Skill` and `Agent`, and the fields in the `SessionStart` payload (`source`).
2. Codex: event names, how a plugin ships hooks, and the trust step.
3. Antigravity: whether a plugin can ship hooks.
4. Whether `FNL_DISPATCH_ID` reaches a hook through `codex exec` and through `agybird`.
5. A `file://` page loading a sibling `data.js` in Chrome, Safari and Firefox, and the system opener on macOS, Linux and Windows.

Each result goes in the change that depends on it. A failed item changes the scope for that host only.
