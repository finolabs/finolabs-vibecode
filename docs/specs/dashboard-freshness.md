# Dashboard freshness

Status: implemented; ledger and Antigravity rebuild triggers and the per-host freshness line (release 0.1.10, package 9, pull request 108).

Owner concern, 2026-11-06: the dashboard must show current information. Audit of what is current today and
what is not, and the fix for the parts that can be fixed without a background process. A live mode (a refresh
loop that runs while no session does) is a separate, opt-in piece for 0.2.0, because autopilot monitoring needs it.

## Audit (code and measurement, 2026-11-06)

- `data.js` is rebuilt by `refresh.py`. The page reloads it every 5 seconds while its tab is visible and again
  when the tab becomes visible.
- The metrics hook starts a rebuild after a Claude Code or Codex `PostToolUse` (at most one per 10 seconds) and
  after `Stop`. Observed: `data.js` and the newest event had the same minute while a session ran.
- Not current: Antigravity events (its hook is not asynchronous, so it never starts a rebuild); ledger writes
  (`ledger.py start` and `finish` start nothing); anything while no session runs a tool; Codex events while its
  hooks are not trusted (no hook runs, so no event); quota readings (on demand before delegation, at least 15 minutes apart; see `quota-on-demand.md`); the new panels
  (processes, progress), which depend on a rebuild.
- A hidden tab polls nothing; the page cannot tell the user that its data is old.

## Corrections to the first audit

A ledger write by a coordinator session that has hooks is already followed by a rebuild: the write runs through a
tool call, and the `PostToolUse` hook starts one right after it unless the last rebuild is under 10 seconds old.
The ledger is stale only when it is written outside a hooked session (a terminal, or an Antigravity coordinator)
or inside the 10-second window. The current hook also rebuilds synchronously with a 4-second timeout; it is not
fire-and-forget.

## Changes

1. **Newer ledger bypasses the throttle.** `refresh.py run --throttle 10` compares the ledger's modification time
   with `data.js` and rebuilds when the ledger is newer, so the next rebuild of any kind picks a ledger write up at
   once. No cross-skill call: `ledger.py` is untouched (the skills stay self-contained). Enforcer: the script.
2. **Antigravity hook starts a detached rebuild.** `scripts/metrics_hook.py` (the plugin-level hook script; no hook
   declaration file changes) starts the rebuild without waiting for it, so a tool call is never held up. A new start
   is not made when the refresh lock is held, or when metrics consent is not recorded. Fixed argv
   (`sys.executable -I <refresh.py> run --throttle 10`), an environment limited to what the interpreter needs,
   output discarded, a new session, failures ignored. `refresh.py` carries its own wall-clock cap of 20 seconds
   (it exits itself), because a detached process has no parent timeout. This is new start-and-forget behaviour, not
   a reuse of the Claude Code path.
3. **Freshness line on the page.** Shows when `data.js` was built, the time of the newest event per host, the age of
   the ledger's last line and of the quota reading, and warns per host when it has been quiet for more than 15
   minutes while another host is active ("Codex: last event 09:12; hooks may need trust"). When `data.js` itself is
   older than 60 seconds and the tab is visible, the page says "data is N minutes old; it updates while a session
   runs tools". All values are text from the data, rendered with `textContent`.
4. **Not done here:** live mode (0.2.0); fixing Codex trust (the host owns it).

## Not in scope

A local web server; a push channel; per-second updates; starting quota readings from dashboard hooks.

## Acceptance

1. A ledger newer than `data.js` makes `refresh.py run --throttle 10` rebuild; an older ledger does not; `ledger.py`
   is unchanged and no skill calls another skill's script.
2. The Antigravity hook returns without waiting for the rebuild (timed test), starts none while the lock is held or
   without metrics consent, uses the fixed argv and environment, and the rebuild exits itself at 20 seconds; the
   Claude Code and Codex paths are unchanged.
3. `refresh.py` writes the freshness block (build time, newest event per host, ledger age, quota age); the
   page shows the line, the per-host quiet warning and the stale-data message with fake timers; hostile host
   or value text renders as text.
4. `PRIVACY.md` unchanged in meaning (times and host names only); `check-references.py`,
   `claude plugin validate .` and targeted tests pass; no hook declaration file changed (the hook script does).
