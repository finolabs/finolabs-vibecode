# Context reading (Claude Code and Antigravity)

When the user configured the status-line recorder, run `python3 -I <this skill folder>/scripts/context_snapshot.py read --latest --host <claude|antigravity>` for the active host. Use `check --latest --host <host> --threshold <chosen tokens> --boundary <yes|no|unknown>` to feed those counts to the steward (advisory, agent judgment). Without a host, `--latest` reads whichever host wrote last.

The host's session id is not visible to the model: `--latest` avoids guessing it. A host filter can still select another parallel session of that host. Use it as your own only when the active session is unambiguous; otherwise use `--session <known id> --host <host>` from a supported host interface or say that your own reading is unavailable (advisory, agent judgment). Claude uses `session_id`; Antigravity uses `conversation_id`. Session lookups default to Claude when no host is given.

The SessionStart Context line is Claude-only and always refers to the starting session, on every source except `compact`; it is only a reading at that time. There is no Antigravity SessionStart hook here.

Enforcer: `context_snapshot.py` validates bounded integer input, stores metadata privately and atomically, retains at most 20 snapshots across both hosts and enforces freshness (default one hour). `read`/`check` exit 3 with a fixed message when unavailable or stale. Their JSON output has no host key. Antigravity window zero means unknown and records nothing; null or invalid usage clears only that host's old reading. No transcript is read.

Setup offers each present host separate context-reading consent and preview approval (advisory, agent judgment); an enabled Antigravity compaction stop does not imply consent to this recorder. Without a reading, say so and never invent numbers (advisory, agent judgment). Codex has no equivalent signal and is out of scope. Antigravity's separate stop continues to use transcript bytes; live Antigravity status-line payloads and `invocationNum` semantics remain unverified.
