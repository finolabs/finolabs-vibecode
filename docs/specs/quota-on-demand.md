# Quota reading on demand, with a rate-limit marker (release 0.2.0)

Status: implemented; release 0.2.0 on-demand reads and rate-limit markers have local fixture tests; live StopFailure payload and provider readings remain unverified.

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

- New command `quota_probe.py read --family <agy|claude|codex> [--max-age-minutes N]`, in every copy of the script. `N` is raised to 15 when lower; no caller can read more often than once per 15 minutes per family. A success writes `retry_after` 15 minutes ahead (the 4-hour `FRESH` constant goes); the 30-minute failure and 24-hour shape backoffs stay, and so does the 7-day prompt backoff.
  It reads the canonical host config (`Quota probe: on`, `FNL_QUOTA_PROBE=off`, the same checks as today), the cache,
  and the backoff times; if the family's reading is newer than the maximum age, a failed run is still inside its 30
  minutes, or an unexpected shape is still inside its 24 hours, it prints the cached state and runs nothing. Otherwise it
  runs the family's one command exactly as the 0.1.8 worker did (fixed argv, no shell, allowlisted environment,
  neutral empty working folder, 30-second limit with the process group killed, 64 KiB cap) and writes the cache.
  It waits for its own run, starts no detached worker and prints one line per install: family (and the user's label), state
  (`fresh`, `read`, `backoff`, `off`, `busy`, `unverified`) and age; never provider text. `agy` and `codex` run one command; `claude` runs one command per listed install (at most four, one after the other), each within its own 30-second limit, so a call is bounded by 30 seconds times the installs.
- At most one reading runs at a time, kept by a single in-flight marker that holds a per-run random token and its start time (the old nonce guard is replaced by it); the stale bound derives from the maximum listed installs times the per-command limit plus 30 seconds for parsing and publication: `MAX_INSTALLS * TIMEOUT + 30 = 4 * 30 + 30 = 150 seconds`. A marker at or beyond that age is stale and replaced. A second command finding a live marker prints `busy` and reads the cache. Tests: two concurrent reads, and a killed run whose marker goes stale.
- The child `claude -p` run keeps `FNL_METRICS=off` and runs with the update check off (`FNL_UPDATE_CHECK=off` in its allowlisted environment), because the nonce that quieted its hooks is gone; the other hooks only read local files. The setup consent sentence about the usual configuration running stays.
- Reading is still opt-in and never turns on from the environment. The setup text changes (no 4-hour background step):
  "When the coordinator is about to delegate, and a reading is older than 15 minutes, it runs each agent's own
  read-only usage command (`agy`, `claude`, `codex`) once; those programs contact their providers with your own
  accounts, and the plugin sends nothing about you."
- The session-start and `PostToolUse` hooks stop starting workers: they keep reading the cache only. The worker
  code, its nonce guard (`FNL_QUOTA_WORKER`, imported today by `session_start.py`, `metrics_hook.py`, `update_check.py`, `auto_gate_hook.py` and `precompact.py`) and its tests are removed, each importer updated; the guard test that no hook starts a
  worker is kept and strengthened (no hook starts any process).
- `fnl-delegate` Route step 4 now says: before routing, for each candidate family run
  `quota_probe.py read --family <f>` (advisory, agent judgment; the script enforces the age, backoff and limits),
  then `quota_probe.py status`; honor markers (part B); a reading older than 8 hours stays `unverified`; the user's own
  statement wins. A delegated headless run reads and does not start readings (advisory, agent judgment; the script enforces the age and busy rules for everyone). Autopilot (`autopilot.md`) stops on a missing reading, so it runs `read` first.

## B. The rate-limit marker

- One new hook entry in the Claude plugin manifest (not Codex, not Antigravity) for the `StopFailure` event, running a small script. It reads the event input (capped at 64 KiB, JSON) and writes only when `error` equals the exact string `rate_limit`. It reads the canonical `host.md` (no-follow, owned by the user) to check `Quota probe: on` and `FNL_QUOTA_PROBE`, and `state/quota/limits.json` (private folder, mode 0600, no-follow, owner-checked) under an exclusive lock, then replaces it atomically with `{claude: <UTC time>}`. It runs no process and sends nothing. It exits 0 on every path; fails closed means no write. The payload shape is pinned by a test fixture (unverified against a live event; a real one is captured before release).
- The marker is advisory. A repository can influence the error (for example through a project `ANTHROPIC_BASE_URL`), and the marker is per family, so one limited install marks all Claude installs. Therefore a newer successful `read` of the family overrides the marker, it excludes the family only from routing offers, and the user's statement wins.
- Expiry, single rule: out of quota until the family's cached reset time when that lies in the future and within five hours after the marker; otherwise one hour after the marker; never longer than five hours. A test pins both cases and the override.
- Codex and Antigravity get no marker (no documented equivalent was found); their on-demand reading is the signal.
- Adding a hook entry to the Claude manifest makes Claude Code ask the user to trust the changed hooks; Codex and Antigravity read their own manifests and get no new prompt. This is called out in the release notes and the PR.

## C. The Homebrew exception to the executable check

`quota_setup.py` (`excluded()`) and `quota_probe.py` (`checked_path`) refuse an executable inside a git work tree. The narrow exception, now in `CLAUDE.md`: the walk from the file up to the root may meet a `.git` only at exactly `/opt/homebrew`; a `.git` at any other level (a tap under `Library/Taps`, a clone) still refuses. The resolved target and any interpreter (for example `node`) must lie inside `/opt/homebrew`, with no symlink leaving it. Every component from the prefix to the file is owned by the user and not world-writable; a component may be group-writable only when its group is `admin` (the stock Homebrew layout is `drwxrwxr-x user admin`, and members of `admin` already hold `sudo`). The preview shows the path for the user to confirm. All other checks stay (owner, no temporary or downloads folder, interpreter rules). The Intel prefix needs no exception (its repository is `/usr/local/Homebrew`, not an ancestor of `bin` or `Cellar`; its modes are unverified).

## D. Not in scope

The status line route; a marker for Codex or Antigravity; reading quota from provider APIs; a reading on session
start; any new network call by the plugin; changing which commands are run or their parsers.

## Acceptance

- `read` runs nothing with probe off, with `FNL_QUOTA_PROBE=off`, with a fresh reading, inside a backoff, or with a
  live in-flight marker; it runs exactly one command per due install otherwise (one for `agy` or `codex`, up to four sequential commands for `claude`), kills the process group on timeout, and
  never starts a detached process (a fake executable that forks is reaped or reported); output is one line per install without
  provider text; fixtures with fake `agy`, `claude`, `codex` as in 0.1.8.
- Hooks start no process and make no reading (the guard test iterates the hook commands of every manifest); the worker
  code and nonce are gone, and a test shows a child `claude` run triggers no update-check request.
- `read` raises `--max-age-minutes 0` to 15, and a success is not repeated within 15 minutes.
- The `StopFailure` hook writes the marker only for `error: rate_limit` and only with the probe on, writes
  family and time only, exits 0 on bad input, a missing folder, a symlinked state folder or a failed write, and does
  nothing for any other error value; a planted `FNL_STATE_DIR`, `HOME` or `XDG_STATE_HOME` redirects nothing.
- Routing: a test pins the 15-minute age, that a marker excludes its family until the reset time or one hour (never
  more than five), that an older cache is `unverified`, and that the user's statement wins.
- Homebrew: tests for the stock layout (group `admin`, group-writable, allowed), a group-writable component of another group, a world-writable component, a symlink leaving the prefix, a tap or nested repository under the prefix, an interpreter outside the prefix, and an executable in another repository (all refused).
- Every consumer of the 4-hour cadence or the hook-started worker is updated: `tests/test_quota_probe.py` (the cadence sentence and nonce tests), `tests/test_session_start.py`, `tests/test_metrics_hook.py`, README, `fnl-setup` `SKILL.md`, `check.md` and `host-template.md`, the `FRESH` constant in the script copies (CI compares them), `dashboard-freshness.md`, `autopilot.md`, and `PRIVACY.md` (which keeps the line about the family and time of a rate-limit marker).
- `PRIVACY.md`, `fnl-delegate` text and references, `fnl-setup` Check/preview text, `docs/specs/release-0.1.8.md`
  (a note that its cadence and its "no new hook entry" premise are superseded here) and `CHANGELOG.md` updated; the rule in `CLAUDE.md` is this spec's source
  and was merged first.
- The implementation pull request gets its own security review.

## Open decisions

None blocking. Later: a status-line feed for Claude (documented `rate_limits` fields, account-or-session scope
unverified); whether Codex hooks expose a rate-limit event.
