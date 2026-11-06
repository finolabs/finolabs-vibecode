# Usage metrics and the status dashboard

Status: implemented; in `0.1.6`; later releases add the `kept` event (`0.1.7`) and `judge` receipts (`0.1.8`). Depth: DEEP (hooks run on every matching tool call and record behavior data).

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
| 4 | The same hook script serves Claude Code, Codex and Antigravity through a small adapter. Codex and Antigravity record fewer events than Claude Code (below). |
| 5 | `fnl-status` is upgraded into the dashboard. No new skill. |
| 6 | Sessions started by a delegate dispatch are marked with `FNL_DISPATCH_ID`; sessions of unknown origin (no recorded session start) are shown as "unclassified". |
| 7 | Retention is chosen in `fnl-setup` (30, 90 or 365 days), default 90, plus a `purge` command. |
| 8 | The dashboard is one static local page, `dashboard.html`, that loads its numbers from a `data.js` beside it. The agent creates and publishes nothing; there is no Artifact and no terminal report. A refresh script keeps `data.js` current. (Replaces the earlier Artifact decision.) |
| 9 | Codebase and direction analysis is a later, separate spec. |

## Metrics

Each is computed by the refresh script from the event store and the ledger; the hooks compute nothing.

| Metric | Definition | Action it supports |
| --- | --- | --- |
| Router coverage | Sessions with a change (a `first_edit` event, or a `commit` event when the files were written through the shell, which no edit hook sees) whose first `router` or `skill` event for `fnl-coding-router` precedes that first change, over sessions with a change. Dispatch sessions are excluded. Unclassified sessions (a file edit but no recorded `session_start`, so the origin is unknown, for example a session that began before consent) are shown apart. The hook cannot tell a desktop-app task session from a user-started one, so those are not separated. | Router not firing: check `CLAUDE.md`, `fnl-setup` and the session reminder. |
| Skill and agent use | Count of `skill` and `agent` events per `fnl-` name over the period (top ten), and calls per week. | Remove or fix what is never used. |
| Load cost | Per session, the sum of bytes of `SKILL.md` for each `skill` event, divided by four, labeled as an estimate. | Trim a skill that is loaded often and rarely acted on. |
| Depth vs outcome | Per router receipt, the depth, and whether the next pull request in that repository got a `REWORK` verdict before merge. Indicative only: the join is by repository and time, not by session. | Thresholds too loose when `MIN` work is reworked often. |
| Delegation | `ledger.py summary` per agent, model and grade: first-pass acceptance, quota and error rates, rework rounds. Groups under five runs show counts without comment. Beside them, the tasks coordinators kept (`kept` events, per coordinator, reason and who settled it) and the implementation runs handed off in the period, without in-session subagents and reroutes after a failed run. Only a recorded receipt counts, so a skipped check still shows nothing. | Reroute or change budgets; a kept count growing on one reason says which rule or brief to change. |
| Judge | Decisions per site by grader; usable answers are validated judge receipts divided by all judge receipts, and followed is `followed=yes` divided by validated judge receipts. Separately, first-pass acceptance by `route_by=judge` versus `table` from the ledger. Show only with receipts or a judge-routed ledger run; without receipts show the association alone and say none were recorded. Show n and an open ring below five runs, without judgment. Cost, latency and accuracy are not measured; association is not proof the judge was right. | Check use and fallback frequency; compare outcomes without claiming causation. |
| Review gate | Per pull request: review verdicts in order. Share of pull requests that took at least one `REWORK`. | Briefs or acceptance criteria too thin. |

## Event store

Directory: `${FNL_STATE_DIR:-~/.finolabs/vibecode/state}` (a machine that already has `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` and no new folder keeps using the old one; nothing is moved, and every folder created here, `~/.finolabs` included, is mode `0700`); a folder that already exists keeps its mode; files `0600`. `FNL_STATE_DIR` counts only when it is an absolute path, and the `markers` folder inside must be a real folder, never a symlink. One file per month, `events-YYYY-MM.jsonl`, one JSON object per line, written with a single append.

