# Privacy

`finolabs-vibecode` is a set of Agent Skills: Markdown instructions plus small local Python scripts. It has no server. Its only network call is the update check described below; it sends nothing about you or your sessions. If you choose, it records usage metadata on your machine so you can see how the practice performs; that record never leaves the machine, and it is off until you consent.

The agent scan script itself uses no network and runs `--version` only on three fixed executables (`claude`, `codex`, `agy`) without a shell and reads `host.md`; it stores nothing outside `host.md`.

## Where your data goes

The data folder can be relocated through `fnl-setup`; the fixed pointer `~/.finolabs/vibecode/root.json` contains its absolute `root` path and a random `id` matching the new folder's `.root-id`.

The skills run inside a host agent such as Claude Code or Codex, which processes your conversation under its provider's policy. When you follow the delegation skills and delegate work to another agent (for example Codex or Antigravity), the brief, the files that agent reads and anything it produces are processed by that agent's provider under that provider's terms. Delegate only work over files you are allowed to share with that provider.

## Update check

The update check is **on by default**, separate from usage metrics and their consent. At startup on Claude Code and Codex, a detached worker makes one HTTPS GET to `https://api.github.com/repos/finolabs/finolabs-vibecode/releases/latest` when the cache is missing or at least 24 hours old. It uses only the generic User-Agent `finolabs-vibecode-update-check`: no request body, credentials, cookies, username, machine, repository, session, installed version, prompts, code, paths or usage events. It sends nothing about the user. GitHub necessarily sees your connection's source IP. There are no redirects, proxies or retries.

Set `FNL_UPDATE_CHECK=off` in your host's environment to stop requests and notices. A “never ask” choice suppresses notices while checking continues. A “skip this version” choice suppresses only that version. The checker never updates the plugin; `fnl-update` asks for your clear yes before a native host update. Host-native updates have their own network behavior.

The resolved data root's `state/` folder (normally `~/.finolabs/vibecode/state/`, without environment overrides) holds `update-check.json` with only `checked_at` (Unix timestamp) and `tag` (validated stable release tag), plus `update-state.json` with only `skipped` (versions) and `never_ask` (boolean). Both are mode `0600`. No response body or error text is stored. These files are separate from usage events and metrics consent; turning metrics off or purging them does not stop the update check. Turning the update check off leaves existing files unchanged.

The first stable release carrying the checker gives no notice of itself: older installs have no checker, and an equal version produces no notice. Missing caches initialize silently; failures print nothing and never stop a session. See the [update-check spec](docs/specs/update-check.md) for the exact data and limits.

## Quota probe

For the quota probe, the plugin itself makes no network call. The user's own `agy`, `claude` and `codex` programs contact their providers with the user's own accounts; the plugin sends nothing about the user. This is separate from the update check above.

The probe stays off until setup records the dated opt-in in the canonical `<data root>/host.md`, under `## Quota probe`. That section lists selected agents, confirmed absolute executable and interpreter paths, and labelled Claude config folders. Each Claude install starts with its usual configuration, including hooks, plugins and servers. `FNL_QUOTA_PROBE=off` stops probing; metrics consent neither enables nor disables it.

`<data root>/state/quota/quota.json` stores, per agent and user-chosen label, only `measured`, `source` and groups with `name`, `window`, `remaining_fraction` and `reset_time`. It contains no account, identity, email, path, plan, credit or token fields. `backoff.json` stores only `retry_after` and an error class per agent and label; `worker.json` holds a random nonce and heartbeat while a worker runs. Files are private (0600) in a private folder (0700). No raw program output is saved. Successful readings wait 4 hours; failures wait at least 30 minutes, changed formats 24 hours, and Claude replies treated as prompts 7 days. The commands run from an empty private folder under `<data root>/tmp/`, removed afterwards. Turning probing off leaves cached files unchanged; delete the quota state to clear it. Hook-started worker survival after session end, other Claude text formats and Windows remain unverified.

## What the plugin stores on your machine

- With the auto gate enabled, `<data root>/state/auto-gate/<key>.json`: a repository key in the filename (the first 12 hex characters of SHA-256 of the normalized repository root), `decision` (`handoff` or `keep`) with `decided`, and optionally `denied`, both ISO timestamps. Before a decision, the file can contain only `denied`. The script stores no path, task label or session id and sends nothing over the network. This local-only state is independent of usage metrics. The account home comes from the operating system, never `HOME`, `FNL_STATE_DIR` or `XDG_STATE_HOME`. The hook uses an 8-hour window; stale state can be replaced on the next write, not automatically purged. Turning the gate off leaves existing files unchanged; delete them to clear the state.

- `<data root>/ledger.jsonl` (no environment override): one line per delegated run with a short task label, the agent, the model, timings and the outcome. It holds no prompts, code, secrets or personal data. Delete the file to clear it.
- Only after you consent in `fnl-setup`, through the plugin's hooks on Claude Code and Codex, and on Antigravity when you add its hook in setup: usage events in `<data root>/state/events-YYYY-MM.jsonl` (or under `FNL_STATE_DIR`, or in the older `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` folder where it already exists), one line per event. A line holds a time, a session id, a short code derived from the repository path, and a few fixed fields: the name of an `fnl-` skill or agent that ran, the coding router's depth, a review verdict with a pull request number, the number of tasks a coordinator kept with a fixed reason and who settled it, or whether a session was started by a delegated run. It never holds prompts, code, command text, file paths or review text. Judge receipts hold only `site`, `grader`, `result`, and `followed` from fixed enumerations; they never hold a question, an answer, a cost, a file name or a path. Consent always lives in `<data root>/state/consent.json` (the date and how long to keep events), ignoring environment overrides; an invalid root pointer disables consent. The events folder holds a marker file per session, an error counter with the class name of the latest error (never its text), and the dashboard (`dashboard.html` and `data.js`), which `fnl-status` opens in your browser from your disk. Events older than the retention you chose (30, 90 or 365 days) are deleted at the start of a session, and `fnl-status purge` deletes them all at once. Set `FNL_METRICS=off`, or run `fnl-status` `consent --revoke`, to stop recording at any time. The events are best effort: they are read from tool calls and command text, so they can miss an action or count one that was only written out.
- `.finolabs/` in your repository (older versions used `.orchestration/`), when you follow `fnl-delegate` "Where files go": briefs, logs and handover notes that you or your agents write. The skill tells agents to keep this folder out of git.
- The host config file you create from `skills/fnl-delegate/references/host-template.md`, at a path you choose.

## Reporting issues

Public issues and pull requests are visible to everyone. Remove credentials, personal data and private repository content from any transcript, brief or log before you post it. Report security problems privately as described in [SECURITY.md](SECURITY.md).
