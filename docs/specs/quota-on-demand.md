# Quota reading on demand, with a rate-limit marker (release 0.1.11)

Status: accepted; owner decisions recorded on 2026-11-07; implementation not started.

## Why

The quota probe of release 0.1.8 (`release-0.1.8.md` package 13) reads each agent's usage limits through a detached
worker that the session-start and `PostToolUse` hooks start when a cache is older than 4 hours. The owner rejected
that timer on 2026-11-07: a periodic background run is not wanted, and what the coordinator needs is a fresh answer
at the moment it decides whom to delegate to. Checking the documentation of Claude Code the same day showed that
hooks do not receive quota or rate-limit state; only the status line input carries `rate_limits`, and the
`StopFailure` hook event reports `error: rate_limit` without a reset time. A fixed Homebrew prefix also blocked the
Codex probe: `/opt/homebrew` is a git work tree, and the executable check refuses any executable inside one.

## Decisions settled (owner, 2026-11-07)

- Hook-started periodic reading is removed. A reading happens on demand, right before a routing or delegation
  decision, when the cached reading of a candidate family is older than 15 minutes.
- A `StopFailure` marker records that Claude Code hit a rate limit, as a reactive signal.
- The executable check gets one narrow exception for the Homebrew prefix `/opt/homebrew`.
- The status line route (writing `rate_limits` to a file) is not built. It stays a later option.

## A. On-demand reading

- New command `quota_probe.py read --family <agy|claude|codex> [--max-age-minutes 15]`, in every copy of the script.
  It reads the canonical host config (`Quota probe: on`, `FNL_QUOTA_PROBE=off`, the same checks as today), the cache,
  and the backoff times; if the family's reading is newer than the maximum age, a failed run is still inside its 30
  minutes, or an unexpected shape is still inside its 24 hours, it prints the cached state and runs nothing. Otherwise it
  runs the family's one command exactly as the 0.1.8 worker did (fixed argv, no shell, allowlisted environment,
  neutral empty working folder, 30-second limit with the process group killed, 64 KiB cap) and writes the cache.
  It waits for its own run, exits within the limit, starts no detached worker and prints one line: family, state
  (`fresh`, `read`, `backoff`, `off`, `unverified`) and age; never provider text.
- At most one reading runs at a time, kept by the existing single in-flight marker; a second command finding a live
  marker prints `busy` and reads the cache.
- Reading is still opt-in and never turns on from the environment. The setup text changes (no 4-hour background step):
  "When the coordinator is about to delegate, and a reading is older than 15 minutes, it runs each agent's own
  read-only usage command (`agy`, `claude`, `codex`) once; those programs contact their providers with your own
  accounts, and the plugin sends nothing about you."
- The session-start and `PostToolUse` hooks stop starting workers: they keep reading the cache only. The worker
  code, its nonce guard (`FNL_QUOTA_WORKER`) and its tests are removed; the guard test that no hook starts a
  worker is kept and strengthened (no hook starts any process).
- `fnl-delegate` Route step 4 now says: before routing, for each candidate family run
  `quota_probe.py read --family <f>` (advisory, agent judgment; the script enforces the age, backoff and limits),
  then `quota_probe.py status`; honor markers (part B); a reading older than 8 hours stays `unverified`; the user's own
  statement wins. A delegated headless run reads and does not start readings.

## B. The rate-limit marker

- One new hook entry in the Claude plugin manifest for the `StopFailure` event, running a small script that reads the
  event input and, only when `error` equals `rate_limit`, writes `state/quota/limits.json` (private folder, mode
  0600, atomic) with the entry `{claude: <UTC time>}`. It exits 0 on every path, fails closed, reads no file and runs no
  process. It needs no consent beyond `Quota probe: on` being recorded, which it reads from the canonical host config;
  with the probe off it does nothing. `FNL_QUOTA_PROBE=off` stops it.
- Codex and Antigravity get no marker (no documented equivalent was found); their on-demand reading is the signal.
- The coordinator treats a marker as "out of quota" for that family until the family's known reset time from the
  cache, else one hour, never longer than five hours after the marker; the user's statement wins. Markers hold only
  the family and the time and are never shown with text.
- Adding a hook entry makes Claude Code and Codex ask the user to trust changed hooks only where that host reads this
  manifest; the manifest change is called out in the release notes and the PR.

## C. The Homebrew exception to the executable check

`quota_setup.py` and the probe refuse an executable inside a git work tree. The narrow exception, now in `CLAUDE.md`:
the resolved target and its ancestors may sit inside the work tree rooted at exactly `/opt/homebrew` only when
every component from the prefix to the file is owned by the user and not group- or world-writable, the file is not
reached through a symlink that leaves the prefix, and the preview shows the path for the user to confirm. All other
checks stay (owner, mode, no temporary or downloads folder, interpreter rules). The Intel prefix needs no exception
(its repository is `/usr/local/Homebrew`, not an ancestor of `bin` or `Cellar`).

## D. Not in scope

The status line route; a marker for Codex or Antigravity; reading quota from provider APIs; a reading on session
start; any new network call by the plugin; changing which commands are run or their parsers.

## Acceptance

- `read` runs nothing with probe off, with `FNL_QUOTA_PROBE=off`, with a fresh reading, inside a backoff, or with a
  live in-flight marker; it runs exactly one command per call otherwise, kills the process group on timeout, and
  never starts a detached process (a fake executable that forks is reaped or reported); output is one line without
  provider text; fixtures with fake `agy`, `claude`, `codex` as in 0.1.8.
- Hooks start no process and make no reading (the guard test iterates the hook commands of both manifests); the worker
  code and nonce are gone.
- The `StopFailure` hook writes the marker only for `error: rate_limit` and only with the probe on, writes
  family and time only, exits 0 on bad input, a missing folder, a symlinked state folder or a failed write, and does
  nothing for any other error value; a planted `FNL_STATE_DIR`, `HOME` or `XDG_STATE_HOME` redirects nothing.
- Routing: a test pins the 15-minute age, that a marker excludes its family until the reset time or one hour (never
  more than five), that an older cache is `unverified`, and that the user's statement wins.
- Homebrew: tests for the allowed layout, a group-writable component, a symlink leaving the prefix, an executable in
  another repository, and the prefix repository itself (refused when any condition fails).
- `PRIVACY.md`, `fnl-delegate` text and references, `fnl-setup` Check/preview text, `docs/specs/release-0.1.8.md`
  (a note that its cadence is superseded here) and `CHANGELOG.md` updated; the rule in `CLAUDE.md` is this spec's source
  and was merged first.
- The implementation pull request gets its own security review.

## Open decisions

None blocking. Later: a status-line feed for Claude (documented `rate_limits` fields, account-or-session scope
unverified); whether Codex hooks expose a rate-limit event.
