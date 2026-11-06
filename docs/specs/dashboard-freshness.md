# Dashboard freshness

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
  hooks are not trusted (no hook runs, so no event); quota readings (every 4 hours by design); the new panels
  (processes, progress), which depend on a rebuild.
- A hidden tab polls nothing; the page cannot tell the user that its data is old.

## Changes

1. **Ledger triggers a rebuild.** After a successful `start` or `finish`, `ledger.py` starts `refresh.py run
   --throttle 10` detached (new session, output discarded, no wait, a failure ignored). Enforcer: the script.
2. **Antigravity hook starts a detached rebuild.** The hook does not wait: it starts the same detached
   `refresh.py run --throttle 10` and returns at once, so a tool call is never held up; it keeps its current
   behaviour otherwise.
3. **Freshness line on the page.** Shows when `data.js` was built, the time of the newest event per host, the
   age of the ledger's last line and of the quota reading, and warns per host when it has been quiet for more
   than 15 minutes while another host is active ("Codex: last event 09:12; hooks may need trust"). When
   `data.js` itself is older than 60 seconds and the tab is visible, the page says "data is N minutes old; it
   updates while a session runs tools". All values are text from the data, rendered with `textContent`.
4. **Not done here:** live mode (0.2.0); fixing Codex trust (the host owns it).

## Not in scope

A local web server; a push channel; per-second updates; changing the 4-hour quota cadence.

## Acceptance

1. `ledger.py start/finish` start one detached rebuild (a fake runner), never wait, never fail the ledger write
   when the rebuild cannot start; throttle holds across rapid calls.
2. The Antigravity hook returns without waiting for the rebuild (timed test) and the Claude Code and Codex
   paths are unchanged.
3. `refresh.py` writes the freshness block (build time, newest event per host, ledger age, quota age); the
   page shows the line, the per-host quiet warning and the stale-data message with fake timers; hostile host
   or value text renders as text.
4. `PRIVACY.md` unchanged in meaning (times and host names only); `check-references.py`,
   `claude plugin validate .` and targeted tests pass; no hook file changed.
