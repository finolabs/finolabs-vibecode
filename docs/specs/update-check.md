# Plugin update check

Status: implemented; for package D of 0.1.7; check and notice verified on Claude Code, unverified on Codex and Antigravity; no live network or host update validation.
Owner decisions: 2026-11-04. The check is on by default, independent of usage metrics consent. `FNL_UPDATE_CHECK=off` stops every helper action. It is the one allowed network call made by the plugin itself. Updating through a host is a separate, explicitly authorized native operation.

## What and why

Installed plugins can remain old without a visible reminder. A synchronous `SessionStart` command for matcher `startup` on Claude Code and Codex reads a local cache and emits at most one short line telling the agent to let the user know a newer version is available and that they can type `/fnl-update` (on Codex `$fnl-update`). It never installs anything. The existing reminder and all async metrics hooks stay in place. Antigravity gets the skill, but no automatic update hook in this package.

The hook starts a detached `subprocess.Popen` worker when the cache is missing or at least 24 hours old. It never waits and never performs network I/O itself. Worker stdin, stdout and stderr are discarded. On POSIX the worker uses `start_new_session=True`; on Windows (`sys.platform == "win32"`) it instead uses `creationflags=0x00000008 | 0x00000200` (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`). Windows execution is untested; only its spawn arguments are tested with mocks. `urllib.request` and the redirect handler are loaded only inside the worker's `fetch()`. The hook uses only the snapshot it already read, so a missing cache cannot produce a notice on that startup even if the worker finishes immediately. The hook has a five-second host timeout, suppresses stderr and returns 0 even if Python or the script is missing. Python errors are swallowed with exit 0. Concurrent startups may each start one worker; there is no scheduler or retry loop.

## Exact data and network boundary

The worker makes one HTTPS GET to `https://api.github.com/repos/finolabs/finolabs-vibecode/releases/latest`, with a three-second timeout and User-Agent `finolabs-vibecode-update-check`. Standard-library TLS certificate verification applies. No request body, query parameters, credentials, cookies, telemetry or installed version are supplied. No username, machine, repository, session, prompts, code, command text, file paths or other product versions are sent. As with any HTTPS request, GitHub sees the source IP. Proxy use and redirects are disabled; there are no retries, backoff or additional settings.

The response read is capped at 65,537 bytes; more than 65,536 bytes is rejected. Only an object with a string `tag_name` matching the whole pattern `^v?\d+\.\d+\.\d+$` (ASCII digits, at most 64 characters) is accepted. All other fields are discarded. Newlines, shell metacharacters, prereleases, URLs, wrong JSON types and malformed JSON are rejected. Nothing from the response is executed or used as a command. Only the validated version can reach the notice or status output.

All files use `fnl_metrics.state_dir()`: by default `~/.finolabs/vibecode/state/`, with that function's existing override and legacy-folder rules. The checker never calls the metrics consent or recording functions and adds no usage events or schema fields.

| File | Exact fields | Example |
| --- | --- | --- |
| `update-check.json` | `checked_at`: finite nonnegative Unix timestamp in seconds, not in the future; `tag`: validated stable release tag | `{"checked_at":1793750400,"tag":"v0.1.7"}` |
| `update-state.json` | `skipped`: list of validated stable versions; `never_ask`: boolean | `{"skipped":["0.1.8"],"never_ask":false}` |

Both files are written through `fnl_metrics.atomic_write` with mode `0600`; new state directories are mode `0700`. The cache is replaced only after a valid successful response. No response bodies or error text are retained. Local reads use the shared bounded regular-file reader and reject symlinks and pipes. Stored skip choices are normalized without the leading `v`. The never-ask choice suppresses notices, not requests; `FNL_UPDATE_CHECK=off` suppresses both. Existing cached data stays on disk while off.

## Versions, bootstrap and notice

Read the installed version from `.claude-plugin/plugin.json`, the source of truth, never from a host's version or a hard-coded release. The manifest read is capped at 64 KB, independently of the 4 KB local state reader; larger manifests are rejected. Numeric major, minor and patch fields compare numerically; `0.1.7-dev` precedes `0.1.7`, and build metadata does not change precedence. Release responses accept stable versions only; installed builds accept stable or `-dev` with optional build metadata. Equal or older releases produce no notice.

Bootstrap requires no special flag: pre-0.1.7 installs have no checker, and the first carrying stable release (0.1.7) equals the latest release when it ships, so nobody is notified of that release. Development installs can be notified when their own stable release appears, as required by SemVer. Missing caches initialize silently. Future newer stable releases can notify normally.

Notice: `A newer finolabs-vibecode (X.Y.Z) is available. Let the user know they can type /fnl-update (on Codex $fnl-update); do not update on your own.` The hook has no session tracking and reads no session payload. The agent must tell the user at most once per session; only the user can invoke the skill. Explicit `skip <version>` and `never` choices persist across sessions. A dismissal without either choice can produce another notice at a later startup.

## Skill and native composition

`fnl-update` is user-invoked (`disable-model-invocation: true`). It shows local status before proposing a host update, requires a clear yes to that concrete command, and reports observed success or failure. It can record a requested skip or never-ask choice without updating. Its helper and shared core are byte-identical copies in its own folder. A standalone skill without the plugin manifest reports installed version unknown and uses the native plugin listing; it creates no startup hook.

The task explicitly requires host update guidance here, an exception to the general convention of putting host-specific commands in host config. No manifest version is changed.

Composition probes on 2026-11-04, all exit 0, no updates executed:

- `claude plugin --help`: native `list` and `update`. `claude plugin update --help`: `update <plugin>`, restart required. Syntax verified; successful update execution unverified.
- `codex plugin --help`: `add`, `list`, `marketplace`, `remove`, no update subcommand. `codex plugin marketplace --help`: `upgrade` refreshes marketplace snapshots; installed-plugin update behavior unverified. Both commands warn that PATH aliases could not be created (`Operation not permitted`), but print help successfully. Codex hooks require trust again after an update through `/hooks`.
- `agy plugin --help` and `agy plugin help`: no update subcommand. Install-over-existing behavior unverified, so the skill does not prescribe it as an update.

## Failure behavior and limits

Malformed cache or choices, unreadable state, unsupported installed version, missing manifest, failed spawn, failed TLS/HTTP, redirects, timeout, invalid JSON, oversized response or bad tag: no error output and exit 0. Network failures preserve the prior cache; a later eligible startup may attempt a new check, with no in-process retry. An invalid cache (including malformed JSON, wrong fields or a future timestamp) is treated as missing, so the next startup schedules a worker to replace it after a successful fetch. Invalid choices default to `{"skipped":[],"never_ask":false}` for `status`, `skip` and `never`; either write command replaces the invalid file. The startup hook suppresses notices while choices are invalid but can still refresh the cache. No invalid state content is printed to the agent. A stale valid cached release can still produce a notice while a refresh runs; `status` identifies stale facts. Missing or corrupt facts never justify an automatic update. A skipped release or never-ask choice suppresses the notice. Off returns before state reads, writes or spawning.

## Targeted verification

`tests/test_update_check.py` uses mocked transports and `Popen`: numeric version precedence, development/release ordering, bootstrap, equal/older suppression, hostile response types/text, request destination/method/headers, timeout and read bounds, no redirects/proxies, cache age and invalid-cache recovery, invalid-choice defaults and replacement, manifests over 4 KB, detached POSIX and mocked Windows process options, private file modes, off, skip, never, status, silent error handling, and both hosts' synchronous startup commands including a real shell run with a missing script. `tests/test_metrics.py` pins both copied helpers byte for byte. No real GitHub request or host update is part of validation. Live Codex hook loading remains unverified as documented in the usage-metrics spec.
