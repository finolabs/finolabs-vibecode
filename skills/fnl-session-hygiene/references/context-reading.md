# Context reading (Claude Code)

When the user configured the status-line recorder, run `python3 -I <this skill folder>/scripts/context_snapshot.py read --latest` to see the newest local reading, or `check --latest --threshold <chosen tokens> --boundary <yes|no|unknown>` to feed its real counts to the steward (advisory, agent judgment).

The hook's `session_id` is not visible to the model: `--latest` avoids guessing it.

It can belong to another parallel session, so use it as your own only when the active session is unambiguous; otherwise use `--session <known id>` from a supported host interface or say that your own reading is unavailable (advisory, agent judgment).

The SessionStart Context line always refers to the starting session, on every source except `compact`, and is only a reading at that time.

The script enforces bounded integer input, metadata-only private atomic storage, at most 20 snapshots and freshness (default one hour); `read`/`check` exit 3 with a fixed message when unavailable or stale.

No transcript is read; without a reading, say so and never invent numbers (advisory, agent judgment).

Codex and Antigravity are not covered by this recorder.
