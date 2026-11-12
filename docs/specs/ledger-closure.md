# Ledger closure: stop delegate ledger records from staying open

Status: accepted; owner decision 2026-11-12 ("all four in 0.2.5"); code and tests written on branch `ledger-closure`, tests not yet run, live-host hook delivery unverified.

## Why

On 2026-11-12 the shared ledger held 1374 dispatches, and about one in nine never got a `finish` line from its coordinator. The rate follows the coordinator session, not the agent: one coordinator left 35 of 41 open, another 38 of 60, another 46 of 235. The same day a session in an unrelated repository ran `ledger.py stale --close` and recorded 112 records of six other projects as `cancelled` with no log. A `finish` line cannot be corrected, so those outcomes are lost.

Four causes:

1. `finish` is only agent judgment: nothing reminds the coordinator session that owns a run.
2. A review dispatch cannot be accepted without a verify receipt for the checkout head, which a review never produces, so coordinators skip the finish or use `--accept-unverified`.
3. `stale --close` acts on every project from any checkout.
4. Nothing records that a run's process ended, so `open` and `stale` cannot tell a finished run from a live one.

## The four fixes

### D. `stale` is scoped to this repository's project

`stale` (preview and `--close`) considers only records whose `project` equals this repository's ledger project, resolved as `status` resolves it: the approved `ledger` entry of the repository's project settings, else the checkout folder name. `ledger.py this_project()` reuses `project_store.identity` and `project_store.settings_state`; broken settings resolve to nothing, as the status join reads unknown. With no resolved project and no `--all-projects`, `stale` refuses with a message naming `--all-projects`.

`--all-projects` widens the preview to every project and prints a warning that other projects' runs cannot be judged from this checkout. The saved plan now carries `project` (the name, or null for every project), so the digest binds the scope: a one-project preview closes only when the current checkout resolves the same project and without `--all-projects`; an all-projects preview closes only with `--all-projects`; at close each record must still belong to the previewed project.

Enforcer: `ledger.py`.

### C. A review dispatch is accepted on its posted review

For a dispatch whose start has `kind: review`, `finish --outcome accepted` needs no verify receipt and no `--accept-unverified`. It takes `--head <40-char sha>` (now allowed for `implement` and `review`) and an optional `--review-url https://github.com/<owner>/<repo>/pull/<n>#issuecomment-<id>`, validated by pattern only, never fetched and never stored; when given, the line records `review_posted: true`. A review's head is stored as `reviewed_head`, not `head`, because `review_route.author_family` reads every line whose `head` matches and takes its `agent` as an author family: a reviewer's head line would break authorship for that head. `--review-url` goes only with an accepted review dispatch. Every other kind keeps the receipt rule.

`--reason` may go with any outcome. It is bounded (nonempty, at most 4096 characters) and stored only as its SHA-256 digest (`reason_id`), as before.

Enforcer: `ledger.py`. Reading the posted marker before accepting stays agent judgment.

### B. The dispatch wrapper records that the run ended

After `delegate_env.py` runs its child, when `FNL_DISPATCH_ID` matches the id pattern `ledger.py start` writes (`d<8 digits>-<6 digits>-<4 hex>`), it appends `{"event": "ended", "id", "ts", "exit"}` through `away_lease.append_ledger`, the plugin's existing safe append (no-follow, owner- and mode-checked file, data-root folder checks, one appended line; it takes no lock, as `ledger.py append` takes none). A signal-terminated child records its negative code. Nothing is written for a missing or invalid id, an unresolved data root or a ledger file that does not exist yet; every failure is silent and the wrapper's exit status stays the child's. The line holds no command text, output or path.

`ledger.py load(ended=None)` fills an optional map with valid `ended` lines and never counts them as finishes or as malformed; callers that pass nothing get the same two maps as before. `open` adds `ended exit=<n>` to an open record that has one. `stale` treats an ended record as due without waiting for twice its budget: 24 hours, or `--older-than-hours` when given (even inside the budget, since the run is over); it proposes `error` for a nonzero exit and `cancelled` with the note "run ended exit 0; no verdict recorded" for exit 0, and does not read the log. `summary` ignores the line. The session-start count and `review_route` read only `start`, `finish` and `head`, so they are unchanged.

Enforcer: `delegate_env.py` and `ledger.py`.

### A. A per-session reminder on Claude Code

A new `UserPromptSubmit` hook in its own group of `.claude-plugin/hooks.json`, never in the metrics group: `python3 -I scripts/open_dispatch_nudge.py; exit 0`. It reads the hook input's `session_id` (validated as `ledger.py start` validates `CLAUDE_CODE_SESSION_ID`), hashes it as `start` computes `coord_session`, and reads the ledger through `data_root.read_data` with a 4 MiB bound. It selects this session's records with no `finish` line and either an `ended` line or an age past `budget_min` (60 minutes when absent), and prints one fixed line:

`Delegated runs this session started have no ledger outcome: <n> (<up to five ids>). Record each with ledger.py finish (delegate "Record"); a run still working stays open.`

It prints at most once per 30 minutes per session. The mark, one integer timestamp, is written atomically with mode 0600 at `<data root>/state/dispatch-nudge/<sha256(session id)[:16]>` before printing; at most 200 marks are kept, oldest removed; if the mark cannot be written nothing is printed. Any error prints nothing; it always exits 0, records no metrics event, sends nothing, reads only the ledger and its own mark, and `FNL_DISPATCH_NUDGE=off` disables it. Codex and Antigravity are not covered.

The hook only prints and never denies, so it needs no new scoped exception in `CLAUDE.md`.

Enforcer: the hook prints; recording the outcome stays agent judgment (advisory).

## Tests

- `tests/test_ledger.py`: stale scope (another project's records neither previewed nor closed; `--all-projects` includes them with the warning and binds the scope; a one-project preview refuses a close with `--all-projects` or from another project; an unresolved project refuses; the resolver returns the checkout folder name and nothing outside a repository); `ended` read by `load` and `open`, ignored by `summary`; stale due time and outcome from the exit code, including `--older-than-hours` inside a budget; review-kind accept with and without `--review-url`, URL pattern refusals, the URL never stored, `reviewed_head` never `head`; non-review kinds still refused without a receipt; `--reason` with any outcome kept as a digest.
- `tests/test_delegate_env.py`: the ended line holds the child's exit code and nothing else; a signal gives a negative code; nothing is written for a missing or malformed id or an absent ledger; the exit status is the child's when the ledger write fails; `ledger.load` reads the line as open.
- `tests/test_open_dispatch_nudge.py`: prints for this session's overdue and ended records only, never another session's; at most five ids; throttle and private integer mark; an unwritable mark prints nothing; the 200-mark cap; `FNL_DISPATCH_NUDGE=off`; malformed input prints nothing and exits 0; no process or network use; the manifest group is its own and ends with `exit 0`.
- `tests/test_metrics_hook.py` and `tests/test_session_start.py` now account for the second `UserPromptSubmit` group.

## What stays unverified

- The tests were written but not run on the branch that adds them; the coordinator runs them.
- Delivery of the hook's stdout into the model context on a live Claude Code session, and whether the reminder changes coordinator behavior, are unverified.
- The `ended` line covers only runs started through `delegate_env.py` with `FNL_DISPATCH_ID` set; in-session subagents and app sessions never get one.
- Records closed by the 2026-11-12 cross-project `stale --close` stay as recorded; this change prevents a repeat and does not correct them.
- The fixed line points to delegate "Record", which is step 7 of `delegate`'s loop (`references/loop.md`), not a heading of `delegate/SKILL.md`.