Common fields: `ts` (UTC, ISO 8601), `sid` (the host's session id), `repo` (first 8 hex characters of SHA-256 of the main repository's root path, so a linked worktree shares its repository's code), `event`. No other free-form field exists.

| `event` | Extra fields | Recorded by |
| --- | --- | --- |
| `session_start` | `host`, `dispatch` (value of `FNL_DISPATCH_ID` or null), `source` (`startup`, `resume`, `clear`, `compact`) | hook on `SessionStart` |
| `skill` | `name` (only when it starts with `fnl-`) | hook after the `Skill` tool |
| `agent` | `name` (only when it starts with `fnl-`) | hook after the `Agent` tool |
| `first_edit` | none; written once per session | hook after `Edit` or `Write`, guarded by a marker file per session |
| `commit` | none | hook after `Bash`, only when the command contains `git commit` |
| `review` | `kind` (`code` or `security`), `verdict` (`APPROVE` or `REWORK`), `pr` (number) | hook after `Bash`, only when the command posts a comment (`gh pr comment`) whose body (a file, `--body`, or a heredoc on stdin) starts with a `fnl-review` marker line |
| `router` | `depth` (`MIN`, `NORMAL`, `DEEP`), `trigger` (one value from a fixed list in the router skill) | hook after `Bash`, when the command is the router's `record.py router --depth D --trigger T`. The command only prints a receipt; the hook records it with the session id, which the router does not have. |
| `kept` | `tasks` (1 to 999), `reason` (one value from a fixed list), `route_by` (`table`, `judge`, `user`) | hook after `Bash`, when the command is `fnl-delegate`'s `record.py keep --tasks N --reason R [--route-by B]`, which only prints a receipt. |
| `task` | `id` (only `^T[0-9]{1,4}$`) | hook after a `record.py task --id T012` command; the command validates the id and only prints a receipt. |
| `judge` | `site` (`route`, `depth`, `activity`, `instruction`), `grader` (`judge`, `agent`), `result` (`validated`, `unverified`), `followed` (`yes`, `no`, `na`) | hook after a `record.py judge --site S --grader G --result R --followed F` command; the command only prints a receipt. |

Task events hold only a task id of the form `T` plus one to four ASCII digits, besides the common fields; no command text or other content is stored. They are advisory dashboard data, never input to task selection or a gate: any session can forge an event.

Judge receipts hold only `site`, `grader`, `result`, and `followed` from fixed enumerations; they never hold a question, an answer, a cost, a file name or a path.

Rules the writer enforces, so a hook bug cannot widen what is stored:

- Fields are checked against the table; an unknown field or a value outside its enum drops the whole event.
- For `judge`, `followed` must be `na` unless `grader=judge` and `result=validated`; every `agent` grade has `result=validated`. Both the recording path and stored-event reader reject impossible pairs. A site is never joined to a file identity. Running the receipt after each judge decision is advisory (agent judgment); no judge means no receipt.
- For `review`, only the first line of the body file is read, capped at 4 KB, regular files only (no symlink follow). Nothing from the comment body is stored except `kind` and `verdict` parsed from the marker.
- For `commit` and `review`, the command string is tested for the trigger and discarded; it is never written or logged.
- The writer exits 0 on every path and finishes within 2 seconds. A failure appends one byte to `errors.count` in the state directory (only while metrics are on) and writes nothing else; the dashboard shows that count.
- `FNL_METRICS=off` makes the writer exit before touching the store. Without recorded consent (`consent.json`, written by `fnl-setup`) it also exits before touching the store.

## Hooks

Plugin-level, not inside a skill: they only exist when the whole plugin is installed, and the dashboard says so when it finds no events.

- Claude Code: extend `.claude-plugin/hooks.json` with a `PostToolUse` entry (matcher `Skill|Agent|Edit|Write|NotebookEdit|Bash`) and a `SessionStart` entry with no matcher, beside the existing reminder. Every entry is `async`, so a hook never delays a tool call. The `Bash` entry has no `if` filter: the host's `if` takes one permission rule and the docs do not say how it matches compound commands such as `cd x && git commit`, so the script tests the command text itself and discards it. The script is `scripts/metrics_hook.py`, called as `python3 -I`; it reads `tool_input.skill` for the Skill tool and `tool_input.subagent_type` for the Agent tool, the names the session transcripts use.
- On `SessionStart` and `Stop`, the hook runs the refresh (below). On `PostToolUse` it runs it when `data.js` is more than 10 seconds old, after a `stat` that spares most tool calls a process. Antigravity's hook is not async, so it never refreshes. Rebuilds run one at a time under an operating-system lock on `refresh.lock` (released when the process ends, so a killed rebuild leaves nothing to clean up; Windows uses `msvcrt`, untested). A run waits up to three seconds for a rebuild in progress and then rebuilds itself, reading the events only once it holds the lock, so the run that reads last publishes last and `data.js` never goes back to an older snapshot. A throttled run (`--throttle`) skips once it holds the lock if `data.js` is fresh, which is how two hooks that both passed the cheap age check rebuild once; a forced run (`Stop`, `SessionStart`) never skips. A run that cannot get the lock in time gives up quietly (the next hook rebuilds), and `--open` still opens the existing page. The lock file is created with `NOFOLLOW` and mode 0600, must be a regular file, and is never removed, not even by `purge`: removing it while a holder has it would let a second process lock a new file.
- Codex: `.codex-plugin/hooks.json`, named by the `hooks` key of `.codex-plugin/plugin.json` (an explicit value replaces the default `hooks/hooks.json` discovery, which Claude Code would also load, so that path is not used). The command is `metrics_hook.py --host codex`, async, with the plugin root from `PLUGIN_ROOT` or `CODEX_PLUGIN_ROOT`. Codex names its shell tool `Bash` and its edit tool `apply_patch`, may send a command as an array, and has no Skill tool. Codex's hook documentation says `spawn_agent` matches `Agent`, and the metrics hook handles `Agent`, but the shipped Codex matcher omits it; it records sessions, first edits, commits, review comments, router, keep and judge receipts. A user must trust the plugin's hooks once with `/hooks`; until then they do not run, and `fnl-setup` says so.
- Antigravity: the same script serves it (`--host antigravity --event <session_start|post_tool_use>`), but the plugin does not ship its hook yet. A plugin-root `hooks.json` would have to name the script by a relative path, and whether Antigravity runs a plugin hook from the plugin folder or from the workspace is unverified; if it were the workspace, opening a repository that ships its own `scripts/metrics_hook.py` would run it. So the hook is set up in the user's own `~/.gemini/config/hooks.json` instead, with an absolute path: `refresh.py antigravity-hook --yes` (run by `fnl-setup` after a clear yes) merges one group, `finolabs-vibecode`, keeps every other group, writes a backup first and keeps the file's mode, refuses a file that is not a JSON object (or one holding `NaN`), edits a symlinked file in place, refuses to run unless the skill sits in a plugin root (`.claude-plugin/plugin.json` named `finolabs-vibecode` beside `scripts/metrics_hook.py`, so a script from outside a plugin root is refused; this guards against a mistake, not against a repository that ships a fake manifest, whose own code would already be running with the user's rights), and `--remove` takes the group out. Its payloads are camelCase with no event name (hence `--event`), the session id is `conversationId`, the folder is the first of `workspacePaths`, the shell tool is `run_command` with `CommandLine`, and the host's file tools are `write_to_file`, `replace_file_content` and `multi_replace_file_content`; `write_file`, seen once in an early run, is not a real tool name, so the script still tolerates it but the shipped matcher leaves it out. It has no Skill or Agent tool in the payload, so it records the same events as Codex. The hook prints `{}` on every path. It is not documented as async, so it would run in the tool's path (about 50 ms); for that reason its session start does not refresh the dashboard, which `fnl-status` does.

## Dispatch marker

`fnl-delegate`'s host template exports `FNL_DISPATCH_ID=<ledger id>` in each headless dispatch command. The writer copies it into `session_start`. The ledger id is already a short label with no task data.

## Setup, consent and retention

`fnl-setup` gains a section that, in this order, states what is recorded and where, states that the dashboard is a local page and that nothing leaves the machine, asks for consent, asks the retention (30, 90, 365 days), and writes `consent.json` with the date and the retention. Consent is asked on its own and never bundled, like the route judge. Declining leaves everything off and the dashboard still shows the ledger.

A new event containing only counts or values from a closed set needs no fresh consent if it stays local under the existing retention, purge and revoke controls and is listed in `PRIVACY.md`, `fnl-setup` section F and `fnl-status`; adding free text, paths, command text or anything sent off the machine requires fresh consent with a consent version.

Retention: on each `session_start` the writer deletes event files that end before the retention window, drops the older lines from the file the window cuts through, and deletes marker files older than seven days. `fnl-status purge` deletes the whole store, `data.js` and `dashboard.html` after one confirmation.

## Dashboard

Two files in the state directory:

- `dashboard.html`: the page, shipped as `skills/fnl-status/assets/dashboard.html` and copied into the state directory by every refresh, so it follows the installed plugin version. It is static; the agent never writes, edits or republishes it.
- `data.js`: `window.FNL_DATA = {...};`, written by `skills/fnl-status/scripts/refresh.py` from the event store and the ledger. A browser will not read a local JSON file from a page, but it loads a sibling script, so this is how the page gets its numbers with no server and no agent.

The refresh runs when `fnl-status` is called, on `SessionStart` and `Stop`, and after a tool call when `data.js` is more than 10 seconds old. While its tab is visible the page loads `data.js` again every 5 seconds through a new script element and redraws in place when the numbers changed, keeping the month shown and the open tables; a page on disk cannot watch a file, and no local server or listener is involved. Checked in Chrome; Safari and Firefox are unverified. The page shows its `generated` time, so a stale page says so. `fnl-status` (`disable-model-invocation: true` stays) is one step: run `python3 -I refresh.py --open`, which refreshes and opens `dashboard.html` with the system opener, then report the script's one-line summary: the period, the number of sessions, unclassified sessions, the writer's error count and any missing source (no hooks installed, consent not given, ledger empty). A missing source is stated, never shown as zero.

The dashboard shows a project's folder name only after the user runs `fnl-status` in that repository with consent (see the [registration rule](dashboard-infographics.md#data-changes-all-local-metadata-only)); an explicit host-config project label takes precedence.

`ledger.py` provides `summary --json` so the refresh reads the same numbers the text report would. Its `summary_rows` accepts `route_by` as a grouping key without changing the default agent/model/kind/grade output; legacy lines with no known routing source are excluded from this split.

### Page contract

The layout is fixed, so every user's dashboard has the same sections in the same order: the prompt line, four KPI tiles, two bands of panes, delegation, the data tables, then sources and a status line. The conditional Judge pane sits after delegation and also appears in the data tables. The page renders every value with `textContent` or an attribute, never as markup, and reads `window.FNL_DATA` only; when a source is missing it keeps its full size: each pane shows placeholder shapes and the reason, and with no data at all a card over a lightly blurred layer says so (the card stays in view while the page scrolls). It is a complete HTML document with a doctype, `<meta charset="utf-8">` and a viewport meta, because nothing wraps it (without the charset a browser reads it as Windows-1252 and garbles its punctuation). It has a `<title>` of two to four words, colors as tokens on `:root` with a dark and a light set and an explicit `body` background, a layout that works at phone width, an inline script and style, and no external script, stylesheet, font or image. A `Content-Security-Policy` meta tag (`default-src 'none'`, scripts only from the page itself and `file:`) blocks any network request.

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
- The writer never exits non-zero. A `Bash` call that is not a trigger does start it (there is no `if` filter and the hook is async) but records and prints nothing; a test pins this. Malformed input creates no file when metrics are off or not consented.
- Hooks are async, so they add no latency to a tool call. Process time is measured once and reported (median 48 to 58 ms on the developer's machine, under the 100 ms target), and a `SessionStart` that also refreshes is bounded by the refresh's own eight-second timeout.

**US2. Router and dispatch marker.**
- `fnl-coding-router` records `router` with a depth and a trigger from the fixed list.
- A dispatch command from the host template sets `FNL_DISPATCH_ID`, and the matching `session_start` carries it.

**US3. Dashboard.**
- After `fnl-status`, opening `dashboard.html` shows the dashboard with the ledger's and the store's numbers, with no agent step in between; an open page follows `data.js` as the hooks rebuild it during a session.
- Each metric matches a hand computation over a fixture store.
- With no events, the page says which source is missing and shows no zeros; with no `data.js`, it shows its empty state.
- No value from the store reaches the page as markup, and `data.js` cannot be broken out of by stored text (a test feeds `</script>` and U+2028 through the writer).
- The copied `dashboard.html` is byte-identical to the shipped one.

**US4. Setup, privacy and retention.**
- `fnl-setup` asks consent and retention in their own question and writes `consent.json`.
- Files older than the retention are removed at the next `session_start`; `purge` removes the store and both dashboard files after one confirmation.
- `PRIVACY.md` replaces the "no analytics and no telemetry" sentence with an accurate statement: local usage metrics when consented, shown on a local page, nothing sent by the plugin.

## Security review triggers

This change hits `fnl-security-review-gate` for: new input to a process that runs automatically (hook payloads and command text), writes of user behavior data, a file read named by a command, and a script file generated from stored data and loaded by a page. The reviewer checks at least: event validation and enum bounds, path handling for the marker file, file modes and atomic writes, no command text reaching disk or logs, escaping in `data.js` and in the page, behavior when the state directory is unwritable or full, and that off means off. Known limits, accepted: the repository code is an unsalted short hash of the repository path, a pseudonym that anyone with a list of candidate paths could reverse, kept local; backups of the user's hooks file are not pruned; the retention rewrite of the one month file the cutoff cuts through can lose an event another session appends in the same few milliseconds; the `review` event is read from command text, so a model can write a marker it did not post (every number here is best effort, and the docs say so), which is an integrity limit of any command-text hook and not a security boundary; a review is recorded from `--body-file <path>` (a `~` is expanded, a `$VAR` is not), `--body-file -` with a heredoc or pipe, `--body`, and `--body "$(cat <<EOF`, and every other way of posting goes unrecorded. The hook opens a file named in a command only to read its first line: any readable regular file, never a symlink or a pipe, and nothing but a marker match is kept.

## Out of scope for tests

Tests cover the writer, the refresh computations and the escaping. No load or scale tests: the store holds a few thousand lines at most (about 8 MB for 90 days at the heaviest observed rate, an estimate of 200 bytes per event that was not measured).

## Files

New: `scripts/fnl_metrics.py` (the shared core, copied byte for byte into `skills/fnl-coding-router/scripts/` , `skills/fnl-status/scripts/` and `skills/fnl-update/scripts/`; CI and a test keeps the copies equal), `scripts/metrics_hook.py`, `skills/fnl-coding-router/scripts/record.py`, `skills/fnl-status/scripts/refresh.py`, `skills/fnl-status/assets/dashboard.html`, `.github/social-preview.json` and its rendered `.github/social-preview.png`, the two dashboard screenshots under `assets/`, and tests for the core, the hook and the refresh. The core's schema is the one list of events, so there is no separate `events.md`.
Changed: `.claude-plugin/hooks.json`, `skills/fnl-status/SKILL.md`, `skills/fnl-coding-router/SKILL.md` (receipt call), `skills/fnl-delegate/scripts/ledger.py` (`summary --json`), `skills/fnl-delegate/references/host-template.md`, `skills/fnl-setup/SKILL.md`, `PRIVACY.md`, `README.md`, `CHANGELOG.md`.

## Verify before building

1. Claude Code: checked on 03/11/2026 against the hooks reference and the session transcripts. Plugin hooks use the `${CLAUDE_PLUGIN_ROOT}` variable and a `hooks` wrapper. The Agent tool is `Agent`; the Skill tool's name and its `skill` input key come from the transcripts, not from the docs. `SessionStart` carries `source` (`startup`, `resume`, `clear`, `compact`, `fork`). A PostToolUse hook's output never reaches the model. A command hook can be `async`. The `if` field takes a single permission rule and was not used (see "Hooks").
2. Codex: the hooks reference and installed plugins (the shape, the event names, the `hooks` manifest key, the trust step) were read on 04/11/2026. A real run was not possible: the probe hook in a throwaway project was not loaded because the project layer was untrusted, the trust-bypass flag was refused, and the account was out of quota. The payload shape, the root variable name and plugin hooks from a marketplace install are therefore unverified.
3. Antigravity: a real `agy` run with a project `.agents/hooks.json` fired both hooks and gave the payload shape above, with no trust step; with the user-level group installed, a real headless run recorded `session_start` (so `SessionStart` fires in the CLI), the router receipt and a `commit` through the shell tool `run_command` (the hook runs with the folder of the session, sees the environment, and the absolute script path works). The shell tool runs a command first inside its sandbox and, when that is refused, again with `BypassSandbox`, and each attempt is a separate payload with an empty `error`, so one commit can be counted twice on Antigravity (a known best-effort limit); a headless run auto-denies the file tool, so `first_edit` from Antigravity is unverified; `agy plugin validate . --strict` accepted a root `hooks.json`. Not verified, and the reason the plugin ships no hook: the working folder of a plugin hook on a real install (probe: install a throwaway plugin whose hook prints its folder), and the shell tool's payload (a headless run denies the command, so its hook did not fire; the denied action is displayed as `RunCommand`, consistent with `run_command`), and async behavior.
4. Whether `FNL_DISPATCH_ID` reaches a hook through `codex exec` and through `agybird`.
5. A `file://` page loading a sibling `data.js` in Chrome, Safari and Firefox, and the system opener on macOS, Linux and Windows.

Each result goes in the change that depends on it. A failed item changes the scope for that host only.
